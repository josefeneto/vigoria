"""Testes da intensidade efetiva (REGRAS_DOMINIO §3)."""

import pytest

from vigoria.modelos.questionario import Intensidade
from vigoria.regras import textos
from vigoria.regras.intensidade import (
    Limitador,
    abaixo_do_minimo,
    calcular_intensidade_efetiva,
    intensidade_por_disponibilidade,
    sessoes_curtas,
)

LIGEIRA, MEDIA, ALTA = Intensidade.LIGEIRA, Intensidade.MEDIA, Intensidade.ALTA


@pytest.mark.parametrize(
    ("dias", "minutos", "esperada"),
    [
        (1, 60, LIGEIRA),
        (2, 60, LIGEIRA),
        (3, 60, LIGEIRA),
        (4, 30, MEDIA),
        (5, 30, MEDIA),
        (5, 20, LIGEIRA),
        (6, 30, ALTA),
        (7, 30, ALTA),
        (7, 20, LIGEIRA),
        (7, 15, LIGEIRA),
        (4, 45, MEDIA),
    ],
)
def test_tabela_disponibilidade(dias: int, minutos: int, esperada: Intensidade) -> None:
    assert intensidade_por_disponibilidade(dias, minutos) is esperada


@pytest.mark.parametrize(("dias", "minutos"), [(0, 30), (3, 0)])
def test_disponibilidade_invalida(dias: int, minutos: int) -> None:
    with pytest.raises(ValueError):
        intensidade_por_disponibilidade(dias, minutos)


@pytest.mark.parametrize(("dias", "esperado"), [(1, True), (2, True), (3, False)])
def test_abaixo_do_minimo(dias: int, esperado: bool) -> None:
    assert abaixo_do_minimo(dias) is esperado


@pytest.mark.parametrize(("minutos", "esperado"), [(15, True), (20, True), (30, False)])
def test_sessoes_curtas(minutos: int, esperado: bool) -> None:
    assert sessoes_curtas(minutos) is esperado


def test_sem_reducao_nao_ha_explicacao() -> None:
    a = calcular_intensidade_efetiva(ALTA, None, 7, 30)
    assert a.efetiva is ALTA
    assert a.limitada_por == ()
    assert a.explicacao is None


def test_pedida_abaixo_dos_tetos_mantem_se() -> None:
    a = calcular_intensidade_efetiva(LIGEIRA, MEDIA, 7, 60)
    assert a.efetiva is LIGEIRA
    assert a.explicacao is None


def test_teto_prudente_reduz_para_media() -> None:
    a = calcular_intensidade_efetiva(ALTA, MEDIA, 7, 30)
    assert a.efetiva is MEDIA
    assert a.limitada_por == (Limitador.MODO,)
    assert a.explicacao == textos.INTENSIDADE_REDUZIDA.format(
        pedida="Alta", efetiva="Média", motivo=textos.MOTIVO_TETO_PRUDENTE
    )


def test_teto_imc_reduz_para_ligeira() -> None:
    a = calcular_intensidade_efetiva(ALTA, LIGEIRA, 7, 30)
    assert a.efetiva is LIGEIRA
    assert a.limitada_por == (Limitador.MODO,)
    assert textos.MOTIVO_TETO_IMC in (a.explicacao or "")


def test_disponibilidade_reduz() -> None:
    a = calcular_intensidade_efetiva(ALTA, None, 5, 20)
    assert a.efetiva is LIGEIRA
    assert a.limitada_por == (Limitador.DISPONIBILIDADE,)
    assert a.explicacao is not None
    assert "5 dias por semana e 20 min por dia" in a.explicacao


def test_um_dia_no_singular() -> None:
    a = calcular_intensidade_efetiva(MEDIA, None, 1, 30)
    assert "com 1 dia por semana" in (a.explicacao or "")


def test_os_dois_limitadores_com_o_mesmo_teto() -> None:
    a = calcular_intensidade_efetiva(ALTA, MEDIA, 5, 30)
    assert a.efetiva is MEDIA
    assert a.limitada_por == (Limitador.MODO, Limitador.DISPONIBILIDADE)
    assert a.explicacao is not None
    assert textos.MOTIVO_TETO_PRUDENTE in a.explicacao
    assert "5 dias" in a.explicacao


def test_disponibilidade_mais_restritiva_que_o_modo() -> None:
    a = calcular_intensidade_efetiva(ALTA, MEDIA, 3, 30)
    assert a.efetiva is LIGEIRA
    assert a.limitada_por == (Limitador.DISPONIBILIDADE,)
