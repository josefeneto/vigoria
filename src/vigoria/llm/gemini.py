"""Provedor Gemini (SDK google-genai), com saída JSON estruturada por schema Pydantic.

O modelo vem de GEMINI_MODEL (config.py); nunca fica fixado no código.
O erro 429 (limite de pedidos) é repetido com espera exponencial, até 3 tentativas.
"""

import time
from typing import Any

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from tenacity.wait import WaitBaseT

from vigoria.config import obter_configuracao
from vigoria.llm.base import ErroLLM, Metricas, registar_metricas

MAX_TENTATIVAS = 3
ESPERA_429 = wait_exponential(multiplier=2, min=2, max=30)  # 2 s, 4 s, ...


def _e_limite_de_pedidos(erro: BaseException) -> bool:
    return isinstance(erro, errors.APIError) and erro.code == 429


class ProvedorGemini:
    """Implementa ProvedorLLM com o Gemini.

    `client` e `espera` só se passam nos testes (cliente simulado, sem esperas reais).
    """

    nome = "gemini"

    def __init__(
        self,
        modelo: str | None = None,
        client: Any | None = None,
        espera: WaitBaseT = ESPERA_429,
    ) -> None:
        if modelo is None:
            modelo = obter_configuracao().gemini_model
        if not modelo:
            raise ErroLLM("GEMINI_MODEL não está definido (ver .env.example).")
        if client is None:
            chave = obter_configuracao().gemini_api_key
            if chave is None:
                raise ErroLLM("GEMINI_API_KEY não está definida (ver .env.example).")
            client = genai.Client(api_key=chave.get_secret_value())
        self.modelo = modelo
        self._client = client
        self._espera = espera

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        config = types.GenerateContentConfig(
            system_instruction=sistema,
            response_mime_type="application/json",
            response_schema=schema,
        )
        inicio = time.perf_counter()
        tentativas = Retrying(
            retry=retry_if_exception(_e_limite_de_pedidos),
            stop=stop_after_attempt(MAX_TENTATIVAS),
            wait=self._espera,
        )
        try:
            resposta = tentativas(
                self._client.models.generate_content,
                model=self.modelo,
                contents=pedido,
                config=config,
            )
        except RetryError as erro:
            raise ErroLLM(
                f"O Gemini recusou {MAX_TENTATIVAS} pedidos seguidos por limite de utilização "
                "(429). Tente mais tarde."
            ) from erro
        except errors.APIError as erro:
            # Só o código: a mensagem do serviço pode citar partes do pedido.
            raise ErroLLM(f"O Gemini devolveu um erro (código {erro.code}).") from None

        uso = getattr(resposta, "usage_metadata", None)
        registar_metricas(
            Metricas(
                provedor=self.nome,
                modelo=self.modelo,
                segundos=round(time.perf_counter() - inicio, 3),
                tentativas=tentativas.statistics.get("attempt_number", 1),
                tokens_entrada=getattr(uso, "prompt_token_count", None),
                tokens_saida=getattr(uso, "candidates_token_count", None),
            )
        )
        try:
            return schema.model_validate_json(resposta.text or "")
        except ValidationError:
            # Sem o conteúdo nem os detalhes da validação (podem citar a resposta).
            raise ErroLLM("A resposta do Gemini não respeita o formato do plano.") from None
