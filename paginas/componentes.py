"""Componentes visuais da Vigoria: HTML com as classes .v-* de estilos.py.

Só aspeto: recebem textos já decididos e devolvem HTML. Todo o texto passa por
html.escape (o do plano pode vir da LLM). Os ícones são decorativos (aria-hidden).
"""

from collections.abc import Iterable
from html import escape
from pathlib import Path

import streamlit as st

from paginas.estilos import ICONES_ATIVIDADES, RAIZ, icone

PASTA_FOTOS = RAIZ / "assets" / "img"


def _icone(nome: str, cor: str = "principal", destaque: str = "terracota") -> str:
    return f'<span class="v-icone">{icone(nome, cor, destaque)}</span>'


def fotografia(nome: str, alt: str, *, proporcao: str = "3 / 2", marcador: bool = True) -> None:
    """Fotografia de assets/img/<nome>.webp; sem ela, um marcador desenhado (ou nada)."""
    caminho: Path = PASTA_FOTOS / f"{nome}.webp"
    if caminho.exists():
        with st.container(key=f"foto_{nome}"):
            st.image(str(caminho), width="stretch", alt=alt)
    elif marcador:
        desenho = icone("rebento", "nevoa", "pessego")
        st.html(f'<div class="v-marcador" style="--proporcao:{proporcao}">{desenho}</div>')


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
