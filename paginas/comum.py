"""Apoio comum às páginas: estado da sessão, erros junto aos campos e avisos do plano."""

from typing import Any

import streamlit as st

from vigoria.conteudo.carregar import carregar_avisos
from vigoria.interface.estado import PREFIXO, chave, estado_inicial, para_respostas
from vigoria.modelos.plano import Plano

ERROS = "erros_passo"  # {campo: mensagem}, preenchido ao carregar em «Seguinte»
PASSO = "passo"
RESULTADO = "resultado"  # ResultadoPipeline do último plano gerado
TERMINADO_GRAVIDEZ = "terminado_gravidez"

PAGINA_QUESTIONARIO = "paginas/questionario.py"
PAGINA_PLANO = "paginas/plano.py"
PAGINA_PRIVACIDADE = "paginas/privacidade.py"


def iniciar_estado() -> None:
    """Chaves de todos os widgets do questionário, antes de os desenhar."""
    for k, v in estado_inicial().items():
        st.session_state.setdefault(k, v)
    st.session_state.setdefault(PASSO, "0")


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


def avisos(plano: Plano) -> None:
    """Avisos de segurança: no fim de cada separador do plano."""
    st.warning(
        "\n".join(f"- {a}" for a in plano.avisos),
        title=carregar_avisos().rotulos.plano["avisos"],
        icon=":material/health_and_safety:",
    )
