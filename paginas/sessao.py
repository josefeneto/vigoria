"""Sessão iniciada e base de dados nas páginas: quem entrou e a fábrica de sessões SQLAlchemy.

A lógica está em vigoria.contas e vigoria.dados; aqui só se liga ao st.user e ao
st.session_state. Com VIGORIA_UTILIZADOR_LOCAL=1 (só AMBIENTE=local), entra-se como um
utilizador fictício, sem Auth0: serve para os testes das páginas (AppTest não faz login).
"""

import logging
from typing import NoReturn

import streamlit as st
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from paginas import textos as t
from vigoria.config import obter_configuracao
from vigoria.contas.entrada import Identidade, identidade_de
from vigoria.dados import repositorios
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.repositorios import Recusa
from vigoria.dados.tabelas import Utilizador

registo = logging.getLogger(__name__)

UTILIZADOR = "utilizador"  # (sub, id) do utilizador desta sessão
UTILIZADOR_LOCAL = Identidade(
    sub="local|desenvolvimento", email="local@vigoria.invalid", email_verificado=True
)


@st.cache_resource(show_spinner=False)
def _fabrica(url: str) -> sessionmaker[Session]:
    """Uma por processo e por endereço; aplica as migrações em falta ao arrancar."""
    motor = criar_motor(url)
    migrar(motor)
    return fabrica_sessoes(motor)


def fabrica() -> sessionmaker[Session]:
    return _fabrica(obter_configuracao().database_url)


def identidade() -> Identidade | None:
    """Quem entrou (None: sem sessão iniciada)."""
    if obter_configuracao().vigoria_utilizador_local:
        return UTILIZADOR_LOCAL
    if not st.user.get("is_logged_in"):  # sem [auth] (ou no AppTest) a chave não existe
        return None
    return identidade_de(st.user.to_dict())


def entrar() -> int | Recusa | None:
    """O id interno do utilizador (conta criada no primeiro login), uma recusa, ou None."""
    quem = identidade()
    if quem is None:
        st.session_state.pop(UTILIZADOR, None)
        return None
    guardado = st.session_state.get(UTILIZADOR)
    if guardado is not None and guardado[0] == quem.sub:
        return guardado[1]
    with fabrica().begin() as s:
        resultado = repositorios.entrar(s, quem)
        if isinstance(resultado, Utilizador):
            st.session_state[UTILIZADOR] = (quem.sub, resultado.id)
            return resultado.id
    return resultado


def utilizador_id() -> int:
    """Nas páginas que só existem com sessão iniciada (app.py garante-o)."""
    return st.session_state[UTILIZADOR][1]


def base_indisponivel(erro: OperationalError) -> NoReturn:
    """Base de dados sem resposta (o Neon a acordar, rede): mensagem clara em vez de rodar."""
    registo.warning("base de dados indisponível: %s", type(erro.orig).__name__)
    st.error(t.BD_INDISPONIVEL, icon=":material/cloud_off:")
    st.button(t.TENTAR_DE_NOVO, icon=":material/refresh:")  # carregar já volta a correr a app
    st.stop()


def esquecer() -> None:
    """Depois de apagar a conta: o utilizador desta sessão já não existe."""
    st.session_state.pop(UTILIZADOR, None)
