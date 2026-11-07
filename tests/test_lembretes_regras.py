"""Regras dos lembretes por email (regras/lembretes.py; REGRAS_DOMINIO §9 e §9.2, L1 a L5)."""

from datetime import date, timedelta

import pytest

from vigoria.modelos.questionario import FrequenciaRegisto
from vigoria.regras.lembretes import Lembrete, LembreteFeito, lembrete_devido, suspensos
from vigoria.regras.progresso import periodo_em_falta, periodos_terminados

INICIO = date(2026, 1, 5)
SEMANAL = FrequenciaRegisto.SEMANAL
QUATRO = FrequenciaRegisto.A_CADA_4_SEMANAS


def _prazo(ultima_semana: int) -> date:
    """O último dia da semana indicada."""
    return INICIO + timedelta(days=7 * ultima_semana - 1)


def _feito(semanas: tuple[int, int], numero: int, dia: date) -> LembreteFeito:
    return LembreteFeito(semanas=semanas, numero=numero, dia=dia)


def _devido(
    hoje: date,
    semanas: set[int] | None = None,
    enviados: list[LembreteFeito] | None = None,
    frequencia: FrequenciaRegisto = SEMANAL,
) -> Lembrete | None:
    return lembrete_devido(INICIO, hoje, frequencia, semanas or set(), enviados or [])


# ---------------------------------------------------------------- Períodos terminados


def test_periodos_terminados_do_mais_recente_para_o_mais_antigo() -> None:
    assert list(periodos_terminados(INICIO, _prazo(3) + timedelta(days=1), SEMANAL)) == [
        (3, 3),
        (2, 2),
        (1, 1),
    ]
    # O último dia do período ainda conta: no prazo, a semana 3 não terminou.
    assert next(periodos_terminados(INICIO, _prazo(3), SEMANAL)) == (2, 2)
    assert list(periodos_terminados(INICIO, INICIO, SEMANAL)) == []


def test_periodos_terminados_passam_a_4_semanas_na_manutencao() -> None:
    hoje = _prazo(20) + timedelta(days=1)
    assert list(periodos_terminados(INICIO, hoje, SEMANAL))[:3] == [(17, 20), (16, 16), (15, 15)]


def test_periodo_em_falta_continua_igual() -> None:
    hoje = _prazo(5) + timedelta(days=1)
    assert periodo_em_falta(INICIO, hoje, SEMANAL, {4, 5}) == (3, 3)
    assert periodo_em_falta(INICIO, hoje, SEMANAL, {1, 2, 3, 4, 5}) is None


# ---------------------------------------------------------------- L1: 2 e 5 dias, máximo de 2


@pytest.mark.parametrize("dias", [0, 1])
def test_sem_lembrete_antes_de_2_dias_depois_do_prazo(dias: int) -> None:
    assert _devido(_prazo(1) + timedelta(days=dias)) is None


def test_primeiro_lembrete_2_dias_depois_do_prazo() -> None:
    assert _devido(_prazo(1) + timedelta(days=2)) == Lembrete(semanas=(1, 1), numero=1)


def test_entre_o_primeiro_e_o_quinto_dia_nada_mais() -> None:
    primeiro = _feito((1, 1), 1, _prazo(1) + timedelta(days=2))
    for dias in (2, 3, 4):
        assert _devido(_prazo(1) + timedelta(days=dias), enviados=[primeiro]) is None


def test_segundo_lembrete_5_dias_depois_do_prazo() -> None:
    primeiro = _feito((1, 1), 1, _prazo(1) + timedelta(days=2))
    hoje = _prazo(1) + timedelta(days=5)
    assert _devido(hoje, enviados=[primeiro]) == Lembrete(semanas=(1, 1), numero=2)


def test_nunca_dois_no_mesmo_dia() -> None:
    hoje = _prazo(1) + timedelta(days=5)
    # A tarefa falhou nos dias anteriores: hoje sai o primeiro e o segundo só amanhã.
    assert _devido(hoje) == Lembrete(semanas=(1, 1), numero=1)
    feito_hoje = _feito((1, 1), 1, hoje)
    assert _devido(hoje, enviados=[feito_hoje]) is None
    amanha = hoje + timedelta(days=1)
    assert _devido(amanha, enviados=[feito_hoje]) == Lembrete(semanas=(1, 1), numero=2)


def test_maximo_de_2_por_periodo() -> None:
    enviados = [
        _feito((1, 4), 1, _prazo(4) + timedelta(days=2)),
        _feito((1, 4), 2, _prazo(4) + timedelta(days=5)),
    ]
    assert _devido(_prazo(4) + timedelta(days=6), enviados=enviados, frequencia=QUATRO) is None


