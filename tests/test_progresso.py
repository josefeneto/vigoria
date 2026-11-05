"""Regras do acompanhamento (regras/progresso.py) e modelo do registo, com casos-limite."""

import random
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from vigoria.modelos.questionario import FrequenciaRegisto
from vigoria.modelos.registo import OBSERVACOES_MAX, Comparacao, ValoresRegisto
from vigoria.regras.calculos import marcos_peso_kg, ritmo_maximo_perda_pct
from vigoria.regras.progresso import (
    Alerta,
    ContextoPlano,
    Medicao,
    TipoAlerta,
    avaliar,
    em_manutencao,
    esforco_acima,
    evolucao_abaixo,
    fase_da_semana,
    frequencia_efetiva,
    inicio_do_plano,
    linha_indicativa,
    perda_rapida,
    periodo,
    periodo_em_falta,
    periodo_ocupado,
    proximo_marco,
    ritmo_medio_kg_semana,
    semana_do_plano,
    subida_manutencao,
)

SEMANAL = FrequenciaRegisto.SEMANAL
QUATRO = FrequenciaRegisto.A_CADA_4_SEMANAS
INICIO = date(2026, 1, 5)
PESO = 94.0  # persona de teste: 68 anos, 94 → 85 kg, ritmo usado = máximo (0,376 kg/semana)
IDADE = 68
ALVO = 85.0
MARCOS = tuple(zip((4, 8, 12, 16), marcos_peso_kg(PESO, ALVO, IDADE), strict=True))
FASES = {n: (3, 6) for n in (1, 2, 3, 4)}


def _pesos(*pares: tuple[int, float]) -> list[Medicao]:
    return [Medicao(semana=s, peso_kg=p) for s, p in pares]


# ---------------------------------------------------------------- Semanas e fases


@pytest.mark.parametrize(
    ("dias", "semana"), [(0, 1), (6, 1), (7, 2), (13, 2), (14, 3), (111, 16), (112, 17)]
)
def test_semana_do_plano(dias: int, semana: int) -> None:
    assert semana_do_plano(INICIO, INICIO + timedelta(days=dias)) == semana


def test_sem_semanas_antes_do_inicio() -> None:
    with pytest.raises(ValueError, match="anterior"):
        semana_do_plano(INICIO, INICIO - timedelta(days=1))


def test_inicio_na_hora_de_lisboa_e_sem_fuso_vem_em_utc() -> None:
    # Verão: 23:30 UTC já é o dia seguinte em Lisboa.
    assert inicio_do_plano(datetime(2026, 7, 1, 23, 30, tzinfo=UTC)) == date(2026, 7, 2)
    assert inicio_do_plano(datetime(2026, 7, 1, 23, 30)) == date(2026, 7, 2)  # noqa: DTZ001
    assert inicio_do_plano(datetime(2026, 1, 1, 23, 30, tzinfo=UTC)) == date(2026, 1, 1)


@pytest.mark.parametrize(
    ("semana", "fase", "marco"),
    [
        (1, 1, 4),
        (4, 1, 4),
        (5, 2, 8),
        (8, 2, 8),
        (9, 3, 12),
        (13, 4, 16),
        (16, 4, 16),
        (17, None, None),
        (40, None, None),
    ],
)
def test_fase_e_proximo_marco(semana: int, fase: int | None, marco: int | None) -> None:
    assert fase_da_semana(semana) == fase
    assert proximo_marco(semana) == marco
    assert em_manutencao(semana) is (fase is None)


@pytest.mark.parametrize("funcao", [fase_da_semana, proximo_marco, em_manutencao])
def test_semana_zero_nao_existe(funcao: object) -> None:
    with pytest.raises(ValueError, match="a partir de 1"):
        funcao(0)  # type: ignore[operator]


# ---------------------------------------------------------------- Períodos


@pytest.mark.parametrize(
    ("semana", "frequencia", "esperado"),
    [
        (1, SEMANAL, (1, 1)),
        (16, SEMANAL, (16, 16)),
        (1, QUATRO, (1, 4)),
        (4, QUATRO, (1, 4)),
        (5, QUATRO, (5, 8)),
        (16, QUATRO, (13, 16)),
        (17, QUATRO, (17, 20)),
        (21, QUATRO, (21, 24)),
    ],
)
def test_periodo(semana: int, frequencia: FrequenciaRegisto, esperado: tuple[int, int]) -> None:
    assert periodo(semana, frequencia) == esperado


