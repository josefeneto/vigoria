# Fotografias da Vigoria

Enquanto uma fotografia não existir, a app mostra um marcador desenhado (fundo petróleo
com um rebento) no lugar das duas obrigatórias; a opcional simplesmente não aparece.

| Ficheiro final | Original a pôr em `originais/` | Tema | Tamanho |
|---|---|---|---|
| `inicio_topo.webp` | `inicio_topo.jpg` | Pessoa com 50 a 65 anos a treinar em casa (sala com luz natural, cadeira ou halteres leves, ar descontraído). Sem foco no corpo nem roupa de competição. | 1600×1067 (3:2) |
| `plano_topo.webp` | `plano_topo.jpg` | Sem pessoas: tapete, garrafa de água, ténis, halteres leves. | 1600×600 (8:3) |
| `questionario_fim.webp` (opcional) | `questionario_fim.jpg` | Pessoa ao ar livre (caminhar, alongar, beber água). Aparece enquanto o plano é preparado. **Vertical**: não é recortada, só reduzida para caber em 800×1200. | até 800×1200 (2:3) |

Regras: sem imagens de «antes e depois» nem mensagens de transformação corporal; nada que
pareça uma pessoa real a recomendar a app ou a fazer afirmações de saúde.

## Vídeo do topo do início

Original em `originais/inicio_video.mp4`. Resultado em `static/video/` (servido pela app):
`inicio.mp4` (1280 px, sem som, até 2,5 MB) e `inicio_capa.webp` (primeiro fotograma). Sem
vídeo convertido, o topo mostra `inicio_topo.webp`. Converter com
`python scripts/converter_video.py` (precisa do ffmpeg: `winget install ffmpeg`).

## Como converter

1. Pôr os JPG em `assets/img/originais/` com os nomes da tabela (a pasta não vai para o Git).
2. Correr, em PowerShell, com o ambiente ativado: `python scripts/converter_fotos.py`
   (recorta ao centro, reduz e grava em webp com até 200 KB).
3. Registar autor, ligação e licença em `docs/CREDITOS_IMAGENS.md`.
