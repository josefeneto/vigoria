"""Testes do acolhimento, da estratégia e da CLI (REGRAS_DOMINIO §1 a §5)."""

import json
from pathlib import Path
from typing import Any

import pytest

from vigoria.modelos.estrategia import Estrategia, Zona
from vigoria.modelos.questionario import Intensidade, Questionario
from vigoria.motor import cli
from vigoria.motor.acolhimento import acolher
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.regras import textos
from vigoria.regras.elegibilidade import Modo
from vigoria.regras.intensidade import Limitador

PERSONA = Path(__file__).parent.parent / "exemplos" / "persona_teste.json"

# Altura 172 cm e 70 kg: IMC 23,7; cintura abaixo do limiar; 7 dias × 30 min.
NEUTRO = {
    "peso_kg": 70.0,
    "peso_alvo_kg": 68.0,
    "cintura_cm": 88,
    "cintura_alvo_cm": None,
    "condicoes": ["nenhuma"],
    "condicoes_controladas": {},
    "limitacoes": ["nenhuma"],
    "limitacoes_gravidade": {},
    "medicacao_afeta_fc": "nao",
    "dias_semana": 7,
    "minutos_dia": 30,
}


def _questionario(**alteracoes: Any) -> Questionario:
    dados = json.loads(PERSONA.read_text(encoding="utf-8"))
    dados.update(NEUTRO)
    dados.update(alteracoes)
    return Questionario.model_validate(dados)


def _estrategia(**alteracoes: Any) -> Estrategia:
    return gerar_estrategia(_questionario(**alteracoes))


def _persona() -> Questionario:
    return Questionario.model_validate(json.loads(PERSONA.read_text(encoding="utf-8")))


# --- Intensidade efetiva -----------------------------------------------------


def test_neutro_alta_fica_alta() -> None:
    e = _estrategia(intensidade_pedida="alta")
    assert e.modo is Modo.BASE
    assert e.intensidade_efetiva is Intensidade.ALTA
    assert e.explicacao_intensidade is None


def test_doenca_cardiovascular_alta_fica_media() -> None:
    e = _estrategia(condicoes=["doenca_cardiovascular"], intensidade_pedida="alta")
    assert e.modo is Modo.PRUDENTE
    assert e.intensidade_efetiva is Intensidade.MEDIA
    assert e.intensidade_limitada_por == (Limitador.MODO,)
    assert textos.MOTIVO_TETO_PRUDENTE in (e.explicacao_intensidade or "")
    assert textos.VALIDACAO_MEDICA_ANTES in e.avisos
    assert textos.ORIENTACAO_INDIVIDUALIZADA in e.avisos


def test_hipertensao_controlada_alta_7x30_fica_alta() -> None:
    e = _estrategia(
        condicoes=["hipertensao"],
        condicoes_controladas={"hipertensao": True},
        intensidade_pedida="alta",
    )
    assert e.modo is Modo.BASE
    assert e.intensidade_efetiva is Intensidade.ALTA
    assert e.explicacao_intensidade is None
    assert textos.INTENSIFICACAO_VALIDACAO_MEDICA in e.avisos
    assert textos.ORIENTACAO_INDIVIDUALIZADA not in e.avisos


@pytest.mark.parametrize(
    ("dias", "minutos", "esperada", "caminhada_extra"),
    [
        (2, 30, Intensidade.LIGEIRA, True),
        (3, 30, Intensidade.LIGEIRA, False),
        (5, 20, Intensidade.LIGEIRA, False),
        (7, 30, Intensidade.ALTA, False),
    ],
)
def test_disponibilidade(
    dias: int, minutos: int, esperada: Intensidade, caminhada_extra: bool
) -> None:
    e = _estrategia(intensidade_pedida="alta", dias_semana=dias, minutos_dia=minutos)
    assert e.intensidade_efetiva is esperada
    assert e.caminhada_diaria_extra is caminhada_extra
    assert (textos.DISPONIBILIDADE_2_DIAS in e.avisos) is caminhada_extra
    assert textos.DISPONIBILIDADE_1_DIA not in e.avisos
    if esperada is not Intensidade.ALTA:
        assert e.intensidade_limitada_por == (Limitador.DISPONIBILIDADE,)


def test_um_dia_por_semana() -> None:
    e = _estrategia(dias_semana=1)
    assert e.intensidade_efetiva is Intensidade.LIGEIRA
    assert e.caminhada_diaria_extra
    assert textos.DISPONIBILIDADE_1_DIA in e.avisos
    assert textos.DISPONIBILIDADE_2_DIAS not in e.avisos


