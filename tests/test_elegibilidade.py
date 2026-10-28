"""Testes da elegibilidade (REGRAS_DOMINIO §1 e tabela 1.1)."""

import json
from pathlib import Path
from typing import Any

import pytest

from vigoria.modelos.questionario import Condicao, Intensidade, Limitacao, Questionario
from vigoria.regras import textos
from vigoria.regras.elegibilidade import Modo, avaliar_elegibilidade

PERSONA = Path(__file__).parent.parent / "exemplos" / "persona_teste.json"

# Altura 172 cm e 70 kg: IMC 23,7, longe dos limiares.
NEUTRO = {
    "peso_kg": 70.0,
    "peso_alvo_kg": 68.0,
    "condicoes": ["nenhuma"],
    "condicoes_controladas": {},
    "limitacoes": ["nenhuma"],
    "limitacoes_gravidade": {},
    "medicacao_afeta_fc": "nao",
}


def _questionario(**alteracoes: Any) -> Questionario:
    dados = json.loads(PERSONA.read_text(encoding="utf-8"))
    dados.update(NEUTRO)
    dados.update(alteracoes)
    return Questionario.model_validate(dados)


def test_neutro_e_base() -> None:
    e = avaliar_elegibilidade(_questionario())
    assert e.modo is Modo.BASE
    assert e.motivos == ()
    assert e.intensidade_maxima is None
    assert e.usar_frequencia_cardiaca


def test_persona_e_base_sem_frequencia_cardiaca() -> None:
    q = Questionario.model_validate(json.loads(PERSONA.read_text(encoding="utf-8")))
    e = avaliar_elegibilidade(q)
    assert e.modo is Modo.BASE
    assert not e.usar_frequencia_cardiaca


# --- Idade e gravidez --------------------------------------------------------


def test_idade_17_nao_elegivel() -> None:
    # O modelo recusa idades < 18; model_copy cria a cópia sem validar.
    q = _questionario().model_copy(update={"idade": 17})
    e = avaliar_elegibilidade(q)
    assert e.modo is Modo.NAO_ELEGIVEL
    assert e.motivos == (textos.MENOR_IDADE,)


@pytest.mark.parametrize("idade", [18, 44, 45, 60, 61])
def test_idades_adultas_elegiveis(idade: int) -> None:
    assert avaliar_elegibilidade(_questionario(idade=idade)).modo is Modo.BASE


def test_gravidez_nao_elegivel_mesmo_com_imc_35() -> None:
    e = avaliar_elegibilidade(
        _questionario(condicoes=["gravidez"], sexo="feminino", peso_kg=110.0, altura_cm=170)
    )
    assert e.modo is Modo.NAO_ELEGIVEL
    assert e.motivos == (textos.GRAVIDEZ,)
    assert e.intensidade_maxima is None


# --- IMC ---------------------------------------------------------------------


def test_imc_34_9_base() -> None:
    e = avaliar_elegibilidade(_questionario(peso_kg=100.86, altura_cm=170))
    assert e.modo is Modo.BASE


def test_imc_35_0_prudente_com_teto_ligeira() -> None:
    e = avaliar_elegibilidade(_questionario(peso_kg=101.15, altura_cm=170))
    assert e.modo is Modo.PRUDENTE
    assert e.intensidade_maxima is Intensidade.LIGEIRA
    assert e.motivos == ("IMC de 35,0 (igual ou superior a 35).",)


def test_imc_35_com_condicao_prudente_fica_ligeira() -> None:
    e = avaliar_elegibilidade(
        _questionario(peso_kg=101.15, altura_cm=170, condicoes=["doenca_cardiovascular"])
    )
    assert e.intensidade_maxima is Intensidade.LIGEIRA
    assert textos.DOENCA_CARDIOVASCULAR in e.motivos


# --- Tabela 1.1: condições (uma linha de teste por linha da tabela) ----------

