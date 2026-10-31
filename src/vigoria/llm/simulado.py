"""Fornecedor simulado: devolve sempre a resposta guardada da persona de teste, sem rede.

Serve para ver a interface sem gastar quota (decisão de 31/10/2026). Só é aceite com
AMBIENTE=local (config.py) e nunca tem reserva (llm/escolha.py). Com respostas diferentes
das da persona de teste, a verificação pode recusar o plano: é o comportamento esperado.
"""

from importlib.resources import files
from importlib.resources.abc import Traversable

from pydantic import BaseModel

from vigoria.llm.base import ErroLLM, RespostaTeste

# Dados do pacote, como os prompts; os testes usam a mesma resposta (ler_resposta_simulada).
RESPOSTA = files("vigoria.llm").joinpath("resposta_simulada.json")


def ler_resposta_simulada() -> str:
    """A resposta do gerador para a persona de teste, em JSON."""
    return RESPOSTA.read_text(encoding="utf-8")


class ProvedorSimulado:
    """Implementa ProvedorLLM com a resposta guardada em vigoria/llm/resposta_simulada.json."""

    nome = "simulado"
    modelo = "persona_teste"

    def __init__(self, resposta: Traversable = RESPOSTA) -> None:
        self._resposta = resposta
        self.ultimo_provedor: str | None = None

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        try:
            texto = self._resposta.read_text(encoding="utf-8")
        except OSError:
            raise ErroLLM(f"Falta a resposta simulada ({self._resposta.name}).") from None
        self.ultimo_provedor = self.nome
        return schema.model_validate_json(texto)

    def testar_ligacao(self) -> RespostaTeste:
        return RespostaTeste(texto="ok (simulado)")
