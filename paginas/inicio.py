"""Página de boas-vindas."""

import streamlit as st

from paginas import comum
from paginas import textos as t

st.title(t.MARCA)
st.subheader(t.ASSINATURA)
st.write(t.INICIO_TEXTO)
st.write(t.INICIO_COMO)
if st.button(t.COMECAR, type="primary", icon=":material/arrow_forward:", width="stretch"):
    st.switch_page(comum.PAGINA_QUESTIONARIO)
if comum.RESULTADO in st.session_state:
    st.page_link(
        comum.PAGINA_PLANO, label=t.VER_PLANO, icon=":material/description:", width="stretch"
    )
st.caption(t.INICIO_SESSAO)
