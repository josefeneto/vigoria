"""Cartão «Hoje» (Fase 8D): o que a semana-tipo prevê para um dia, pela data do plano."""

from datetime import UTC, date, datetime, timedelta

import pytest

from vigoria.modelos.plano import DiaSemana, SessaoDia
from vigoria.regras.hoje import TipoHoje, dia_da_semana, sessao_de_hoje
from vigoria.regras.progresso import inicio_do_plano

INICIO = date(2026, 11, 9)  # uma segunda-feira


def _sessao(dia: DiaSemana, minutos: int, atividade: str = "Força") -> SessaoDia:
    return SessaoDia(dia=dia, atividade=atividade, duracao_min=minutos, descricao="…")


# Segunda, quarta e sexta com sessão; terça e quinta sem; sábado sem entrada; domingo descanso.
SEMANA = (
    _sessao(DiaSemana.SEGUNDA, 30),
    _sessao(DiaSemana.TERCA, 0, "Caminhada leve (opcional)"),
    _sessao(DiaSemana.QUARTA, 30, "Cardio + mobilidade"),
    _sessao(DiaSemana.QUINTA, 0, "Caminhada leve (opcional)"),
    _sessao(DiaSemana.SEXTA, 45),
    _sessao(DiaSemana.DOMINGO, 0, "Descanso"),
)


@pytest.mark.parametrize(
    ("deslocamento", "esperado"),
    list(enumerate(DiaSemana)),
)
def test_dia_da_semana_nos_sete_dias(deslocamento: int, esperado: DiaSemana) -> None:
    assert dia_da_semana(INICIO + timedelta(days=deslocamento)) is esperado


@pytest.mark.parametrize(
    ("deslocamento", "tipo"),
    [
        (0, TipoHoje.SESSAO),
        (1, TipoHoje.DESCANSO),
        (2, TipoHoje.SESSAO),
        (3, TipoHoje.DESCANSO),
        (4, TipoHoje.SESSAO),
        (5, TipoHoje.DESCANSO),  # sábado: sem entrada na semana-tipo
        (6, TipoHoje.DESCANSO),
    ],
)
def test_sessao_ou_descanso_em_cada_dia(deslocamento: int, tipo: TipoHoje) -> None:
    hoje = sessao_de_hoje(SEMANA, INICIO, INICIO + timedelta(days=deslocamento))
    assert hoje.tipo is tipo
    assert hoje.semana == 1 and hoje.fase == 1


def test_sessao_devolve_a_entrada_do_dia() -> None:
    hoje = sessao_de_hoje(SEMANA, INICIO, INICIO + timedelta(days=4))
    assert hoje.sessao == SEMANA[4] and hoje.sessao.duracao_min == 45


def test_dia_sem_entrada_nao_tem_sessao() -> None:
    assert sessao_de_hoje(SEMANA, INICIO, INICIO + timedelta(days=5)).sessao is None


def test_duracao_zero_e_descanso_mesmo_com_atividade() -> None:
    hoje = sessao_de_hoje(SEMANA, INICIO, INICIO + timedelta(days=1))
    assert hoje.tipo is TipoHoje.DESCANSO
    assert hoje.sessao is not None and hoje.sessao.atividade == "Caminhada leve (opcional)"


def test_ultimo_dia_da_semana_16_ainda_e_do_programa() -> None:
    hoje = sessao_de_hoje(SEMANA, INICIO, INICIO + timedelta(days=16 * 7 - 1))
    assert (hoje.semana, hoje.fase, hoje.tipo) == (16, 4, TipoHoje.DESCANSO)  # um domingo


def test_primeiro_dia_da_semana_17_e_manutencao() -> None:
    hoje = sessao_de_hoje(SEMANA, INICIO, INICIO + timedelta(days=16 * 7))
    assert (hoje.semana, hoje.fase, hoje.tipo) == (17, None, TipoHoje.MANUTENCAO)
    assert hoje.dia is DiaSemana.SEGUNDA and hoje.sessao == SEMANA[0]


@pytest.mark.parametrize(("semana", "fase"), [(4, 1), (5, 2), (8, 2), (9, 3), (13, 4)])
def test_fase_nas_fronteiras(semana: int, fase: int) -> None:
    hoje = sessao_de_hoje(SEMANA, INICIO, INICIO + timedelta(days=(semana - 1) * 7))
    assert (hoje.semana, hoje.fase) == (semana, fase)


def test_dia_anterior_ao_inicio_conta_como_semana_1() -> None:
    hoje = sessao_de_hoje(SEMANA, INICIO, INICIO - timedelta(days=1))
    assert hoje.semana == 1 and hoje.fase == 1
    assert hoje.dia is DiaSemana.DOMINGO and hoje.tipo is TipoHoje.DESCANSO


def test_semana_tipo_vazia_e_descanso() -> None:
    assert sessao_de_hoje((), INICIO, INICIO).tipo is TipoHoje.DESCANSO


def test_viragem_do_dia_em_lisboa_e_nao_em_utc() -> None:
    """Às 23h30 UTC de 31 de maio já é 1 de junho em Lisboa (hora de verão)."""
    criado = datetime(2026, 5, 31, 23, 30, tzinfo=UTC)
    inicio = inicio_do_plano(criado)
    assert inicio == date(2026, 6, 1)  # uma segunda-feira
    assert sessao_de_hoje(SEMANA, inicio, inicio).dia is DiaSemana.SEGUNDA
