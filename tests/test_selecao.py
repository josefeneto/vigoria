"""Seleção dos exercícios permitidos por fase (motor/selecao.py, REGRAS_DOMINIO §6)."""

import json
from pathlib import Path

import pytest

from vigoria.conteudo.carregar import Exercicio, Grupo, Impacto, Nivel, carregar_exercicios
from vigoria.modelos.estrategia import Estrategia, Restricoes, Zona
from vigoria.modelos.questionario import Equipamento, Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.selecao import ExercicioPermitido, selecionar_exercicios
from vigoria.regras import textos

EXEMPLOS = Path(__file__).parent.parent / "exemplos"
BIBLIOTECA = carregar_exercicios()
FASES = (1, 2, 3, 4)


def _estrategia(ficheiro: str) -> Estrategia:
    dados = json.loads((EXEMPLOS / ficheiro).read_text(encoding="utf-8"))
    return gerar_estrategia(Questionario.model_validate(dados))


def _com(restricoes: Restricoes) -> Estrategia:
    """Estratégia da persona de teste com outras restrições."""
    return _estrategia("persona_teste.json").model_copy(update={"restricoes": restricoes})


def _ids(lista: tuple[ExercicioPermitido, ...]) -> list[str]:
    return [e.id for e in lista]


def _por_id(lista: tuple[ExercicioPermitido, ...]) -> dict[str, ExercicioPermitido]:
    return {e.id: e for e in lista}


TODO_O_EQUIPAMENTO = (Equipamento.HALTERES, Equipamento.PASSADEIRA, Equipamento.ELIPTICA)


# ---------------------------------------------------------------- Regras gerais


@pytest.mark.parametrize(
    "ficheiro",
    ["persona_teste.json", "persona_renal.json", "persona_imc36.json", "persona_osteoporose.json"],
)
@pytest.mark.parametrize("fase", FASES)
def test_so_base_baixo_impacto_e_fase_permitida(ficheiro: str, fase: int) -> None:
    lista = selecionar_exercicios(_estrategia(ficheiro), fase)
    assert lista
    assert len(_ids(lista)) == len(set(_ids(lista)))  # sem repetições
    for permitido in lista:
        ex = BIBLIOTECA[permitido.id]
        assert ex.nivel is Nivel.BASE
        assert ex.impacto is Impacto.BAIXO
        assert permitido.grupo is ex.grupo
        # Os originais respeitam a fase; uma regressão pode vir de uma fase posterior.
        originais = permitido.substitui or (permitido.id,)
        assert all(BIBLIOTECA[o].fase_minima <= fase for o in originais)


def test_nao_gera_plano_da_erro() -> None:
    e = _estrategia("persona_teste.json").model_copy(update={"pode_gerar_plano": False})
    with pytest.raises(ValueError, match="não permite"):
        selecionar_exercicios(e, 1)


@pytest.mark.parametrize("fase", [0, 5])
def test_fase_invalida(fase: int) -> None:
    with pytest.raises(ValueError, match="Fase inválida"):
        selecionar_exercicios(_estrategia("persona_teste.json"), fase)


def test_cresce_com_a_fase() -> None:
    e = _com(Restricoes(equipamento=TODO_O_EQUIPAMENTO))
    tamanhos = [len(selecionar_exercicios(e, f)) for f in FASES]
    assert tamanhos == sorted(tamanhos)
    assert "lunge_atras_apoio" not in _ids(selecionar_exercicios(e, 1))
    assert "lunge_atras_apoio" in _ids(selecionar_exercicios(e, 2))


def test_sem_restricoes_todos_os_base_da_fase() -> None:
    e = _com(Restricoes(equipamento=TODO_O_EQUIPAMENTO))
    for fase in FASES:
        esperado = [
            ex.id
            for ex in BIBLIOTECA.values()
            if ex.nivel is Nivel.BASE and ex.impacto is Impacto.BAIXO and ex.fase_minima <= fase
        ]
        lista = selecionar_exercicios(e, fase)
        assert _ids(lista) == esperado
        assert all(not p.substitui and p.esforco_max is None and not p.notas for p in lista)


# ---------------------------------------------------------------- Equipamento


def test_sem_equipamento_declarado() -> None:
    lista = _ids(selecionar_exercicios(_com(Restricoes()), 4))
    for id_ in ("remada_halteres", "remada_unilateral_apoio", "passadeira", "eliptica"):
        assert id_ not in lista
    # Cadeira, parede, bancada e degrau contam como existentes em casa.
    for id_ in ("agachamento_cadeira", "flexao_parede", "subida_degrau_apoio"):
        assert id_ in lista


