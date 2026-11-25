"""Gestão (25/11/2026): números da Vigoria e lista de contas, só para VIGORIA_ADMINS.

O app.py só regista esta página para as contas de administração; a verificação repete-se
aqui, para o caso de alguém chegar cá de outra forma. Os dados vêm de vigoria.dados.gestao.
"""

import logging

import streamlit as st

from paginas import comum, sessao
from paginas import textos as t
from vigoria.dados import gestao

registo = logging.getLogger(__name__)

if not sessao.e_admin():
    st.switch_page(comum.PAGINA_INICIO)

st.title(t.PAGINAS["gestao"])
st.caption(t.GESTAO_INTRO)

try:
    with sessao.fabrica().begin() as s:
        resumo = gestao.resumo(s, comum.hoje())
        contas = gestao.contas(s)
except Exception as e:  # sem o conteúdo: só o tipo do erro
    registo.error("gestão não lida: %s", type(e).__name__)
    st.error(t.GESTAO_ERRO)
    comum.parar()

st.subheader(t.GESTAO_NUMEROS)
cartoes: list[tuple[str, int, str]] = [
    (t.GESTAO_ROTULOS["contas_ativas"], resumo.contas_ativas, t.GESTAO_SEM_PERIODO),
    (t.GESTAO_ROTULOS["com_plano"], resumo.com_plano, t.GESTAO_COM_PLANO_NOTA),
]
for tipo, numeros in resumo.contagens.items():
    periodos = t.GESTAO_PERIODOS.format(d7=numeros.ultimos[7], d30=numeros.ultimos[30])
    cartoes.append((t.GESTAO_ROTULOS[tipo.value], numeros.total, periodos))
for linha in range(0, len(cartoes), 2):
    for coluna, (rotulo, valor, nota) in zip(
        st.columns(2), cartoes[linha : linha + 2], strict=False
    ):
        with coluna, st.container(border=True):
            st.metric(rotulo, valor)
            st.caption(nota)

st.subheader(t.GESTAO_CONTAS)
st.caption(t.GESTAO_CONTAS_NOTA)
if not contas:
    st.info(t.GESTAO_SEM_CONTAS)
else:
    tabela = [
        dict(
            zip(
                t.GESTAO_COLUNAS,
                (
                    c.email,
                    t.GESTAO_FORNECEDORES.get(c.fornecedor, c.fornecedor),
                    c.criada_em.strftime("%d/%m/%Y"),
                    c.planos,
                ),
                strict=True,
            )
        )
        for c in contas
    ]
    st.dataframe(tabela, hide_index=True, width="stretch")
    st.download_button(
        t.GESTAO_CSV,
        data=gestao.contas_csv(contas, t.GESTAO_COLUNAS).encode("utf-8"),
        file_name=t.GESTAO_CSV_FICHEIRO.format(data=comum.hoje().isoformat()),
        mime="text/csv",
        icon=":material/download:",
        on_click="ignore",
    )
