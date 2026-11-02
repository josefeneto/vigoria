"""Logotipo, ícones e favicon (gerados por scripts/gerar_logotipo.py)."""

import ast
import json
from pathlib import Path

import pytest
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
MARCA = RAIZ / "assets" / "marca"
STATIC = RAIZ / "static"
LOGOTIPOS = {"vigoria_logo.svg": "#123F45", "vigoria_logo_claro.svg": "#F7F3EC"}
TAMANHOS = (32, 180, 192, 512)


@pytest.mark.parametrize(
    "caminho",
    [
        "assets/marca/vigoria_simbolo.svg",
        "assets/marca/vigoria_simbolo_claro.svg",
        "assets/marca/vigoria_icone.svg",
        "assets/marca/vigoria_logo.svg",
        "assets/marca/vigoria_logo_claro.svg",
        "static/vigoria_logo.svg",
        "static/vigoria_icone.svg",
        "pwa/manifest.webmanifest",
    ],
)
def test_ficheiro_existe(caminho: str) -> None:
    assert (RAIZ / caminho).is_file()


@pytest.mark.parametrize(("nome", "cor"), LOGOTIPOS.items())
def test_logotipo_so_com_contornos(nome: str, cor: str) -> None:
    """A palavra está em contornos: não depende de a letra estar instalada."""
    svg = (MARCA / nome).read_text(encoding="utf-8")
    assert "<text" not in svg
    assert "font-family" not in svg
    assert f'fill="{cor}"' in svg
    assert 'aria-label="Vigoria"' in svg


@pytest.mark.parametrize(("nome", "simbolo"), [
    ("vigoria_logo.svg", "vigoria_simbolo.svg"),
    ("vigoria_logo_claro.svg", "vigoria_simbolo_claro.svg"),
])  # fmt: skip
def test_logotipo_tem_o_simbolo_sem_alteracoes(nome: str, simbolo: str) -> None:
    desenho = (MARCA / simbolo).read_text(encoding="utf-8")
    interior = desenho.split(">", 1)[1].rsplit("</svg>", 1)[0].strip()
    assert interior in (MARCA / nome).read_text(encoding="utf-8")


@pytest.mark.parametrize("nome", ["vigoria_logo.svg", "vigoria_icone.svg"])
def test_copias_publicas_iguais(nome: str) -> None:
    assert (STATIC / nome).read_bytes() == (MARCA / nome).read_bytes()


@pytest.mark.parametrize("lado", TAMANHOS)
def test_icone_png_com_o_tamanho_certo(lado: int) -> None:
    with Image.open(STATIC / "icones" / f"icone-{lado}.png") as imagem:
        assert imagem.format == "PNG"
        assert imagem.size == (lado, lado)


def test_favicon_definido() -> None:
    """app.py passa a FAVICON a st.set_page_config e o ficheiro existe."""
    codigo = (RAIZ / "app.py").read_text(encoding="utf-8")
    arvore = ast.parse(codigo)
    chamadas = [
        n
        for n in ast.walk(arvore)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "set_page_config"
    ]
    assert len(chamadas) == 1
    icone = next(k.value for k in chamadas[0].keywords if k.arg == "page_icon")
    assert isinstance(icone, ast.Name) and icone.id == "FAVICON"
    assert (RAIZ / "static" / "icones" / "icone-32.png").is_file()
    assert '"icone-32.png"' in codigo


def test_manifesto_com_os_icones() -> None:
    manifesto = json.loads((RAIZ / "pwa" / "manifest.webmanifest").read_text(encoding="utf-8"))
    tamanhos = {i["sizes"] for i in manifesto["icons"]}
    assert {"192x192", "512x512"} <= tamanhos
    for i in manifesto["icons"]:
        ficheiro = RAIZ / i["src"].removeprefix("/app/")  # servido em app/static/
        assert ficheiro.is_file(), i["src"]
