"""Converte os vídeos do topo do início para a app, com o ffmpeg.

Os originais ficam em assets/img/originais/ (fora do Git); alternam no topo do início
(um homem e uma mulher). Para cada um, o resultado vai para static/video/ (servido pela
app em app/static/video/):

- <nome>.mp4: 1280 px de largura, H.264, sem som, pronto a começar antes de acabar de
  descarregar (faststart), com até 2,5 MB (a compressão sobe até caber);
- <nome>_capa.webp: o primeiro fotograma, mostrado enquanto o vídeo carrega e a quem
  pede menos movimento no sistema (até 120 KB).

O ffmpeg instala-se com «winget install ffmpeg» (abrir um terminal novo a seguir).

    python scripts/converter_video.py                 # todos
    python scripts/converter_video.py inicio_mulher   # só um (pelo nome de destino)
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ORIGINAIS = RAIZ / "assets" / "img" / "originais"
VIDEOS = {  # nome de destino: (original, segundo do fotograma da capa)
    "inicio": ("inicio_video.mp4", 0.0),
    "inicio_mulher": ("inicio_video_mulher.mp4", 10.0),  # no início só se veem as pernas
}
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


def converter_capa(ffmpeg: str, origem: Path, destino: Path, segundo: float = 0.0) -> int:
    """Um fotograma do vídeo já convertido (o primeiro, por omissão), em webp; devolve os bytes."""
    with tempfile.TemporaryDirectory() as pasta:
        png = Path(pasta) / "capa.png"
        comando = [ffmpeg, "-v", "error", "-y", "-ss", str(segundo), "-i", str(origem)]
        comando += ["-frames:v", "1", str(png)]
        subprocess.run(comando, check=True)
        with Image.open(png) as imagem:
            for qualidade in range(80, 39, -5):
                imagem.convert("RGB").save(destino, "WEBP", quality=qualidade, method=6)
                if destino.stat().st_size <= MAXIMO_CAPA:
                    return destino.stat().st_size
    destino.unlink()
    raise ValueError("A capa não cabe em 120 KB")


def main() -> None:
    nomes = sys.argv[1:] or list(VIDEOS)
    if desconhecidos := [n for n in nomes if n not in VIDEOS]:
        sys.exit(f"Nomes desconhecidos: {', '.join(desconhecidos)} (válidos: {', '.join(VIDEOS)}).")
    ffmpeg = _ffmpeg()
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome in nomes:
        nome_original, segundo_capa = VIDEOS[nome]
        original = ORIGINAIS / nome_original
        if not original.exists():
            sys.exit(f"Não encontrei {original.relative_to(RAIZ)}.")
        video = DESTINO / f"{nome}.mp4"
        tamanho, crf = converter_video(ffmpeg, original, video)
        print(f"  {video.relative_to(RAIZ)}: {tamanho // 1024} KB, CRF {crf}")
        capa = DESTINO / f"{nome}_capa.webp"
        tamanho_capa = converter_capa(ffmpeg, video, capa, segundo_capa)
        print(f"  {capa.relative_to(RAIZ)}: {tamanho_capa // 1024} KB")


if __name__ == "__main__":
    main()
