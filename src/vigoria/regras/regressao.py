"""Aplicação das regressões por zona articular (REGRAS_DOMINIO §6.6)."""

from collections.abc import Collection, Mapping

from pydantic import BaseModel, ConfigDict

from vigoria.conteudo.carregar import Exercicio
from vigoria.modelos.estrategia import Zona
from vigoria.regras import textos

ESFORCO_MAXIMO_FIM_DA_CADEIA = 4


class Regressao(BaseModel):
    """Exercício a usar no lugar do pedido, com o limite de esforço quando se aplica."""

    model_config = ConfigDict(frozen=True)

    exercicio_id: str
    esforco_max: int | None = None
    nota: str | None = None


def resolver_regressao(
    exercicio_id: str, zonas: Collection[Zona], biblioteca: Mapping[str, Exercicio]
) -> Regressao:
    """Segue a cadeia de regressões até um exercício que não solicite nenhuma das zonas.

    Se a cadeia acabar e o último ainda solicitar uma delas, usa esse último com
    esforço máximo 4 e a nota «amplitude confortável, sem dor».
    """
    atual = biblioteca[exercicio_id]
    vistos = {atual.id}
    while set(atual.zonas) & set(zonas):
        if atual.regressao is None:
            return Regressao(
                exercicio_id=atual.id,
                esforco_max=ESFORCO_MAXIMO_FIM_DA_CADEIA,
                nota=textos.AMPLITUDE_CONFORTAVEL,
            )
        if atual.regressao in vistos:
            raise ValueError(f"Ciclo nas regressões a partir de {exercicio_id}")
        atual = biblioteca[atual.regressao]
        vistos.add(atual.id)
    return Regressao(exercicio_id=atual.id)
