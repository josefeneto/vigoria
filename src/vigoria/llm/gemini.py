"""Provedor Gemini (SDK google-genai), com saída JSON estruturada por schema Pydantic.

O modelo vem de GEMINI_MODEL (config.py); nunca fica fixado no código.
Cada chamada tem um tempo máximo (o SDK, por omissão, espera para sempre).
Erro 429: o limite por minuto repete com espera, até 3 tentativas; a quota diária
esgotada não repete. O progresso vai para stderr, só com metadados, nunca conteúdo.
"""

import re
import sys
import time
from collections.abc import Callable
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from vigoria.config import obter_configuracao
from vigoria.llm.base import ErroLLM, Metricas, registar_metricas

MAX_TENTATIVAS = 3
TIMEOUT_S = 120  # por chamada
TIMEOUT_TESTE_S = 30  # --testar-ligacao
ESPERA_MAX_S = 60.0
ESPERA_429 = wait_exponential(multiplier=2, min=2, max=ESPERA_MAX_S)  # 2 s, 4 s, ...
PERGUNTA_TESTE = "Responde só: ok"
QUOTA_DIARIA = "quota diária esgotada, tenta depois das 8h00"

Progresso = Callable[[str], None]


def progresso_stderr(mensagem: str) -> None:
    """Escreve uma linha de progresso em stderr (só metadados)."""
    print(f"[vigoria.llm] {mensagem}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- Erro 429


def _detalhes(erro: errors.APIError) -> list[dict[str, Any]]:
    """Os «details» do erro da API (google.rpc), venham ou não dentro de «error»."""
    corpo = erro.details if isinstance(erro.details, dict) else {}
    corpo = corpo.get("error", corpo)
    detalhes = corpo.get("details", []) if isinstance(corpo, dict) else []
    return [d for d in detalhes if isinstance(d, dict)]


def e_quota_diaria(erro: BaseException) -> bool:
    """429 com uma violação de quota por dia (quotaId «...PerDay...»)."""
    if not isinstance(erro, errors.APIError) or erro.code != 429:
        return False
    for detalhe in _detalhes(erro):
        for violacao in detalhe.get("violations", []):
            if "PerDay" in str(violacao.get("quotaId", "")):
                return True
    return False


def e_limite_por_minuto(erro: BaseException) -> bool:
    """429 que vale a pena repetir: qualquer 429 que não seja a quota diária."""
    return isinstance(erro, errors.APIError) and erro.code == 429 and not e_quota_diaria(erro)


def espera_sugerida_s(erro: BaseException) -> float | None:
    """Espera indicada pelo serviço (RetryInfo.retryDelay, por exemplo «39s»)."""
    if not isinstance(erro, errors.APIError):
        return None
    for detalhe in _detalhes(erro):
        atraso = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(detalhe.get("retryDelay", "")))
        if atraso:
            return float(atraso.group(1))
    return None


def _espera(estado: RetryCallState) -> float:
    """A maior entre a exponencial e a sugerida pelo serviço, no máximo 60 s."""
    sugerida = espera_sugerida_s(estado.outcome.exception()) if estado.outcome else None
    return min(max(ESPERA_429(estado), sugerida or 0.0), ESPERA_MAX_S)


# ---------------------------------------------------------------- Provedor


