"""Ponto de entrada da Vigoria (Streamlit): configuração e navegação.

As cores vêm de .streamlit/config.toml e de paginas/estilos.py; os textos, de paginas/textos.py.
Fase 5: ainda sem contas; as respostas e o plano vivem só em st.session_state.
"""

from pathlib import Path

import streamlit as st

from paginas import estilos
from paginas import textos as t
from vigoria.config import obter_configuracao

FAVICON = Path(__file__).parent / "static" / "icones" / "icone-32.png"  # scripts/gerar_logotipo.py

st.set_page_config(page_title=t.MARCA, page_icon=FAVICON, layout="centered")
estilos.aplicar()

# Na demonstração (Streamlit Community Cloud), em todas as páginas.
if obter_configuracao().ambiente == "demo":
    st.warning(t.DEMO_AVISO, icon=":material/science:")

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
