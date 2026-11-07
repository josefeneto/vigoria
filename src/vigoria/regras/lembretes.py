"""Lembretes de registo por email (REGRAS_DOMINIO §9 e §9.2, regras L1 a L5).

Funções puras: a data de hoje (Lisboa) entra sempre como argumento. Só usam as semanas com
registo, nunca os valores registados.
"""

from collections.abc import Collection, Iterable
from datetime import date
from itertools import islice

from pydantic import BaseModel, ConfigDict

from vigoria.modelos.questionario import FrequenciaRegisto
from vigoria.regras.progresso import periodos_terminados, tem_registo, ultimo_dia_do_periodo

DIAS_PRIMEIRO = 2  # §9: em falta 2 dias depois do prazo
DIAS_SEGUNDO = 5  # §9: segundo e último, 5 dias depois do prazo
DIAS_MAXIMO = 7  # L3: nada mais de 7 dias depois do prazo
MAXIMO_POR_PERIODO = 2
PERIODOS_PARA_SUSPENDER = 3  # L5


class Lembrete(BaseModel):
    """Um lembrete (a enviar ou já enviado) de um período do plano."""

    model_config = ConfigDict(frozen=True)

    semanas: tuple[int, int]
    numero: int  # 1 ou 2


class LembreteFeito(Lembrete):
    dia: date  # dia do envio, em Lisboa


def suspensos(
    inicio: date, hoje: date, frequencia: FrequenciaRegisto, semanas_com_registo: Iterable[int]
) -> bool:
    """L5: os 3 últimos períodos terminaram sem registo (retoma com um registo novo)."""
    semanas = set(semanas_com_registo)
    ultimos = list(islice(periodos_terminados(inicio, hoje, frequencia), PERIODOS_PARA_SUSPENDER))
    return len(ultimos) == PERIODOS_PARA_SUSPENDER and not any(
        tem_registo(p, semanas) for p in ultimos
    )


def lembrete_devido(
    inicio: date,
    hoje: date,
    frequencia: FrequenciaRegisto,
    semanas_com_registo: Collection[int],
    enviados: Iterable[LembreteFeito],
) -> Lembrete | None:
    """O lembrete a enviar hoje, ou None.

    L1: o primeiro a partir de 2 dias depois do prazo, o segundo a partir de 5, nunca dois
    no mesmo dia nem mais de 2 por período. L2: só o período terminado mais recente. L3: nada
    mais de 7 dias depois do prazo. L5: suspensos com 3 períodos seguidos sem registo.
    Quem chama trata de L4 (só o plano mais recente) e das preferências da conta.
    """
    ultimo = next(periodos_terminados(inicio, hoje, frequencia), None)
    if ultimo is None or tem_registo(ultimo, semanas_com_registo):
        return None
    if suspensos(inicio, hoje, frequencia, semanas_com_registo):
        return None
    dias = (hoje - ultimo_dia_do_periodo(inicio, ultimo)).days
    if not DIAS_PRIMEIRO <= dias <= DIAS_MAXIMO:
        return None
    feitos = [e for e in enviados if e.semanas == ultimo]
    if len(feitos) >= MAXIMO_POR_PERIODO or any(e.dia >= hoje for e in feitos):
        return None
    if not feitos:
        return Lembrete(semanas=ultimo, numero=1)
    if dias >= DIAS_SEGUNDO:
        return Lembrete(semanas=ultimo, numero=2)
    return None
