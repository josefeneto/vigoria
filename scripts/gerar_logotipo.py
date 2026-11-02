"""Gera o logotipo completo e os ícones PNG da Vigoria, só em desenvolvimento.

- assets/marca/vigoria_logo.svg e vigoria_logo_claro.svg: símbolo (sem alterações) + a palavra
  «Vigoria» em Fraunces 700 convertida em contornos (não depende da letra estar instalada).
- static/icones/icone-{32,180,192,512}.png a partir de assets/marca/vigoria_icone.svg (Chrome).
- static/vigoria_logo.svg e static/vigoria_icone.svg: cópias com endereço público.

Unidades do logotipo: 1 em = 100, ou seja, a palavra em letra de N px ocupa N/100 por unidade.

    python scripts/gerar_logotipo.py
"""

import re
import shutil
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
MARCA = RAIZ / "assets" / "marca"
STATIC = RAIZ / "static"
LETRA = STATIC / "fontes" / "fraunces-latin-700-normal.woff2"
PALAVRA = "Vigoria"
CORES = {"vigoria_logo": ("vigoria_simbolo.svg", "#123F45"),
         "vigoria_logo_claro": ("vigoria_simbolo_claro.svg", "#F7F3EC")}  # fmt: skip
TAMANHOS_PNG = (32, 180, 192, 512)

EM = 100  # unidades do SVG por em
# Parte visível do símbolo na sua caixa 64×64 (traço de 9 com pontas redondas e círculo):
# x de 5,5 a 59; o círculo começa em y = 3, o «V» vai de y = 13,5 (pontas) a 56,5 (vértice).
SIMBOLO_X, SIMBOLO_LARGURA, SIMBOLO_TOPO = 5.5, 53.5, 3.0
V_TOPO, V_FUNDO = 13.5, 56.5
ESPACO = 16  # entre o símbolo e a palavra


def _kerning(fonte: TTFont, esquerda: str, direita: str) -> int:
    """Acerto horizontal entre dois glifos (GPOS «kern», PairPos formatos 1 e 2)."""
    for lookup in fonte["GPOS"].table.LookupList.Lookup:
        if lookup.LookupType != 2:
            continue
        for sub in lookup.SubTable:
            if esquerda not in sub.Coverage.glyphs:
                continue
            if sub.Format == 1:
                indice = sub.Coverage.glyphs.index(esquerda)
                for par in sub.PairSet[indice].PairValueRecord:
                    if par.SecondGlyph == direita and par.Value1 is not None:
                        return getattr(par.Value1, "XAdvance", 0) or 0
            else:
                c1 = sub.ClassDef1.classDefs.get(esquerda, 0)
                c2 = sub.ClassDef2.classDefs.get(direita, 0)
                valor = sub.Class1Record[c1].Class2Record[c2].Value1
                if valor is not None and getattr(valor, "XAdvance", 0):
                    return valor.XAdvance
    return 0


def _palavra() -> tuple[str, float, float, float, float, float]:
    """Caminho SVG da palavra com a linha de base em y = 0 (y para baixo), os limites x/y
    e a altura das maiúsculas."""
    fonte = TTFont(LETRA)
    glifos = fonte.getGlyphSet()
    mapa = fonte.getBestCmap()
    escala = EM / fonte["head"].unitsPerEm
    nomes = [mapa[ord(c)] for c in PALAVRA]
    caneta = SVGPathPen(glifos, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    limites = BoundsPen(glifos)
    x = 0.0
    for i, nome in enumerate(nomes):
        transformacao = (escala, 0, 0, -escala, x * escala, 0)
        glifos[nome].draw(TransformPen(caneta, transformacao))
        glifos[nome].draw(TransformPen(limites, transformacao))
        x += glifos[nome].width
        if i + 1 < len(nomes):
            x += _kerning(fonte, nome, nomes[i + 1])
    xmin, ymin, xmax, ymax = limites.bounds
    maiusculas = fonte["OS/2"].sCapHeight * escala
    return caneta.getCommands(), xmin, xmax, ymin, ymax, maiusculas


def _simbolo(ficheiro: str) -> str:
    """Conteúdo do SVG do símbolo, tal como está (sem o elemento <svg>)."""
    texto = (MARCA / ficheiro).read_text(encoding="utf-8")
    return re.search(r"<svg[^>]*>(.*)</svg>", texto, re.S).group(1).strip()


def gerar_logotipos() -> None:
    caminho, xmin, xmax, ymin, ymax, maiusculas = _palavra()
    # O «V» do símbolo alinha como uma letra: vértice na linha de base, pontas à altura das
    # maiúsculas; o círculo fica por cima, como o pingo do «i».
    escala = maiusculas / (V_FUNDO - V_TOPO)
    base = max(-ymin, (V_FUNDO - SIMBOLO_TOPO) * escala)  # y da linha de base no SVG
    altura = base + ymax
    y_simbolo = base - V_FUNDO * escala
    x_palavra = SIMBOLO_LARGURA * escala + ESPACO - xmin
    largura = x_palavra + xmax
    for nome, (ficheiro, cor) in CORES.items():
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura:.1f} {altura:.1f}" '
            f'width="{largura:.0f}" height="{altura:.0f}" role="img" aria-label="Vigoria">\n'
            f'  <g transform="translate({-SIMBOLO_X * escala:.2f} {y_simbolo:.2f}) '
            f'scale({escala:.4f})">\n'
            f"    {_simbolo(ficheiro)}\n  </g>\n"
            f'  <path transform="translate({x_palavra:.2f} {base:.2f})" fill="{cor}" '
            f'd="{caminho}"/>\n</svg>\n'
        )
        (MARCA / f"{nome}.svg").write_text(svg, encoding="utf-8", newline="\n")
        print(f"  assets/marca/{nome}.svg ({largura:.0f}×{altura:.0f}, 1 em = {EM})")


def gerar_pngs() -> None:
    destino = STATIC / "icones"
    destino.mkdir(exist_ok=True)
    svg = (MARCA / "vigoria_icone.svg").read_text(encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for lado in TAMANHOS_PNG:
            page = browser.new_page(viewport={"width": lado, "height": lado})
            # Só no elemento <svg>: o retângulo de fundo também tem width/height.
            estilo = f"*{{margin:0}}svg{{display:block;width:{lado}px;height:{lado}px}}"
            page.set_content(f"<style>{estilo}</style>{svg}")
            page.screenshot(path=str(destino / f"icone-{lado}.png"), omit_background=True)
            page.close()
            print(f"  static/icones/icone-{lado}.png")
        browser.close()


def copiar_publicos() -> None:
    for nome in ("vigoria_icone.svg", "vigoria_logo.svg"):
        shutil.copyfile(MARCA / nome, STATIC / nome)
        print(f"  static/{nome}")


if __name__ == "__main__":
    gerar_logotipos()
    gerar_pngs()
    copiar_publicos()
