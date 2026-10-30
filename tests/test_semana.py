"""Semana-tipo determinística (motor/semana.py, Fase 4C)."""

import json
from pathlib import Path

import pytest

from vigoria.conteudo.carregar import carregar_avisos
from vigoria.modelos.plano import DiaSemana, SessaoDia
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.semana import SESSOES, TIPOS_FORCA, construir_semana

EXEMPLOS = Path(__file__).parent.parent / "exemplos"
ROTULOS = carregar_avisos().rotulos.semana
FORCA = {ROTULOS[t].atividade for t in TIPOS_FORCA}


def _semana(dias: int, minutos: int = 30) -> tuple[SessaoDia, ...]:
    dados = json.loads((EXEMPLOS / "persona_teste.json").read_text(encoding="utf-8"))
    q = Questionario.model_validate(dados | {"dias_semana": dias, "minutos_dia": minutos})
    return construir_semana(gerar_estrategia(q), q)


@pytest.mark.parametrize("dias", range(1, 8))
@pytest.mark.parametrize("minutos", [15, 30, 60])
def test_dias_e_duracao(dias: int, minutos: int) -> None:
    semana = _semana(dias, minutos)
    assert [s.dia for s in semana] == list(DiaSemana)
    com_sessao = [s for s in semana if s.duracao_min > 0]
    assert len(com_sessao) == dias
    assert all(s.duracao_min == minutos for s in com_sessao)


@pytest.mark.parametrize(
    ("dias", "forca"), [(1, 1), (2, 2), (3, 2), (4, 2), (5, 3), (6, 3), (7, 3)]
)
def test_dias_de_forca(dias: int, forca: int) -> None:
    assert sum(s.atividade in FORCA for s in _semana(dias)) == forca


@pytest.mark.parametrize("dias", range(1, 8))
def test_nunca_dois_dias_de_forca_seguidos(dias: int) -> None:
    semana = _semana(dias)
    forca = [s.atividade in FORCA for s in semana]
    pares = zip(forca, forca[1:] + forca[:1], strict=True)  # domingo → segunda também
    assert not any(a and b for a, b in pares)


def test_semana_de_5_dias_igual_a_semana_base() -> None:
    semana = {s.dia: s.atividade for s in _semana(5)}
    assert semana[DiaSemana.SEGUNDA] == "Força"
    assert semana[DiaSemana.TERCA] == "Cardio + mobilidade"
    assert semana[DiaSemana.QUARTA] == "Força + equilíbrio"
    assert semana[DiaSemana.QUINTA] == "Cardio leve + mobilidade"
    assert semana[DiaSemana.SEXTA] == "Força"
    assert semana[DiaSemana.SABADO] == "Caminhada leve (opcional)"
    assert semana[DiaSemana.DOMINGO] == "Descanso"


def test_7_dias_com_recuperacao_ativa_ao_domingo() -> None:
    domingo = _semana(7)[-1]
    assert (domingo.atividade, domingo.duracao_min) == ("Recuperação ativa", 30)


@pytest.mark.parametrize("dias", [1, 2])
def test_menos_de_3_dias_com_caminhada_diaria(dias: int) -> None:
    livres = [s for s in _semana(dias) if s.duracao_min == 0 and s.dia is not DiaSemana.DOMINGO]
    assert livres and all(s.atividade == "Caminhada diária" for s in livres)


def test_tabela_completa() -> None:
    assert set(SESSOES) == set(range(1, 8))
    for dias, sessoes in SESSOES.items():
        assert len(sessoes) == dias
        assert set(sessoes.values()) <= set(ROTULOS)
