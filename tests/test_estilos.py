"""Sistema visual (Fase 5B): cores, contraste WCAG AA, ícones, letra, HTML e fotografias."""

import base64
import importlib.util
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from paginas import componentes, estilos
from paginas import textos as t
from vigoria.conteudo.carregar import Grupo, carregar_avisos
from vigoria.interface.passos import PASSOS

RAIZ = Path(__file__).resolve().parents[1]
TEMA = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]


def _luminancia(cor: str) -> float:
    canais = [int(cor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    claro, escuro = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def test_contraste_de_referencia() -> None:
    assert contraste("#000000", "#FFFFFF") == pytest.approx(21)
    assert contraste("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)  # limite do AA


@pytest.mark.parametrize(
    ("opcao", "cor"),
    [
        ("primaryColor", "principal"),
        ("backgroundColor", "fundo"),
        ("secondaryBackgroundColor", "fundo_secundario"),
        ("textColor", "texto"),
        ("borderColor", "borda"),
        ("linkColor", "principal"),
        ("yellowTextColor", "aviso_texto"),
        ("yellowBackgroundColor", "aviso_fundo"),
        ("yellowColor", "aviso_borda"),
        ("orangeColor", "cobre"),
        ("orangeBackgroundColor", "argila"),
        ("orangeTextColor", "cobre_escuro"),
        ("blueBackgroundColor", "nevoa"),
        ("greenTextColor", "sucesso"),
        ("redTextColor", "erro"),
        ("grayTextColor", "texto_secundario"),
    ],
)
def test_cores_do_tema_iguais_as_de_estilos(opcao: str, cor: str) -> None:
    assert TEMA[opcao].upper() == estilos.CORES[cor].upper()


@pytest.mark.parametrize(("texto", "fundo"), estilos.PARES_TEXTO)
def test_pares_de_texto_com_contraste_aa(texto: str, fundo: str) -> None:
    assert contraste(estilos.CORES[texto], estilos.CORES[fundo]) >= 4.5


@pytest.mark.parametrize("cor", ["yellow", "orange", "blue", "green", "red"])
def test_alertas_do_tema_com_contraste_aa(cor: str) -> None:
    assert contraste(TEMA[f"{cor}TextColor"], TEMA[f"{cor}BackgroundColor"]) >= 4.5


def test_terracota_so_serve_para_formas() -> None:
    """A terracota do briefing não chega aos 4,5:1: só ícones (o mínimo para gráficos é 3:1)."""
    assert 3 <= contraste(estilos.CORES["terracota"], estilos.CORES["fundo"]) < 4.5


def test_letra_base_e_ficheiros_da_letra() -> None:
    assert TEMA["baseFontSize"] >= 18
    for face in TEMA["fontFaces"]:
        assert face["url"].startswith("app/static/")
        assert (RAIZ / face["url"].removeprefix("app/")).is_file()
    assert (RAIZ / "static" / "fontes" / "OFL.txt").is_file()
    assert "googleapis" not in (RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8")


def test_icones_existem_para_passos_grupos_e_atividades() -> None:
    assert set(estilos.ICONES_PASSOS) == set(PASSOS)
    nomes = (
        set(estilos.ICONES_PASSOS.values())
        | {g.value for g in Grupo}
        | set(estilos.ICONES_ATIVIDADES.values())
        | {i for i, _, _ in t.BENEFICIOS}
        | {"bandeira", "intensidade", "calendario", "rebento"}
    )
    for nome in nomes:
        assert (estilos.PASTA_ICONES / f"{nome}.svg").is_file(), nome


@pytest.mark.parametrize("ficheiro", sorted((RAIZ / "assets" / "icones").glob("*.svg")))
def test_icones_svg_validos_e_decorativos(ficheiro: Path) -> None:
    raiz = ET.fromstring(ficheiro.read_text(encoding="utf-8"))
    assert raiz.get("viewBox") == "0 0 24 24"
    assert raiz.get("aria-hidden") == "true"


def test_icone_em_img_com_cores_da_marca() -> None:
    html = estilos.icone("forca")
    assert html.startswith('<img src="data:image/svg+xml;base64,') and 'alt=""' in html
    svg = base64.b64decode(html.split(",", 1)[1].split('"', 1)[0]).decode("utf-8")
    assert "currentColor" not in svg and 'class="d"' not in svg
    assert estilos.CORES["principal"] in svg and estilos.CORES["terracota"] in svg


def test_todas_as_atividades_da_semana_tem_icone_proprio() -> None:
    for chave, rotulo in carregar_avisos().rotulos.semana.items():
        esperado = "descanso" if chave == "descanso" else None
        icone = componentes.icone_atividade(rotulo.atividade)
        assert icone == esperado if esperado else icone != "descanso", rotulo.atividade


def test_componentes_escapam_o_texto() -> None:
    """O texto do plano pode vir da LLM: nunca entra como HTML."""
    html = componentes.exercicio("forca", "<b>x</b>", ["3 séries"], "<script>alert(1)</script>")
    assert "<script>" not in html and "&lt;script&gt;" in html and "&lt;b&gt;" in html
    html = componentes.cartao_fase("Fase 1", "A", "<i>foco</i>", [("Peso", "<u>1</u>")])
    assert "<i>" not in html and "<u>" not in html


def test_cabecalho_do_passo_com_barra_acessivel() -> None:
    html = componentes.cabecalho_passo("alvo", "Passo 3 de 10", "Saúde", 2, 10)
    assert 'role="progressbar"' in html and 'aria-valuenow="3"' in html
    assert html.count('class="feito"') == 2 and html.count('class="atual"') == 1


def _converter_fotos():  # type: ignore[no-untyped-def]
    caminho = RAIZ / "scripts" / "converter_fotos.py"
    especificacao = importlib.util.spec_from_file_location("converter_fotos", caminho)
    assert especificacao is not None and especificacao.loader is not None
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


def _fotografia(caminho: Path, grao: int) -> None:
    """Imagem 3000×2000 parecida com uma fotografia: gradientes de cor com grão."""
    fundo = Image.merge(
        "RGB",
        (
            Image.linear_gradient("L").resize((3000, 2000)),
            Image.radial_gradient("L").resize((3000, 2000)),
            Image.linear_gradient("L").rotate(90).resize((3000, 2000)),
        ),
    )
    ruido = Image.effect_noise((3000, 2000), 255).convert("RGB")
    Image.blend(fundo, ruido, grao / 100).save(caminho, quality=95)


def test_converter_fotos_recorta_reduz_e_cabe_em_200_kb(tmp_path: Path) -> None:
    origem = tmp_path / "original.jpg"
    _fotografia(origem, grao=15)
    destino = tmp_path / "inicio_topo.webp"
    tamanho, _ = _converter_fotos().converter(origem, destino, (1600, 1067))
    assert tamanho <= 200 * 1024
    with Image.open(destino) as imagem:
        assert imagem.format == "WEBP" and imagem.size == (1600, 1067)


def test_converter_fotos_recusa_o_que_nao_cabe(tmp_path: Path) -> None:
    origem = tmp_path / "original.jpg"
    _fotografia(origem, grao=100)  # só ruído: não se comprime
    destino = tmp_path / "inicio_topo.webp"
    with pytest.raises(ValueError, match="200 KB"):
        _converter_fotos().converter(origem, destino, (1600, 1067))
    assert not destino.exists()