def test_na_manutencao_sempre_a_cada_4_semanas() -> None:
    assert frequencia_efetiva(SEMANAL, 16) is SEMANAL
    assert frequencia_efetiva(SEMANAL, 17) is QUATRO
    assert frequencia_efetiva(QUATRO, 3) is QUATRO


def test_um_registo_por_periodo() -> None:
    assert periodo_ocupado(5, SEMANAL, [5])
    assert not periodo_ocupado(6, SEMANAL, [5])
    assert periodo_ocupado(6, QUATRO, [5])
    assert not periodo_ocupado(9, QUATRO, [5])
    assert periodo_ocupado(18, SEMANAL, [20])  # manutenção: bloco 17–20
    assert not periodo_ocupado(16, SEMANAL, [17])


def _hoje(semana: int, dia: int = 0) -> date:
    return INICIO + timedelta(days=7 * (semana - 1) + dia)


def test_periodo_em_falta_so_depois_do_ultimo_dia() -> None:
    assert periodo_em_falta(INICIO, INICIO, SEMANAL, set()) is None
    assert periodo_em_falta(INICIO, _hoje(1, 6), SEMANAL, set()) is None  # último dia da semana 1
    assert periodo_em_falta(INICIO, _hoje(2), SEMANAL, set()) == (1, 1)
    assert periodo_em_falta(INICIO, _hoje(2), SEMANAL, {1}) is None


def test_periodo_em_falta_e_o_mais_recente_mesmo_com_falha_no_meio() -> None:
    assert periodo_em_falta(INICIO, _hoje(6), SEMANAL, {1, 2, 3}) == (5, 5)
    assert periodo_em_falta(INICIO, _hoje(6), SEMANAL, {1, 2, 3, 5}) == (4, 4)
    assert periodo_em_falta(INICIO, _hoje(6), SEMANAL, {1, 2, 3, 4, 5}) is None


def test_periodo_em_falta_a_cada_4_semanas() -> None:
    assert periodo_em_falta(INICIO, _hoje(4, 6), QUATRO, set()) is None
    assert periodo_em_falta(INICIO, _hoje(5), QUATRO, set()) == (1, 4)
    assert periodo_em_falta(INICIO, _hoje(5), QUATRO, {2}) is None


def test_periodo_em_falta_na_manutencao_usa_blocos_de_4() -> None:
    registadas = set(range(1, 17))
    assert periodo_em_falta(INICIO, _hoje(20, 6), SEMANAL, registadas) is None
    assert periodo_em_falta(INICIO, _hoje(21), SEMANAL, registadas) == (17, 20)
    assert periodo_em_falta(INICIO, _hoje(21), SEMANAL, registadas | {18}) is None


def test_mudar_de_frequencia_a_meio_nao_inventa_faltas() -> None:
    # Registou semanalmente até à 6 e passou a 4 semanas: os blocos 1–4 e 5–8 estão cobertos.
    assert periodo_em_falta(INICIO, _hoje(9), QUATRO, {1, 2, 3, 4, 5, 6}) is None


# ---------------------------------------------------------------- Linha indicativa


def test_linha_indicativa_passa_pelos_marcos() -> None:
    assert linha_indicativa(PESO, MARCOS, 0) == PESO
    for semana, peso in MARCOS:
        assert linha_indicativa(PESO, MARCOS, semana) == peso
    assert linha_indicativa(PESO, MARCOS, 2) == pytest.approx((PESO + MARCOS[0][1]) / 2, abs=0.01)
    assert linha_indicativa(PESO, MARCOS, 30) == MARCOS[-1][1]


# ---------------------------------------------------------------- R8: evolução abaixo


def _linha(semana: int) -> float:
    return linha_indicativa(PESO, MARCOS, semana)


def test_abaixo_em_dois_registos_seguidos() -> None:
    lento = _pesos((5, 93.5), (6, 93.4))
    assert evolucao_abaixo(lento, PESO, MARCOS, ALVO)


