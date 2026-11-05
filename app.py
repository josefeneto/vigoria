"""Ponto de entrada da Vigoria (Streamlit): configuração, sessão e navegação.

As cores vêm de .streamlit/config.toml e de paginas/estilos.py; os textos, de paginas/textos.py.
Sem sessão iniciada só se veem o Início e a Privacidade (Fase 6); o resto exige login.
"""

from pathlib import Path

import streamlit as st
from sqlalchemy.exc import OperationalError

from paginas import comum, estilos, sessao
from paginas import textos as t
from vigoria.config import obter_configuracao
from vigoria.dados.repositorios import Recusa

RAIZ = Path(__file__).parent
FAVICON = RAIZ / "static" / "icones" / "icone-32.png"  # scripts/gerar_logotipo.py
LOGOTIPO = RAIZ / "assets" / "marca" / "vigoria_logo.svg"

st.set_page_config(page_title=t.MARCA, page_icon=FAVICON, layout="centered")
estilos.aplicar()
# Fixo no topo de todas as páginas (imagem de marca). Sem icon_image, para se ver sempre a
# palavra Vigoria, mesmo com a barra lateral fechada (telemóvel).
st.logo(str(LOGOTIPO), size="large")

# Na demonstração (Streamlit Community Cloud), em todas as páginas.
config = obter_configuracao()
if config.ambiente == "demo":
    st.warning(t.DEMO_AVISO, icon=":material/science:")


def _sair() -> None:
    """O st.logout() termina também a sessão no Auth0 (end_session_endpoint)."""
    st.session_state.clear()
    if config.vigoria_utilizador_local:
        st.switch_page(comum.PAGINA_INICIO)
    st.logout()


if comum.CONTA_APAGADA in st.session_state:
    # Depois de apagar a conta: não voltar a entrar (criaria uma conta nova) até sair.
    entrada = None
    st.success(
        t.CONTA_APAGADA
        if st.session_state[comum.CONTA_APAGADA]
        else t.CONTA_APAGADA_AUTH0_PENDENTE,
        icon=":material/check_circle:",
    )
    if st.button(t.CONTA_APAGADA_SAIR, type="primary", icon=":material/logout:"):
        _sair()
else:
    try:
        entrada = sessao.entrar()
    except OperationalError as erro:
        sessao.base_indisponivel(erro)
if entrada is Recusa.NAO_CONVIDADO:
    # Só a mensagem e o botão: sem questionário, plano, conta nem outras páginas.
    st.info(t.SO_POR_CONVITE, icon=":material/lock:")
    if st.button(t.PAGINAS["sair"], type="primary", icon=":material/logout:"):
        _sair()
    st.stop()
elif isinstance(entrada, Recusa):
    titulo, texto, botao = t.RECUSAS[entrada]
    st.warning(texto, title=titulo, icon=":material/mark_email_unread:")
    if st.button(botao, icon=":material/login:"):
        _sair()
elif entrada is not None:
    try:
        comum.carregar_da_conta(entrada)
    except OperationalError as erro:
        sessao.base_indisponivel(erro)
    if config.vigoria_utilizador_local:
        st.sidebar.caption(t.UTILIZADOR_LOCAL)

inicio = st.Page(
    comum.PAGINA_INICIO, title=t.PAGINAS["inicio"], icon=":material/home:", default=True
)
privacidade = st.Page(
    comum.PAGINA_PRIVACIDADE, title=t.PAGINAS["privacidade"], icon=":material/policy:"
)
if isinstance(entrada, int):
    paginas = [
        inicio,
        st.Page(
            comum.PAGINA_QUESTIONARIO,
            title=t.PAGINAS["questionario"],
            icon=":material/checklist:",
        ),
        st.Page(comum.PAGINA_PLANO, title=t.PAGINAS["plano"], icon=":material/description:"),
        st.Page(comum.PAGINA_PROGRESSO, title=t.PAGINAS["progresso"], icon=":material/monitoring:"),
        st.Page(comum.PAGINA_CONTA, title=t.PAGINAS["conta"], icon=":material/person:"),
        privacidade,
        st.Page(_sair, title=t.PAGINAS["sair"], icon=":material/logout:", url_path="sair"),
    ]
else:
    paginas = [inicio, privacidade]

try:
    st.navigation(paginas, position="top").run()
except OperationalError as erro:
    sessao.base_indisponivel(erro)
