"""Ponto de entrada da Vigoria (Streamlit): configuração, sessão e navegação.

As cores vêm de .streamlit/config.toml e de paginas/estilos.py; os textos, de paginas/textos.py.
Sem sessão iniciada só se vê o Início, com «Entrar» no topo, e a Ajuda e a Privacidade no
rodapé (Fases 6, 8B e 8D); o resto exige login. A página para deixar de receber lembretes
(Fase 8) abre-se com ou sem sessão, fora do menu. Todas as páginas acabam no rodapé (comum.rodape).
"""

from pathlib import Path

import streamlit as st
from sqlalchemy.exc import OperationalError
from streamlit.navigation.page import StreamlitPage

from paginas import comum, estilos, navegacao, sessao
from paginas import textos as t
from vigoria.config import obter_configuracao
from vigoria.dados.repositorios import Recusa

RAIZ = Path(__file__).parent
FAVICON = RAIZ / "static" / "icones" / "icone-32.png"  # scripts/gerar_logotipo.py

st.set_page_config(page_title=t.MARCA, page_icon=FAVICON, layout="centered")
estilos.aplicar()
# O logotipo está no topo desenhado por paginas/navegacao.py (Fase 8D), não no st.logo.

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

inicio = st.Page(
    comum.PAGINA_INICIO, title=t.PAGINAS["inicio"], icon=":material/home:", default=True
)
# Fora do menu (Fase 8B): no rodapé de todas as páginas e no passo do consentimento.
privacidade = st.Page(
    comum.PAGINA_PRIVACIDADE,
    title=t.PAGINAS["privacidade"],
    icon=":material/policy:",
    url_path="privacidade",
    visibility="hidden",
)
ajuda = st.Page(
    comum.PAGINA_AJUDA, title=t.PAGINAS["ajuda"], icon=":material/help:", url_path="ajuda"
)
# A ligação dos emails de lembrete: com ou sem sessão, fora do menu.
cancelar_lembretes = st.Page(
    comum.PAGINA_CANCELAR_LEMBRETES,
    title=t.PAGINAS["cancelar_lembretes"],
    icon=":material/unsubscribe:",
    url_path="cancelar-lembretes",
    visibility="hidden",
)
paginas: list[StreamlitPage]
nomeadas: dict[str, StreamlitPage] | None = None
if isinstance(entrada, int):
    nomeadas = {
        "inicio": inicio,
        "questionario": st.Page(
            comum.PAGINA_QUESTIONARIO, title=t.PAGINAS["questionario"], icon=":material/checklist:"
        ),
        "plano": st.Page(
            comum.PAGINA_PLANO, title=t.PAGINAS["plano"], icon=":material/description:"
        ),
        "progresso": st.Page(
            comum.PAGINA_PROGRESSO, title=t.PAGINAS["progresso"], icon=":material/monitoring:"
        ),
        "ajuda": ajuda,
        "conta": st.Page(comum.PAGINA_CONTA, title=t.PAGINAS["conta"], icon=":material/person:"),
        "privacidade": privacidade,
        "sair": st.Page(_sair, title=t.PAGINAS["sair"], icon=":material/logout:", url_path="sair"),
        "cancelar_lembretes": cancelar_lembretes,
    }
    paginas = list(nomeadas.values())
else:
    paginas = [inicio, ajuda, privacidade, cancelar_lembretes]

try:
    # Menu do Streamlit escondido: a navegação é a de paginas/navegacao.py (Fase 8D).
    atual = st.navigation(paginas, position="hidden")
    navegacao.desenhar(atual, nomeadas)
    atual.run()
    comum.rodape()  # as páginas que param a meio usam comum.parar(), que o desenha antes
    if isinstance(entrada, int) and config.vigoria_utilizador_local:
        st.caption(t.UTILIZADOR_LOCAL)  # no fim, para não abrir a barra lateral
except OperationalError as erro:
    sessao.base_indisponivel(erro)
