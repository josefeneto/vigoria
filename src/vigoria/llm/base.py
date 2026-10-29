"""Interface comum aos provedores de LLM (Gemini principal, Groq de reserva).

Os provedores só registam métricas (tempo, tokens, tentativas), nunca o conteúdo
do pedido ou da resposta: o pedido leva dados de saúde (REGRAS_DOMINIO e RGPD).
"""

import logging
from typing import Protocol

from pydantic import BaseModel, ConfigDict

registo = logging.getLogger("vigoria.llm")


class ErroLLM(Exception):
    """Falha na chamada à LLM. A mensagem nunca inclui o conteúdo do pedido ou da resposta."""


class Metricas(BaseModel):
    """O que se regista de cada chamada."""

    model_config = ConfigDict(frozen=True)

    provedor: str
    modelo: str
    segundos: float
    tentativas: int
    tokens_entrada: int | None = None
    tokens_saida: int | None = None


class ProvedorLLM(Protocol):
    """Gera uma resposta JSON validada pelo schema Pydantic indicado."""

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        """Chama a LLM com o prompt de sistema e o pedido; devolve a resposta validada.

        Levanta ErroLLM se a chamada falhar ou a resposta não respeitar o schema.
        """
        ...


def registar_metricas(metricas: Metricas) -> None:
    """Regista só identificadores técnicos e números."""
    registo.info("chamada LLM concluída", extra={"metricas": metricas.model_dump()})
