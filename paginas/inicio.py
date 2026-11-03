"""Página de boas-vindas, em faixas a toda a largura (Fase 5C).

Topo em petróleo profundo (promessa, botão e vídeo), benefícios, «Como funciona» e um
convite final. No telemóvel, o texto e o botão vêm antes do vídeo, para o botão caber no
primeiro ecrã; no computador, ficam lado a lado. As faixas e a largura maior só existem
nesta página (estilos.css, pelas chaves faixa_*).

Sem sessão iniciada, o botão principal é «Entrar ou criar conta» (st.login, Auth0).
"""

from html import escape

import streamlit as st

from paginas import componentes, comum, sessao
from paginas import textos as t
from vigoria.config import obter_auth0


def _comecar(chave: str) -> None:
    if sessao.UTILIZADOR in st.session_state:
        if st.button(
            t.COMECAR, type="primary", icon=":material/arrow_forward:", width="stretch", key=chave
        ):
            st.switch_page(comum.PAGINA_QUESTIONARIO)
    elif st.button(t.ENTRAR, type="primary", icon=":material/login:", width="stretch", key=chave):
        if obter_auth0() is None:
            st.error(t.LOGIN_POR_CONFIGURAR, icon=":material/key_off:")
        else:
            st.login("auth0")


with st.container(key="faixa_topo"):
    texto, media = st.columns([1, 1], gap="large", vertical_alignment="center")
    with texto:
        st.html(
            componentes.logotipo(t.MARCA, claro=True, grande=True)
            + f'<h1 class="v-promessa">{escape(t.PROMESSA)}</h1>'
            f'<p class="v-faixa-texto">{escape(t.INICIO_TEXTO)}</p>'
        )
        _comecar("comecar")
        if comum.RESULTADO in st.session_state:
            st.page_link(
                comum.PAGINA_PLANO,
                label=t.VER_PLANO,
                icon=":material/description:",
                width="stretch",
            )
    with media:
        if not componentes.video_topo(t.VIDEO_DESCRICAO, t.VIDEO_PAUSAR, t.VIDEO_REPRODUZIR):
            componentes.fotografia("inicio_topo", t.ALT_FOTO_INICIO)

with st.container(key="faixa_beneficios"):
    st.html(componentes.cartoes(t.BENEFICIOS))

with st.container(key="faixa_como"):
    st.html(f'<h2 class="v-faixa-titulo">{escape(t.INICIO_COMO_TITULO)}</h2>')
    st.html(componentes.cartoes(t.COMO_FUNCIONA))

with st.container(key="faixa_final"):
    st.html(f'<h2 class="v-faixa-titulo">{escape(t.FINAL_TITULO)}</h2>')
    _comecar("comecar_fim")
    st.caption(t.INICIO_SESSAO)
