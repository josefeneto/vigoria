"""Política de privacidade, a mesma em todos os ambientes (paginas/textos_privacidade.py).

A faixa «RASCUNHO» só aparece enquanto o texto tiver campos «[PREENCHER».
"""

import streamlit as st

from paginas.textos_privacidade import em_rascunho, privacidade

st.title("Política de privacidade")
texto = privacidade()
if em_rascunho(texto):
    st.warning(
        "Este texto é um rascunho, ainda por completar. Não está em vigor.",
        title="RASCUNHO",
        icon=":material/edit_note:",
    )

st.markdown(texto)