LINHAS_CONDICOES = [
    # (condição, alterações ao questionário, modo esperado, motivo esperado)
    ("hipertensao", {"condicoes_controladas": {"hipertensao": True}}, Modo.BASE, None),
    (
        "hipertensao",
        {"condicoes_controladas": {"hipertensao": False}},
        Modo.PRUDENTE,
        textos.HIPERTENSAO_NAO_CONTROLADA,
    ),
    (
        "diabetes",
        {"condicoes_controladas": {"diabetes": True}},
        Modo.PRUDENTE,
        textos.DIABETES_CONTROLADA,
    ),
    (
        "diabetes",
        {"condicoes_controladas": {"diabetes": False}},
        Modo.PRUDENTE,
        textos.DIABETES_NAO_CONTROLADA,
    ),
    ("doenca_cardiovascular", {}, Modo.PRUDENTE, textos.DOENCA_CARDIOVASCULAR),
    ("doenca_respiratoria", {}, Modo.PRUDENTE, textos.DOENCA_RESPIRATORIA),
    ("doenca_renal", {}, Modo.PRUDENTE, textos.DOENCA_RENAL),
    ("osteoporose", {"osteoporose_risco": "sim"}, Modo.PRUDENTE, textos.OSTEOPOROSE_COM_RISCO),
    (
        "osteoporose",
        {"osteoporose_risco": "nao_sei"},
        Modo.PRUDENTE,
        textos.OSTEOPOROSE_RISCO_DESCONHECIDO,
    ),
    ("osteoporose", {"osteoporose_risco": "nao"}, Modo.BASE, None),
    (
        "doenca_inflamatoria_intestinal",
        {"condicoes_controladas": {"doenca_inflamatoria_intestinal": True}},
        Modo.BASE,
        None,
    ),
    (
        "doenca_inflamatoria_intestinal",
        {"condicoes_controladas": {"doenca_inflamatoria_intestinal": False}},
        Modo.PRUDENTE,
        textos.DII_NAO_CONTROLADA,
    ),
    ("dor_articular_persistente", {}, Modo.PRUDENTE, textos.DOR_ARTICULAR_PERSISTENTE),
    ("protese_ou_cirurgia_recente", {}, Modo.PRUDENTE, textos.PROTESE_OU_CIRURGIA_RECENTE),
    ("gravidez", {}, Modo.NAO_ELEGIVEL, textos.GRAVIDEZ),
    ("outra", {"condicoes_outras": "texto qualquer"}, Modo.PRUDENTE, textos.CONDICAO_OUTRA),
    ("nenhuma", {}, Modo.BASE, None),
]


@pytest.mark.parametrize(("condicao", "alteracoes", "modo", "motivo"), LINHAS_CONDICOES)
def test_tabela_1_1_condicoes(
    condicao: str, alteracoes: dict[str, Any], modo: Modo, motivo: str | None
) -> None:
    e = avaliar_elegibilidade(_questionario(condicoes=[condicao], **alteracoes))
    assert e.modo is modo
    assert e.motivos == ((motivo,) if motivo else ())
    teto = {Modo.PRUDENTE: Intensidade.MEDIA}.get(modo)
    assert e.intensidade_maxima is teto


def test_todas_as_condicoes_tem_linha_de_teste() -> None:
    assert {Condicao(linha[0]) for linha in LINHAS_CONDICOES} == set(Condicao)


def test_outra_condicao_prudente_seja_qual_for_o_texto() -> None:
    for texto in ("nada de especial", "está tudo bem", "x"):
        e = avaliar_elegibilidade(_questionario(condicoes=["outra"], condicoes_outras=texto))
        assert e.modo is Modo.PRUDENTE


def test_varias_condicoes_juntam_motivos() -> None:
    e = avaliar_elegibilidade(
        _questionario(
            condicoes=["hipertensao", "doenca_respiratoria", "doenca_renal"],
            condicoes_controladas={"hipertensao": True},
        )
    )
    assert e.modo is Modo.PRUDENTE
    assert e.motivos == (textos.DOENCA_RESPIRATORIA, textos.DOENCA_RENAL)


# --- Tabela 1.1: limitações --------------------------------------------------

ZONAS = ["joelhos", "ancas", "ombros", "coluna", "equilibrio"]


@pytest.mark.parametrize("zona", ZONAS)
def test_limitacao_ligeira_base(zona: str) -> None:
    e = avaliar_elegibilidade(
        _questionario(limitacoes=[zona], limitacoes_gravidade={zona: "ligeira"})
    )
    assert e.modo is Modo.BASE


@pytest.mark.parametrize("zona", ZONAS)
def test_limitacao_importante_prudente(zona: str) -> None:
    e = avaliar_elegibilidade(
        _questionario(limitacoes=[zona], limitacoes_gravidade={zona: "importante"})
    )
    assert e.modo is Modo.PRUDENTE
    assert e.intensidade_maxima is Intensidade.MEDIA
    zona_texto = textos.ZONAS_LIMITACAO[Limitacao(zona)]
    assert e.motivos == (textos.LIMITACAO_IMPORTANTE.format(zona=zona_texto),)


@pytest.mark.parametrize("gravidade", ["ligeira", "importante"])
def test_outra_limitacao_sempre_prudente(gravidade: str) -> None:
    e = avaliar_elegibilidade(
        _questionario(
            limitacoes=["outra"],
            limitacoes_gravidade={"outra": gravidade},
            limitacoes_outra="texto qualquer",
        )
    )
    assert e.modo is Modo.PRUDENTE
    assert e.motivos == (textos.LIMITACAO_OUTRA,)


def test_todas_as_limitacoes_tem_teste() -> None:
    testadas = {*ZONAS, "outra", "nenhuma"}
    assert {Limitacao(z) for z in testadas} == set(Limitacao)


# --- Medicação que altera a resposta cardíaca --------------------------------


@pytest.mark.parametrize(
    ("resposta", "usar_fc"), [("sim", False), ("nao_sei", False), ("nao", True)]
)
def test_medicacao_nao_sei_equivale_a_sim(resposta: str, usar_fc: bool) -> None:
    e = avaliar_elegibilidade(_questionario(medicacao_afeta_fc=resposta))
    assert e.usar_frequencia_cardiaca is usar_fc
    assert e.modo is Modo.BASE  # a medicação, só por si, não muda o modo