def test_equipamento_declarado() -> None:
    lista = _ids(selecionar_exercicios(_com(Restricoes(equipamento=(Equipamento.HALTERES,))), 1))
    assert "remada_halteres" in lista
    assert "passadeira" not in lista


# ---------------------------------------------------------------- Contraindicações e osteoporose


def test_contraindicado_sai() -> None:
    lista = _ids(selecionar_exercicios(_com(Restricoes(contraindicacoes=("osteoporose",))), 2))
    assert "abdominal_crunch" not in lista
    assert "bird_dog" in lista


def test_contraindicacao_sem_relacao_nao_retira() -> None:
    lista = _ids(selecionar_exercicios(_com(Restricoes(contraindicacoes=("hipertensao",))), 2))
    assert "abdominal_crunch" in lista


def test_sem_flexao_tronco_passa_a_bird_dog() -> None:
    """Mesmo sem a contraindicação na biblioteca, o crunch passa à regressão."""
    lista = _por_id(selecionar_exercicios(_com(Restricoes(sem_flexao_tronco_com_carga=True)), 2))
    assert "abdominal_crunch" not in lista
    assert lista["bird_dog"].substitui == ("abdominal_crunch",)


def test_flexao_tronco_sem_regressao_sai() -> None:
    crunch = BIBLIOTECA["abdominal_crunch"].model_copy(update={"regressao": None})
    bib = {**BIBLIOTECA, "abdominal_crunch": crunch}
    lista = _ids(selecionar_exercicios(_com(Restricoes(sem_flexao_tronco_com_carga=True)), 2, bib))
    assert "abdominal_crunch" not in lista


@pytest.mark.parametrize("fase", FASES)
def test_persona_osteoporose(fase: int) -> None:
    e = _estrategia("persona_osteoporose.json")
    lista = _por_id(selecionar_exercicios(e, fase))
    assert not any(BIBLIOTECA[i].flexao_tronco_carga for i in lista)
    assert "abdominal_crunch" not in lista
    assert "bird_dog" in lista
    assert not any(Equipamento.HALTERES in BIBLIOTECA[i].equipamento for i in lista)
    assert "passadeira" not in lista
    for id_, permitido in lista.items():
        ex = BIBLIOTECA[id_]
        precisa_apoio = ex.de_pe or ex.grupo is Grupo.EQUILIBRIO
        assert (textos.APOIO_POR_PERTO in permitido.notas) == precisa_apoio


# ---------------------------------------------------------------- Equilíbrio com apoio


def test_sem_equilibrio_com_apoio_nao_ha_nota() -> None:
    lista = selecionar_exercicios(_com(Restricoes()), 4)
    assert all(textos.APOIO_POR_PERTO not in p.notas for p in lista)


def test_equilibrio_com_apoio_em_todos_os_de_pe() -> None:
    e = _com(Restricoes(equilibrio_com_apoio=True, equipamento=TODO_O_EQUIPAMENTO))
    lista = _por_id(selecionar_exercicios(e, 4))
    # De pé, mas sem apoio previsto no texto: a nota vem do campo de_pe.
    for id_ in ("agachamento_cadeira", "remada_halteres", "prensa_ombros", "caminhada"):
        assert BIBLIOTECA[id_].de_pe and not BIBLIOTECA[id_].apoio_equilibrio
        assert textos.APOIO_POR_PERTO in lista[id_].notas
    assert textos.APOIO_POR_PERTO in lista["flexao_inclinada_joelhos"].notas  # inclinada = de pé
    for id_ in ("ponte_gluteos", "bird_dog", "prancha_antebracos", "abdominal_crunch"):
        assert textos.APOIO_POR_PERTO not in lista[id_].notas


def test_de_pe_definido_em_todos() -> None:
    de_pe = {id_ for id_, ex in BIBLIOTECA.items() if ex.de_pe}
    assert {ex.id for ex in BIBLIOTECA.values() if ex.apoio_equilibrio} <= de_pe
    assert {ex.id for ex in BIBLIOTECA.values() if ex.grupo is Grupo.EQUILIBRIO} <= de_pe
    assert {ex.id for ex in BIBLIOTECA.values() if ex.grupo is Grupo.CARDIO} - de_pe == {
        "escaladores"
    }


# ---------------------------------------------------------------- Regressão por zona (§6.6)


def _questionario_com(**alteracoes: object) -> Estrategia:
    dados = json.loads((EXEMPLOS / "persona_teste.json").read_text(encoding="utf-8"))
    dados |= alteracoes
    return gerar_estrategia(Questionario.model_validate(dados))


