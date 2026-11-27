"""Gestão (25/11/2026): números da Vigoria e lista de contas, só para VIGORIA_ADMINS.

Desde 26/11/2026 também os lembretes: números, um lembrete de teste para a própria conta
e a simulação do envio de hoje (vigoria.tarefas.lembretes).

O app.py só regista esta página para as contas de administração; a verificação repete-se
aqui, para o caso de alguém chegar cá de outra forma. Os dados vêm de vigoria.dados.gestao.
"""

import logging
from datetime import UTC, datetime

import streamlit as st

from paginas import comum, sessao
from paginas import textos as t
from paginas.navegacao import TEMPORARIO
from vigoria.config import obter_configuracao
from vigoria.dados import gestao
from vigoria.tarefas import lembretes

registo = logging.getLogger(__name__)

# Temporários: ao voltar à Gestão vinda de outra página, já não aparecem (navegacao.py).
TESTE = f"{TEMPORARIO}gestao_teste_lembrete"  # (estado, detalhe) do último envio de teste
SIMULACAO = f"{TEMPORARIO}gestao_simulacao"  # linhas da última simulação
MENSAGENS_TESTE = {
    lembretes.EstadoTeste.ENVIADO: (st.success, t.GESTAO_TESTE_ENVIADO),
    lembretes.EstadoTeste.SEM_CONFIGURACAO: (st.warning, t.GESTAO_TESTE_SEM_CONFIGURACAO),
    lembretes.EstadoTeste.FALHOU: (st.error, t.GESTAO_TESTE_FALHOU),
}


def _cartoes(cartoes: list[tuple[str, int | str, str]]) -> None:
    """Dois por linha (no telemóvel ficam um por baixo do outro)."""
    for linha in range(0, len(cartoes), 2):
        for coluna, (rotulo, valor, nota) in zip(
            st.columns(2), cartoes[linha : linha + 2], strict=False
        ):
            with coluna, st.container(border=True):
                st.metric(rotulo, valor)
                st.caption(nota)


def _periodos(numeros: gestao.Numeros) -> str:
    return t.GESTAO_PERIODOS.format(d7=numeros.ultimos[7], d30=numeros.ultimos[30])


def _enviar_teste() -> None:
    quem = sessao.identidade()
    if quem is None:
        return
    st.session_state[TESTE] = lembretes.enviar_teste(
        obter_configuracao(), sessao.utilizador_id(), quem.sub, quem.email, datetime.now(UTC)
    )


def _simular() -> None:
    linhas: list[str] = []
    lembretes.executar(
        sessao.fabrica(),
        obter_configuracao(),
        datetime.now(UTC),
        simular=True,
        escrever=linhas.append,
    )
    st.session_state[SIMULACAO] = linhas


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
_cartoes(
    [
        (t.GESTAO_ROTULOS["contas_ativas"], resumo.contas_ativas, t.GESTAO_SEM_PERIODO),
        (t.GESTAO_ROTULOS["com_plano"], resumo.com_plano, t.GESTAO_COM_PLANO_NOTA),
    ]
    + [
        (
            t.GESTAO_ROTULOS[tipo.value],
            resumo.contagens[tipo].total,
            _periodos(resumo.contagens[tipo]),
        )
        for tipo in gestao.NUMEROS_GERAIS
    ]
)

st.subheader(t.GESTAO_LEMBRETES)
ultimo = resumo.ultimo_envio_diario
enviados = resumo.contagens[gestao.TipoContagem.LEMBRETE_ENVIADO]
falhados = resumo.contagens[gestao.TipoContagem.LEMBRETE_FALHADO]
cancelados = resumo.contagens[gestao.TipoContagem.LEMBRETES_CANCELADOS]
_cartoes(
    [
        (t.GESTAO_ROTULOS["lembretes_ligados"], resumo.lembretes_ligados, t.GESTAO_LIGADOS_NOTA),
        (
            t.GESTAO_ROTULOS["envio_diario"],
            ultimo.strftime("%d/%m/%Y") if ultimo else t.GESTAO_ENVIO_NUNCA,
            t.GESTAO_ENVIO_NOTA,
        ),
        (t.GESTAO_ROTULOS["lembrete_enviado"], enviados.total, _periodos(enviados)),
        (
            t.GESTAO_ROTULOS["lembrete_falhado"],
            falhados.total,
            t.GESTAO_FALHADO_NOTA.format(d7=falhados.ultimos[7], d30=falhados.ultimos[30]),
        ),
        (
            t.GESTAO_ROTULOS["lembretes_cancelados"],
            cancelados.total,
            t.GESTAO_CANCELADO_NOTA.format(d7=cancelados.ultimos[7], d30=cancelados.ultimos[30]),
        ),
    ]
)

st.subheader(t.GESTAO_TESTES)
quem = sessao.identidade()
st.caption(t.GESTAO_TESTES_NOTA.format(email=quem.email if quem else "—"))
with st.container(horizontal=True, key="gestao_testes"):
    st.button(t.GESTAO_TESTE_ENVIAR, icon=":material/send:", on_click=_enviar_teste)
    st.button(t.GESTAO_SIMULAR, icon=":material/play_circle:", on_click=_simular)
if TESTE in st.session_state:
    estado, detalhe = st.session_state[TESTE]
    mostrar, texto = MENSAGENS_TESTE[estado]
    mostrar(texto.format(email=quem.email if quem else "—", detalhe=detalhe))
if SIMULACAO in st.session_state:
    st.write(t.GESTAO_SIMULAR_TITULO)
    st.code("\n".join(st.session_state[SIMULACAO]), language=None, wrap_lines=True)

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
