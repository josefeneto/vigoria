"""Componentes visuais da Vigoria: HTML com as classes .v-* de estilos.py.

Só aspeto: recebem textos já decididos e devolvem HTML. Todo o texto passa por
html.escape (o do plano pode vir da LLM). Os ícones são decorativos (aria-hidden).
"""

import base64
from collections.abc import Iterable
from functools import cache
from html import escape
from pathlib import Path

import streamlit as st

from paginas.estilos import ICONES_ATIVIDADES, RAIZ, icone

PASTA_FOTOS = RAIZ / "assets" / "img"
PASTA_MARCA = RAIZ / "assets" / "marca"
PASTA_VIDEO = RAIZ / "static" / "video"  # servida em app/static/video/
# Vídeos do topo do início, que alternam (um homem e uma mulher): scripts/converter_video.py.
VIDEOS_TOPO = ("inicio", "inicio_mulher")
CAPA_VIDEO = PASTA_VIDEO / "inicio_capa.webp"

# Vídeos do topo do início: sem som, um a seguir ao outro em ciclo, com capa e botão de pausa
# (WCAG 2.2.2). Só arrancam por código e só se o sistema não pedir menos movimento; sem
# código, fica a capa. O segundo só começa a descarregar quando o primeiro já está a passar.
# A capa do primeiro vai embutida como fundo da caixa: vê-se mesmo que o servidor demore ou
# os vídeos falhem (no Community Cloud, logo a seguir a entrar ou sair); um vídeo com erro
# sai do ciclo e, sem nenhum, saem também o botão e os vídeos.
_UM_VIDEO = """<video muted playsinline preload="%(preload)s" poster="%(poster)s"
 aria-label="%(descricao)s"><source src="app/static/video/%(nome)s.mp4" type="video/mp4"></video>"""
_VIDEO = """<div class="v-video" style="background-image:url(%(capa)s)">
%(videos)s
<button type="button" class="v-video-botao" data-pausar="%(pausar)s"
 data-reproduzir="%(reproduzir)s">%(reproduzir)s</button></div>
<script>
(() => {
  const menos = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll(".v-video:not([data-pronto])").forEach((caixa) => {
    caixa.dataset.pronto = "1";
    const botao = caixa.querySelector("button");
    let videos = [...caixa.querySelectorAll("video")];
    let atual = videos[0];
    const mostrar = (aCorrer) => {
      botao.textContent = aCorrer ? botao.dataset.pausar : botao.dataset.reproduzir;
      botao.classList.toggle("a-correr", aCorrer);
    };
    const tocar = (video) => video.play().then(() => mostrar(true)).catch(() => mostrar(false));
    const visivel = (video) => videos.forEach((v) => {
      v.classList.toggle("visivel", v === video);
      v.setAttribute("aria-hidden", v === video ? "false" : "true");
    });
    const seguinte = () => {
      const proximo = videos[(videos.indexOf(atual) + 1) %% videos.length];
      proximo.currentTime = 0;
      atual = proximo;
      visivel(atual);
      tocar(atual);
    };
    const falhou = (video) => {
      videos = videos.filter((v) => v !== video);
      video.remove();
      if (!videos.length) { botao.remove(); return; }
      if (video === atual) { atual = videos[0]; visivel(atual); if (!menos) tocar(atual); }
    };
    videos.forEach((video) => {
      video.querySelector("source").addEventListener("error", () => falhou(video));
      video.addEventListener("error", () => falhou(video));
      video.addEventListener("ended", seguinte);
    });
    // O segundo vídeo só se descarrega depois de o primeiro começar (poupa dados no telemóvel).
    videos[0].addEventListener("playing", () => videos.slice(1).forEach((v) => {
      if (v.preload === "none") { v.preload = "auto"; v.load(); }
    }), { once: true });
    botao.addEventListener("click", () => {
      if (atual.paused) { tocar(atual); } else { atual.pause(); mostrar(false); }
    });
    visivel(atual);
    if (!menos) tocar(atual);
  });
})();
</script>"""


@cache
def logotipo(alt: str, *, claro: bool = False, grande: bool = False) -> str:
    """Logotipo completo (assets/marca/, gerado por scripts/gerar_logotipo.py) como <img>.

    claro: para fundos escuros. grande: o do topo do início; sem ele, o dos topos das páginas.
    """
    nome = "vigoria_logo_claro.svg" if claro else "vigoria_logo.svg"
    dados = base64.b64encode((PASTA_MARCA / nome).read_bytes()).decode("ascii")
    classe = "v-logo v-logo-grande" if grande else "v-logo"
    return f'<img class="{classe}" src="data:image/svg+xml;base64,{dados}" alt="{escape(alt)}">'


def _icone(nome: str, cor: str = "principal", destaque: str = "terracota") -> str:
    return f'<span class="v-icone">{icone(nome, cor, destaque)}</span>'


def fotografia(
    nome: str,
    alt: str,
    *,
    proporcao: str = "3 / 2",
    marcador: bool = True,
    largura_maxima: int | None = None,
) -> None:
    """Fotografia de assets/img/<nome>.webp; sem ela, um marcador desenhado (ou nada).

    Com largura_maxima (fotografias verticais), fica centrada e nunca mais larga do que isso.
    """
    caminho: Path = PASTA_FOTOS / f"{nome}.webp"
    if caminho.exists():
        with st.container(key=f"foto_{nome}", horizontal_alignment="center"):
            st.image(str(caminho), width=largura_maxima or "stretch", alt=alt)
    elif marcador:
        desenho = icone("rebento", "nevoa", "pessego")
        st.html(f'<div class="v-marcador" style="--proporcao:{proporcao}">{desenho}</div>')


