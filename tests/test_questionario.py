"""Testes do modelo Questionario."""

import json
import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from vigoria.modelos.questionario import Condicao, Questionario

PERSONA = Path(__file__).parent.parent / "exemplos" / "persona_teste.json"


@pytest.fixture
def dados() -> dict[str, Any]:
    """Dados da persona fictícia, prontos a alterar em cada teste."""
    return json.loads(PERSONA.read_text(encoding="utf-8"))


def test_persona_e_valida(dados: dict[str, Any]) -> None:
    q = Questionario.model_validate(dados)
    assert q.idade == 68
    assert q.condicoes == [Condicao.HIPERTENSAO]
    assert q.halteres_kg == 2
    assert q.refeicoes.ceia == ""


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("idade", 18),
        ("idade", 100),
        ("altura_cm", 120),
        ("peso_kg", 250),
        ("sono_horas", 3),
        ("sono_horas", 12),
        ("objetivo_muscular", 2),
        ("objetivo_muscular", 0.5),
        ("cintura_alvo_cm", None),
    ],
)
def test_valores_nos_limites_sao_aceites(dados: dict[str, Any], campo: str, valor: Any) -> None:
    dados[campo] = valor
    Questionario.model_validate(dados)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("aceita_termos", False),
        ("consentimento_saude", False),
        ("confirma_maior_idade", False),
        ("idade", 17),
        ("idade", 101),
        ("altura_cm", 119),
        ("altura_cm", 221),
        ("peso_kg", 34.9),
        ("sono_horas", 6.3),
        ("sono_horas", 12.5),
        ("cintura_cm", 49),
        ("dias_semana", 0),
        ("dias_semana", 8),
        ("minutos_dia", 25),
        ("vinho_copos_dia", 11),
        ("espirituosas_dl_dia", 5.1),
        ("doces_por_semana", 15),
        ("objetivo_muscular", 2.5),
        ("objetivo_muscular", 0),
        ("objetivo_muscular", "ganhar_muito"),
        ("sexo", "outro"),
        ("agua_litros", "3"),
        ("medicacao_notas", "x" * 201),
        ("refeicoes", {"almoco": "x" * 151}),
        ("refeicoes", {"brunch": "ovos"}),
        ("campo_desconhecido", 1),
    ],
)
def test_valores_invalidos_sao_rejeitados(dados: dict[str, Any], campo: str, valor: Any) -> None:
    dados[campo] = valor
    with pytest.raises(ValidationError):
        Questionario.model_validate(dados)


@pytest.mark.parametrize(
    "alteracoes",
    [
        # «nenhuma» combinada com outra escolha
        {"condicoes": ["nenhuma", "hipertensao"]},
        {"limitacoes": ["nenhuma", "joelhos"], "limitacoes_gravidade": {"joelhos": "ligeira"}},
        {"equipamento": ["nenhum", "step"], "halteres_kg": None},
        # condições controladas em falta ou a mais
        {"condicoes_controladas": {}},
        {"condicoes_controladas": {"hipertensao": True, "diabetes": True}},
        # osteoporose sem a pergunta de risco
        {"condicoes": ["osteoporose"], "condicoes_controladas": {}},
        # «outra» sem texto, ou texto sem «outra»
        {"condicoes": ["outra"], "condicoes_controladas": {}},
        {"condicoes_outras": "asma ligeira"},
        {"limitacoes": ["outra"], "limitacoes_gravidade": {"outra": "ligeira"}},
        # dor articular sem zonas, zonas sem dor articular, «outra» zona sem texto
        {"condicoes": ["dor_articular_persistente"], "condicoes_controladas": {}},
        {"dor_articular_zonas": ["joelhos"]},
        {
            "condicoes": ["dor_articular_persistente"],
            "condicoes_controladas": {},
            "dor_articular_zonas": ["outra"],
        },
        {"dor_articular_outra": "pulsos"},
        {"restricoes_alimentares": ["outra"]},
        # gravidade em falta
        {"limitacoes_gravidade": {}},
        # halteres sem peso, ou peso sem halteres
        {"halteres_kg": None},
        {"equipamento": ["cadeira_firme"]},
    ],
)
def test_incoerencias_sao_rejeitadas(dados: dict[str, Any], alteracoes: dict[str, Any]) -> None:
    dados.update(alteracoes)
    with pytest.raises(ValidationError):
        Questionario.model_validate(dados)


def test_sem_condicoes_nem_limitacoes(dados: dict[str, Any]) -> None:
    dados.update(
        condicoes=["nenhuma"],
        condicoes_controladas={},
        limitacoes=["nenhuma"],
        limitacoes_gravidade={},
    )
    Questionario.model_validate(dados)


def test_dor_articular_com_zonas(dados: dict[str, Any]) -> None:
    dados.update(
        condicoes=["dor_articular_persistente"],
        condicoes_controladas={},
        dor_articular_zonas=["ombros", "outra"],
        dor_articular_outra="pulsos",
    )
    Questionario.model_validate(dados)


def test_gravidez_e_aceite_pelo_modelo(dados: dict[str, Any]) -> None:
    """O modelo aceita; é a estratégia (Fase 2) que impede a geração do plano."""
    dados.update(condicoes=["gravidez"], condicoes_controladas={})
    Questionario.model_validate(dados)


@pytest.mark.llm
def test_marcador_llm_so_corre_com_variavel() -> None:
    """Saltado por omissão pelo conftest.py; só corre com VIGORIA_TESTES_LLM_REAIS=1."""
    assert os.environ.get("VIGORIA_TESTES_LLM_REAIS") == "1"
