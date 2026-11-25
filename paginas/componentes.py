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
# Vídeos do topo do início, que alternam (nome do .mp4, capa): o homem e a mulher
# (scripts/converter_video.py) e, desde 20/11/2026, os das atividades opcionais.
VIDEOS_TOPO = (
    ("inicio", "inicio_capa.webp"),
    ("danca_web", "danca_poster.jpg"),
    ("inicio_mulher", "inicio_mulher_capa.webp"),
    ("taichi_web", "taichi_poster.jpg"),
)
CAPA_VIDEO = PASTA_VIDEO / "inicio_capa.webp"
# Vídeos dos cartões das atividades opcionais (Pexels, docs/CREDITOS_IMAGENS.md):
# <atividade>_web.mp4 e a capa <atividade>_poster.jpg.
VIDEO_DANCA = "danca_web"
CAPA_DANCA = PASTA_VIDEO / "danca_poster.jpg"
VIDEO_TAICHI = "taichi_web"
CAPA_TAICHI = PASTA_VIDEO / "taichi_poster.jpg"

# Vídeos do topo do início: sem som, um a seguir ao outro em ciclo, com capa e botão de pausa
# (WCAG 2.2.2). Só arrancam por código e só se o sistema não pedir menos movimento; sem
# código, fica a capa. Cada um só começa a descarregar quando o anterior já está a passar.
# A capa do primeiro vai embutida como fundo da caixa: vê-se mesmo que o servidor demore ou
# os vídeos falhem (logo a seguir a entrar ou sair); um vídeo com erro
# sai do ciclo e, sem nenhum, saem também o botão e os vídeos.
_UM_VIDEO = """<video muted playsinline preload="%(preload)s" poster="%(poster)s"
 aria-label="%(descricao)s"><source src="app/static/video/%(nome)s.mp4" type="video/mp4"></video>"""
