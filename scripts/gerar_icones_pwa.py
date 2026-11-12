"""Ícones da camada PWA (Fase 10), a partir de static/icones/icone-512.png.

Uso (PowerShell, na raiz do projeto): python scripts/gerar_icones_pwa.py

Gera em pwa/ (servidos pelo Caddy na raiz do site):
- icones/icone-192.png e icones/icone-512.png: o ícone tal como está (cantos transparentes);
- icones/icone-maskable-512.png: fundo cheio e símbolo dentro da zona segura (80 %), para o
  Android recortar à sua maneira;
- apple-touch-icon.png (180 px): fundo cheio, porque o iPhone pinta de preto os cantos
  transparentes e arredonda ele próprio;
- favicon.ico (16, 32 e 48 px).
"""

from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "static" / "icones" / "icone-512.png"
PWA = RAIZ / "pwa"
FUNDO = (0x12, 0x3F, 0x45, 255)  # petróleo profundo, a cor de fundo do próprio ícone
ZONA_SEGURA = 0.8


def cheio(icone: Image.Image, lado: int, escala: float) -> Image.Image:
    """O ícone reduzido e centrado num quadrado de fundo cheio."""
    tela = Image.new("RGBA", (lado, lado), FUNDO)
    interior = round(lado * escala)
    reduzido = icone.resize((interior, interior), Image.Resampling.LANCZOS)
    margem = (lado - interior) // 2
    tela.alpha_composite(reduzido, (margem, margem))
    return tela


def principal() -> None:
    icone = Image.open(ORIGEM).convert("RGBA")
    (PWA / "icones").mkdir(parents=True, exist_ok=True)
    for lado in (192, 512):
        destino = PWA / "icones" / f"icone-{lado}.png"
        icone.resize((lado, lado), Image.Resampling.LANCZOS).save(destino, optimize=True)
        print(f"  pwa/icones/icone-{lado}.png")
    cheio(icone, 512, ZONA_SEGURA).save(PWA / "icones" / "icone-maskable-512.png", optimize=True)
    print("  pwa/icones/icone-maskable-512.png")
    cheio(icone, 180, 1.0).convert("RGB").save(PWA / "apple-touch-icon.png", optimize=True)
    print("  pwa/apple-touch-icon.png")
    icone.save(PWA / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("  pwa/favicon.ico")


if __name__ == "__main__":
    principal()
