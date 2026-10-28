"""Testes dos cálculos (REGRAS_DOMINIO §2)."""

import pytest

from vigoria.modelos.questionario import Condicao, Sexo
from vigoria.regras import textos
from vigoria.regras.calculos import (
    ClasseImc,
    avaliar_ganho_muscular,
    avaliar_perda_peso,
    calcular_hidratacao,
    calcular_imc,
    calcular_proteina,
    cintura_de_risco,
    classe_imc,
    ganho_muscular_maximo_kg,
    imc_leva_a_prudente,
    limiar_cintura_cm,
    ritmo_maximo_perda_pct,
)

# --- IMC ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("peso", "altura", "esperado"),
    [
        (94, 172, 31.8),  # persona
        (100.86, 170, 34.9),
        (101.15, 170, 35.0),
        (101.0055, 170, 35.0),  # 34,95 exato: arredonda para cima
    ],
)
def test_imc_arredondado_a_uma_casa(peso: float, altura: int, esperado: float) -> None:
    assert calcular_imc(peso, altura) == esperado


@pytest.mark.parametrize(("peso", "altura"), [(0, 170), (-70, 170), (70, 0)])
def test_imc_rejeita_valores_nao_positivos(peso: float, altura: int) -> None:
    with pytest.raises(ValueError):
        calcular_imc(peso, altura)


@pytest.mark.parametrize(
    ("imc", "classe"),
    [
        (18.4, ClasseImc.BAIXO_PESO),
        (18.5, ClasseImc.NORMAL),
        (24.9, ClasseImc.NORMAL),
        (25.0, ClasseImc.EXCESSO_PESO),
        (29.9, ClasseImc.EXCESSO_PESO),
        (30.0, ClasseImc.OBESIDADE_I),
        (34.9, ClasseImc.OBESIDADE_I),
        (35.0, ClasseImc.FORA_DA_VERSAO_BASE),
    ],
)
def test_classe_imc_nos_limiares(imc: float, classe: ClasseImc) -> None:
    assert classe_imc(imc) is classe


def test_imc_35_leva_a_prudente_e_34_9_nao() -> None:
    assert imc_leva_a_prudente(35.0)
    assert not imc_leva_a_prudente(34.9)


# --- Cintura -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("sexo", "cintura", "risco"),
    [
        (Sexo.MASCULINO, 94, False),
        (Sexo.MASCULINO, 94.5, True),
        (Sexo.MASCULINO, 95, True),
        (Sexo.FEMININO, 80, False),
        (Sexo.FEMININO, 81, True),
        (Sexo.FEMININO, 94, True),
    ],
)
def test_cintura_de_risco(sexo: Sexo, cintura: float, risco: bool) -> None:
    assert cintura_de_risco(sexo, cintura) is risco


def test_limiar_cintura_por_sexo() -> None:
    assert limiar_cintura_cm(Sexo.MASCULINO) == 94
    assert limiar_cintura_cm(Sexo.FEMININO) == 80


# --- Hidratação --------------------------------------------------------------


def test_hidratacao_sem_condicoes() -> None:
    h = calcular_hidratacao(94, [Condicao.NENHUMA])
    assert (h.minimo_ml, h.central_ml, h.maximo_ml) == (2350, 2820, 3290)
    assert h.nota is None


def test_hidratacao_doenca_renal_sem_valores() -> None:
    h = calcular_hidratacao(94, [Condicao.DOENCA_RENAL])
    assert (h.minimo_ml, h.central_ml, h.maximo_ml) == (None, None, None)
    assert h.nota == textos.HIDRATACAO_DOENCA_RENAL


def test_hidratacao_doenca_cardiovascular_com_nota_de_liquidos() -> None:
    h = calcular_hidratacao(94, [Condicao.DOENCA_CARDIOVASCULAR])
    assert (h.minimo_ml, h.central_ml, h.maximo_ml) == (2350, 2820, 3290)
    assert h.nota == textos.HIDRATACAO_DOENCA_CARDIOVASCULAR


def test_hidratacao_renal_prevalece_sobre_cardiovascular() -> None:
    h = calcular_hidratacao(94, [Condicao.DOENCA_CARDIOVASCULAR, Condicao.DOENCA_RENAL])
    assert h.central_ml is None
    assert h.nota == textos.HIDRATACAO_DOENCA_RENAL


# --- Proteína ----------------------------------------------------------------


def test_proteina_sem_condicoes() -> None:
    p = calcular_proteina(94, [Condicao.NENHUMA])
    assert (p.minimo_g, p.maximo_g) == (94, 112)  # 1,2 × 94 = 112,8 → nunca acima
    assert (p.por_refeicao_min_g, p.por_refeicao_max_g) == (25, 30)
    assert p.nota is None


