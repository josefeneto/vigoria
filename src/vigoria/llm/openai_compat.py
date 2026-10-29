"""Provedores com API compatível com a OpenAI (Groq; mais tarde, Mistral), com httpx.

Um provedor novo deste tipo é uma subclasse com `nome`, `rotulo` e `url_base`, mais
as variáveis `<NOME>_API_KEY` e `<NOME>_MODEL` em config.py e .env.example.
A saída JSON segue o schema Pydantic em modo estrito (`schema_estrito`).
"""

import json
import math
import re
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel

from vigoria.config import Configuracao, obter_configuracao
from vigoria.llm.base import (
    PERGUNTA_TESTE,
    TIMEOUT_S,
    TIMEOUT_TESTE_S,
    ErroLLM,
    FalhaApi,
    Progresso,
    ProvedorBase,
    RespostaTeste,
    TipoFalha,
    progresso_stderr,
)

# A mensagem do 429 diz qual o limite atingido, por exemplo
# «... on tokens per day (TPD): Limit 200000 ...» ou «... requests per day (RPD) ...».
_POR_DIA = re.compile(r"per day|\((?:TPD|RPD)\)", re.IGNORECASE)


class ErroHttp(Exception):
    """Resposta com código de erro. O corpo e os cabeçalhos nunca vão para mensagens ou logs."""

    def __init__(self, codigo: int, cabecalhos: httpx.Headers, corpo: str) -> None:
        super().__init__(f"HTTP {codigo}")
        self.codigo = codigo
        self.cabecalhos = cabecalhos
        self.corpo = corpo

    def mensagem_servico(self) -> str:
        """error.message do corpo (só para classificar o erro; nunca se mostra)."""
        try:
            return str(json.loads(self.corpo)["error"]["message"])
        except ValueError, KeyError, TypeError:
            return ""


def schema_estrito(schema: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema do modelo no formato do modo estrito: referências ($ref) expandidas,
    todos os campos obrigatórios e `additionalProperties: false` em todos os objetos."""
    completo = schema.model_json_schema()
    definicoes = completo.pop("$defs", {})

    def expandir(no: Any) -> Any:
        if isinstance(no, list):
            return [expandir(x) for x in no]
        if not isinstance(no, dict):
            return no
        if "$ref" in no:
            return expandir(definicoes[no["$ref"].rsplit("/", 1)[-1]])
        novo = {chave: expandir(valor) for chave, valor in no.items()}
        if novo.get("type") == "object" and "properties" in novo:
            novo["required"] = list(novo["properties"])
            novo["additionalProperties"] = False
        return novo

    return expandir(completo)


def segundos_retry_after(cabecalhos: httpx.Headers) -> float | None:
    """Cabeçalho retry-after em segundos (só vem com o 429)."""
    try:
        return float(cabecalhos["retry-after"])
    except KeyError, ValueError:
        return None


class ProvedorCompativelOpenAI(ProvedorBase):
    """POST {url_base}/chat/completions com response_format json_schema (modo estrito).

    `client`, `dormir` e `progresso` só se mudam nos testes (sem rede, sem esperas reais).
    """

    url_base = ""
    # Cabeçalhos com os limites da conta e a forma de os mostrar (--testar-ligacao).
    cabecalhos_limites: tuple[tuple[str, str], ...] = ()
    notas_limites: tuple[str, ...] = ()

    def __init__(
        self,
        modelo: str | None = None,
        client: httpx.Client | None = None,
        timeout_s: float = TIMEOUT_S,
        dormir: Callable[[float], None] = time.sleep,
        progresso: Progresso = progresso_stderr,
        config: Configuracao | None = None,
    ) -> None:
        variavel = self.nome.upper()
        if modelo is None:
            modelo = getattr(config or obter_configuracao(), f"{self.nome}_model")
        if not modelo:
            raise ErroLLM(f"{variavel}_MODEL não está definido (ver .env.example).")
        if client is None:
            chave = getattr(config or obter_configuracao(), f"{self.nome}_api_key")
            if chave is None:
                raise ErroLLM(f"{variavel}_API_KEY não está definida (ver .env.example).")
            client = httpx.Client(
                base_url=self.url_base,
                headers={"Authorization": f"Bearer {chave.get_secret_value()}"},
                timeout=timeout_s,
            )
        super().__init__(modelo, timeout_s, dormir, progresso)
        self._client = client

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        corpo = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": pedido},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema_estrito(schema),
                },
            },
        }
        resposta = self._executar(lambda: self._post(corpo, self.timeout_s), self.timeout_s)
        return self._validar(schema, self._texto(resposta))

    def testar_ligacao(self) -> RespostaTeste:
        """Envia «Responde só: ok» (30 s no máximo, sem repetições) e lê os limites."""
        corpo = {"model": self.modelo, "messages": [{"role": "user", "content": PERGUNTA_TESTE}]}
        resposta = self._executar(
            lambda: self._post(corpo, TIMEOUT_TESTE_S), TIMEOUT_TESTE_S, repetir=False
        )
        return RespostaTeste(
            texto=self._texto(resposta).strip(), limites=self.limites(resposta.headers)
        )

    def limites(self, cabecalhos: httpx.Headers) -> tuple[str, ...]:
        """Os limites da conta que vêm nos cabeçalhos da resposta, em linhas legíveis."""
        linhas = [
            f"{rotulo}: {cabecalhos.get(nome, 'não indicado')}"
            for nome, rotulo in self.cabecalhos_limites
        ]
        return (*linhas, *self.notas_limites)

    def _post(self, corpo: dict[str, Any], timeout_s: float) -> httpx.Response:
        resposta = self._client.post("/chat/completions", json=corpo, timeout=timeout_s)
        if resposta.status_code >= 400:
            raise ErroHttp(resposta.status_code, resposta.headers, resposta.text)
        return resposta

    def _texto(self, resposta: httpx.Response) -> str:
        try:
            return str(resposta.json()["choices"][0]["message"]["content"] or "")
        except ValueError, KeyError, IndexError, TypeError:
            return ""

    def _falha(self, erro: BaseException) -> FalhaApi | None:
        if not isinstance(erro, ErroHttp):
            return None
        codigo = erro.codigo
        if codigo == 429:
            tipo = (
                TipoFalha.QUOTA_DIARIA
                if _POR_DIA.search(erro.mensagem_servico())
                else TipoFalha.POR_MINUTO
            )
        elif codigo == 413:
            tipo = TipoFalha.DEMASIADO_GRANDE
        elif codigo in (503, 504):
            tipo = TipoFalha.INDISPONIVEL
        else:
            tipo = TipoFalha.OUTRA
        return FalhaApi(codigo=codigo, tipo=tipo, espera_s=segundos_retry_after(erro.cabecalhos))

    def _tokens(self, resposta: Any) -> tuple[int | None, int | None]:
        try:
            uso = resposta.json().get("usage") or {}
        except ValueError:
            return None, None
        return uso.get("prompt_tokens"), uso.get("completion_tokens")

    def _texto_quota_diaria(self, falha: FalhaApi) -> str:
        """A janela diária é contínua: o retry-after diz quando há quota outra vez."""
        if falha.espera_s is None:
            return "quota diária esgotada, tenta mais tarde"
        return f"quota diária esgotada, tenta daqui a {math.ceil(falha.espera_s / 60)} min"
