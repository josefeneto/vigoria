"""Passos do questionário: campos, validação de cada passo e montagem do Questionario."""

from pathlib import Path
from typing import Any

import pytest

from vigoria.interface.estado import (
    INTEIROS,
    ZERO_E_VAZIO,
    chave,
    estado_inicial,
    para_estado,
    para_respostas,
)
from vigoria.interface.passos import (
    CALCULADOS,
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
from vigoria.motor.semana import DIAS_FIXOS, sessoes

RAIZ = Path(__file__).resolve().parents[1]
PERSONAS = sorted(p.name for p in (RAIZ / "exemplos").glob("persona_*.json"))


def _q_antigo(ficheiro: str = "persona_teste.json") -> Questionario:
    """Como nos ficheiros: só com `dias_semana` (questionário anterior a 18/11/2026)."""
    return Questionario.model_validate_json((RAIZ / "exemplos" / ficheiro).read_text("utf-8"))


def _q(ficheiro: str = "persona_teste.json") -> Questionario:
    """Com os dias de treino escolhidos (os da semana fixa), como os da interface."""
    q = _q_antigo(ficheiro)
    dias = [d.value for d in DIAS_FIXOS[q.dias_semana]]
    return Questionario.model_validate(q.model_dump(mode="json") | {"dias_treino": dias})


def _r(**alteracoes: Any) -> dict[str, Any]:
    return respostas_de_questionario(_q()) | alteracoes


def _codigos(passo: str, respostas: dict[str, Any]) -> list[tuple[str, str]]:
    return [(e.campo, e.codigo.value) for e in validar_passo(passo, respostas)]


def test_passos_cobrem_todos_os_campos_uma_vez() -> None:
    assert PASSOS == ("0", "1", "2a", "2b", "3", "4a", "4b", "5", "6", "7")
    todos = [c for p in PASSOS for c in CAMPOS[p]]
    assert sorted(todos) == sorted(set(Questionario.model_fields) - CALCULADOS)


@pytest.mark.parametrize("ficheiro", PERSONAS)
def test_personas_passam_em_todos_os_passos_e_voltam_iguais(ficheiro: str) -> None:
    q = _q(ficheiro)
    respostas = respostas_de_questionario(q)
    for passo in PASSOS:
        assert validar_passo(passo, respostas) == [], passo
    assert montar_questionario(respostas) == q


@pytest.mark.parametrize("ficheiro", PERSONAS)
def test_questionario_antigo_volta_com_os_dias_da_semana_fixa(ficheiro: str) -> None:
    antigo = _q_antigo(ficheiro)
    assert antigo.dias_treino == []
    respostas = respostas_de_questionario(antigo)
    assert respostas["dias_treino"] == [d.value for d in DIAS_FIXOS[antigo.dias_semana]]
    novo = montar_questionario(respostas)
    assert novo.dias_semana == antigo.dias_semana
    assert sessoes(novo) == sessoes(antigo)


def test_dias_de_treino_obrigatorios() -> None:
    assert ("dias_treino", "obrigatorio") in _codigos("3", _r(dias_treino=[]))
    assert _codigos("3", _r(dias_treino=["sabado", "domingo"])) == []


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


# ---------------------------------------------------------------- Chaves dos widgets


@pytest.mark.parametrize("ficheiro", PERSONAS)
def test_estado_dos_widgets_ida_e_volta(ficheiro: str) -> None:
    q = _q(ficheiro)
    volta = montar_questionario(para_respostas(para_estado(respostas_de_questionario(q))))
    # Os campos pedidos em inteiros voltam arredondados (6,5 h de sono → 7); o resto igual.
    inteiros = {c: int(v + 0.5) for c in INTEIROS if isinstance(v := getattr(q, c, None), float)}
    assert volta == q.model_copy(update=inteiros)


def test_caixas_comecam_vazias_e_zero_e_sem_resposta() -> None:
    """Desde 19/11/2026 as caixas de número começam vazias (antes começavam em 0)."""
    estado = estado_inicial()
    assert all(estado[chave(c)] is None for c in ZERO_E_VAZIO)
    assert estado[chave("vinho_copos_dia")] is None and estado[chave("doces_por_semana")] is None
    r = para_respostas(estado)
    assert r["peso_kg"] is None and r["cintura_alvo_cm"] is None
    assert {e.campo for e in validar_passo("1", r)} >= {"idade", "altura_cm", "peso_kg"}
    # 0 escrito à mão continua a ser «sem resposta» nestes campos.
    estado[chave("idade")] = 0
    assert para_respostas(estado)["idade"] is None
    estado[chave("objetivo_muscular_tipo")] = "kg"
    assert para_respostas(estado)["objetivo_muscular"] is None
    estado[chave("objetivo_muscular_kg")] = 2
    assert para_respostas(estado)["objetivo_muscular"] == 2
    assert para_estado(_r(halteres_kg=None))[chave("halteres_kg")] is None


@pytest.mark.parametrize(
    ("campo", "antigo", "botao"),
    [
        ("vinho_copos_dia", 0, 0),
        ("vinho_copos_dia", 4, 4),
        ("vinho_copos_dia", 10, 4),
        ("doces_por_semana", 7, 7),
        ("doces_por_semana", 14, 7),
    ],
)
def test_vinho_e_doces_antigos_no_ultimo_botao(campo: str, antigo: int, botao: int) -> None:
    estado = para_estado(_r(**{campo: antigo}))
    assert estado[chave(campo)] == botao
    assert para_respostas(estado)[campo] == botao


def test_botoes_do_vinho_e_dos_doces() -> None:
    from paginas import textos as t
    from vigoria.interface.estado import ULTIMA_OPCAO

    assert list(t.VINHO) == list(range(ULTIMA_OPCAO["vinho_copos_dia"] + 1))
    assert list(t.DOCES) == list(range(ULTIMA_OPCAO["doces_por_semana"] + 1))
    assert t.VINHO[0] == t.DOCES[0] == "Nenhum"
    assert t.VINHO[4] == "4 ou mais" and t.DOCES[7] == "7 ou mais"


def test_campos_inteiros_arredondam_a_meia_unidade_para_cima() -> None:
    estado = para_estado(_r(peso_kg=94.4, sono_horas=6.5, cintura_cm=113.2))
    assert [estado[chave(c)] for c in ("peso_kg", "sono_horas", "cintura_cm")] == [94, 7, 113]
    assert all(type(estado[chave(c)]) is int for c in ("peso_kg", "sono_horas", "cintura_cm"))
    assert para_estado(_r(espirituosas_dl_dia=0.5))[chave("espirituosas_dl_dia")] == 0.5


def test_estado_inicial_vazio_com_acompanhamento_por_omissao() -> None:
    r = para_respostas(estado_inicial())
    assert r["condicoes"] == [] and r["peso_kg"] is None
    assert (r["acompanhamento_ativo"], r["frequencia_registo"], r["lembretes_email"]) == (
        True,
        "semanal",
        True,
    )
    assert "objetivo_muscular" not in r
    assert validar_passo("6", r) == []


def test_objetivo_muscular_em_kg_e_controlo_sim_nao() -> None:
    estado = para_estado(_r(objetivo_muscular=1.5))
    assert estado[chave("objetivo_muscular_tipo")] == "kg"
    assert para_respostas(estado)["objetivo_muscular"] == 2  # pedido em kg inteiros
    assert estado[chave("condicoes_controladas", "hipertensao")] == "sim"
    estado[chave("condicoes_controladas", "hipertensao")] = "nao"
    assert para_respostas(estado)["condicoes_controladas"] == {"hipertensao": False}


@pytest.mark.parametrize(
    ("antes", "agora", "fica"),
    [
        ([], ["nenhum"], ["nenhum"]),
        (["halteres", "step"], ["nenhum", "halteres", "step"], ["nenhum"]),
        (["nenhum"], ["nenhum", "halteres"], ["halteres"]),
        (["halteres"], ["halteres", "step"], ["halteres", "step"]),
        (["halteres"], [], []),
    ],
)
def test_nenhum_exclui_as_outras_escolhas(
    antes: list[str], agora: list[str], fica: list[str]
) -> None:
    from vigoria.interface.passos import escolha_sem_conflito

    assert escolha_sem_conflito("equipamento", antes, agora) == fica


def test_nenhum_so_nas_escolhas_que_o_tem() -> None:
    from vigoria.interface.passos import NENHUMA, escolha_sem_conflito

    assert set(NENHUMA) == {"condicoes", "limitacoes", "equipamento"}
    assert escolha_sem_conflito("condicoes", ["diabetes"], ["diabetes", "nenhuma"]) == ["nenhuma"]
    assert escolha_sem_conflito("preferencias", [], ["caminhada", "danca"]) == [
        "caminhada",
        "danca",
    ]


def test_outro_antigo_deixa_de_vir_marcado() -> None:
    """Questionários antigos com «outro» continuam válidos, mas a opção já não aparece."""
    from paginas import textos as t
    from vigoria.interface.estado import RETIRADAS

    estado = para_estado(_r(equipamento=["halteres", "outro"], preferencias=["outro", "danca"]))
    assert estado[chave("equipamento")] == ["halteres"]
    assert estado[chave("preferencias")] == ["danca"]
    assert all(not (RETIRADAS[c] & set(t.OPCOES[c])) for c in RETIRADAS)
    q = _q()
    assert q.model_validate(q.model_dump() | {"preferencias": ["outro"]}).preferencias
