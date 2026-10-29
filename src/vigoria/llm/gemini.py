"""Provedor Gemini (SDK google-genai), com saída JSON estruturada por schema Pydantic.

O modelo vem de GEMINI_MODEL (config.py); nunca fica fixado no código.
Cada chamada tem um tempo máximo (o SDK, por omissão, espera para sempre).
Repetições, progresso e mensagens de erro: llm/base.py. Aqui só se classificam os
erros do Gemini: 429 por minuto ou quota diária (pelo quotaId), 503/504.
"""

import re
import time
from collections.abc import Callable
from typing import Any

from google import genai
from google.genai import errors, types
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

QUOTA_DIARIA = "quota diária esgotada, tenta depois das 8h00"


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


def espera_sugerida_s(erro: BaseException) -> float | None:
    """Espera indicada pelo serviço (RetryInfo.retryDelay, por exemplo «39s»)."""
    if not isinstance(erro, errors.APIError):
        return None
    for detalhe in _detalhes(erro):
        atraso = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(detalhe.get("retryDelay", "")))
        if atraso:
            return float(atraso.group(1))
    return None


# ---------------------------------------------------------------- Provedor


class ProvedorGemini(ProvedorBase):
    """Implementa ProvedorLLM com o Gemini.

    `client`, `dormir` e `progresso` só se mudam nos testes (sem rede, sem esperas reais).
    """

    nome = "gemini"
    rotulo = "Gemini"

    def __init__(
        self,
        modelo: str | None = None,
        client: Any | None = None,
        timeout_s: float = TIMEOUT_S,
        dormir: Callable[[float], None] = time.sleep,
        progresso: Progresso = progresso_stderr,
        config: Configuracao | None = None,
    ) -> None:
        if modelo is None:
            modelo = (config or obter_configuracao()).gemini_model
        if not modelo:
            raise ErroLLM("GEMINI_MODEL não está definido (ver .env.example).")
        if client is None:
            chave = (config or obter_configuracao()).gemini_api_key
            if chave is None:
                raise ErroLLM("GEMINI_API_KEY não está definida (ver .env.example).")
            client = genai.Client(
                api_key=chave.get_secret_value(),
                http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
            )
        super().__init__(modelo, timeout_s, dormir, progresso)
        self._client = client

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        config = types.GenerateContentConfig(
            system_instruction=sistema,
            response_mime_type="application/json",
            response_schema=schema,
            http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000)),
        )
        resposta = self._executar(lambda: self._gerar(pedido, config), self.timeout_s)
        return self._validar(schema, resposta.text or "")

    def testar_ligacao(self) -> RespostaTeste:
        """Envia «Responde só: ok» (30 s no máximo, sem repetições)."""
        config = types.GenerateContentConfig(
            http_options=types.HttpOptions(timeout=TIMEOUT_TESTE_S * 1000)
        )
        resposta = self._executar(
            lambda: self._gerar(PERGUNTA_TESTE, config), TIMEOUT_TESTE_S, repetir=False
        )
        return RespostaTeste(texto=(resposta.text or "").strip())

    def _gerar(self, conteudo: str, config: types.GenerateContentConfig) -> Any:
        return self._client.models.generate_content(
            model=self.modelo, contents=conteudo, config=config
        )

    def _falha(self, erro: BaseException) -> FalhaApi | None:
        if not isinstance(erro, errors.APIError):
            return None
        codigo = erro.code
        if e_quota_diaria(erro):
            tipo = TipoFalha.QUOTA_DIARIA
        elif codigo == 429:
            tipo = TipoFalha.POR_MINUTO  # sem detalhes: tratado como por minuto
        elif codigo in (503, 504):
            tipo = TipoFalha.INDISPONIVEL
        else:
            tipo = TipoFalha.OUTRA
        return FalhaApi(codigo=codigo, tipo=tipo, espera_s=espera_sugerida_s(erro))

    def _tokens(self, resposta: Any) -> tuple[int | None, int | None]:
        uso = getattr(resposta, "usage_metadata", None)
        entrada = getattr(uso, "prompt_token_count", None)
        return entrada, getattr(uso, "candidates_token_count", None)

    def _texto_quota_diaria(self, falha: FalhaApi) -> str:
        return QUOTA_DIARIA
