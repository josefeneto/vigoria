"""O que a interface mostra das decisões do motor, antes de gerar (passos 1, 5 e 7).

Só reorganiza o que regras/ e motor/ já calcularam; não decide nada de novo.
As frases à volta (títulos, explicações) ficam em paginas/textos.py.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from vigoria.interface.passos import montar_questionario
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.questionario import Intensidade, Questionario
from vigoria.motor.acolhimento import acolher
from vigoria.motor.estrategia import avisos_objetivo
from vigoria.motor.voz import textos_obrigatorios
from vigoria.regras.calculos import ClasseImc, calcular_imc, classe_imc
from vigoria.regras.elegibilidade import Modo


class Decisoes(BaseModel):
    """As decisões da estratégia, prontas a mostrar no passo 7."""

    model_config = ConfigDict(frozen=True)

    pode_gerar_plano: bool
    modo: Modo
    motivos: tuple[str, ...]  # porque está em modo prudente (ou não é elegível)
    intensidade_pedida: Intensidade
    intensidade_efetiva: Intensidade | None
    explicacao_intensidade: str | None  # só quando a efetiva é mais baixa do que a pedida
    peso_atual_kg: float
    peso_alvo_kg: float  # o usado pelo plano (limitado a IMC 18,5)
    alvo_semana_16_kg: float | None
    objetivo_realista: bool
    semana_objetivo: int | None  # semana estimada para o objetivo completo; None sem perda
    modulo_gordura_visceral: bool
    usar_frequencia_cardiaca: bool
    sessoes_curtas: bool
    caminhada_diaria_extra: bool
    avisos_obrigatorios: tuple[str, ...]
    avisos_condicionais: tuple[str, ...]


def decisoes_estrategia(e: Estrategia, q: Questionario) -> Decisoes:
    ind = e.indicadores
    perda = ind.perda_peso if ind is not None else None
    obrigatorios = textos_obrigatorios()
    return Decisoes(
        pode_gerar_plano=e.pode_gerar_plano,
        modo=e.modo,
        motivos=e.motivos,
        intensidade_pedida=e.intensidade_pedida,
        intensidade_efetiva=e.intensidade_efetiva,
        explicacao_intensidade=e.explicacao_intensidade,
        peso_atual_kg=q.peso_kg,
        peso_alvo_kg=ind.peso_alvo_usado_kg if ind is not None else q.peso_alvo_kg,
        alvo_semana_16_kg=perda.alvo_semana_16_kg if perda is not None else None,
        objetivo_realista=perda.realista if perda is not None else True,
        semana_objetivo=perda.semana_objetivo if perda is not None else None,
        modulo_gordura_visceral=e.modulo_gordura_visceral,
        usar_frequencia_cardiaca=e.usar_frequencia_cardiaca,
        sessoes_curtas=e.sessoes_curtas,
        caminhada_diaria_extra=e.caminhada_diaria_extra,
        avisos_obrigatorios=tuple(a for a in e.avisos if a in obrigatorios),
        avisos_condicionais=tuple(a for a in e.avisos if a not in obrigatorios),
    )


def imc_com_classe(peso_kg: float, altura_cm: float) -> tuple[float, ClasseImc]:
    """IMC e classe, para a frase de contexto no fim do passo 1."""
    imc = calcular_imc(peso_kg, altura_cm)
    return imc, classe_imc(imc)


# O passo 5 ainda pode não ter estas respostas; não mudam os avisos do objetivo.
_PROVISORIOS = {"objetivo_muscular": "aumentar_forca_tonus", "intensidade_pedida": "media"}


def avisos_passo_objetivo(respostas: Mapping[str, Any]) -> tuple[str, ...]:
    """Avisos imediatos do passo 5: peso-alvo pouco realista ou incoerente (REGRAS §2)."""
    if respostas.get("peso_alvo_kg") is None:
        return ()
    try:
        q = montar_questionario(_PROVISORIOS | dict(respostas))
    except ValidationError:
        return ()
    return tuple(avisos_objetivo(acolher(q)))
