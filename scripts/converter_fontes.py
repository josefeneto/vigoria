"""Prepara os recursos do PDF em src/vigoria/exportacao/recursos/: letras em TTF e logotipo.

As letras vêm de static/fontes/*.woff2: o fpdf2 só lê .woff2 com a brotli instalada em produção;
em TTF, não precisa dela. O logotipo é cópia de assets/marca/ (um teste confirma que é igual).
Corre-se uma vez, e de novo se as letras ou o logotipo mudarem; tudo fica no Git e no pacote.
Licença OFL: static/fontes/OFL*.txt (copiadas também).

    python scripts/converter_fontes.py
"""

import shutil
from pathlib import Path

from fontTools.ttLib import TTFont

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "static" / "fontes"
DESTINO = RAIZ / "src" / "vigoria" / "exportacao" / "recursos"
LOGOTIPO = RAIZ / "assets" / "marca" / "vigoria_logo.svg"
LETRAS = {
    "atkinson-hyperlegible-next-latin-400-normal.woff2": "Atkinson-Regular.ttf",
    "atkinson-hyperlegible-next-latin-400-italic.woff2": "Atkinson-Italic.ttf",
    "atkinson-hyperlegible-next-latin-700-normal.woff2": "Atkinson-Bold.ttf",
    "fraunces-latin-600-normal.woff2": "Fraunces-SemiBold.ttf",
    "fraunces-latin-700-normal.woff2": "Fraunces-Bold.ttf",
}


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for origem, destino in LETRAS.items():
        letra = TTFont(ORIGEM / origem)
        letra.flavor = None  # sem compressão WOFF2: TTF normal
        letra.save(DESTINO / destino)
        print(destino)
    for licenca in ("OFL.txt", "OFL-Fraunces.txt"):
        shutil.copy(ORIGEM / licenca, DESTINO / licenca)
    shutil.copy(LOGOTIPO, DESTINO / LOGOTIPO.name)


if __name__ == "__main__":
    main()
