"""Apoio comum às páginas: estado da sessão, erros junto aos campos e avisos do plano."""

from typing import Any

import streamlit as st

from paginas import sessao
from vigoria.conteudo.carregar import carregar_avisos
from vigoria.dados import repositorios
from vigoria.interface.estado import PREFIXO, chave, estado_inicial, para_estado, para_respostas
from vigoria.interface.passos import CAMPOS, respostas_de_questionario
from vigoria.modelos.plano import Plano

ERROS = "erros_passo"  # {campo: mensagem}, preenchido ao carregar em «Seguinte»
PASSO = "passo"
RESULTADO = "resultado"  # PlanoDaConta (dados/repositorios.py) do plano que se está a ver
ERRO_GUARDAR = "erro_guardar"  # o plano gerado não ficou guardado na conta
CONTA_APAGADA = "conta_apagada"  # True/False: a conta de entrada no Auth0 também foi apagada
CARREGADO = "conta_carregada"  # o último plano e as últimas respostas já vieram da conta
TERMINADO_GRAVIDEZ = "terminado_gravidez"

PAGINA_INICIO = "paginas/inicio.py"
PAGINA_QUESTIONARIO = "paginas/questionario.py"
PAGINA_PLANO = "paginas/plano.py"
PAGINA_PRIVACIDADE = "paginas/privacidade.py"
PAGINA_CONTA = "paginas/conta.py"


def iniciar_estado() -> None:
    """Chaves de todos os widgets do questionário, antes de os desenhar."""
    for k, v in estado_inicial().items():
        st.session_state.setdefault(k, v)
    st.session_state.setdefault(PASSO, "0")


def carregar_da_conta(utilizador_id: int) -> None:
    """No início da sessão: o último plano guardado e as últimas respostas, sem gerar de novo.

    Os consentimentos do passo 0 não vêm preenchidos: voltam a marcar-se em cada plano.
    """
    if st.session_state.get(CARREGADO):
        return
    st.session_state[CARREGADO] = True
    with sessao.fabrica().begin() as s:
        plano = repositorios.ultimo_plano(s, utilizador_id)
        q = repositorios.ultimo_questionario(s, utilizador_id)
    if plano is not None:
        st.session_state[RESULTADO] = plano
    if q is not None:
        consentimentos = {chave(c) for c in CAMPOS["0"]}
        for k, v in para_estado(respostas_de_questionario(q)).items():
            st.session_state[k] = False if k in consentimentos else v


def respostas() -> dict[str, Any]:
    return para_respostas(st.session_state.to_dict())


def apagar_respostas() -> None:
    """Apaga todas as respostas e o plano (gravidez e recomeçar)."""
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith(PREFIXO):
            del st.session_state[k]
    for k in (ERROS, RESULTADO):
        st.session_state.pop(k, None)
    st.session_state[PASSO] = "0"


def widget(campo: str, opcao: str | None = None) -> dict[str, Any]:
    """Argumentos comuns: chave e valor guardado na sessão, mesmo noutro passo ou página."""
    return {"key": chave(campo, opcao), "persist_state": "session"}


def erro(campo: str) -> None:
    """Mostra o erro de validação deste campo, se houver."""
    mensagem = st.session_state.get(ERROS, {}).get(campo)
    if mensagem:
        st.error(mensagem, icon=":material/error:")


def avisos(plano: Plano, chave: str) -> None:
    """Avisos de segurança: no fim de cada separador do plano, em caixa bem visível."""
    with st.container(key=f"avisos{chave}"):
        st.warning(
            "\n".join(f"- {a}" for a in plano.avisos),
            title=carregar_avisos().rotulos.plano["avisos"],
            icon=":material/health_and_safety:",
        )
