"""Converte as fotografias originais (JPG) em webp para a app, com o Pillow.

Os originais ficam em assets/img/originais/ (fora do Git) com o nome do destino:
inicio_topo.jpg, plano_topo.jpg e questionario_fim.jpg. Cada um é recortado ao centro
para a proporção certa, reduzido ao tamanho indicado e gravado em assets/img/<nome>.webp
com até 200 KB (a qualidade desce até caber).

    python scripts/converter_fotos.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageOps

RAIZ = Path(__file__).resolve().parents[1]
ORIGINAIS = RAIZ / "assets" / "img" / "originais"
DESTINO = RAIZ / "assets" / "img"
MAXIMO_BYTES = 200 * 1024
TAMANHOS = {
    "inicio_topo": (1600, 1067),
    "plano_topo": (1600, 600),
    "questionario_fim": (1200, 800),
}
EXTENSOES = (".jpg", ".jpeg", ".JPG", ".JPEG", ".png", ".webp")


def _original(nome: str) -> Path | None:
    return next((p for e in EXTENSOES if (p := ORIGINAIS / f"{nome}{e}").exists()), None)


def converter(origem: Path, destino: Path, tamanho: tuple[int, int]) -> tuple[int, int]:
    """Recorta, reduz e grava em webp; devolve (bytes, qualidade usada)."""
    with Image.open(origem) as imagem:
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")  # rodar como a máquina gravou
        imagem = ImageOps.fit(imagem, tamanho, method=Image.Resampling.LANCZOS)
        for qualidade in range(82, 39, -4):
            imagem.save(destino, "WEBP", quality=qualidade, method=6)
            if destino.stat().st_size <= MAXIMO_BYTES:
                return destino.stat().st_size, qualidade
    destino.unlink()
    raise ValueError(f"{origem.name}: não cabe em 200 KB nem com qualidade 40")


def main() -> None:
    if not ORIGINAIS.exists():
        sys.exit(f"Não encontrei a pasta {ORIGINAIS.relative_to(RAIZ)}.")
    for nome, tamanho in TAMANHOS.items():
        origem = _original(nome)
        if origem is None:
            print(f"  {nome}: sem original (fica o marcador)")
            continue
        destino = DESTINO / f"{nome}.webp"
        tamanho_bytes, qualidade = converter(origem, destino, tamanho)
        print(
            f"  {destino.relative_to(RAIZ)}: {tamanho[0]}×{tamanho[1]}, "
            f"{tamanho_bytes // 1024} KB, qualidade {qualidade}"
        )


if __name__ == "__main__":
    main()
