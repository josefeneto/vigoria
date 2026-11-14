"""Ajuda (Fase 8B): perguntas frequentes por tema, com ou sem sessão iniciada.

O texto vem de conteudo/ajuda.yaml, com os números preenchidos pelo código
(vigoria.interface.ajuda). Com ?tema=<id> (ligações «Como funciona?»), esse tema aparece
primeiro e com as perguntas abertas: os st.expander não se abrem por âncora no endereço.
"""

import streamlit as st

from paginas import textos as t
from vigoria.config import obter_configuracao
from vigoria.interface.ajuda import ajuda

pedido = st.query_params.get("tema")

st.title(t.AJUDA_TITULO)
st.write(t.AJUDA_INTRO)
config = obter_configuracao()
for tema in ajuda(config.ambiente, primeiro=pedido, acesso=config.vigoria_acesso):
    st.subheader(tema.titulo, anchor=tema.id)
    for p in tema.perguntas:
        # Sem key: com key, o estado aberto/fechado guardava-se e ignorava um ?tema novo.
        with st.expander(p.pergunta, expanded=tema.id == pedido):
            st.markdown(p.resposta)
