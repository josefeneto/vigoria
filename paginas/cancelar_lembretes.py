"""Deixar de receber lembretes: a ligação dos emails, sem sessão iniciada (Fase 8).

Abrir a ligação não desliga nada (os antivírus do email abrem ligações sozinhos): só o botão
o faz. A verificação do token está em vigoria.notificacoes.cancelamento.
"""

import streamlit as st

from paginas import comum, sessao
from paginas import textos as t
from vigoria.config import obter_configuracao
from vigoria.notificacoes.cancelamento import cancelar_lembretes
from vigoria.notificacoes.token import id_do_token

FEITO = "cancelar_lembretes_feito"  # True / False depois de carregar no botão


def _cancelar(token: str) -> None:
    with sessao.fabrica().begin() as s:
        st.session_state[FEITO] = cancelar_lembretes(
            s, token, obter_configuracao().vigoria_segredo_lembretes
        )


st.title(t.CANCELAR_TITULO)
token = st.query_params.get("t", "")
feito = st.session_state.get(FEITO)
if feito:
    st.success(t.CANCELAR_FEITO, icon=":material/check_circle:")
    st.write(t.CANCELAR_REATIVAR)
elif feito is False or id_do_token(token) is None:
    st.warning(t.CANCELAR_INVALIDA, icon=":material/link_off:")
    st.page_link(comum.PAGINA_INICIO, label=t.CANCELAR_INICIO, icon=":material/home:")
else:
    st.write(t.CANCELAR_PERGUNTA)
    st.button(
        t.CANCELAR_BOTAO,
        type="primary",
        icon=":material/unsubscribe:",
        width="stretch",
        on_click=_cancelar,
        args=(token,),
    )