DOR_JOELHOS = {
    "condicoes": ["dor_articular_persistente"],
    "condicoes_controladas": {},
    "dor_articular_zonas": ["joelhos"],
    "limitacoes": ["nenhuma"],
    "limitacoes_gravidade": {},
}


def test_estrategia_separa_ligeira_de_completa() -> None:
    r = _estrategia("persona_teste.json").restricoes
    assert r.zonas_regressao == ()
    assert r.zonas_regressao_ligeira == (Zona.JOELHOS,)

    r = _questionario_com(**DOR_JOELHOS).restricoes
    assert r.zonas_regressao == (Zona.JOELHOS,)
    assert r.zonas_regressao_ligeira == ()

    r = _questionario_com(limitacoes_gravidade={"joelhos": "importante"}).restricoes
    assert r.zonas_regressao == (Zona.JOELHOS,)
    assert r.zonas_regressao_ligeira == ()

    # A mesma zona nas duas: vale a regra completa (a mais restritiva, §1).
    ambas = DOR_JOELHOS | {
        "limitacoes": ["joelhos", "ombros"],
        "limitacoes_gravidade": {"joelhos": "ligeira", "ombros": "ligeira"},
    }
    r = _questionario_com(**ambas).restricoes
    assert r.zonas_regressao == (Zona.JOELHOS,)
    assert r.zonas_regressao_ligeira == (Zona.OMBROS,)


@pytest.mark.parametrize(
    "ficheiro", ["persona_teste.json", "persona_renal.json", "persona_imc36.json"]
)
@pytest.mark.parametrize("fase", FASES)
def test_limitacao_ligeira_nos_joelhos(ficheiro: str, fase: int) -> None:
    """Regra ligeira: fase 1 e cardio mantêm-se com a nota; fase 2 a 4, um passo."""
    lista = _por_id(selecionar_exercicios(_estrategia(ficheiro), fase))
    assert all(p.esforco_max is None for p in lista.values())  # sem limite adicional
    for id_ in ("agachamento_cadeira", "caminhada", "passadeira", "marcha_rapida_lugar"):
        assert lista[id_].notas == (textos.AMPLITUDE_CONFORTAVEL,)
        if id_ != "agachamento_cadeira":  # o agachamento recebe os de fase 2 a 4
            assert lista[id_].substitui == ()
    assert "apoio_unipodal_assistido" in lista  # fase 1: mantém-se
    for id_, permitido in lista.items():
        if Zona.JOELHOS in BIBLIOTECA[id_].zonas:
            assert textos.AMPLITUDE_CONFORTAVEL in permitido.notas
        for original in permitido.substitui:
            assert BIBLIOTECA[original].fase_minima >= 2
            assert BIBLIOTECA[original].regressao == id_  # um passo só
    assert "eliptica" not in lista  # não declarada


def test_limitacao_ligeira_fase_4() -> None:
    lista = _por_id(selecionar_exercicios(_estrategia("persona_teste.json"), 4))
    assert set(lista["agachamento_cadeira"].substitui) == {
        "lunge_atras_apoio",
        "agachamento_sumo",
        "agachamento_dividido_apoio",
        "agachamento_elevacao_calcanhares",
        "subida_degrau_apoio",
        "agachamento_prensa_ombros",
    }
    assert lista["ponte_gluteos"].substitui == ()


@pytest.mark.parametrize("fase", FASES)
def test_dor_persistente_nos_joelhos_regra_completa(fase: int) -> None:
    lista = _por_id(selecionar_exercicios(_questionario_com(**DOR_JOELHOS), fase))
    for id_, permitido in lista.items():
        if Zona.JOELHOS in BIBLIOTECA[id_].zonas:
            # Fim da cadeia: ainda solicita os joelhos ⇒ esforço 4 e amplitude confortável.
            assert permitido.esforco_max == 4
            assert textos.AMPLITUDE_CONFORTAVEL in permitido.notas
        else:
            assert permitido.esforco_max is None
    assert "agachamento_cadeira" not in lista
    assert "agachamento_cadeira" in lista["ponte_gluteos"].substitui
    assert lista["caminhada"].substitui == ("marcha_rapida_lugar",)
    assert lista["passadeira"].esforco_max == 4
    assert lista["transferencias_peso"].substitui == ("apoio_unipodal_assistido",)


def test_limitacao_importante_regra_completa() -> None:
    e = _questionario_com(limitacoes_gravidade={"joelhos": "importante"})
    lista = _por_id(selecionar_exercicios(e, 1))
    assert "agachamento_cadeira" not in lista
    assert lista["caminhada"].esforco_max == 4


