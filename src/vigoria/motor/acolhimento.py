"""Acolhimento (papel 1, determinístico): indicadores e incoerências do questionário.

O Questionario já chega validado pelo Pydantic; aqui calculam-se os valores da
REGRAS_DOMINIO §2 e detetam-se as incoerências nos objetivos (avisos, nunca bloqueios).
"""

from pydantic import BaseModel, ConfigDict

from vigoria.modelos.estrategia import Indicadores
from vigoria.modelos.questionario import Questionario
from vigoria.regras import textos
from vigoria.regras.calculos import (
    avaliar_ganho_muscular,
    avaliar_perda_peso,
    calcular_hidratacao,
    calcular_imc,
    calcular_proteina,
    cintura_de_risco,
    classe_imc,
    limiar_cintura_cm,
    peso_minimo_saudavel_kg,
)


class Acolhimento(BaseModel):
    model_config = ConfigDict(frozen=True)

    indicadores: Indicadores
    incoerencias: tuple[str, ...]


def acolher(q: Questionario) -> Acolhimento:
    """Calcula os indicadores e deteta as incoerências nos objetivos (decisão de 28/10/2026)."""
    incoerencias = []

    peso_alvo = q.peso_alvo_kg
    peso_minimo = peso_minimo_saudavel_kg(q.altura_cm)
    if peso_alvo < peso_minimo:
        incoerencias.append(
            textos.PESO_ALVO_IMC_BAIXO.format(
                peso_alvo=textos.numero(peso_alvo), peso_minimo=textos.numero(peso_minimo)
            )
        )
        peso_alvo = peso_minimo
    if peso_alvo >= q.peso_kg:
        incoerencias.append(textos.PESO_ALVO_SEM_PERDA)
    if q.cintura_alvo_cm is not None and q.cintura_alvo_cm >= q.cintura_cm:
        incoerencias.append(
            textos.CINTURA_ALVO_NAO_REDUZ.format(
                cintura_alvo=textos.numero(q.cintura_alvo_cm), cintura=textos.numero(q.cintura_cm)
            )
        )

    imc = calcular_imc(q.peso_kg, q.altura_cm)
    indicadores = Indicadores(
        imc=imc,
        classe_imc=classe_imc(imc),
        cintura_cm=q.cintura_cm,
        limiar_cintura_cm=limiar_cintura_cm(q.sexo),
        cintura_de_risco=cintura_de_risco(q.sexo, q.cintura_cm),
        peso_alvo_usado_kg=peso_alvo,
        hidratacao=calcular_hidratacao(q.peso_kg, q.condicoes),
        proteina=calcular_proteina(q.peso_kg, q.condicoes),
        perda_peso=avaliar_perda_peso(q.peso_kg, peso_alvo, q.idade),
        ganho_muscular=avaliar_ganho_muscular(q.objetivo_muscular),
    )
    return Acolhimento(indicadores=indicadores, incoerencias=tuple(incoerencias))
