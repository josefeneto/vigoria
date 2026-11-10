"""Ícones dos exercícios (Fase 5D): cópia para o PDF e folha de revisão.

Uso: python scripts/folha_icones.py

- Copia assets/icones/exercicios/*.svg para src/vigoria/exportacao/recursos/icones/
  (o PDF lê-os do pacote, como o logotipo; um teste confirma que as cópias são iguais).
- Gera saidas/icones_exercicios.html e .png (Playwright com o Chrome instalado): cada ícone
  a 96, 48 e 32 px, no fundo «argila», e a tabela exercício → ícone de exercicios.yaml.
"""

import base64
import shutil
import sys
from html import escape
from pathlib import Path

from playwright.sync_api import sync_playwright

from vigoria.conteudo.carregar import IconeExercicio, carregar_exercicios

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))  # para importar paginas/ (cores da marca)
from paginas.estilos import CORES  # noqa: E402

ORIGEM = RAIZ / "assets" / "icones" / "exercicios"
DESTINO = RAIZ / "src" / "vigoria" / "exportacao" / "recursos" / "icones"
SAIDAS = RAIZ / "saidas"


def copiar() -> None:
    DESTINO.mkdir(exist_ok=True)
    for svg in sorted(ORIGEM.glob("*.svg")):
        shutil.copyfile(svg, DESTINO / svg.name)
        print(f"  {DESTINO.relative_to(RAIZ) / svg.name}")


def _img(nome: str, px: int) -> str:
    svg = (ORIGEM / f"{nome}.svg").read_text(encoding="utf-8")
    svg = svg.replace("currentColor", CORES["principal_profundo"])
    svg = svg.replace('class="d"', f'stroke="{CORES["terracota"]}"')
    dados = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    lado = round(px * 64 / 48)
    return (
        f'<span class="t" style="width:{lado}px;height:{lado}px;border-radius:{lado // 4}px">'
        f'<img src="data:image/svg+xml;base64,{dados}" width="{px}" height="{px}" alt=""></span>'
    )


def folha() -> None:
    exercicios = carregar_exercicios().values()
    celulas = "".join(
        f'<div class="c">{_img(i, 96)}<div class="p">{_img(i, 48)}{_img(i, 32)}</div>'
        f"<b>{i}</b></div>"
        for i in IconeExercicio
    )
    linhas = "".join(
        f"<tr><td>{_img(i, 32)}</td><td><b>{i}</b></td><td>"
        + "<br>".join(
            escape(x.nome) + ("" if x.nivel == "base" else f" <i>({x.nivel})</i>")
            for x in exercicios
            if x.icone == i
        )
        + "</td></tr>"
        for i in IconeExercicio
    )
    html = f"""<!doctype html><html lang="pt-PT"><meta charset="utf-8">
<title>Ícones dos exercícios</title>
<style>body{{font-family:system-ui,sans-serif;background:{CORES["fundo"]};color:{CORES["texto"]};
margin:24px;width:1200px}}h1{{color:{CORES["principal_profundo"]}}}
.g{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}}
.c{{background:{CORES["cartao"]};border:1px solid {CORES["borda"]};border-radius:16px;padding:12px;
display:flex;flex-direction:column;align-items:center;gap:8px}}
.t{{background:{CORES["argila"]};display:inline-flex;align-items:center;justify-content:center}}
.p{{display:flex;gap:10px;align-items:center}}
table{{border-collapse:collapse;margin-top:24px;background:{CORES["cartao"]}}}
td{{border-bottom:1px solid {CORES["borda"]};padding:6px 12px;vertical-align:middle}}</style>
<h1>Ícones dos exercícios</h1><p>Cada ícone a 96, 48 e 32 px, no fundo «argila».</p>
<div class="g">{celulas}</div><table>{linhas}</table></html>"""
    SAIDAS.mkdir(exist_ok=True)
    pagina = SAIDAS / "icones_exercicios.html"
    pagina.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        aba = browser.new_page(viewport={"width": 1250, "height": 800})
        aba.goto(pagina.as_uri())
        aba.screenshot(path=str(SAIDAS / "icones_exercicios.png"), full_page=True)
        browser.close()
    print(f"  {pagina.relative_to(RAIZ)} e .png")


if __name__ == "__main__":
    copiar()
    folha()