def test_ligeira_nao_desce_para_zona_da_regra_completa() -> None:
    """Ligeira nos joelhos e completa nas ancas: o passo não pode solicitar as ancas."""
    e = _com(
        Restricoes(
            zonas_regressao=(Zona.ANCAS,),
            zonas_regressao_ligeira=(Zona.JOELHOS,),
            equipamento=TODO_O_EQUIPAMENTO,
        )
    )
    for permitido in selecionar_exercicios(e, 4):
        ex = BIBLIOTECA[permitido.id]
        if Zona.ANCAS in ex.zonas:
            assert permitido.esforco_max == 4


def test_varias_zonas_ao_mesmo_tempo() -> None:
    zonas = (Zona.JOELHOS, Zona.ANCAS)
    e = _com(Restricoes(zonas_regressao=zonas, equipamento=TODO_O_EQUIPAMENTO))
    for permitido in selecionar_exercicios(e, 4):
        if set(BIBLIOTECA[permitido.id].zonas) & set(zonas):
            assert permitido.esforco_max == 4
            assert BIBLIOTECA[permitido.id].regressao is None


def test_regressao_em_qualquer_fase() -> None:
    """REGRAS §6.6, ponto 4: a regressão entra mesmo com fase_minima posterior."""
    assert BIBLIOTECA["remada_halteres"].fase_minima == 1
    assert BIBLIOTECA["remada_unilateral_apoio"].fase_minima == 3
    e = _com(Restricoes(zonas_regressao=(Zona.COLUNA,), equipamento=TODO_O_EQUIPAMENTO))
    lista = _por_id(selecionar_exercicios(e, 1))
    assert "remada_halteres" not in lista
    assert lista["remada_unilateral_apoio"].substitui == ("remada_halteres",)
    assert lista["remada_unilateral_apoio"].esforco_max == 4  # ainda solicita a coluna


def test_regressao_em_qualquer_fase_biblioteca_sintetica() -> None:
    """O mesmo, com uma regressão de fase 4 que já não solicita a zona."""
    bib = {
        "a": Exercicio(
            id="a", nome="A", descricao="a", grupo=Grupo.FORCA, fase_minima=1,
            impacto=Impacto.BAIXO, nivel=Nivel.BASE, de_pe=False, regressao="b",
            zonas=(Zona.OMBROS,),
        ),
        "b": Exercicio(
            id="b", nome="B", descricao="b", grupo=Grupo.FORCA, fase_minima=4,
            impacto=Impacto.BAIXO, nivel=Nivel.BASE, de_pe=False,
        ),
    }  # fmt: skip
    e = _com(Restricoes(zonas_regressao=(Zona.OMBROS,)))
    assert selecionar_exercicios(e, 1, bib) == (
        ExercicioPermitido(id="b", grupo=Grupo.FORCA, substitui=("a",)),
    )
    # Sem a limitação, «b» só aparece na fase 4.
    assert _ids(selecionar_exercicios(_com(Restricoes()), 1, bib)) == ["a"]


def test_regressao_que_falha_filtros_sai() -> None:
    """A regressão tem de cumprir os filtros (exceto a fase); se não cumprir, sai."""
    bib = {
        "a": Exercicio(
            id="a", nome="A", descricao="a", grupo=Grupo.FORCA, fase_minima=1,
            impacto=Impacto.BAIXO, nivel=Nivel.BASE, de_pe=False, regressao="b",
            zonas=(Zona.OMBROS,),
        ),
        "b": Exercicio(
            id="b", nome="B", descricao="b", grupo=Grupo.FORCA, fase_minima=1,
            impacto=Impacto.BAIXO, nivel=Nivel.BASE, de_pe=False, contraindicacoes=("osteoporose",),
        ),
    }  # fmt: skip
    restricoes = Restricoes(zonas_regressao=(Zona.OMBROS,), contraindicacoes=("osteoporose",))
    assert selecionar_exercicios(_com(restricoes), 1, bib) == ()


# ---------------------------------------------------------------- Regressão geral («outra»)


def test_regressao_geral_desce_um_passo() -> None:
    e = _com(Restricoes(regressao_geral=True, equipamento=TODO_O_EQUIPAMENTO))
    lista = _por_id(selecionar_exercicios(e, 2))
    assert "agachamento_cadeira" in lista["ponte_gluteos"].substitui
    # lunge_atras_apoio → agachamento_cadeira: só um passo, não segue para a ponte.
    assert lista["agachamento_cadeira"].substitui == ("lunge_atras_apoio", "agachamento_sumo")
    assert all(p.esforco_max is None for p in lista.values())
    # Sem regressão na biblioteca: fica como está.
    assert lista["elevacao_gemeos"].substitui == ()
