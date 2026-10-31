"""Fornecedor simulado: devolve sempre a resposta guardada da persona de teste, sem rede.

Serve para ver a interface sem gastar quota (decisão de 31/10/2026). Só é aceite com
AMBIENTE=local (config.py) e nunca tem reserva (llm/escolha.py). Com respostas diferentes
das da persona de teste, a verificação pode recusar o plano: é o comportamento esperado.
"""

from pathlib import Path

from pydantic import BaseModel

from vigoria.llm.base import ErroLLM, RespostaTeste

RAIZ = Path(__file__).resolve().parents[3]
RESPOSTA = RAIZ / "tests" / "fixtures" / "resposta_gerador_persona_teste.json"


class ProvedorSimulado:
    """Implementa ProvedorLLM com a resposta de tests/fixtures/."""

    nome = "simulado"
    modelo = "persona_teste"

    def __init__(self, resposta: Path = RESPOSTA) -> None:
        self._resposta = resposta
        self.ultimo_provedor: str | None = None

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        try:
            texto = self._resposta.read_text("utf-8")
        except OSError:
            raise ErroLLM(f"Falta a resposta simulada ({self._resposta.name}).") from None
        self.ultimo_provedor = self.nome
        return schema.model_validate_json(texto)

    def testar_ligacao(self) -> RespostaTeste:
        return RespostaTeste(texto="ok (simulado)")