def test_sessoes_curtas_com_20_minutos() -> None:
    assert _estrategia(minutos_dia=20).sessoes_curtas
    assert not _estrategia(minutos_dia=30).sessoes_curtas


def test_imc_35_ou_mais_alta_fica_ligeira() -> None:
    e = _estrategia(peso_kg=104.0, peso_alvo_kg=98.0, intensidade_pedida="alta")  # IMC 35,2
    assert e.modo is Modo.PRUDENTE
    assert e.intensidade_efetiva is Intensidade.LIGEIRA
    assert textos.MOTIVO_TETO_IMC in (e.explicacao_intensidade or "")


# --- Não elegível ------------------------------------------------------------


def test_gravidez_nao_gera_plano() -> None:
    e = _estrategia(condicoes=["gravidez"])
    assert not e.pode_gerar_plano
    assert e.modo is Modo.NAO_ELEGIVEL
    assert e.motivos == (textos.GRAVIDEZ,)
    assert e.intensidade_efetiva is None
    assert e.indicadores is None
    assert e.marcos == ()
    assert "Não é possível gerar plano" in cli.formatar_estrategia(e)


# --- Avisos obrigatórios e condicionais -------------------------------------


@pytest.mark.parametrize(
    "alteracoes",
    [
        {},
        {"condicoes": ["doenca_renal"]},
        {"peso_kg": 104.0, "peso_alvo_kg": 98.0},
        {"dias_semana": 1},
    ],
)
def test_avisos_obrigatorios_sempre_primeiro(alteracoes: dict[str, Any]) -> None:
    e = _estrategia(**alteracoes)
    assert e.avisos[:2] == (textos.AVISO_GERAL, textos.SINAIS_INTERROMPER)


def test_avisos_sem_repeticoes() -> None:
    # Hipertensão controlada + cintura de risco pedem o mesmo aviso de intensificação.
    e = _estrategia(
        condicoes=["hipertensao"], condicoes_controladas={"hipertensao": True}, cintura_cm=100
    )
    assert e.avisos.count(textos.INTENSIFICACAO_VALIDACAO_MEDICA) == 1


@pytest.mark.parametrize(
    ("alteracoes", "esperados"),
    [
        (
            {"condicoes": ["hipertensao"], "condicoes_controladas": {"hipertensao": False}},
            [textos.FALAR_COM_MEDICO_ANTES],
        ),
        (
            {"condicoes": ["diabetes"], "condicoes_controladas": {"diabetes": True}},
            [textos.DIABETES_HIPOGLICEMIA],
        ),
        (
            {"condicoes": ["diabetes"], "condicoes_controladas": {"diabetes": False}},
            [textos.DIABETES_HIPOGLICEMIA, textos.FALAR_COM_MEDICO_ANTES],
        ),
        ({"condicoes": ["doenca_respiratoria"]}, [textos.RESPIRATORIA_TESTE_DA_FALA]),
        (
            {
                "condicoes": ["doenca_inflamatoria_intestinal"],
                "condicoes_controladas": {"doenca_inflamatoria_intestinal": True},
            },
            [textos.DII_PLANO_ALIMENTAR],
        ),
        (
            {
                "condicoes": ["doenca_inflamatoria_intestinal"],
                "condicoes_controladas": {"doenca_inflamatoria_intestinal": False},
            },
            [textos.DII_PLANO_ALIMENTAR, textos.DII_ADIAR_MUDANCAS],
        ),
        ({"condicoes": ["protese_ou_cirurgia_recente"]}, [textos.VALIDACAO_CIRURGIAO_ANTES]),
        ({"medicacao_afeta_fc": "sim"}, [textos.ESFORCO_PERCEBIDO]),
        ({"medicacao_afeta_fc": "nao_sei"}, [textos.ESFORCO_PERCEBIDO]),
    ],
)
def test_avisos_condicionais(alteracoes: dict[str, Any], esperados: list[str]) -> None:
    e = _estrategia(**alteracoes)
    for aviso in esperados:
        assert aviso in e.avisos


def test_doenca_renal_sem_valores_de_proteina_nem_hidratacao() -> None:
    e = _estrategia(condicoes=["doenca_renal"])
    assert e.indicadores is not None
    assert e.indicadores.proteina.minimo_g is None
    assert e.indicadores.hidratacao.central_ml is None


# --- Restrições de exercício -------------------------------------------------


def test_versao_base_so_com_as_restricoes_gerais() -> None:
    r = _estrategia().restricoes
    assert r.sem_impacto  # para todos, no MVP (§6.3)
    assert not (r.sem_intervalos or r.sem_flexao_tronco_com_carga or r.regressao_geral)
    assert not r.equilibrio_com_apoio
    assert r.zonas_regressao == ()