def video_topo(descricoes: tuple[str, ...], pausar: str, reproduzir: str) -> bool:
    """Vídeos do topo do início, que alternam; False se ainda não houver nenhum convertido.

    `descricoes`: uma por vídeo de VIDEOS_TOPO, pela mesma ordem (para leitores de ecrã).
    """
    existentes = [
        (nome, descricao)
        for nome, descricao in zip(VIDEOS_TOPO, descricoes, strict=True)
        if (PASTA_VIDEO / f"{nome}.mp4").exists()
    ]
    if not existentes or not CAPA_VIDEO.exists():
        return False
    videos = "\n".join(
        _UM_VIDEO
        % {
            "nome": nome,
            "descricao": escape(descricao),
            "preload": "auto" if i == 0 else "none",
            "poster": f"app/static/video/{nome}_capa.webp",
        }
        for i, (nome, descricao) in enumerate(existentes)
    )
    st.html(
        _VIDEO
        % {
            "capa": _capa_video(),
            "videos": videos,
            "pausar": escape(pausar),
            "reproduzir": escape(reproduzir),
        },
        unsafe_allow_javascript=True,
    )
    return True


@cache
def _capa_video() -> str:
    """A capa do primeiro vídeo como data URI (cerca de 40 KB): não depende de outro pedido."""
    dados = base64.b64encode(CAPA_VIDEO.read_bytes()).decode("ascii")
    return f"data:image/webp;base64,{dados}"


def cabecalho_passo(nome_icone: str, rotulo: str, titulo: str, indice: int, total: int) -> str:
    """Ícone, «Passo n de total», título e barra de progresso em segmentos."""
    segmentos = "".join(
        f'<span class="{"feito" if i < indice else "atual" if i == indice else ""}"></span>'
        for i in range(total)
    )
    return (
        f'<div class="v-passo">{_icone(nome_icone)}<div>'
        f'<p class="v-passo-n">{escape(rotulo)}</p><h1>{escape(titulo)}</h1></div></div>'
        f'<div class="v-barra" role="progressbar" aria-label="{escape(rotulo)}" '
        f'aria-valuemin="1" aria-valuemax="{total}" aria-valuenow="{indice + 1}" '
        f'style="--total:{total}">{segmentos}</div>'
    )


def cartoes(itens: Iterable[tuple[str, str, str]], colunas: int = 3) -> str:
    """Cartões com ícone, título e texto: (ícone, título, texto)."""
    corpo = "".join(
        f'<div class="v-cartao">{_icone(i)}<h3>{escape(titulo)}</h3><p>{escape(texto)}</p></div>'
        for i, titulo, texto in itens
    )
    return f'<div class="v-grelha v-grelha-{colunas}">{corpo}</div>'


def numeros(itens: Iterable[tuple[str, str, str]]) -> str:
    """Cartão de topo do plano: (ícone, rótulo, valor)."""
    corpo = "".join(
        f'<div class="v-numero">{_icone(i, "fundo", "pessego")}<div>'
        f'<p class="v-numero-rotulo">{escape(rotulo)}</p>'
        f'<p class="v-numero-valor">{escape(valor)}</p></div></div>'
        for i, rotulo, valor in itens
    )
    return f'<div class="v-numeros">{corpo}</div>'


def cartao_fase(
    sobretitulo: str, titulo: str, texto: str, detalhes: Iterable[tuple[str, str]]
) -> str:
    """Cartão de uma fase: sobretítulo, nome, foco e lista de termos e valores."""
    lista = "".join(f"<dt>{escape(t)}</dt><dd>{escape(v)}</dd>" for t, v in detalhes)
    return (
        f'<div class="v-cartao"><p class="v-sobretitulo">{escape(sobretitulo)}</p>'
        f"<h3>{escape(titulo)}</h3><p>{escape(texto)}</p><dl>{lista}</dl></div>"
    )


def grelha(cartoes_html: Iterable[str], colunas: int = 2) -> str:
    return f'<div class="v-grelha v-grelha-{colunas}">{"".join(cartoes_html)}</div>'


def icone_atividade(atividade: str) -> str:
    """Ícone de um dia da semana-tipo, pela primeira palavra; desconhecida, o do descanso."""
    primeira = atividade.split()[0].lower() if atividade else ""
    return ICONES_ATIVIDADES.get(primeira, "descanso")


def semana(dias: Iterable[tuple[str, str, str, str]]) -> str:
    """Semana-tipo em lista (legível a 390 px): (ícone, dia, atividade, duração)."""
    linhas = "".join(
        f'<li>{_icone(i)}<div class="v-semana-texto"><p class="v-semana-dia">{escape(dia)}</p>'
        f'<p>{escape(atividade)}</p></div><span class="v-semana-min">{escape(duracao)}</span></li>'
        for i, dia, atividade, duracao in dias
    )
    return f'<div class="v-cartao"><ul class="v-semana">{linhas}</ul></div>'


def exercicio(
    nome_icone: str,
    nome: str,
    prescricao: Iterable[str],
    descricao: str,
    extras: Iterable[str] = (),
) -> str:
    """Cartão de um exercício: ícone do grupo ao lado do nome, prescrição em etiquetas,
    descrição e notas (a toda a largura, para caber bem a 390 px)."""
    chips = "".join(f"<span>{escape(p)}</span>" for p in prescricao)
    notas = "".join(f'<p class="v-nota">{escape(n)}</p>' for n in extras)
    return (
        f'<div class="v-cartao v-exercicio"><div class="v-exercicio-topo">{_icone(nome_icone)}'
        f'<h4>{escape(nome)}</h4></div><div class="v-chips">{chips}</div>'
        f"<p>{escape(descricao)}</p>{notas}</div>"
    )
