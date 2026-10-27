"""Ponto de entrada da Vigoria (Streamlit): configuração e navegação.

As cores vêm de .streamlit/config.toml; os textos vivem nas páginas, em paginas/.
"""

import streamlit as st

st.set_page_config(page_title="Vigoria", page_icon="🌿", layout="centered")

navegacao = st.navigation([st.Page("paginas/inicio.py", title="Início", default=True)])
navegacao.run()
