"""Ponto de entrada da Vigoria (Streamlit): configuração e navegação.

As cores vêm de .streamlit/config.toml; os textos vivem nas páginas, em paginas/.
Fase 5: ainda sem contas; as respostas e o plano vivem só em st.session_state.
"""

import streamlit as st

from paginas import textos as t

st.set_page_config(page_title=t.MARCA, page_icon="🌿", layout="centered")

# Botões altos, fáceis de tocar no telemóvel (público 45+). Só tamanhos, sem cores.
st.html(
    """<style>
    button[data-testid^="stBaseButton"] { min-height: 3rem; }
    [data-testid="stPageLink"] a { min-height: 3rem; align-items: center; }
    </style>"""
)

navegacao = st.navigation(
    [
        st.Page(
            "paginas/inicio.py", title=t.PAGINAS["inicio"], icon=":material/home:", default=True
        ),
        st.Page(
            "paginas/questionario.py",
            title=t.PAGINAS["questionario"],
            icon=":material/checklist:",
        ),
        st.Page("paginas/plano.py", title=t.PAGINAS["plano"], icon=":material/description:"),
        st.Page("paginas/privacidade.py", title=t.PAGINAS["privacidade"], icon=":material/policy:"),
    ],
    position="top",
)
navegacao.run()
