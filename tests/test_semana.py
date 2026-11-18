"""Semana-tipo determinística (motor/semana.py; dias escolhidos desde 18/11/2026)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from vigoria.conteudo.carregar import carregar_avisos
from vigoria.modelos.plano import DiaSemana, SessaoDia
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.semana import (
    DIAS_FIXOS,
    TIPOS_FORCA,
    construir_semana,
    dias_de_forca,
    sessoes,
)

D = DiaSemana
EXEMPLOS = Path(__file__).parent.parent / "exemplos"
ROTULOS = carregar_avisos().rotulos.semana
FORCA = {ROTULOS[t].atividade for t in TIPOS_FORCA}
# A semana fixa até 18/11/2026: os questionários antigos têm de continuar iguais.
SEMANA_ANTIGA: dict[int, dict[DiaSemana, str]] = {
    1: {D.QUARTA: "forca"},
    2: {D.SEGUNDA: "forca", D.QUINTA: "forca"},
    3: {D.SEGUNDA: "forca", D.QUARTA: "cardio_mobilidade", D.SEXTA: "forca"},
    4: {D.SEGUNDA: "forca", D.TERCA: "cardio_mobilidade", D.QUINTA: "forca", D.SABADO: "cardio"},
    5: {
        D.SEGUNDA: "forca",
        D.TERCA: "cardio_mobilidade",
        D.QUARTA: "forca_equilibrio",
        D.QUINTA: "cardio_leve_mobilidade",
        D.SEXTA: "forca",
    },
}
SEMANA_ANTIGA[6] = SEMANA_ANTIGA[5] | {D.SABADO: "cardio"}
SEMANA_ANTIGA[7] = SEMANA_ANTIGA[6] | {D.DOMINGO: "recuperacao_ativa"}


def _dados() -> dict[str, Any]:
    return json.loads((EXEMPLOS / "persona_teste.json").read_text(encoding="utf-8"))


def _q(dias: int | list[DiaSemana], minutos: int = 30) -> Questionario:
    escolha = {"dias_semana": dias} if isinstance(dias, int) else {"dias_treino": dias}
    return Questionario.model_validate(
        {k: v for k, v in _dados().items() if k != "dias_semana"}
        | escolha
        | {"minutos_dia": minutos}
    )


def _semana(dias: int | list[DiaSemana], minutos: int = 30) -> tuple[SessaoDia, ...]:
    q = _q(dias, minutos)
    return construir_semana(gerar_estrategia(q), q)


def _sem_forca_seguida(semana: tuple[SessaoDia, ...]) -> bool:
    forca = [s.atividade in FORCA for s in semana]
    pares = zip(forca, forca[1:] + forca[:1], strict=True)  # domingo → segunda também
    return not any(a and b for a, b in pares)


@pytest.mark.parametrize("dias", range(1, 8))
@pytest.mark.parametrize("minutos", [15, 30, 60])
def test_dias_e_duracao(dias: int, minutos: int) -> None:
    semana = _semana(dias, minutos)
    assert [s.dia for s in semana] == list(DiaSemana)
    com_sessao = [s for s in semana if s.duracao_min > 0]
    assert len(com_sessao) == dias
    assert all(s.duracao_min == minutos for s in com_sessao)


@pytest.mark.parametrize("dias", range(1, 8))
def test_questionario_antigo_igual_a_semana_fixa(dias: int) -> None:
    assert sessoes(_q(dias)) == SEMANA_ANTIGA[dias]


@pytest.mark.parametrize("dias", range(1, 8))
def test_dias_fixos_escolhidos_dao_a_mesma_semana(dias: int) -> None:
    assert sessoes(_q(list(DIAS_FIXOS[dias]))) == SEMANA_ANTIGA[dias]


@pytest.mark.parametrize(
    ("dias", "forca"), [(1, 1), (2, 2), (3, 2), (4, 2), (5, 3), (6, 3), (7, 3)]
)
def test_dias_de_forca(dias: int, forca: int) -> None:
    assert sum(s.atividade in FORCA for s in _semana(dias)) == forca


@pytest.mark.parametrize("dias", range(1, 8))
def test_nunca_dois_dias_de_forca_seguidos(dias: int) -> None:
    assert _sem_forca_seguida(_semana(dias))


def test_todas_as_escolhas_possiveis() -> None:
    """As 127 escolhas: sessões só nos dias escolhidos, força nunca seguida e, salvo com dois
    dias seguidos, o número de dias de força da regra."""
    from itertools import combinations

    from vigoria.motor.semana import numero_dias_forca

    for n in range(1, 8):
        for escolha in combinations(list(DiaSemana), n):
            semana = _semana(list(escolha))
            assert {s.dia for s in semana if s.duracao_min > 0} == set(escolha)
            assert _sem_forca_seguida(semana)
            forca = sum(s.atividade in FORCA for s in semana)
            assert forca == numero_dias_forca(n) or (n == 2 and forca == 1), escolha


@pytest.mark.parametrize(
    ("dias", "esperado"),
    [
        ([D.SABADO, D.DOMINGO], {D.SABADO: "forca", D.DOMINGO: "cardio_mobilidade"}),
        ([D.SEGUNDA, D.TERCA], {D.SEGUNDA: "forca", D.TERCA: "cardio_mobilidade"}),
        ([D.DOMINGO, D.SEGUNDA], {D.SEGUNDA: "forca", D.DOMINGO: "cardio_mobilidade"}),
        ([D.SABADO, D.SEGUNDA], {D.SEGUNDA: "forca", D.SABADO: "forca"}),
        (
            [D.SEXTA, D.SABADO, D.DOMINGO],
            {D.SEXTA: "forca", D.SABADO: "cardio_mobilidade", D.DOMINGO: "forca"},
        ),
    ],
)
def test_fim_de_semana_e_dias_seguidos(
    dias: list[DiaSemana], esperado: dict[DiaSemana, str]
) -> None:
    assert sessoes(_q(dias)) == esperado


def test_domingo_e_um_dia_como_os_outros() -> None:
    semana = {s.dia: s for s in _semana([D.QUARTA, D.DOMINGO])}
    assert semana[D.DOMINGO].duracao_min == 30
    assert semana[D.DOMINGO].atividade in FORCA
    sem_sessao = _semana(5)[-1]
    assert sem_sessao.dia is D.DOMINGO
    assert sem_sessao.atividade == "Caminhada leve (opcional)"


def test_forca_o_mais_espacada_possivel() -> None:
    assert dias_de_forca((D.SEGUNDA, D.TERCA, D.QUARTA, D.QUINTA)) == (D.SEGUNDA, D.QUINTA)
    assert dias_de_forca((D.QUARTA, D.QUINTA, D.SEXTA, D.SABADO, D.DOMINGO)) == (
        D.QUARTA,
        D.SEXTA,
        D.DOMINGO,
    )
    assert dias_de_forca(()) == ()


def test_dias_escolhidos_ordenados_sem_repeticoes() -> None:
    q = _q([D.DOMINGO, D.SEGUNDA, D.DOMINGO, D.QUARTA])
    assert q.dias_treino == [D.SEGUNDA, D.QUARTA, D.DOMINGO]
    assert q.dias_semana == 3


def test_dias_escolhidos_mandam_no_numero_de_dias() -> None:
    q = Questionario.model_validate(_dados() | {"dias_treino": ["sabado"], "dias_semana": 5})
    assert q.dias_semana == 1


def test_dia_invalido_recusado() -> None:
    with pytest.raises(ValidationError, match="dias_treino"):
        Questionario.model_validate(_dados() | {"dias_treino": ["feriado"]})


@pytest.mark.parametrize("dias", [1, 2])
def test_menos_de_3_dias_com_caminhada_diaria(dias: int) -> None:
    livres = [s for s in _semana(dias) if s.duracao_min == 0]
    assert livres and all(s.atividade == "Caminhada diária" for s in livres)


def test_tabela_dos_dias_fixos() -> None:
    assert set(DIAS_FIXOS) == set(range(1, 8))
    for dias, fixos in DIAS_FIXOS.items():
        assert len(fixos) == dias
