"""Converte as fotografias originais (JPG) em webp para a app, com o Pillow.

Os originais ficam em assets/img/originais/ (fora do Git) com o nome do destino:
inicio_topo.jpg, plano_topo.jpg e questionario_fim.jpg. As faixas horizontais são
recortadas ao centro para a proporção certa; a fotografia vertical do fim do questionário
não é recortada, só reduzida para caber no tamanho indicado. Cada uma é gravada em
assets/img/<nome>.webp com até 200 KB (a qualidade desce até caber).

    python scripts/converter_fotos.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageOps

RAIZ = Path(__file__).resolve().parents[1]
ORIGINAIS = RAIZ / "assets" / "img" / "originais"
DESTINO = RAIZ / "assets" / "img"
MAXIMO_BYTES = 200 * 1024
# nome: (largura, altura, recortar). Sem recorte, a imagem fica dentro da caixa, na sua proporção.
TAMANHOS = {
    "inicio_topo": (1600, 1067, True),
    "plano_topo": (1600, 600, True),
    "questionario_fim": (800, 1200, False),  # vertical (2:3)
}
EXTENSOES = (".jpg", ".jpeg", ".JPG", ".JPEG", ".png", ".webp")


def _original(nome: str) -> Path | None:
    return next((p for e in EXTENSOES if (p := ORIGINAIS / f"{nome}{e}").exists()), None)


def converter(
    origem: Path, destino: Path, tamanho: tuple[int, int], recortar: bool = True
) -> tuple[int, int, tuple[int, int]]:
    """Recorta (ou só reduz), grava em webp; devolve (bytes, qualidade, tamanho final)."""
    with Image.open(origem) as imagem:
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")  # rodar como a máquina gravou
        if recortar:
            imagem = ImageOps.fit(imagem, tamanho, method=Image.Resampling.LANCZOS)
        else:
            imagem = ImageOps.contain(imagem, tamanho, method=Image.Resampling.LANCZOS)
        for qualidade in range(82, 39, -4):
            imagem.save(destino, "WEBP", quality=qualidade, method=6)
            if destino.stat().st_size <= MAXIMO_BYTES:
                return destino.stat().st_size, qualidade, imagem.size
    destino.unlink()
    raise ValueError(f"{origem.name}: não cabe em 200 KB nem com qualidade 40")


def main() -> None:
    if not ORIGINAIS.exists():
        sys.exit(f"Não encontrei a pasta {ORIGINAIS.relative_to(RAIZ)}.")
    for nome, (largura, altura, recortar) in TAMANHOS.items():
        origem = _original(nome)
        if origem is None:
            print(f"  {nome}: sem original (fica o marcador)")
            continue
        destino = DESTINO / f"{nome}.webp"
        tamanho_bytes, qualidade, final = converter(origem, destino, (largura, altura), recortar)
        print(
            f"  {destino.relative_to(RAIZ)}: {final[0]}×{final[1]}, "
            f"{tamanho_bytes // 1024} KB, qualidade {qualidade}"
        )


if __name__ == "__main__":
    main()
