"""Página de boas-vindas (Fase 5C, aspeto da Fase 8D: maqueta Main.dc.html).

Topo em petróleo profundo em três blocos: texto, vídeo e ação. No telemóvel é um cartão
com cantos redondos e os blocos seguem esta ordem (como na maqueta); no computador, uma
faixa a toda a largura com o texto e o botão à esquerda e o vídeo à direita (grelha CSS em
estilos.css; sem o CSS, ficam pela ordem do telemóvel). Depois: benefícios (no telemóvel,
mosaicos só com o título), «Como funciona» em passos numerados e um convite final.

Sem sessão iniciada, o botão principal é «Entrar ou criar conta» (st.login, Auth0).
"""

from html import escape

import streamlit as st

from paginas import componentes, comum, sessao
from paginas import textos as t


def _comecar(chave: str) -> None:
    if sessao.UTILIZADOR in st.session_state:
        if st.button(
            t.COMECAR, type="primary", icon=":material/arrow_forward:", width="stretch", key=chave
        ):
            st.switch_page(comum.PAGINA_QUESTIONARIO)
    elif st.button(t.ENTRAR, type="primary", icon=":material/login:", width="stretch", key=chave):
        comum.pedir_login()


with st.container(key="faixa_topo"):
    with st.container(key="topo_texto"):
        st.html(
            componentes.selo(t.INICIO_SELO) + f'<h1 class="v-promessa">{escape(t.PROMESSA)}</h1>'
            f'<p class="v-faixa-texto">{escape(t.INICIO_TEXTO)}</p>'
        )
    with st.container(key="topo_media"):
        if not componentes.video_topo(t.VIDEO_DESCRICOES, t.VIDEO_PAUSAR, t.VIDEO_REPRODUZIR):
            componentes.fotografia("inicio_topo", t.ALT_FOTO_INICIO)
    with st.container(key="topo_acao"):
        _comecar("comecar")
        st.html(f'<p class="v-topo-duracao">{escape(t.INICIO_DURACAO)}</p>')
        if comum.RESULTADO in st.session_state:
            st.page_link(
                comum.PAGINA_PLANO,
                label=t.VER_PLANO,
                icon=":material/description:",
                width="stretch",
            )

with st.container(key="faixa_beneficios"):
    st.html(componentes.cartoes(t.BENEFICIOS))

with st.container(key="faixa_como"):
    st.html(f'<h2 class="v-faixa-titulo">{escape(t.INICIO_COMO_TITULO)}</h2>')
    st.html(componentes.passos((titulo, texto) for _, titulo, texto in t.COMO_FUNCIONA))

with st.container(key="faixa_final"):
    st.html(f'<h2 class="v-faixa-titulo">{escape(t.FINAL_TITULO)}</h2>')
    _comecar("comecar_fim")
    st.caption(t.INICIO_SESSAO)
    comum.ligacao_ajuda("como_funciona")

st.html(f'<p class="v-aviso-final">{escape(t.INICIO_AVISO)}</p>')
