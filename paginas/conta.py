"""A minha conta: planos anteriores (abrir ou apagar), descarregar os dados (JSON) e apagar
a conta.

Apagar pede confirmação dupla (caixa e a palavra APAGAR). A ordem é: primeiro os dados da
Vigoria, depois a conta de entrada no Auth0; se o Auth0 falhar, a pessoa fica a saber que os
dados já foram apagados e o `sub` fica registado para o José apagar à mão (contas/auth0.py).
"""

import json

import streamlit as st

from paginas import comum, sessao
from paginas import textos as t
from vigoria.config import obter_auth0, obter_configuracao
from vigoria.contas.auth0 import apagar_conta_auth0
from vigoria.dados import repositorios
from vigoria.modelos.questionario import FrequenciaRegisto

CONFIRMA = "conta_apagar_confirma"
PALAVRA = "conta_apagar_palavra"
APAGAR_PLANO = "conta_apagar_plano"  # id do plano à espera de confirmação
ACOMPANHAMENTO_ATIVO = "conta_acompanhamento_ativo"
FREQUENCIA = "conta_frequencia"
LEMBRETES_EMAIL = "conta_lembretes_email"


def _abrir(plano_id: int) -> None:
    with sessao.fabrica().begin() as s:
        plano = repositorios.obter_plano(s, sessao.utilizador_id(), plano_id)
    if plano is not None:
        st.session_state[comum.RESULTADO] = plano
        st.session_state.pop(comum.ERRO_GUARDAR, None)
        st.switch_page(comum.PAGINA_PLANO)


def _pedir_apagar_plano(plano_id: int | None) -> None:
    st.session_state[APAGAR_PLANO] = plano_id


def _apagar_plano(plano_id: int) -> None:
    uid = sessao.utilizador_id()
    with sessao.fabrica().begin() as s:
        apagado = repositorios.apagar_plano(s, uid, plano_id)
        ultimo = repositorios.ultimo_plano(s, uid)
    st.session_state.pop(APAGAR_PLANO, None)
    if not apagado:
        return
    if getattr(st.session_state.get(comum.RESULTADO), "id", None) == plano_id:
        # O plano aberto passa a ser o mais recente que ficou (ou nenhum).
        if ultimo is None:
            st.session_state.pop(comum.RESULTADO, None)
        else:
            st.session_state[comum.RESULTADO] = ultimo
    st.toast(t.CONTA_PLANO_APAGADO, icon=":material/delete:")


def _guardar_acompanhamento() -> None:
    preferencias = repositorios.Preferencias(
        ativo=st.session_state[ACOMPANHAMENTO_ATIVO],
        frequencia=st.session_state[FREQUENCIA],
        lembretes_email=st.session_state[LEMBRETES_EMAIL],
    )
    with sessao.fabrica().begin() as s:
        repositorios.guardar_preferencias(s, sessao.utilizador_id(), preferencias)
    st.toast(t.CONTA_ACOMPANHAMENTO_GUARDADO, icon=":material/check_circle:")


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


st.title(t.CONTA_TITULO)
uid = sessao.utilizador_id()
quem = sessao.identidade()
if quem is not None:
    st.markdown(t.CONTA_EMAIL.format(email=quem.email))

with sessao.fabrica().begin() as s:
    planos = repositorios.listar_planos(s, uid)
    dados = repositorios.exportar_dados(s, uid)
    preferencias = repositorios.obter_preferencias(s, uid)

st.subheader(t.CONTA_PLANOS)
if not planos:
    st.caption(t.CONTA_SEM_PLANOS)
atual = getattr(st.session_state.get(comum.RESULTADO), "id", None)
por_confirmar = st.session_state.get(APAGAR_PLANO)
for p in planos:
    data = t.data_hora(p.criado_em)
    # A data numa linha e os botões por baixo: no telemóvel não cabem os três lado a lado.
    st.markdown(t.CONTA_PLANO_DE.format(data=data))
    with st.container(horizontal=True, key=f"plano_{p.id}"):
        st.button(
            t.CONTA_ATUAL if p.id == atual else t.CONTA_ABRIR,
            key=f"abrir_{p.id}",
            disabled=p.id == atual,
            icon=":material/description:",
            on_click=_abrir,
            args=(p.id,),
        )
        st.button(
            t.CONTA_APAGAR_PLANO,
            key=f"apagar_{p.id}",
            icon=":material/delete:",
            on_click=_pedir_apagar_plano,
            args=(p.id,),
        )
        comum.botao_pdf(p.criado_em, plano_id=p.id, chave=f"pdf_{p.id}")
    if p.id == por_confirmar:
        with st.container(border=True, key=f"confirmar_{p.id}"):
            st.write(t.CONTA_APAGAR_PLANO_PERGUNTA.format(data=data))
            with st.container(horizontal=True):
                st.button(
                    t.CONTA_APAGAR_PLANO_SIM,
                    key=f"apagar_sim_{p.id}",
                    type="primary",
                    icon=":material/delete_forever:",
                    on_click=_apagar_plano,
                    args=(p.id,),
                )
                st.button(
                    t.CONTA_APAGAR_PLANO_NAO,
                    key=f"apagar_nao_{p.id}",
                    on_click=_pedir_apagar_plano,
                    args=(None,),
                )

st.subheader(t.CONTA_ACOMPANHAMENTO)
ativo = st.toggle(
    t.CONTA_ACOMPANHAMENTO_ATIVO,
    value=preferencias.ativo,
    key=ACOMPANHAMENTO_ATIVO,
    on_change=_guardar_acompanhamento,
)
frequencias = list(FrequenciaRegisto)
st.radio(
    t.ROTULOS_QUESTIONARIO_FREQUENCIA,
    frequencias,
    index=frequencias.index(preferencias.frequencia),
    format_func=lambda f: t.FREQUENCIA_PLANO[f.value],
    key=FREQUENCIA,
    disabled=not ativo,
    on_change=_guardar_acompanhamento,
)
st.toggle(
    t.CONTA_LEMBRETES_EMAIL,
    value=preferencias.lembretes_email,
    key=LEMBRETES_EMAIL,
    disabled=not ativo,
    on_change=_guardar_acompanhamento,
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