class ProvedorGemini:
    """Implementa ProvedorLLM com o Gemini.

    `client`, `dormir` e `progresso` só se mudam nos testes (sem rede, sem esperas reais).
    """

    nome = "gemini"

    def __init__(
        self,
        modelo: str | None = None,
        client: Any | None = None,
        timeout_s: float = TIMEOUT_S,
        dormir: Callable[[float], None] = time.sleep,
        progresso: Progresso = progresso_stderr,
    ) -> None:
        if modelo is None:
            modelo = obter_configuracao().gemini_model
        if not modelo:
            raise ErroLLM("GEMINI_MODEL não está definido (ver .env.example).")
        if client is None:
            chave = obter_configuracao().gemini_api_key
            if chave is None:
                raise ErroLLM("GEMINI_API_KEY não está definida (ver .env.example).")
            client = genai.Client(
                api_key=chave.get_secret_value(),
                http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
            )
        self.modelo = modelo
        self.timeout_s = timeout_s
        self._client = client
        self._dormir = dormir
        self._progresso = progresso

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        config = types.GenerateContentConfig(
            system_instruction=sistema,
            response_mime_type="application/json",
            response_schema=schema,
            http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000)),
        )
        resposta = self._chamar(pedido, config, self.timeout_s)
        try:
            return schema.model_validate_json(resposta.text or "")
        except ValidationError:
            # Sem o conteúdo nem os detalhes da validação (podem citar a resposta).
            raise ErroLLM("A resposta do Gemini não respeita o formato do plano.") from None

    def testar_ligacao(self) -> str:
        """Envia «Responde só: ok» (30 s no máximo) e devolve o texto da resposta."""
        config = types.GenerateContentConfig(
            http_options=types.HttpOptions(timeout=TIMEOUT_TESTE_S * 1000)
        )
        resposta = self._chamar(PERGUNTA_TESTE, config, TIMEOUT_TESTE_S, repetir=False)
        return (resposta.text or "").strip()

    def _chamar(
        self,
        conteudo: str,
        config: types.GenerateContentConfig,
        timeout_s: float,
        repetir: bool = True,
    ) -> Any:
        """Chama o modelo com as repetições do 429 por minuto e regista as métricas."""
        maximo = MAX_TENTATIVAS if repetir else 1
        tentativas = Retrying(
            retry=retry_if_exception(e_limite_por_minuto),
            stop=stop_after_attempt(maximo),
            wait=_espera,
            sleep=self._dormir,
            before_sleep=self._antes_de_esperar,
            reraise=True,
        )
        inicio = time.perf_counter()
        numero = 0
        try:
            for tentativa in tentativas:
                with tentativa:
                    numero = tentativa.retry_state.attempt_number
                    self._progresso(
                        f"{self.nome}: chamada iniciada (tentativa {numero}/{maximo}, "
                        f"modelo {self.modelo}, tempo máximo {timeout_s:g} s)"
                    )
                    resposta = self._client.models.generate_content(
                        model=self.modelo, contents=conteudo, config=config
                    )
        except errors.APIError as erro:
            raise self._erro_api(erro, numero, inicio) from None
        except httpx.TimeoutException:
            segundos = time.perf_counter() - inicio
            self._progresso(f"{self.nome}: sem resposta ao fim de {segundos:.1f} s")
            raise ErroLLM(
                f"O Gemini não respondeu em {timeout_s:g} s. Verifique a ligação à Internet "
                "e tente de novo."
            ) from None
        except httpx.HTTPError as erro:
            self._progresso(f"{self.nome}: falha de rede ({type(erro).__name__})")
            raise ErroLLM(
                "Não foi possível ligar ao Gemini. Verifique a ligação à Internet."
            ) from None

        segundos = round(time.perf_counter() - inicio, 3)
        uso = getattr(resposta, "usage_metadata", None)
        metricas = Metricas(
            provedor=self.nome,
            modelo=self.modelo,
            segundos=segundos,
            tentativas=numero,
            tokens_entrada=getattr(uso, "prompt_token_count", None),
            tokens_saida=getattr(uso, "candidates_token_count", None),
        )
        registar_metricas(metricas)
        self._progresso(
            f"{self.nome}: chamada concluída em {segundos:.1f} s (tentativa {numero}; "
            f"tokens: {metricas.tokens_entrada} de entrada, {metricas.tokens_saida} de saída)"
        )
        return resposta

    def _antes_de_esperar(self, estado: RetryCallState) -> None:
        espera = estado.next_action.sleep if estado.next_action else 0.0
        self._progresso(
            f"{self.nome}: limite de pedidos por minuto (429) na tentativa "
            f"{estado.attempt_number}; nova tentativa daqui a {espera:.1f} s"
        )

    def _erro_api(self, erro: errors.APIError, tentativas: int, inicio: float) -> ErroLLM:
        """Erro claro, só com o código: a mensagem do serviço pode citar partes do pedido."""
        segundos = time.perf_counter() - inicio
        self._progresso(
            f"{self.nome}: erro {erro.code} ao fim de {segundos:.1f} s (tentativa {tentativas})"
        )
        if e_quota_diaria(erro):
            return ErroLLM(f"O Gemini recusou o pedido: {QUOTA_DIARIA}.", erro.code)
        if erro.code == 429:
            return ErroLLM(
                f"O Gemini recusou {tentativas} pedidos seguidos por limite de pedidos por "
                "minuto (429). Tente daqui a alguns minutos.",
                erro.code,
            )
        return ErroLLM(f"O Gemini devolveu um erro (código {erro.code}).", erro.code)
