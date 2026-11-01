"""Converte o vídeo do topo do início para a app, com o ffmpeg.

O original fica em assets/img/originais/inicio_video.mp4 (fora do Git). O resultado vai
para static/video/ (servido pela app em app/static/video/):

- inicio.mp4: 1280 px de largura, H.264, sem som, pronto a começar antes de acabar de
  descarregar (faststart), com até 2,5 MB (a compressão sobe até caber);
- inicio_capa.webp: o primeiro fotograma, mostrado enquanto o vídeo carrega e a quem
  pede menos movimento no sistema (até 120 KB).

O ffmpeg instala-se com «winget install ffmpeg» (abrir um terminal novo a seguir).

    python scripts/converter_video.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ORIGINAL = RAIZ / "assets" / "img" / "originais" / "inicio_video.mp4"
DESTINO = RAIZ / "static" / "video"
MAXIMO_VIDEO = int(2.5 * 1024 * 1024)
MAXIMO_CAPA = 120 * 1024
LARGURA = 1280


def _ffmpeg() -> str:
    caminho = shutil.which("ffmpeg")
    if caminho is None:
        sys.exit(
            "Não encontrei o ffmpeg: instale-o com «winget install ffmpeg» e abra outro terminal."
        )
    return caminho


def converter_video(ffmpeg: str, origem: Path, destino: Path) -> tuple[int, int]:
    """Grava o vídeo sem som; devolve (bytes, CRF usado). Mais CRF = mais compressão."""
    for crf in (26, 28, 30, 32):
        comando = [ffmpeg, "-v", "error", "-y", "-i", str(origem), "-an"]
        comando += ["-vf", f"scale={LARGURA}:-2:flags=lanczos,format=yuv420p"]
        comando += ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-profile:v", "high"]
        comando += ["-movflags", "+faststart", str(destino)]
        subprocess.run(comando, check=True)
        if destino.stat().st_size <= MAXIMO_VIDEO:
            return destino.stat().st_size, crf
    destino.unlink()
    raise ValueError(f"{origem.name}: não cabe em 2,5 MB nem com CRF 32")


def converter_capa(ffmpeg: str, origem: Path, destino: Path) -> int:
    """Primeiro fotograma do vídeo já convertido, em webp; devolve os bytes."""
    with tempfile.TemporaryDirectory() as pasta:
        png = Path(pasta) / "capa.png"
        comando = [ffmpeg, "-v", "error", "-y", "-i", str(origem), "-frames:v", "1", str(png)]
        subprocess.run(comando, check=True)
        with Image.open(png) as imagem:
            for qualidade in range(80, 39, -5):
                imagem.convert("RGB").save(destino, "WEBP", quality=qualidade, method=6)
                if destino.stat().st_size <= MAXIMO_CAPA:
                    return destino.stat().st_size
    destino.unlink()
    raise ValueError("A capa não cabe em 120 KB")


def main() -> None:
    if not ORIGINAL.exists():
        sys.exit(f"Não encontrei {ORIGINAL.relative_to(RAIZ)}.")
    ffmpeg = _ffmpeg()
    DESTINO.mkdir(parents=True, exist_ok=True)
    video = DESTINO / "inicio.mp4"
    tamanho, crf = converter_video(ffmpeg, ORIGINAL, video)
    print(f"  {video.relative_to(RAIZ)}: {tamanho // 1024} KB, CRF {crf}")
    capa = DESTINO / "inicio_capa.webp"
    print(f"  {capa.relative_to(RAIZ)}: {converter_capa(ffmpeg, video, capa) // 1024} KB")


if __name__ == "__main__":
    main()