def test_abaixo_num_so_registo_nao_chega() -> None:
    assert not evolucao_abaixo(_pesos((6, 93.4)), PESO, MARCOS, ALVO)
    assert not evolucao_abaixo(_pesos((5, _linha(5)), (6, 93.4)), PESO, MARCOS, ALVO)
    assert not evolucao_abaixo(_pesos((5, 93.5), (6, _linha(6))), PESO, MARCOS, ALVO)


def test_abaixo_so_a_partir_da_semana_4() -> None:
    assert not evolucao_abaixo(_pesos((3, 94.0), (4, 94.0)), PESO, MARCOS, ALVO)
    assert evolucao_abaixo(_pesos((4, 94.0), (5, 94.0)), PESO, MARCOS, ALVO)


def test_abaixo_exige_mais_de_1_kg_acima_da_linha() -> None:
    # Exatamente 1 kg acima da linha: não conta, mesmo com menos de 50 % da perda.
    exato = _pesos((4, _linha(4) + 1), (5, _linha(5) + 1))
    assert not evolucao_abaixo(exato, 94.0, MARCOS, ALVO)
    acima = _pesos((4, _linha(4) + 1.01), (5, _linha(5) + 1.01))
    assert evolucao_abaixo(acima, 94.0, MARCOS, ALVO)


def test_abaixo_exige_menos_de_50_por_cento_da_perda() -> None:
    # Objetivo grande: 1,5 kg acima da linha, mas mais de metade da perda feita.
    peso, marcos = 120.0, tuple(zip((4, 8, 12, 16), marcos_peso_kg(120, 100, 50), strict=True))
    linha = linha_indicativa(peso, marcos, 12)
    assert not evolucao_abaixo(_pesos((11, linha + 1.5), (12, linha + 1.5)), peso, marcos, 100.0)


def test_objetivo_de_manter_nunca_fica_abaixo() -> None:
    marcos = tuple(zip((4, 8, 12, 16), marcos_peso_kg(80, 80, 50), strict=True))
    assert not evolucao_abaixo(_pesos((5, 83.0), (6, 84.0)), 80.0, marcos, 80.0)


def test_peso_alvo_atingido_nunca_fica_abaixo() -> None:
    marcos = tuple(zip((4, 8, 12, 16), marcos_peso_kg(70, 68, 50), strict=True))
    assert not evolucao_abaixo(_pesos((14, 68.0), (15, 67.9)), 70.0, marcos, 68.0)


def test_abaixo_ignora_registos_sem_peso() -> None:
    medicoes = [*_pesos((5, 93.5)), Medicao(semana=6, esforco=4), *_pesos((7, 93.4))]
    assert evolucao_abaixo(medicoes, PESO, MARCOS, ALVO)


@pytest.mark.parametrize(
    ("peso", "alvo", "idade"),
    [(94.0, 85.0, 68), (70.0, 68.0, 50), (120.0, 100.0, 50), (60.0, 59.5, 40)],
)
def test_abaixo_nao_dispara_com_oscilacoes(peso: float, alvo: float, idade: int) -> None:
    """±0,8 kg à volta da linha, incluindo objetivos pequenos e o pior caso (sempre +0,8)."""
    marcos = tuple(zip((4, 8, 12, 16), marcos_peso_kg(peso, alvo, idade), strict=True))
    semanas = range(1, 17)
    sempre_acima = [(s, linha_indicativa(peso, marcos, s) + 0.8) for s in semanas]
    assert not evolucao_abaixo(_pesos(*sempre_acima), peso, marcos, alvo)
    for semente in range(100):
        sorteio = random.Random(semente)
        pares = [
            (s, linha_indicativa(peso, marcos, s) + sorteio.uniform(-0.8, 0.8)) for s in semanas
        ]
        for fim in semanas:
            assert not evolucao_abaixo(_pesos(*pares[:fim]), peso, marcos, alvo)


# ---------------------------------------------------------------- R9: perda rápida


