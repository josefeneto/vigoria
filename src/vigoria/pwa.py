"""Camada PWA (Fase 10): acrescenta ao index.html do Streamlit o manifesto e os ícones.

Corre ao construir a imagem Docker (python -m vigoria.pwa). O Streamlit não deixa juntar
<link> ao <head> e o Caddy normal não reescreve HTML; por isso, altera-se o ficheiro instalado.
Se uma versão nova do Streamlit mudar o index.html e o ponto de inserção desaparecer, a
construção falha com uma mensagem clara, em vez de publicar uma app que não se instala.
"""

import sys
from pathlib import Path

PONTO_INSERCAO = "<title>Streamlit</title>"
MARCA_INJECAO = "<!-- vigoria-pwa -->"
COR_TEMA = "#123F45"  # petróleo profundo (paginas/estilos.py, CORES; igual ao manifesto)

ETIQUETAS = f"""{MARCA_INJECAO}
    <link rel="manifest" href="/manifest.webmanifest" />
    <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
    <meta name="theme-color" content="{COR_TEMA}" />
    <meta name="mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-title" content="Vigoria" />
    <meta name="apple-mobile-web-app-status-bar-style" content="default" />
    """


class ErroInjecao(Exception):
    pass


def injetar(html: str) -> str:
    """O HTML com as etiquetas antes do <title>; sem alterações se já as tiver."""
    if MARCA_INJECAO in html:
        return html
    if html.count(PONTO_INSERCAO) != 1:
        raise ErroInjecao(
            f"O index.html do Streamlit não tem «{PONTO_INSERCAO}» (uma só vez). Uma versão "
            "nova do Streamlit mudou o ficheiro: atualize PONTO_INSERCAO em src/vigoria/pwa.py."
        )
    html = html.replace('<html lang="en">', '<html lang="pt-PT">', 1)
    return html.replace(PONTO_INSERCAO, ETIQUETAS + PONTO_INSERCAO, 1)


def index_streamlit() -> Path:
    import streamlit

    return Path(streamlit.__file__).parent / "static" / "index.html"


def principal(caminho: Path | None = None) -> int:
    caminho = index_streamlit() if caminho is None else caminho
    try:
        caminho.write_text(injetar(caminho.read_text(encoding="utf-8")), encoding="utf-8")
    except (ErroInjecao, OSError) as erro:
        print(f"pwa: ERRO: {erro}", file=sys.stderr)
        return 1
    print(f"pwa: etiquetas do manifesto em {caminho}")
    return 0


if __name__ == "__main__":
    sys.exit(principal(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