@pytest.mark.parametrize(
    "alteracoes",
    [
        {},
        {"peso_kg": 104.0, "peso_alvo_kg": 98.0},
        {"condicoes": ["doenca_cardiovascular"]},
        {"condicoes": ["osteoporose"], "osteoporose_risco": "nao"},
        {"limitacoes": ["equilibrio"], "limitacoes_gravidade": {"equilibrio": "ligeira"}},
        {"idade": 30, "intensidade_pedida": "alta"},
    ],
)
def test_sem_impacto_para_todos(alteracoes: dict[str, Any]) -> None:
    assert _estrategia(**alteracoes).restricoes.sem_impacto


def test_prudente_sem_impacto_nem_intervalos() -> None:
    r = _estrategia(condicoes=["doenca_respiratoria"]).restricoes
    assert r.sem_impacto
    assert r.sem_intervalos


def test_osteoporose_sem_risco() -> None:
    e = _estrategia(condicoes=["osteoporose"], osteoporose_risco="nao")
    assert e.modo is Modo.BASE
    assert e.restricoes.sem_impacto
    assert e.restricoes.sem_flexao_tronco_com_carga
    assert not e.restricoes.sem_intervalos
    assert not e.restricoes.equilibrio_com_apoio


@pytest.mark.parametrize("risco", ["sim", "nao_sei"])
def test_osteoporose_com_risco(risco: str) -> None:
    r = _estrategia(condicoes=["osteoporose"], osteoporose_risco=risco).restricoes
    assert r.sem_flexao_tronco_com_carga
    assert r.equilibrio_com_apoio
    assert r.sem_intervalos


@pytest.mark.parametrize(
    ("gravidade", "modo"), [("ligeira", Modo.BASE), ("importante", Modo.PRUDENTE)]
)
def test_limitacao_equilibrio(gravidade: str, modo: Modo) -> None:
    e = _estrategia(limitacoes=["equilibrio"], limitacoes_gravidade={"equilibrio": gravidade})
    assert e.modo is modo
    assert e.restricoes.equilibrio_com_apoio
    assert e.restricoes.zonas_regressao == ()


def test_limitacoes_dao_zonas_de_regressao() -> None:
    e = _estrategia(
        limitacoes=["ombros", "joelhos"],
        limitacoes_gravidade={"ombros": "ligeira", "joelhos": "importante"},
    )
    assert e.restricoes.zonas_regressao == (Zona.JOELHOS, Zona.OMBROS)


def test_dor_articular_nas_zonas_indicadas() -> None:
    e = _estrategia(
        condicoes=["dor_articular_persistente"],
        dor_articular_zonas=["coluna", "ancas"],
        limitacoes=["ancas"],
        limitacoes_gravidade={"ancas": "ligeira"},
    )
    assert e.modo is Modo.PRUDENTE
    assert e.restricoes.zonas_regressao == (Zona.ANCAS, Zona.COLUNA)
    assert not e.restricoes.regressao_geral


def test_dor_articular_outra_da_regressao_geral() -> None:
    e = _estrategia(
        condicoes=["dor_articular_persistente"],
        dor_articular_zonas=["outra"],
        dor_articular_outra="pulsos",
    )
    assert e.restricoes.regressao_geral
    assert e.restricoes.zonas_regressao == ()


# --- Incoerências nos objetivos (decisão de 28/10/2026) ---------------------


def test_peso_alvo_com_imc_abaixo_de_18_5_fica_limitado() -> None:
    a = acolher(_questionario(peso_alvo_kg=50.0))  # 172 cm: mínimo 54,8 kg
    assert a.indicadores.peso_alvo_usado_kg == 54.8
    assert a.incoerencias == (
        textos.PESO_ALVO_IMC_BAIXO.format(peso_alvo="50", peso_minimo="54,8"),
    )
    e = gerar_estrategia(_questionario(peso_alvo_kg=50.0))
    assert e.marcos[-1].peso_indicativo_kg >= 54.8


def test_peso_alvo_no_limite_de_imc_18_5_nao_avisa() -> None:
    a = acolher(_questionario(peso_kg=60.0, peso_alvo_kg=54.8))
    assert a.incoerencias == ()
    assert a.indicadores.peso_alvo_usado_kg == 54.8


