"""A minha conta: planos anteriores, descarregar os dados (JSON) e apagar a conta.

Apagar pede confirmação dupla (caixa e a palavra APAGAR). A ordem é: primeiro os dados da
Vigoria, depois a conta de entrada no Auth0; se o Auth0 falhar, a pessoa fica a saber que os
dados já foram apagados e o `sub` fica registado para o José apagar à mão (contas/auth0.py).
"""

import json

import streamlit as st

from paginas import componentes, comum, sessao
from paginas import textos as t
from vigoria.config import obter_auth0, obter_configuracao
from vigoria.contas.auth0 import apagar_conta_auth0
from vigoria.dados import repositorios

CONFIRMA = "conta_apagar_confirma"
PALAVRA = "conta_apagar_palavra"


def _abrir(plano_id: int) -> None:
    with sessao.fabrica().begin() as s:
        plano = repositorios.obter_plano(s, sessao.utilizador_id(), plano_id)
    if plano is not None:
        st.session_state[comum.RESULTADO] = plano
        st.session_state.pop(comum.ERRO_GUARDAR, None)
        st.switch_page(comum.PAGINA_PLANO)


def _apagar() -> None:
    with sessao.fabrica().begin() as s:
        sub = repositorios.apagar_utilizador(s, sessao.utilizador_id())
    entrada_apagada = (
        sub is not None
        and not obter_configuracao().vigoria_utilizador_local
        and apagar_conta_auth0(sub, obter_auth0())
    )
    st.session_state.clear()
    # app.py deixa de entrar com esta sessão e mostra a mensagem até a pessoa sair.
    st.session_state[comum.CONTA_APAGADA] = entrada_apagada


st.html(componentes.logotipo(t.MARCA))
st.title(t.CONTA_TITULO)
uid = sessao.utilizador_id()
quem = sessao.identidade()
if quem is not None:
    st.markdown(t.CONTA_EMAIL.format(email=quem.email))

with sessao.fabrica().begin() as s:
    planos = repositorios.listar_planos(s, uid)
    dados = repositorios.exportar_dados(s, uid)

st.subheader(t.CONTA_PLANOS)
if not planos:
    st.caption(t.CONTA_SEM_PLANOS)
atual = getattr(st.session_state.get(comum.RESULTADO), "id", None)
for p in planos:
    with st.container(horizontal=True, vertical_alignment="center", key=f"plano_{p.id}"):
        st.markdown(t.CONTA_PLANO_DE.format(data=t.data_hora(p.criado_em)), width="stretch")
        st.button(
            t.CONTA_ATUAL if p.id == atual else t.CONTA_ABRIR,
            key=f"abrir_{p.id}",
            disabled=p.id == atual,
            icon=":material/description:",
            on_click=_abrir,
            args=(p.id,),
        )

st.subheader(t.CONTA_EXPORTAR_TITULO)
st.write(t.CONTA_EXPORTAR_TEXTO)
st.download_button(
    t.CONTA_EXPORTAR,
    data=json.dumps(dados, ensure_ascii=False, indent=2),
    file_name=t.CONTA_EXPORTAR_FICHEIRO,
    mime="application/json",
    icon=":material/download:",
    width="stretch",
)

st.subheader(t.CONTA_APAGAR_TITULO)
st.write(t.CONTA_APAGAR_TEXTO)
confirma = st.checkbox(t.CONTA_APAGAR_CONFIRMA, key=CONFIRMA)
palavra = st.text_input(t.CONTA_APAGAR_ESCREVA, key=PALAVRA, max_chars=10)
st.button(
    t.CONTA_APAGAR,
    icon=":material/delete_forever:",
    width="stretch",
    disabled=not (confirma and palavra.strip().upper() == t.CONTA_APAGAR_PALAVRA),
    on_click=_apagar,
)
