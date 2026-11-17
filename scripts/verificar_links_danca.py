"""Confirma as ligações de conteudo/danca.yaml e lista as que falham (REGRAS §5.1, D7).

Vídeos e listas: pelo oEmbed do YouTube, que devolve o título e o canal. A página de um
canal (/@nome/playlists) não tem oEmbed: basta responder 200. Só lê os URL públicos do YAML;
não envia dados de ninguém. Depois de correr, atualizar à mão `verificado_em` no YAML.

    python scripts/verificar_links_danca.py
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from vigoria.conteudo.carregar import carregar_danca

OEMBED = "https://www.youtube.com/oembed?format=json&url="
AGENTE = "vigoria-verificar-links/1.0"
ESPERA_S = 15


def _pedir(url: str) -> tuple[int, bytes]:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(pedido, timeout=ESPERA_S) as resposta:
            return resposta.status, resposta.read()
    except urllib.error.HTTPError as erro:
        return erro.code, b""


def verificar(url: str) -> tuple[bool, str]:
    """(funciona, detalhe): o título e o canal do oEmbed, ou o código HTTP da falha."""
    try:
        if "/@" in url:
            estado, _ = _pedir(url)
            return estado == 200, f"página do canal (HTTP {estado})"
        estado, corpo = _pedir(OEMBED + urllib.parse.quote(url, safe=""))
        if estado != 200:
            return False, f"oEmbed HTTP {estado}"
        dados = json.loads(corpo)
        return True, f"{dados.get('title', '?')} — {dados.get('author_name', '?')}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erro:
        return False, f"erro: {erro}"


def main() -> int:
    # Os títulos do YouTube trazem emojis; a consola do Windows (cp1252) não os escreve.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    falhas = []
    for ligacao in carregar_danca().ligacoes:
        funciona, detalhe = verificar(ligacao.url)
        marca = "ok   " if funciona else "FALHA"
        print(f"{marca} [{ligacao.nivel}] {ligacao.titulo}\n      {ligacao.url}\n      {detalhe}")
        if not funciona:
            falhas.append(ligacao)
    print()
    if falhas:
        print(f"{len(falhas)} ligação(ões) com falha:")
        for ligacao in falhas:
            print(f"- {ligacao.titulo}: {ligacao.url}")
        return 1
    print("Todas as ligações responderam.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