@pytest.mark.parametrize("peso_alvo", [70.0, 75.0])
def test_peso_alvo_sem_perda(peso_alvo: float) -> None:
    e = _estrategia(peso_alvo_kg=peso_alvo)
    assert textos.PESO_ALVO_SEM_PERDA in e.avisos
    assert all(m.peso_indicativo_kg == 70.0 for m in e.marcos)


@pytest.mark.parametrize("cintura_alvo", [88, 95])
def test_cintura_alvo_nao_inferior_a_atual(cintura_alvo: int) -> None:
    a = acolher(_questionario(cintura_alvo_cm=cintura_alvo))
    assert (
        textos.CINTURA_ALVO_NAO_REDUZ.format(cintura_alvo=cintura_alvo, cintura="88")
        in a.incoerencias
    )


def test_objetivos_coerentes_sem_avisos() -> None:
    assert acolher(_questionario(cintura_alvo_cm=85)).incoerencias == ()


# --- Marcos ------------------------------------------------------------------


def test_marcos_cintura_sem_numero_abaixo_do_limiar() -> None:
    e = _estrategia()
    assert [m.semana for m in e.marcos] == [4, 8, 12, 16]
    assert [m.fase for m in e.marcos] == list(textos.FASES)
    assert all(m.cintura == textos.CINTURA_MEDIR for m in e.marcos)


def test_marcos_cintura_com_limiar_feminino() -> None:
    e = _estrategia(sexo="feminino", cintura_cm=85)
    assert e.modulo_gordura_visceral
    assert e.marcos[0].cintura == textos.CINTURA_MEDIR_COM_LIMIAR.format(limiar=80)


# --- Persona de teste (resultado esperado no campo _nota) -------------------


def test_persona_resultado_esperado() -> None:
    e = gerar_estrategia(_persona())
    assert e.pode_gerar_plano
    assert e.modo is Modo.BASE  # hipertensão controlada; limitação ligeira nos joelhos
    assert e.intensidade_efetiva is Intensidade.MEDIA  # 5 dias × 30 min
    assert e.explicacao_intensidade is None
    assert not e.usar_frequencia_cardiaca  # medicação «não sei»
    assert textos.ESFORCO_PERCEBIDO in e.avisos
    assert e.modulo_gordura_visceral
    assert textos.VISCERAL_INDICADOR in e.avisos

    ind = e.indicadores
    assert ind is not None
    assert not ind.perda_peso.realista
    assert ind.perda_peso.alvo_semana_16_kg == 88.0
    assert ind.perda_peso.semana_objetivo == 24
    assert any(a.startswith("Chegar aos 85 kg em 16 semanas") for a in e.avisos)

    assert e.restricoes.zonas_regressao == (Zona.JOELHOS,)
    assert e.restricoes.sem_impacto
    assert not e.restricoes.equilibrio_com_apoio
    assert not e.restricoes.sem_intervalos
    assert [m.peso_indicativo_kg for m in e.marcos] == [92.5, 91.0, 89.5, 88.0]


# --- CLI ---------------------------------------------------------------------


def test_cli_so_estrategia(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--so-estrategia", str(PERSONA)]) == 0
    saida = capsys.readouterr().out
    assert "Pedida: Média | Efetiva: Média" in saida
    assert "Regressão nas zonas: joelhos" in saida
    assert "Sem impacto: sim" in saida
    assert "Equilíbrio com apoio: não" in saida


def test_cli_limitacao_equilibrio(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dados = json.loads(PERSONA.read_text(encoding="utf-8"))
    dados.update(limitacoes=["equilibrio"], limitacoes_gravidade={"equilibrio": "ligeira"})
    ficheiro = tmp_path / "equilibrio.json"
    ficheiro.write_text(json.dumps(dados), encoding="utf-8")
    assert cli.main(["--so-estrategia", str(ficheiro)]) == 0
    saida = capsys.readouterr().out
    assert "Equilíbrio com apoio: sim" in saida
    assert "Sem impacto: sim" in saida
    assert "sem essa indicação" in saida
    assert "Semana 16 (Integração): peso indicativo 88 kg" in saida


def test_cli_sem_so_estrategia_nao_gera_plano(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([str(PERSONA)]) == 2
    assert "--so-estrategia" in capsys.readouterr().out


def test_cli_ficheiro_inexistente(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert cli.main(["--so-estrategia", str(tmp_path / "nao_existe.json")]) == 1


def test_cli_questionario_invalido(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    ficheiro = tmp_path / "q.json"
    ficheiro.write_text('{"idade": 10}', encoding="utf-8")
    assert cli.main(["--so-estrategia", str(ficheiro)]) == 1
    assert "Questionário inválido" in capsys.readouterr().out
