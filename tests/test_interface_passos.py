"""Passos do questionário: campos, validação de cada passo e montagem do Questionario."""

from pathlib import Path
from typing import Any

import pytest

from vigoria.interface.passos import (
    CAMPOS,
    PASSOS,
    CodigoErro,
    ErroCampo,
    limpar_condicionais,
    montar_questionario,
    respostas_de_questionario,
    tem_gravidez,
    textos_refeicoes,
    validar_passo,
)
from vigoria.modelos.questionario import REFEICAO_SEM_DESCRICAO, Questionario

RAIZ = Path(__file__).resolve().parents[1]
PERSONAS = sorted(p.name for p in (RAIZ / "exemplos").glob("persona_*.json"))


def _q(ficheiro: str = "persona_teste.json") -> Questionario:
    return Questionario.model_validate_json((RAIZ / "exemplos" / ficheiro).read_text("utf-8"))


def _r(**alteracoes: Any) -> dict[str, Any]:
    return respostas_de_questionario(_q()) | alteracoes


def _codigos(passo: str, respostas: dict[str, Any]) -> list[tuple[str, str]]:
    return [(e.campo, e.codigo.value) for e in validar_passo(passo, respostas)]


def test_passos_cobrem_todos_os_campos_uma_vez() -> None:
    assert PASSOS == ("0", "1", "2a", "2b", "3", "4a", "4b", "5", "6", "7")
    todos = [c for p in PASSOS for c in CAMPOS[p]]
    assert sorted(todos) == sorted(Questionario.model_fields)


@pytest.mark.parametrize("ficheiro", PERSONAS)
def test_personas_passam_em_todos_os_passos_e_voltam_iguais(ficheiro: str) -> None:
    q = _q(ficheiro)
    respostas = respostas_de_questionario(q)
    for passo in PASSOS:
        assert validar_passo(passo, respostas) == [], passo
    assert montar_questionario(respostas) == q


# ---------------------------------------------------------------- Obrigatórios e limites


def test_passo_0_exige_as_tres_caixas() -> None:
    assert _codigos("0", {"aceita_termos": True, "consentimento_saude": False}) == [
        ("consentimento_saude", "obrigatorio"),
        ("confirma_maior_idade", "obrigatorio"),
    ]


def test_passo_1_vazio_pede_todos_os_campos() -> None:
    assert {c for c, _ in _codigos("1", {})} == set(CAMPOS["1"])


@pytest.mark.parametrize(
    ("campo", "valor", "minimo", "maximo"),
    [
        ("idade", 17, 18, 100),
        ("idade", 101, 18, 100),
        ("altura_cm", 119, 120, 220),
        ("peso_kg", 250.1, 35, 250),
        ("cintura_cm", 49.9, 50, 200),
    ],
)
def test_passo_1_fora_dos_limites(campo: str, valor: float, minimo: float, maximo: float) -> None:
    assert validar_passo("1", _r(**{campo: valor})) == [
        ErroCampo(campo=campo, codigo=CodigoErro.INTERVALO, minimo=minimo, maximo=maximo)
    ]


@pytest.mark.parametrize("valor", [18, 100])
def test_idade_nos_limites_e_aceite(valor: int) -> None:
    assert validar_passo("1", _r(idade=valor)) == []


def test_sono_de_meia_em_meia_hora() -> None:
    assert _codigos("1", _r(sono_horas=6.3)) == [("sono_horas", "multiplo")]


def test_vinho_zero_e_aceite_e_negativo_nao() -> None:
    assert validar_passo("4b", _r(vinho_copos_dia=0)) == []
    assert validar_passo("4b", _r(vinho_copos_dia=-1)) == [
        ErroCampo(campo="vinho_copos_dia", codigo=CodigoErro.INTERVALO, minimo=0, maximo=10)
    ]


def test_objetivo_muscular_acima_de_2_kg() -> None:
    assert validar_passo("5", _r(objetivo_muscular=2.5)) == [
        # Só o limite que falhou: o campo também aceita «aumentar força e tónus».
        ErroCampo(campo="objetivo_muscular", codigo=CodigoErro.INTERVALO, maximo=2)
    ]
    assert validar_passo("5", _r(objetivo_muscular=2)) == []


def test_texto_livre_demasiado_longo() -> None:
    respostas = _r(condicoes=["outra"], condicoes_outras="x" * 201)
    assert validar_passo("2a", respostas) == [
        ErroCampo(campo="condicoes_outras", codigo=CodigoErro.DEMASIADO_LONGO, maximo=200)
    ]


