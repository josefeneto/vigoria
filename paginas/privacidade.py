"""Política de privacidade — RASCUNHO, a rever juridicamente antes do beta.

O texto muda com o ambiente (demonstração ou produção): paginas/textos_privacidade.py.
"""

import streamlit as st

from paginas.textos_privacidade import privacidade
from vigoria.config import obter_configuracao

st.title("Política de privacidade")
st.warning(
    "Este texto é um rascunho, ainda não revisto por um jurista. Não está em vigor.",
    title="RASCUNHO",
    icon=":material/edit_note:",
)

st.markdown(privacidade(obter_configuracao().ambiente))
