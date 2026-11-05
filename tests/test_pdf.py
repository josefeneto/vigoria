"""Plano em PDF (exportacao/pdf.py) com a persona de teste e o fornecedor simulado.

Sem biblioteca para ler PDFs: os testes registam o texto que o gerador escreve em cada
página (e o tamanho da letra) e confirmam o ficheiro pelo cabeçalho e pelo número de páginas.
"""

import re
import warnings
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from vigoria.conteudo.carregar import carregar_manutencao
from vigoria.exportacao import pdf
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario
from vigoria.motor.pipeline import gerar_plano_verificado

RAIZ = Path(__file__).resolve().parents[1]
DATA = datetime(2026, 11, 4, 17, 30, tzinfo=UTC)


@cache
def _plano(persona: str = "persona_teste") -> Plano:
    q = Questionario.model_validate_json((RAIZ / "exemplos" / f"{persona}.json").read_text("utf-8"))
    return gerar_plano_verificado(q, ProvedorSimulado(), progresso=lambda _: None).plano


def _paginas(dados: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", dados))


@pytest.fixture
def escrito(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, float, str]]:
    """(página, tamanho da letra em pt, texto) de cada bloco de texto escrito."""
    registo: list[tuple[int, float, str]] = []
    original = pdf._Documento.multi_cell

    def espiao(self: pdf._Documento, *args: Any, **kwargs: Any) -> Any:
        texto = kwargs.get("text", args[2] if len(args) > 2 else "")
        if not kwargs.get("dry_run"):
            registo.append((self.page_no(), self.font_size_pt, str(texto)))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pdf._Documento, "multi_cell", espiao)
    return registo


def test_gera_o_pdf_da_persona_de_teste_sem_erros() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # p. ex., letra sem um carácter usado no plano
        dados = pdf.plano_pdf(_plano(), DATA)
    assert dados.startswith(b"%PDF-")
    assert dados.rstrip().endswith(b"%%EOF")
    assert _paginas(dados) >= 10


@pytest.mark.parametrize(
    "persona", ["persona_50_alta", "persona_imc36", "persona_osteoporose", "persona_renal"]
)
def test_gera_o_pdf_das_outras_personas(persona: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dados = pdf.plano_pdf(_plano(persona), DATA)
    assert _paginas(dados) >= 10


def test_conteudo_capa_seccoes_e_avisos_na_ultima_pagina(
    escrito: list[tuple[int, float, str]],
) -> None:
    plano = _plano()
    dados = pdf.plano_pdf(plano, DATA)
    ultima = _paginas(dados)
    capa = [texto for pagina, _, texto in escrito if pagina == 1]
    assert "O seu plano Vigoria" in capa
    assert "Criado a 4 de novembro de 2026" in capa
    todo = "\n".join(texto for _, _, texto in escrito)
    for titulo in ("Resumo", "Marcos", "Semana-tipo", "Alimentação", "Proteína", "Hidratação"):
        assert titulo in todo
    for titulo in ("Hábitos", "O que registar"):
        assert titulo in todo
    for fase in plano.treino.fases:
        assert f"Fase {fase.numero}: {fase.nome}" in todo
        for x in fase.forca:
            assert x.nome in todo and x.descricao in todo
    na_ultima = [texto for pagina, _, texto in escrito if pagina == ultima]
    assert na_ultima[0] == "Avisos importantes"
    for aviso in plano.avisos:
        assert pdf._limpo(aviso) in na_ultima
        assert all(aviso not in t for p, _, t in escrito if p < ultima)  # só na última


def test_manutencao_antes_dos_avisos_e_oms_so_com_65_anos(
    escrito: list[tuple[int, float, str]],
) -> None:
    oms = pdf._limpo(carregar_manutencao().treino.oms_65)
    ultima = _paginas(pdf.plano_pdf(_plano(), DATA, 68))
    paginas = {texto: pagina for pagina, _, texto in escrito}
    assert paginas["Depois das 16 semanas"] < ultima  # antes da página dos avisos
    assert "Recomeçar" in paginas and oms in paginas
    escrito.clear()
    pdf.plano_pdf(_plano("persona_50_alta"), DATA, 50)
    textos = [texto for _, _, texto in escrito]
    assert "Depois das 16 semanas" in textos and oms not in textos


def test_letra_base_de_pelo_menos_11_pt(escrito: list[tuple[int, float, str]]) -> None:
    pdf.plano_pdf(_plano(), DATA)
    assert min(tamanho for _, tamanho, _ in escrito) >= 11


def test_sem_dados_identificativos(escrito: list[tuple[int, float, str]]) -> None:
    dados = pdf.plano_pdf(_plano(), DATA)
    todo = "\n".join(texto for _, _, texto in escrito)
    assert "@" not in todo
    assert b"@" not in dados.split(b"stream")[0]  # metadados (título, autor) sem email


def test_prioridades_sem_fase_repetida() -> None:
    assert pdf._sem_prefixo_fase("Fase 1: criar a rotina") == "criar a rotina"
    assert pdf._sem_prefixo_fase("fase 2 — mais legumes") == "mais legumes"
    assert pdf._sem_prefixo_fase("Mais legumes na fase 3") == "Mais legumes na fase 3"


def test_cores_iguais_as_da_marca() -> None:
    from paginas.estilos import CORES

    for nome, valor in pdf.CORES.items():
        assert CORES[nome] == valor


def test_logotipo_do_pdf_igual_ao_da_marca() -> None:
    copia = (pdf.RECURSOS / "vigoria_logo.svg").read_bytes()
    assert copia == (RAIZ / "assets" / "marca" / "vigoria_logo.svg").read_bytes()