def test_lembretes_de_outro_periodo_nao_contam() -> None:
    antigo = _feito((1, 1), 2, _prazo(1) + timedelta(days=5))
    hoje = _prazo(2) + timedelta(days=2)
    assert _devido(hoje, enviados=[antigo]) == Lembrete(semanas=(2, 2), numero=1)


def test_sem_lembrete_com_o_registo_feito() -> None:
    assert _devido(_prazo(1) + timedelta(days=2), semanas={1}) is None
    primeiro = _feito((1, 1), 1, _prazo(1) + timedelta(days=2))
    assert _devido(_prazo(1) + timedelta(days=5), semanas={1}, enviados=[primeiro]) is None


def test_a_cada_4_semanas_o_prazo_e_o_fim_do_bloco() -> None:
    assert _devido(_prazo(3) + timedelta(days=2), frequencia=QUATRO) is None
    hoje = _prazo(4) + timedelta(days=2)
    assert _devido(hoje, frequencia=QUATRO) == Lembrete(semanas=(1, 4), numero=1)
    assert _devido(hoje, semanas={2}, frequencia=QUATRO) is None


# ---------------------------------------------------------------- L2: só o mais recente


def test_so_o_periodo_terminado_mais_recente() -> None:
    hoje = _prazo(2) + timedelta(days=2)
    # Falta a semana 1, mas a 2 (a mais recente) está feita: nada.
    assert _devido(hoje, semanas={2}) is None


# ---------------------------------------------------------------- L3: até 7 dias


def test_nada_mais_de_7_dias_depois_do_prazo() -> None:
    assert _devido(_prazo(4) + timedelta(days=7), frequencia=QUATRO) == Lembrete(
        semanas=(1, 4), numero=1
    )
    assert _devido(_prazo(4) + timedelta(days=8), frequencia=QUATRO) is None
    primeiro = _feito((1, 4), 1, _prazo(4) + timedelta(days=2))
    assert _devido(_prazo(4) + timedelta(days=8), enviados=[primeiro], frequencia=QUATRO) is None


# ---------------------------------------------------------------- Manutenção (R4)


def test_manutencao_a_cada_4_semanas_mesmo_com_frequencia_semanal() -> None:
    registadas = set(range(1, 17))
    # Na semana 18, o período da manutenção (17 a 20) ainda não terminou.
    assert _devido(_prazo(17) + timedelta(days=2), semanas=registadas) is None
    hoje = _prazo(20) + timedelta(days=2)
    assert _devido(hoje, semanas=registadas) == Lembrete(semanas=(17, 20), numero=1)
    assert _devido(hoje, semanas=registadas | {19}) is None


def test_passagem_da_semana_16_para_a_17() -> None:
    hoje = _prazo(16) + timedelta(days=2)  # já na semana 17
    assert _devido(hoje, semanas=set(range(1, 16))) == Lembrete(semanas=(16, 16), numero=1)


# ---------------------------------------------------------------- L5: suspensão


def test_suspensos_ao_terceiro_periodo_seguido_sem_registo() -> None:
    assert _devido(_prazo(2) + timedelta(days=2)) == Lembrete(semanas=(2, 2), numero=1)
    hoje = _prazo(3) + timedelta(days=2)
    assert suspensos(INICIO, hoje, SEMANAL, set())
    assert _devido(hoje) is None
    assert _devido(_prazo(3) + timedelta(days=5)) is None


def test_suspensao_depois_de_um_registo_antigo() -> None:
    hoje = _prazo(4) + timedelta(days=2)
    assert _devido(hoje, semanas={1}) is None  # semanas 2, 3 e 4 sem registo
    assert _devido(hoje, semanas={2}) == Lembrete(semanas=(4, 4), numero=1)  # só 3 e 4


def test_retoma_depois_de_um_registo_novo() -> None:
    # Suspensos na semana 3; a pessoa regista a semana 4 e falha a 5.
    assert suspensos(INICIO, _prazo(4) + timedelta(days=1), SEMANAL, set())
    assert not suspensos(INICIO, _prazo(4) + timedelta(days=1), SEMANAL, {4})
    hoje = _prazo(5) + timedelta(days=2)
    assert _devido(hoje, semanas={4}) == Lembrete(semanas=(5, 5), numero=1)


def test_a_cada_4_semanas_suspende_ao_terceiro_bloco() -> None:
    assert _devido(_prazo(8) + timedelta(days=2), frequencia=QUATRO) == Lembrete(
        semanas=(5, 8), numero=1
    )
    assert _devido(_prazo(12) + timedelta(days=2), frequencia=QUATRO) is None


def test_menos_de_3_periodos_nao_suspende() -> None:
    assert not suspensos(INICIO, _prazo(2) + timedelta(days=1), SEMANAL, set())
