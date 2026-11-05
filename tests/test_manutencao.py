"""Depois das 16 semanas (Fase 6B): conteúdo, exercícios das fases 3 e 4, OMS e planos antigos."""

from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest

from vigoria.conteudo.carregar import carregar_avisos, carregar_exercicios, carregar_manutencao
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario
from vigoria.motor.manutencao import exercicios_base, orientacoes_manutencao
from vigoria.motor.pipeline import gerar_plano_verificado
from vigoria.motor.voz import encontrar_termos

RAIZ = Path(__file__).resolve().parents[1]
PERSONAS = ["persona_teste", "persona_50_alta", "persona_imc36", "persona_osteoporose"]


@cache
def _plano(persona: str = "persona_teste") -> Plano:
    q = Questionario.model_validate_json((RAIZ / "exemplos" / f"{persona}.json").read_text("utf-8"))
    return gerar_plano_verificado(q, ProvedorSimulado(), progresso=lambda _: None).plano


def _textos(valor: object) -> Iterator[str]:
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _textos(v)
    elif isinstance(valor, list | tuple):
        for v in valor:
            yield from _textos(v)


def test_conteudo_tem_as_quatro_partes() -> None:
    m = carregar_manutencao()
    for parte in (m.treino, m.alimentacao, m.vigiar, m.recomecar):
        assert parte.introducao
    assert "65 ou mais anos" in m.treino.oms_65
    assert m.treino.variar and m.alimentacao.pontos and m.vigiar.pontos and m.recomecar.pontos


def test_textos_sem_promessas_termos_proibidos_nem_brasileirismos() -> None:
    avisos = carregar_avisos()
    texto = "\n".join(_textos(carregar_manutencao().model_dump()))
    for termos in (
        avisos.lista_negra.promessas,
        avisos.lista_negra.termos,
        avisos.brasileirismos,
    ):
        assert encontrar_termos(termos, texto) == ()


@pytest.mark.parametrize("persona", PERSONAS)
def test_exercicios_sao_os_das_fases_3_e_4_sem_repetidos(persona: str) -> None:
    plano = _plano(persona)
    nomes = exercicios_base(plano)
    assert len(nomes) == len(set(nomes))
    esperados = {
        x.nome
        for f in plano.treino.fases
        if f.numero in (3, 4)
        for x in (
            *f.forca,
            *((f.cardio_finalizador,) if f.cardio_finalizador else ()),
            *f.mobilidade_equilibrio,
        )
    }
    assert set(nomes) == esperados
    # Nenhum exercício novo: todos vêm do plano e da biblioteca.
    da_biblioteca = {e.nome for e in carregar_exercicios().values()}
    assert set(nomes) <= da_biblioteca


@pytest.mark.parametrize("persona", ["persona_teste", "persona_imc36"])
def test_com_regressoes_entra_o_substituto_e_nao_o_original(persona: str) -> None:
    plano = _plano(persona)
    nomes = set(exercicios_base(plano))
    biblioteca = carregar_exercicios()
    trocados = [x for f in plano.treino.fases if f.numero in (3, 4) for x in f.forca if x.em_vez_de]
    assert trocados, "a persona devia ter regressões nas fases 3 e 4"
    no_plano = {x.id for f in plano.treino.fases if f.numero in (3, 4) for x in f.forca}
    for x in trocados:
        assert x.nome in nomes
        if x.em_vez_de not in no_plano:
            assert biblioteca[x.em_vez_de].nome not in nomes


def test_oms_so_a_partir_dos_65_anos() -> None:
    oms = carregar_manutencao().treino.oms_65
    assert oms in orientacoes_manutencao(_plano("persona_teste"), 68).treino.notas
    assert oms not in orientacoes_manutencao(_plano("persona_50_alta"), 50).treino.notas
    assert oms in orientacoes_manutencao(_plano(), 65).treino.notas  # no limiar
    assert oms not in orientacoes_manutencao(_plano(), 64).treino.notas
    assert oms not in orientacoes_manutencao(_plano(), None).treino.notas  # idade desconhecida


def test_planos_ja_guardados_tambem_tem_a_seccao() -> None:
    # Um plano gravado antes da 6B não tem nada de manutenção: a secção calcula-se.
    guardado = _plano().model_dump(mode="json")
    assert "manutencao" not in guardado
    lido = Plano.model_validate(guardado)
    m = orientacoes_manutencao(lido, 68)
    assert m.exercicios_base == exercicios_base(_plano())
    assert m.recomecar.introducao and m.alimentacao.pontos
