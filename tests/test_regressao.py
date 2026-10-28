"""Testes da aplicação das regressões por zona (REGRAS_DOMINIO §6.6)."""

import itertools

import pytest

from vigoria.conteudo.carregar import Exercicio, Grupo, Impacto, Nivel, carregar_exercicios
from vigoria.modelos.estrategia import Zona
from vigoria.regras import textos
from vigoria.regras.regressao import resolver_regressao

BIBLIOTECA = carregar_exercicios()
FORCA_BASE = sorted(
    e.id for e in BIBLIOTECA.values() if e.nivel is Nivel.BASE and e.grupo is Grupo.FORCA
)
COMBINACOES = [
    combinacao for n in range(1, len(Zona) + 1) for combinacao in itertools.combinations(Zona, n)
]


@pytest.mark.parametrize("exercicio_id", FORCA_BASE)
@pytest.mark.parametrize("zonas", COMBINACOES, ids=lambda z: "+".join(z))
def test_devolve_sempre_um_exercicio_valido(exercicio_id: str, zonas: tuple[Zona, ...]) -> None:
    r = resolver_regressao(exercicio_id, zonas, BIBLIOTECA)
    escolhido = BIBLIOTECA[r.exercicio_id]
    assert escolhido.nivel is Nivel.BASE
    if set(escolhido.zonas) & set(zonas):
        assert escolhido.regressao is None  # fim da cadeia
        assert r.esforco_max == 4
        assert r.nota == textos.AMPLITUDE_CONFORTAVEL
    else:
        assert r.esforco_max is None and r.nota is None


def test_sem_zona_afetada_fica_o_mesmo() -> None:
    r = resolver_regressao("agachamento_cadeira", [Zona.OMBROS], BIBLIOTECA)
    assert r.exercicio_id == "agachamento_cadeira"
    assert r.esforco_max is None


def test_sem_zonas_fica_o_mesmo() -> None:
    assert resolver_regressao("lunge_atras_apoio", [], BIBLIOTECA).exercicio_id == (
        "lunge_atras_apoio"
    )


def test_joelhos_no_agachamento_passa_a_ponte() -> None:
    r = resolver_regressao("agachamento_cadeira", [Zona.JOELHOS], BIBLIOTECA)
    assert r.exercicio_id == "ponte_gluteos"
    assert r.esforco_max is None


def test_ancas_no_agachamento_fica_na_ponte_com_esforco_4() -> None:
    r = resolver_regressao("agachamento_cadeira", [Zona.ANCAS], BIBLIOTECA)
    assert r.exercicio_id == "ponte_gluteos"
    assert r.esforco_max == 4
    assert r.nota == textos.AMPLITUDE_CONFORTAVEL


def test_cadeia_longa_lunge_joelhos() -> None:
    # lunge_atras_apoio → agachamento_cadeira → ponte_gluteos
    r = resolver_regressao("lunge_atras_apoio", [Zona.JOELHOS], BIBLIOTECA)
    assert r.exercicio_id == "ponte_gluteos"


def test_varias_zonas_ao_mesmo_tempo() -> None:
    # remada_aberta → remada_halteres → remada_unilateral_apoio (ainda ombros) ⇒ fim da cadeia
    r = resolver_regressao("remada_aberta", [Zona.COLUNA, Zona.OMBROS], BIBLIOTECA)
    assert r.exercicio_id == "remada_unilateral_apoio"
    assert r.esforco_max == 4


def test_exercicio_sem_zonas_nunca_regride() -> None:
    r = resolver_regressao("elevacao_gemeos", list(Zona), BIBLIOTECA)
    assert r.exercicio_id == "elevacao_gemeos"
    assert r.esforco_max is None


def test_ciclo_e_detetado() -> None:
    def _ex(id_: str, regressao: str) -> Exercicio:
        return Exercicio(
            id=id_,
            nome=id_,
            descricao="",
            grupo=Grupo.FORCA,
            fase_minima=1,
            impacto=Impacto.BAIXO,
            nivel=Nivel.BASE,
            regressao=regressao,
            zonas=(Zona.JOELHOS,),
        )

    ciclo = {"a": _ex("a", "b"), "b": _ex("b", "a")}
    with pytest.raises(ValueError, match="Ciclo"):
        resolver_regressao("a", [Zona.JOELHOS], ciclo)
