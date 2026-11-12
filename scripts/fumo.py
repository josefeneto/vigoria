"""Teste de fumo da imagem Docker ou do Railway (Fase 10): só leituras, sem login.

Uso (PowerShell): python scripts/fumo.py http://localhost:8080
                  python scripts/fumo.py https://app.vigoria.pt

Confirma: página inicial com o manifesto, manifesto válido, ícones, verificação de saúde do
Streamlit (atravessa o Caddy) e cabeçalhos de segurança. Sai com código 1 se algo falhar.
"""

import sys

import httpx

CABECALHOS = {
    "strict-transport-security": "max-age=31536000",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}


def verificar(base: str) -> list[str]:
    falhas: list[str] = []
    with httpx.Client(base_url=base.rstrip("/"), timeout=20, follow_redirects=True) as c:
        inicio = c.get("/")
        if inicio.status_code != 200:
            falhas.append(f"/ respondeu {inicio.status_code}")
        elif 'rel="manifest"' not in inicio.text:
            falhas.append("/ não tem a ligação ao manifesto (vigoria.pwa não correu?)")
        for nome, valor in CABECALHOS.items():
            recebido = inicio.headers.get(nome)
            if recebido != valor:
                falhas.append(f"cabeçalho {nome}: {recebido!r}, devia ser {valor!r}")

        manifesto = c.get("/manifest.webmanifest")
        try:
            dados = manifesto.json()
            if dados.get("name") != "Vigoria" or dados.get("display") != "standalone":
                falhas.append("manifesto sem name=Vigoria ou display=standalone")
            for icone in dados.get("icons", []):
                if c.get(icone["src"]).status_code != 200:
                    falhas.append(f"ícone em falta: {icone['src']}")
        except ValueError:
            falhas.append(f"/manifest.webmanifest não é JSON (HTTP {manifesto.status_code})")
        if "manifest+json" not in manifesto.headers.get("content-type", ""):
            falhas.append("manifesto sem Content-Type application/manifest+json")

        for caminho in ("/apple-touch-icon.png", "/favicon.ico"):
            if c.get(caminho).status_code != 200:
                falhas.append(f"{caminho} em falta")

        saude = c.get("/_stcore/health")
        if saude.status_code != 200 or saude.text.strip() != "ok":
            falhas.append(f"/_stcore/health: HTTP {saude.status_code}, {saude.text[:40]!r}")
    return falhas


def principal() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    try:
        falhas = verificar(sys.argv[1])
    except httpx.HTTPError as erro:
        print(f"FALHOU: sem ligação a {sys.argv[1]} ({type(erro).__name__})")
        return 1
    for falha in falhas:
        print(f"FALHOU: {falha}")
    if not falhas:
        print("OK: página inicial, manifesto, ícones, saúde e cabeçalhos")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(principal())