_VIDEO = """<div class="v-video" data-auto="%(auto)s" style="background-image:url(%(capa)s)">
%(videos)s
<button type="button" class="v-video-botao" data-pausar="%(pausar)s"
 data-reproduzir="%(reproduzir)s">%(reproduzir)s</button></div>
<script>
(() => {
  const menos = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll(".v-video:not([data-pronto])").forEach((caixa) => {
    caixa.dataset.pronto = "1";
    const sozinho = !menos && caixa.dataset.auto === "1";  // arranca sem toque
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
      if (video === atual) { atual = videos[0]; visivel(atual); if (sozinho) tocar(atual); }
    };
    videos.forEach((video) => {
      video.querySelector("source").addEventListener("error", () => falhou(video));
      video.addEventListener("error", () => falhou(video));
      video.addEventListener("ended", seguinte);
      // O botão diz sempre o que o vídeo está a fazer (o navegador também pausa sozinho,
      // por exemplo fora do ecrã ou em poupança de energia).
      video.addEventListener("playing", () => { if (video === atual) mostrar(true); });
      video.addEventListener("pause", () => {
        if (video === atual && !video.ended) mostrar(false);
      });
    });
    // Cada vídeo só se descarrega quando o anterior começa (poupa dados no telemóvel).
    videos.forEach((video) => video.addEventListener("playing", () => {
      const v = videos[(videos.indexOf(video) + 1) %% videos.length];
      // Nunca o próprio (um só vídeo, nos cartões do plano): o load() parava-o logo ao começar.
      if (v && v !== video && v.preload === "none") { v.preload = "auto"; v.load(); }
    }));
    botao.addEventListener("click", () => {
      if (atual.paused) { tocar(atual); } else { atual.pause(); mostrar(false); }
    });
    visivel(atual);
    if (sozinho) tocar(atual);
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
        (nome, capa, descricao)
        for (nome, capa), descricao in zip(VIDEOS_TOPO, descricoes, strict=True)
        if (PASTA_VIDEO / f"{nome}.mp4").exists() and (PASTA_VIDEO / capa).exists()
    ]
    if not existentes or not CAPA_VIDEO.exists():
        return False
    videos = "\n".join(
        _UM_VIDEO
        % {
            "nome": nome,
            "descricao": escape(descricao),
            "preload": "auto" if i == 0 else "none",
            "poster": f"app/static/video/{capa}",
        }
        for i, (nome, capa, descricao) in enumerate(existentes)
    )
    st.html(
        _VIDEO
        % {
            "capa": _capa_video(),
            "videos": videos,
            "pausar": escape(pausar),
            "reproduzir": escape(reproduzir),
            "auto": "1",
        },
        unsafe_allow_javascript=True,
    )
    return True


def video_danca(descricao: str, pausar: str, reproduzir: str) -> str:
    return video_atividade(VIDEO_DANCA, CAPA_DANCA, descricao, pausar, reproduzir)


def video_taichi(descricao: str, pausar: str, reproduzir: str) -> str:
    return video_atividade(VIDEO_TAICHI, CAPA_TAICHI, descricao, pausar, reproduzir)


def video_atividade(
    nome: str, capa_ficheiro: Path, descricao: str, pausar: str, reproduzir: str
) -> str:
    """Vídeo do cartão de uma atividade opcional: sem som, em ciclo, parado na capa até um
    toque em «Ver o vídeo» (o mesmo código do topo do início). Vazio sem ficheiros."""
    if not (PASTA_VIDEO / f"{nome}.mp4").exists() or not capa_ficheiro.exists():
        return ""
    capa = f"app/static/video/{capa_ficheiro.name}"
    um = _UM_VIDEO % {
        "nome": nome,
        "descricao": escape(descricao),
        "preload": "none",  # só descarrega quando começa (poupa dados no telemóvel)
        "poster": capa,
    }
    return _VIDEO % {
        "capa": capa,
        "videos": um,
        "pausar": escape(pausar),
        "reproduzir": escape(reproduzir),
        "auto": "0",  # no plano, só com um toque em «Ver o vídeo»
    }


def _ligacoes(itens: Iterable[tuple[str, str, str]]) -> str:
    """Ligações externas (D7): abrem no YouTube numa janela nova, sem nada embutido."""
    linhas = "".join(
        f'<li><a href="{escape(url)}" target="_blank" rel="noopener noreferrer">'
        f'{escape(titulo)}</a> <span class="v-atividade-canal">{escape(canal)}</span></li>'
        for titulo, url, canal in itens
    )
    return f'<ul class="v-atividade-ligacoes">{linhas}</ul>'


def cartao_atividade(
    atividade: str,
    icone: str,
    titulo: str,
    minutos: str,
    video_html: str,
    textos: Iterable[str],
    passos: Iterable[tuple[str, str]],
    aviso: str,
    ajuste: str,
    grupos: Iterable[tuple[str, Iterable[tuple[str, str, str]]]],
    nota: str,
) -> str:
    """Cartão de uma atividade opcional («danca», «taichi»): ícone, minutos, vídeo, os passos
    da sessão (D2, T2), o aviso (D5, T5), o ajuste (D6; vazio, sem parágrafo) e as ligações por
    grupo: (rótulo, [(título, url, canal)]). Um passo com rótulo vazio mostra só o texto."""
    corpo = "".join(f"<p>{escape(x)}</p>" for x in textos)
    lista = "".join(
        f"<li><strong>{escape(a)}:</strong> {escape(b)}</li>" if a else f"<li>{escape(b)}</li>"
        for a, b in passos
    )
    ligacoes = "".join(
        f'<p class="v-atividade-grupo">{escape(rotulo)}</p>{_ligacoes(itens)}'
        for rotulo, itens in grupos
    )
    ajuste_html = f"<p>{escape(ajuste)}</p>" if ajuste else ""
    return (
        f'<div class="v-cartao v-{escape(atividade)} v-atividade">'
        f'<div class="v-atividade-topo">{_icone(icone)}'
        f"<div><h3>{escape(titulo)}</h3>"
        f'<p class="v-atividade-min">{escape(minutos)}</p></div></div>'
        f'{video_html}{corpo}<ol class="v-atividade-passos">{lista}</ol>'
        f'<p class="v-atividade-aviso">{escape(aviso)}</p>{ajuste_html}{ligacoes}'
        f'<p class="v-atividade-nota">{escape(nota)}</p></div>'
    )


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


def numeros(itens: Iterable[tuple[str, str]]) -> str:
    """Os números-chave do plano em 3 cartões claros lado a lado: (rótulo, valor)."""
    corpo = "".join(
        f'<div class="v-numero"><p class="v-numero-rotulo">{escape(rotulo)}</p>'
        f'<p class="v-numero-valor">{escape(valor)}</p></div>'
        for rotulo, valor in itens
    )
    return f'<div class="v-numeros">{corpo}</div>'


def semanas(semana: int, titulo: str, fase: str, texto: str, aria: str, total: int = 16) -> str:
    """Cartão «Semana X de 16»: segmentos feitos, o atual e os por fazer (Fase 8D).

    Depois da semana 16 (manutenção), todos feitos. A informação está também no texto.
    """
    atual = min(semana, total + 1)
    segmentos = "".join(
        f'<span class="{"feito" if i < atual else "atual" if i == atual else ""}"></span>'
        for i in range(1, total + 1)
    )
    return (
        f'<div class="v-semanas"><div class="v-semanas-topo"><p class="v-semanas-titulo">'
        f'{escape(titulo)}</p><p class="v-semanas-fase">{escape(fase)}</p></div>'
        f'<div class="v-semanas-barra" role="progressbar" aria-label="{escape(aria)}" '
        f'aria-valuemin="1" aria-valuemax="{total}" aria-valuenow="{min(semana, total)}">'
        f'{segmentos}</div><p class="v-semanas-texto">{escape(texto)}</p></div>'
    )


def hoje(nome_icone: str, sobretitulo: str, titulo: str, texto: str) -> str:
    """Cartão «Hoje» (sem o botão, que é um st.button ao lado)."""
    return (
        f'<div class="v-hoje">{_icone(nome_icone)}<div class="v-hoje-texto">'
        f'<p class="v-sobretitulo">{escape(sobretitulo)}</p>'
        f'<p class="v-hoje-titulo">{escape(titulo)}</p>'
        f'<p class="v-hoje-detalhe">{escape(texto)}</p></div></div>'
    )


def notas(titulo: str, itens: Iterable[str]) -> str:
    """«Notas para si»: cartão argila com a lista das notas personalizadas."""
    lista = "".join(f"<li>{escape(n)}</li>" for n in itens)
    return (
        f'<div class="v-notas"><p class="v-notas-titulo">{escape(titulo)}</p><ul>{lista}</ul></div>'
    )


def selo(texto: str) -> str:
    """Etiqueta pequena sobre o petróleo profundo (topo do início)."""
    return f'<p class="v-selo">{escape(texto)}</p>'


def passos(itens: Iterable[tuple[str, str]]) -> str:
    """«Como funciona»: círculos numerados com título e texto: (título, texto)."""
    linhas = "".join(
        f'<li><span class="v-passos-n" aria-hidden="true">{i}</span><div>'
        f'<p class="v-passos-titulo">{escape(titulo)}</p><p>{escape(texto)}</p></div></li>'
        for i, (titulo, texto) in enumerate(itens, start=1)
    )
    return f'<ol class="v-passos">{linhas}</ol>'


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
    em_vez_de: str | None = None,
) -> str:
    """Cartão de um exercício (maqueta Fase): ícone do movimento (assets/icones/exercicios/,
    figura em petróleo profundo e equipamento em terracota) à esquerda; à direita, o nome, a
    prescrição em etiquetas, a descrição, «Em vez de: …» a cobre e as outras notas (por
    exemplo, «Com halteres: …») a cinzento."""
    chips = "".join(f"<span>{escape(p)}</span>" for p in prescricao)
    troca = f'<p class="v-em-vez">{escape(em_vez_de)}</p>' if em_vez_de else ""
    notas = "".join(f'<p class="v-nota">{escape(n)}</p>' for n in extras)
    icone_html = _icone(f"exercicios/{nome_icone}", "principal_profundo")
    return (
        f'<div class="v-cartao v-exercicio">{icone_html}<div class="v-exercicio-corpo">'
        f'<h4>{escape(nome)}</h4><div class="v-chips">{chips}</div>'
        f"<p>{escape(descricao)}</p>{troca}{notas}</div></div>"
    )


def escala_esforco(minimo: int, maximo: int, rotulo: str, descricao: str) -> str:
    """Escala de esforço de 1 a 10, com o intervalo da fase preenchido e o texto «3 a 6».

    `descricao` (frase completa) fica para os leitores de ecrã; os segmentos são decorativos.
    """
    segmentos = "".join(
        f'<span class="{"dentro" if minimo <= i <= maximo else ""}"></span>' for i in range(1, 11)
    )
    return (
        f'<div class="v-esforco" role="img" aria-label="{escape(descricao)}">'
        f'<span class="v-esforco-rotulo">{escape(rotulo)}</span>'
        f'<span class="v-esforco-barra" aria-hidden="true">{segmentos}</span>'
        f'<span class="v-esforco-rotulo">{minimo} a {maximo}</span></div>'
    )


def cartao_treino_fase(nome: str, semanas: str, foco: str, esforco_html: str) -> str:
    """Cartão da fase escolhida no Treino (névoa): nome, semanas, foco e escala de esforço."""
    return (
        f'<div class="v-fase"><div class="v-fase-topo"><p class="v-fase-nome">{escape(nome)}</p>'
        f'<p class="v-fase-semanas">{escape(semanas)}</p></div><p>{escape(foco)}</p>'
        f"{esforco_html}</div>"
    )


def medias(itens: Iterable[tuple[str, str, str]]) -> str:
    """Médias do progresso em cartões claros: (rótulo, valor, unidade)."""
    corpo = "".join(
        f'<div class="v-numero"><p class="v-numero-rotulo">{escape(rotulo)}</p>'
        f'<p class="v-numero-valor">{escape(valor)} <span class="v-numero-unidade">'
        f"{escape(unidade)}</span></p></div>"
        for rotulo, valor, unidade in itens
    )
    return f'<div class="v-numeros v-medias">{corpo}</div>'


def registo_por_fazer(titulo: str, texto: str, botao: str, ancora: str) -> str:
    """Cartão escuro do progresso: falta o registo deste período, com ligação ao formulário
    (mesma página: a âncora não recarrega nada)."""
    return (
        f'<div class="v-por-fazer"><div><p class="v-por-fazer-titulo">{escape(titulo)}</p>'
        f'<p class="v-por-fazer-texto">{escape(texto)}</p></div>'
        f'<a class="v-por-fazer-botao" href="#{escape(ancora)}" target="_self">{escape(botao)}</a>'
        "</div>"
    )