def test_cintura_alvo_e_opcional() -> None:
    assert validar_passo("5", _r(cintura_alvo_cm=None)) == []


# ---------------------------------------------------------------- Condicionais


def test_nenhuma_nao_se_combina() -> None:
    assert _codigos("2a", _r(condicoes=["nenhuma", "diabetes"])) == [
        ("condicoes", "nenhuma_exclusiva"),
        ("condicoes_controladas.diabetes", "obrigatorio"),
    ]
    assert _codigos("3", _r(equipamento=["nenhum", "step"])) == [
        ("equipamento", "nenhuma_exclusiva")
    ]


def test_articulacoes_so_com_dor_articular() -> None:
    sem_zonas = _r(condicoes=["dor_articular_persistente"])
    assert _codigos("2a", sem_zonas) == [("dor_articular_zonas", "obrigatorio")]
    com_outra = sem_zonas | {"dor_articular_zonas": ["outra"]}
    assert _codigos("2a", com_outra) == [("dor_articular_outra", "obrigatorio")]
    assert validar_passo("2a", com_outra | {"dor_articular_outra": "pulsos"}) == []


def test_osteoporose_pede_o_risco() -> None:
    assert _codigos("2a", _r(condicoes=["osteoporose"])) == [("osteoporose_risco", "obrigatorio")]


def test_controlo_por_condicao() -> None:
    respostas = _r(condicoes=["hipertensao", "diabetes"], condicoes_controladas={"diabetes": False})
    assert _codigos("2a", respostas) == [("condicoes_controladas.hipertensao", "obrigatorio")]


def test_gravidade_de_cada_limitacao() -> None:
    respostas = _r(limitacoes=["joelhos", "ombros", "outra"], limitacoes_outra="pulso")
    assert _codigos("2b", respostas) == [
        ("limitacoes_gravidade.ombros", "obrigatorio"),
        ("limitacoes_gravidade.outra", "obrigatorio"),  # «outra» também tem gravidade
    ]
    assert validar_passo("2b", _r(limitacoes=["nenhuma"], limitacoes_gravidade={})) == []


def test_halteres_pedem_o_peso() -> None:
    assert _codigos("3", _r(halteres_kg=None)) == [("halteres_kg", "obrigatorio")]
    assert validar_passo("3", _r(equipamento=["cadeira_firme"], halteres_kg=None)) == []


def test_limpar_apaga_o_que_deixou_de_se_aplicar() -> None:
    respostas = _r(
        condicoes=["nenhuma"],
        condicoes_controladas={"hipertensao": True},
        dor_articular_zonas=["outra"],
        dor_articular_outra="pulsos",
        limitacoes=["nenhuma"],
        equipamento=["cadeira_firme"],
    )
    limpas = limpar_condicionais(respostas)
    assert limpas["condicoes_controladas"] == {}
    assert "dor_articular_zonas" not in limpas and "dor_articular_outra" not in limpas
    assert limpas["limitacoes_gravidade"] == {}
    assert "halteres_kg" not in limpas
    q = montar_questionario(respostas)
    assert q.condicoes == ["nenhuma"] and q.halteres_kg is None


def test_gravidez() -> None:
    assert tem_gravidez(_r(condicoes=["gravidez"]))
    assert not tem_gravidez(_r())
    assert not tem_gravidez({})


# ---------------------------------------------------------------- Refeições


def test_refeicao_feita_sem_descricao() -> None:
    respostas = _r(
        refeicoes_faz={"pequeno_almoco": True, "almoco": True, "ceia": False},
        refeicoes={"pequeno_almoco": "  ", "almoco": "sopa", "ceia": "chá"},
    )
    assert textos_refeicoes(respostas) == {
        "pequeno_almoco": REFEICAO_SEM_DESCRICAO,
        "almoco": "sopa",
        "lanche": "",
        "jantar": "",
        "ceia": "",  # desmarcada: o texto que lá ficou não segue
    }
    q = montar_questionario(respostas)
    assert q.refeicoes.pequeno_almoco == REFEICAO_SEM_DESCRICAO
    assert respostas_de_questionario(q)["refeicoes"]["pequeno_almoco"] == ""


def test_refeicao_demasiado_longa() -> None:
    respostas = _r(refeicoes={"almoco": "x" * 151}, refeicoes_faz={"almoco": True})
    assert validar_passo("4a", respostas) == [
        ErroCampo(campo="refeicoes.almoco", codigo=CodigoErro.DEMASIADO_LONGO, maximo=150)
    ]
