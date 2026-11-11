"""Navegação da Vigoria (Fase 8D), feita com st.page_link em vez do menu do Streamlit.

app.py chama st.navigation(..., position="hidden") e depois `desenhar`, antes de correr a
página. Um só contentor serve os dois tamanhos (estilos.css, pelas chaves):
- telemóvel (até 768 px): barra fixa no fundo, Início · Plano · Progresso · Conta;
- computador: no topo, à direita do logotipo, Início · Plano · Progresso · Ajuda · Conta ▾.
«Conta» abre um menu (st.popover) com A minha conta, Ajuda, Privacidade e Terminar sessão.
Sem o CSS, as ligações ficam numa fila no topo da página e continuam a funcionar.

A página atual marca-se aqui (chave nav_ativo_*), não por CSS: o st.navigation devolve-a.
"""

from collections.abc import Mapping

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from paginas import componentes, comum
from paginas import textos as t

ICONES = {
    "inicio": ":material/home:",
    "plano": ":material/description:",
    "progresso": ":material/monitoring:",
    "ajuda": ":material/help:",
    "conta": ":material/person:",
    "privacidade": ":material/policy:",
    "sair": ":material/logout:",
}
PRINCIPAIS = ("inicio", "plano", "progresso", "ajuda")
NO_MENU_CONTA = ("conta", "ajuda", "privacidade", "sair")


def _chave(nome: str, ativa: bool) -> str:
    return f"nav_ativo_{nome}" if ativa else f"nav_{nome}"


def desenhar(atual: StreamlitPage, paginas: Mapping[str, StreamlitPage] | None) -> None:
    """Topo com o logotipo e a navegação. `paginas` None: sem sessão (só «Entrar»)."""
    with st.container(key="topo", horizontal=True, vertical_alignment="center", gap="small"):
        st.html(componentes.logotipo(t.MARCA), width="content")
        if paginas is None:
            if st.button(t.ENTRAR_CURTO, icon=":material/login:", key="topo_entrar"):
                comum.pedir_login()
            return
        ativa = next((n for n, p in paginas.items() if p.url_path == atual.url_path), None)
        with st.container(key="barra_nav", horizontal=True, vertical_alignment="center", gap=None):
            for nome in PRINCIPAIS:
                with st.container(key=_chave(nome, nome == ativa)):
                    st.page_link(paginas[nome], label=t.NAV[nome], icon=ICONES[nome])
            conta_ativa = ativa in ("conta", "privacidade")
            with (
                st.container(key=_chave("conta", conta_ativa)),
                st.popover(t.NAV["conta"], icon=ICONES["conta"], key="nav_conta_menu"),
            ):
                for nome in NO_MENU_CONTA:
                    st.page_link(
                        paginas[nome], label=t.PAGINAS[nome], icon=ICONES[nome], width="stretch"
                    )
