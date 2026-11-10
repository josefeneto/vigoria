"""Ícones dos exercícios (Fase 5D): um pictograma por tipo de movimento, em todos os
exercícios da biblioteca, no estilo da maqueta (docs/design/maquetas/Fase.dc.html)."""

import base64
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from paginas import componentes, estilos
from vigoria.conteudo.carregar import IconeExercicio, carregar_exercicios
from vigoria.exportacao import pdf

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "assets" / "icones" / "exercicios"
SVG = "{http://www.w3.org/2000/svg}"


def test_todos_os_exercicios_tem_icone() -> None:
    """O campo é obrigatório (o carregamento falha sem ele); confirmamos o tipo."""
    for x in carregar_exercicios().values():
        assert isinstance(x.icone, IconeExercicio), x.id


def test_cada_icone_existe_e_e_usado() -> None:
    usados = {x.icone for x in carregar_exercicios().values()}
    assert usados == set(IconeExercicio)
    assert {f.stem for f in PASTA.glob("*.svg")} == {i.value for i in IconeExercicio}


@pytest.mark.parametrize("icone", list(IconeExercicio))
def test_svg_no_estilo_da_maqueta(icone: IconeExercicio) -> None:
    """48×48, traço de 2,5, decorativo; só currentColor (figura) e class="d" (equipamento):
    nenhuma cor escrita no ficheiro, para as cores virem sempre da paleta."""
    texto = (PASTA / f"{icone}.svg").read_text(encoding="utf-8")
    raiz = ET.fromstring(texto)
    assert raiz.tag == f"{SVG}svg"
    assert raiz.get("viewBox") == "0 0 48 48"
    assert raiz.get("stroke-width") == "2.5"
    assert raiz.get("stroke") == "currentColor" and raiz.get("fill") == "none"
    assert raiz.get("aria-hidden") == "true"
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", texto)
    assert raiz.find(f"{SVG}circle") is not None  # a cabeça da figura
    assert raiz.find("*[@class='d']") is not None  # equipamento ou chão, em terracota


@pytest.mark.parametrize("icone", list(IconeExercicio))
def test_copias_do_pdf_iguais(icone: IconeExercicio) -> None:
    """scripts/folha_icones.py copia os SVG para o pacote (o PDF lê-os de lá)."""
    copia = (pdf.ICONES / f"{icone}.svg").read_bytes()
    assert copia == (PASTA / f"{icone}.svg").read_bytes()


def test_cartao_da_app_com_o_icone_do_movimento() -> None:
    html = componentes.exercicio("remada", "Remada", ["3 séries"], "Puxar os cotovelos.")
    svg = base64.b64decode(html.split("base64,", 1)[1].split('"', 1)[0]).decode("utf-8")
    assert svg.startswith("<svg") and 'viewBox="0 0 48 48"' in svg
    assert estilos.CORES["principal_profundo"] in svg and estilos.CORES["terracota"] in svg
    assert "currentColor" not in svg and 'class="d"' not in svg


def test_icone_do_pdf_com_as_cores_da_marca() -> None:
    svg = pdf._icone_svg("peso_morto_romeno").read().decode("utf-8")
    assert pdf.CORES["principal_profundo"] in svg and pdf.CORES["terracota"] in svg
    assert "currentColor" not in svg