def test_ritmo_medio_usa_4_semanas_ou_desde_o_inicio() -> None:
    medicoes = _pesos((1, 93.0), (3, 91.0), (4, 90.0), (5, 89.0))
    assert ritmo_medio_kg_semana(medicoes, PESO, 3) == pytest.approx(3 / 3)
    assert ritmo_medio_kg_semana(medicoes, PESO, 4) == pytest.approx(4 / 4)
    assert ritmo_medio_kg_semana(medicoes, PESO, 5) == pytest.approx(4 / 4)  # desde a semana 1


def test_ritmo_medio_com_falhas_usa_o_registo_anterior_mais_proximo() -> None:
    medicoes = _pesos((2, 93.0), (10, 85.0))
    assert ritmo_medio_kg_semana(medicoes, PESO, 10) == pytest.approx(8 / 8)


def test_ritmo_medio_sem_peso_nessa_semana() -> None:
    with pytest.raises(ValueError, match="sem peso"):
        ritmo_medio_kg_semana(_pesos((2, 93.0)), PESO, 3)


def test_perda_rapida_em_dois_registos_seguidos() -> None:
    rapida = _pesos(*((s, PESO - 1.0 * s) for s in range(1, 7)))
    assert perda_rapida(rapida, PESO, IDADE) == 0.4


def test_perda_rapida_um_registo_nao_chega() -> None:
    assert perda_rapida(_pesos((3, 90.0)), PESO, IDADE) is None
    assert perda_rapida(_pesos((3, 90.0), (4, 92.5)), PESO, IDADE) is None


def test_perda_rapida_so_a_partir_da_semana_3() -> None:
    assert perda_rapida(_pesos((1, 92.0), (2, 90.0)), PESO, IDADE) is None
    # A semana 2 ainda não conta: dos dois últimos, só a 3 pode disparar.
    assert perda_rapida(_pesos((2, 90.0), (3, 89.0)), PESO, IDADE) is None
    assert perda_rapida(_pesos((3, 89.0), (4, 88.0)), PESO, IDADE) == 0.4


def test_perda_rapida_no_limite_nao_dispara() -> None:
    # 0,4 % × 100 kg + 0,4 = 0,8 kg/semana: exatamente no limite não dispara; acima, sim.
    exato = _pesos((4, 100 - 3.2), (5, 100 - 4.0))
    assert perda_rapida(exato, 100.0, IDADE) is None
    acima = _pesos((4, 100 - 3.3), (5, 100 - 4.1))
    assert perda_rapida(acima, 100.0, IDADE) == 0.4


@pytest.mark.parametrize(("idade", "pct"), [(30, 0.6), (45, 0.5), (60, 0.5), (61, 0.4)])
def test_perda_rapida_pela_faixa_etaria(idade: int, pct: float) -> None:
    pesos = _pesos(*((s, 100.0 - 1.5 * s) for s in (3, 4)))
    assert perda_rapida(pesos, 100.0, idade) == pct


def test_perda_rapida_tambem_na_manutencao() -> None:
    pesos = _pesos((16, 88.0), (20, 83.0), (24, 78.0))
    assert perda_rapida(pesos, PESO, IDADE) == 0.4


def _nao_dispara_r9(peso: float, alvo: float, idade: int, oscilacao: list[float]) -> None:
    # A reta exata do plano, não os marcos, que estão arredondados a 0,1 kg.
    ritmo = min((peso - alvo) / 16, peso * ritmo_maximo_perda_pct(idade) / 100)
    pares = [(s, peso - ritmo * s + o) for s, o in enumerate(oscilacao, start=1)]
    for fim in range(1, len(pares) + 1):
        assert perda_rapida(_pesos(*pares[:fim]), peso, idade) is None, (fim, oscilacao)


