"""Testes da biblioteca de exercícios e das fases (REGRAS_DOMINIO §5 e §6)."""

import pytest

from vigoria.conteudo.carregar import (
    Exercicio,
    Grupo,
    Impacto,
    Nivel,
    carregar_exercicios,
    carregar_fases,
    carregar_programa,
)
from vigoria.modelos.estrategia import Zona

BIBLIOTECA = carregar_exercicios()
FASES = carregar_fases()


def _ids_nas_fases() -> set[str]:
    return {i for f in FASES for p in f.exercicios for i in (p.id, *p.alternativas)}


def _base() -> list[Exercicio]:
    return [e for e in BIBLIOTECA.values() if e.nivel is Nivel.BASE]


def test_contagens() -> None:
    assert len(BIBLIOTECA) == 45
    assert len(_base()) == 34
    assert sum(e.grupo is Grupo.FORCA for e in _base()) == 24
    assert sum(e.grupo is Grupo.CARDIO for e in _base()) == 4


def test_ids_em_minusculas_sem_acentos() -> None:
    for id_ in BIBLIOTECA:
        assert id_.isascii() and id_ == id_.lower()


def test_exercicios_das_fases_existem_na_biblioteca() -> None:
    assert _ids_nas_fases() <= BIBLIOTECA.keys()


def test_regressoes_existem_na_biblioteca() -> None:
    for e in BIBLIOTECA.values():
        assert e.regressao is None or e.regressao in BIBLIOTECA, e.id


def test_regressao_de_base_e_base() -> None:
    for e in _base():
        if e.regressao is not None:
            assert BIBLIOTECA[e.regressao].nivel is Nivel.BASE, e.id


def test_fases_so_usam_nivel_base_e_ja_disponivel() -> None:
    for fase in FASES:
        for posicao in fase.exercicios:
            for id_ in (posicao.id, *posicao.alternativas):
                exercicio = BIBLIOTECA[id_]
                assert exercicio.nivel is Nivel.BASE, id_
                assert exercicio.fase_minima <= fase.numero, id_


def test_nenhuma_variante_base_tem_impacto() -> None:
    for e in _base():
        assert e.impacto is Impacto.BAIXO, e.id


def test_avancadas_regridem_para_base() -> None:
    for e in BIBLIOTECA.values():
        if e.nivel is not Nivel.BASE:
            assert e.regressao is not None, e.id
            assert BIBLIOTECA[e.regressao].nivel is Nivel.BASE, e.id


def test_cadeias_de_regressao_sem_ciclos() -> None:
    for inicio in BIBLIOTECA.values():
        vistos = {inicio.id}
        atual = inicio
        while atual.regressao is not None:
            assert atual.regressao not in vistos, f"ciclo a partir de {inicio.id}"
            vistos.add(atual.regressao)
            atual = BIBLIOTECA[atual.regressao]


def test_fases_completas() -> None:
    assert [f.numero for f in FASES] == [1, 2, 3, 4]
    assert [f.nome for f in FASES] == ["Adaptação", "Construção", "Consolidação", "Integração"]
    assert [(f.semanas.min, f.semanas.max) for f in FASES] == [(1, 4), (5, 8), (9, 12), (13, 16)]
    for fase in FASES:
        assert fase.esforco.max <= 6, fase.nome
        for posicao in fase.exercicios:
            assert posicao.series >= 1
            assert posicao.repeticoes.strip()
            assert posicao.descanso_s.max > 0


def test_integracao_na_versao_base() -> None:
    integracao = FASES[3]
    for posicao in integracao.exercicios:
        assert posicao.series == 3
        assert posicao.descanso_s.min >= 45
        assert posicao.descanso_s.max <= 60


def test_estrutura_da_sessao_sem_corrida() -> None:
    estrutura = carregar_programa().estrutura_sessao
    assert "marcha rápida no lugar" in estrutura.cardio_finalizador
    assert "corrida" not in estrutura.cardio_finalizador.lower()


@pytest.mark.parametrize("zona", list(Zona))
def test_cada_zona_tem_forca_base_que_nao_a_solicita(zona: Zona) -> None:
    assert any(e.grupo is Grupo.FORCA and zona not in e.zonas for e in _base())


def test_flexao_do_tronco_com_carga_so_no_crunch() -> None:
    com_flexao = [e.id for e in BIBLIOTECA.values() if e.flexao_tronco_carga]
    assert com_flexao == ["abdominal_crunch"]
    crunch = BIBLIOTECA["abdominal_crunch"]
    assert crunch.contraindicacoes == ("osteoporose",)
    assert crunch.regressao == "bird_dog"