@pytest.mark.parametrize("peso", [35, 50.5, 67.3, 94, 112.8, 250])
def test_proteina_nunca_sai_de_1_0_a_1_2_g_por_kg(peso: float) -> None:
    p = calcular_proteina(peso, [Condicao.NENHUMA])
    assert p.minimo_g is not None and p.maximo_g is not None
    assert p.minimo_g >= 1.0 * peso
    assert p.maximo_g <= 1.2 * peso
    assert p.minimo_g <= p.maximo_g


@pytest.mark.parametrize(
    "condicao", [c for c in Condicao if c not in (Condicao.NENHUMA, Condicao.DOENCA_RENAL)]
)
def test_proteina_nota_1_5_com_qualquer_condicao(condicao: Condicao) -> None:
    p = calcular_proteina(80, [condicao])
    assert p.maximo_g == 96
    assert p.nota == textos.PROTEINA_ATE_1_5


def test_proteina_doenca_renal_sem_valores_nem_nota_1_5() -> None:
    p = calcular_proteina(80, [Condicao.HIPERTENSAO, Condicao.DOENCA_RENAL])
    assert (p.minimo_g, p.maximo_g, p.por_refeicao_min_g, p.por_refeicao_max_g) == (
        None,
        None,
        None,
        None,
    )
    assert p.nota == textos.PROTEINA_DOENCA_RENAL


# --- Ritmo de perda de peso --------------------------------------------------


@pytest.mark.parametrize(
    ("idade", "pct"), [(18, 0.6), (44, 0.6), (45, 0.5), (60, 0.5), (61, 0.4), (100, 0.4)]
)
def test_ritmo_maximo_por_faixa_etaria(idade: int, pct: float) -> None:
    assert ritmo_maximo_perda_pct(idade) == pct


def test_ritmo_maximo_rejeita_menores_de_18() -> None:
    with pytest.raises(ValueError):
        ritmo_maximo_perda_pct(17)


def test_perda_peso_persona_alvo_realista_88_semana_24() -> None:
    a = avaliar_perda_peso(94, 85, 68)
    assert not a.realista
    assert a.ritmo_maximo_kg_semana == 0.38
    assert a.ritmo_necessario_kg_semana == 0.56
    assert a.alvo_semana_16_kg == 88.0
    assert a.semana_objetivo == 24


def test_perda_peso_exatamente_no_limite_e_realista() -> None:
    # 61+: 0,4 % × 100 kg = 0,4 kg/semana ⇒ 6,4 kg em 16 semanas
    a = avaliar_perda_peso(100, 93.6, 61)
    assert a.realista
    assert a.alvo_semana_16_kg == 93.6
    assert a.semana_objetivo == 16


def test_perda_peso_logo_acima_do_limite() -> None:
    a = avaliar_perda_peso(100, 93.5, 61)
    assert not a.realista
    assert a.alvo_semana_16_kg == 93.6
    assert a.semana_objetivo == 17  # 6,5 / 0,4 = 16,25


@pytest.mark.parametrize(("idade", "realista"), [(44, True), (45, False), (60, False)])
def test_perda_peso_muda_com_a_faixa_etaria(idade: int, realista: bool) -> None:
    # 9,6 kg em 16 semanas = 0,6 kg/semana = 0,6 % de 100 kg
    assert avaliar_perda_peso(100, 90.4, idade).realista is realista


@pytest.mark.parametrize("alvo", [80, 85])
def test_perda_peso_sem_perda_pedida(alvo: float) -> None:
    a = avaliar_perda_peso(80, alvo, 50)
    assert a.realista
    assert a.perda_pedida_kg == 0
    assert a.semana_objetivo is None


# --- Ganho muscular ----------------------------------------------------------


def test_ganho_muscular_maximo() -> None:
    assert ganho_muscular_maximo_kg() == 2.0
    assert ganho_muscular_maximo_kg(4) == 0.5


def test_ganho_muscular_sem_alvo_numerico() -> None:
    g = avaliar_ganho_muscular("aumentar_forca_tonus")
    assert g.pedido_kg is None
    assert g.realista
    assert g.maximo_kg == 2.0


@pytest.mark.parametrize("pedido", [0.5, 2.0])
def test_ganho_muscular_dentro_do_maximo(pedido: float) -> None:
    g = avaliar_ganho_muscular(pedido)
    assert g.realista
    assert g.alvo_semana_16_kg == pedido
    assert g.semana_objetivo == 16


def test_ganho_muscular_acima_do_maximo() -> None:
    g = avaliar_ganho_muscular(3.0)
    assert not g.realista
    assert g.alvo_semana_16_kg == 2.0
    assert g.semana_objetivo == 24  # 3 kg a 0,125 kg/semana


def test_ganho_muscular_rejeita_valor_nao_positivo() -> None:
    with pytest.raises(ValueError):
        avaliar_ganho_muscular(0)