@pytest.mark.parametrize(
    ("peso", "alvo", "idade"),
    [(94.0, 85.0, 68), (70.0, 68.0, 50), (120.0, 100.0, 50), (80.0, 60.0, 30)],
)
def test_perda_rapida_nao_dispara_com_oscilacoes(peso: float, alvo: float, idade: int) -> None:
    """Quem segue a linha, com ±0,8 kg: alternada, pior caso (+0,8 → −0,8 em 4 semanas), sorteio."""
    alternada = [0.8 if s % 2 else -0.8 for s in range(16)]
    pior_caso = [0.8 if (s // 4) % 2 == 0 else -0.8 for s in range(16)]
    _nao_dispara_r9(peso, alvo, idade, alternada)
    _nao_dispara_r9(peso, alvo, idade, pior_caso)
    for semente in range(100):
        sorteio = random.Random(semente)
        _nao_dispara_r9(peso, alvo, idade, [sorteio.uniform(-0.8, 0.8) for _ in range(16)])


# ---------------------------------------------------------------- R10: esforço


def test_esforco_acima_do_teto() -> None:
    assert esforco_acima([Medicao(semana=2, esforco=6)], FASES) is None
    assert esforco_acima([Medicao(semana=2, esforco=7)], FASES) == (7, (3, 6))


def test_esforco_conta_o_ultimo_registo_com_esforco() -> None:
    medicoes = [Medicao(semana=2, esforco=8), Medicao(semana=3, esforco=5), Medicao(semana=4)]
    assert esforco_acima(medicoes, FASES) is None
    assert esforco_acima(list(reversed(medicoes)), FASES) is None
    assert esforco_acima([Medicao(semana=4, peso_kg=90.0)], FASES) is None


def test_esforco_usa_o_teto_da_fase_e_na_manutencao_o_da_fase_4() -> None:
    fases = {1: (3, 5), 2: (3, 6), 3: (3, 6), 4: (3, 7)}
    assert esforco_acima([Medicao(semana=4, esforco=6)], fases) == (6, (3, 5))
    assert esforco_acima([Medicao(semana=5, esforco=6)], fases) is None
    assert esforco_acima([Medicao(semana=20, esforco=7)], fases) is None
    assert esforco_acima([Medicao(semana=20, esforco=8)], fases) == (8, (3, 7))


# ---------------------------------------------------------------- R11: manutenção


def test_subida_com_referencia_no_ultimo_registo_ate_a_semana_16() -> None:
    pesos = _pesos((16, 88.0), (20, 90.0), (24, 90.5))
    assert subida_manutencao(pesos) == (88.0, None)


def test_subida_no_limite_e_abaixo() -> None:
    assert subida_manutencao(_pesos((16, 88.0), (20, 90.0), (24, 90.0))) == (88.0, None)
    assert subida_manutencao(_pesos((16, 88.0), (20, 89.9), (24, 90.0))) == (None, None)
    assert subida_manutencao(_pesos((16, 88.0), (20, 91.0), (24, 89.0))) == (None, None)


def test_subida_sem_registo_antes_usa_o_primeiro_da_manutencao() -> None:
    assert subida_manutencao(_pesos((20, 88.0), (24, 91.0))) == (None, None)  # o 1.º é a referência
    assert subida_manutencao(_pesos((20, 88.0), (24, 91.0), (28, 91.0))) == (88.0, None)


def test_subida_um_so_registo_na_manutencao_nao_chega() -> None:
    assert subida_manutencao(_pesos((16, 88.0), (20, 95.0))) == (None, None)
    assert subida_manutencao(_pesos((15, 88.0), (16, 95.0))) == (None, None)


def test_subida_da_cintura() -> None:
    def medicoes(a: float, b: float) -> list[Medicao]:
        return [
            Medicao(semana=16, cintura_cm=100.0),
            Medicao(semana=20, cintura_cm=a),
            Medicao(semana=24, cintura_cm=b),
        ]

    assert subida_manutencao(medicoes(103.0, 103.0)) == (None, 100.0)
    assert subida_manutencao(medicoes(102.9, 104.0)) == (None, None)


# ---------------------------------------------------------------- Alertas de hoje


def _contexto(**campos: object) -> ContextoPlano:
    return ContextoPlano(
        **{
            "inicio": INICIO,
            "peso_inicial_kg": PESO,
            "idade": IDADE,
            "peso_alvo_kg": ALVO,
            "marcos": MARCOS,
            "esforco_fases": FASES,
        }
        | campos  # type: ignore[arg-type]
    )


def _tipos(alertas: tuple[Alerta, ...]) -> list[TipoAlerta]:
    return [a.tipo for a in alertas]


def test_avaliar_sem_registos_so_o_periodo_em_falta() -> None:
    assert avaliar(_contexto(), [], SEMANAL, INICIO) == ()
    alertas = avaliar(_contexto(), [], SEMANAL, _hoje(3))
    assert alertas == (Alerta(tipo=TipoAlerta.PERIODO_EM_FALTA, semanas=(2, 2)),)


def test_avaliar_seguranca_primeiro() -> None:
    medicoes = [Medicao(semana=s, peso_kg=PESO - s, esforco=8) for s in range(1, 7)]
    alertas = avaliar(_contexto(), medicoes, SEMANAL, _hoje(7))
    assert _tipos(alertas) == [TipoAlerta.PERDA_RAPIDA, TipoAlerta.ESFORCO_ACIMA]


def test_avaliar_abaixo_ate_a_semana_16() -> None:
    medicoes = _pesos(*((s, 93.9) for s in range(1, 17)))
    assert _tipos(avaliar(_contexto(), medicoes, SEMANAL, _hoje(16))) == [
        TipoAlerta.EVOLUCAO_ABAIXO
    ]


def test_avaliar_manutencao_sem_abaixo_e_com_subida() -> None:
    medicoes = _pesos(*((s, 93.9) for s in range(1, 17)))
    assert (
        _tipos(avaliar(_contexto(), medicoes, SEMANAL, _hoje(17))) == []
    )  # pela data, sem registos
    com_subida = [*medicoes, *_pesos((20, 96.0), (23, 96.5))]
    alertas = avaliar(_contexto(), com_subida, SEMANAL, _hoje(23))
    assert alertas == (Alerta(tipo=TipoAlerta.SUBIDA_PESO, referencia=93.9),)


def test_avaliar_sem_peso_inicial_nem_idade_nao_falha() -> None:
    medicoes = _pesos((5, 93.5), (6, 93.4))
    contexto = _contexto(peso_inicial_kg=None, idade=None)
    assert _tipos(avaliar(contexto, medicoes, SEMANAL, _hoje(6, 3))) == [
        TipoAlerta.PERIODO_EM_FALTA
    ]


# ---------------------------------------------------------------- Modelo do registo


def test_registo_precisa_de_um_campo() -> None:
    assert ValoresRegisto(peso_kg=80).peso_kg == 80
    assert ValoresRegisto(forca=Comparacao.IGUAL).forca is Comparacao.IGUAL
    assert ValoresRegisto(sessoes=0).sessoes == 0  # zero é uma resposta
    with pytest.raises(ValidationError):
        ValoresRegisto()
    with pytest.raises(ValidationError):
        ValoresRegisto(observacoes="   ")


@pytest.mark.parametrize(
    ("campo", "bom", "mau"),
    [
        ("peso_kg", 35, 34.9),
        ("peso_kg", 250, 250.1),
        ("cintura_cm", 50, 49),
        ("cintura_cm", 200, 201),
        ("sessoes", 14, 15),
        ("sessoes", 0, -1),
        ("cardio_min", 600, 601),
        ("energia", 10, 11),
        ("energia", 0, -1),
        ("esforco", 10, 11),
        ("sono_h", 3, 2.5),
        ("sono_h", 12, 12.5),
        ("sono_h", 6.5, 6.3),
    ],
)
def test_registo_limites(campo: str, bom: float, mau: float) -> None:
    assert getattr(ValoresRegisto(**{campo: bom}), campo) == bom
    with pytest.raises(ValidationError):
        ValoresRegisto(**{campo: mau})


def test_registo_observacoes() -> None:
    assert ValoresRegisto(observacoes="  ok  ").observacoes == "ok"
    assert ValoresRegisto(observacoes="x" * OBSERVACOES_MAX).observacoes
    assert ValoresRegisto(peso_kg=80, observacoes="").observacoes is None
    with pytest.raises(ValidationError):
        ValoresRegisto(observacoes="x" * (OBSERVACOES_MAX + 1))


def test_registo_nao_aceita_campos_desconhecidos() -> None:
    with pytest.raises(ValidationError):
        ValoresRegisto(peso_kg=80, nome="alguém")
