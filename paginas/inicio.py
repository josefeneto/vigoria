"""Página de boas-vindas: fotografia, promessa, botão e três benefícios.

No telemóvel, a fotografia vem primeiro e o texto por baixo; no computador, lado a lado.
"""

from html import escape

import streamlit as st

from paginas import componentes, comum
from paginas import textos as t

foto, texto = st.columns([1, 1], gap="large", vertical_alignment="center")
with foto:
    componentes.fotografia("inicio_topo", t.ALT_FOTO_INICIO)
with texto:
    st.html(
        f'<p class="v-marca">{escape(t.MARCA)}</p><h1 class="v-promessa">{escape(t.PROMESSA)}</h1>'
    )
    st.write(t.INICIO_TEXTO)
    if st.button(
        t.COMECAR, type="primary", icon=":material/arrow_forward:", width="stretch", key="comecar"
    ):
        st.switch_page(comum.PAGINA_QUESTIONARIO)
    if comum.RESULTADO in st.session_state:
        st.page_link(
            comum.PAGINA_PLANO, label=t.VER_PLANO, icon=":material/description:", width="stretch"
        )

st.space("medium")
st.html(componentes.cartoes(t.BENEFICIOS))
st.subheader(t.INICIO_COMO_TITULO)
st.write(t.INICIO_COMO)
st.caption(t.INICIO_SESSAO)
