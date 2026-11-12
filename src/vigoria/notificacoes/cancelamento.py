"""Deixar de receber lembretes pela ligação do email, sem sessão iniciada.

Usado pela página Streamlit (demo, paginas/cancelar_lembretes.py) e pelo serviço de
cancelamento num clique (produção, vigoria/web/cancelar.py).
"""

from datetime import datetime

from pydantic import SecretStr
from sqlalchemy.orm import Session

from vigoria.dados import repositorios
from vigoria.notificacoes.token import EstadoToken, id_do_token, verificar_token


def estado_da_ligacao(
    s: Session, token: str, segredo: SecretStr | None, agora: datetime
) -> EstadoToken:
    """Só lê: o token é desta conta e está no prazo? Sem segredo configurado, nunca vale."""
    utilizador_id = id_do_token(token)
    if segredo is None or utilizador_id is None:
        return EstadoToken.INVALIDO
    sub = repositorios.sub_do_utilizador(s, utilizador_id)
    if sub is None:
        return EstadoToken.INVALIDO
    return verificar_token(token, sub, segredo, agora)


def cancelar_lembretes(
    s: Session, token: str, segredo: SecretStr | None, agora: datetime
) -> EstadoToken:
    """Desliga os lembretes da conta do token, se for válido; devolve o estado do token.

    Só desliga os lembretes por email: o acompanhamento e os registos ficam como estão.
    """
    estado = estado_da_ligacao(s, token, segredo, agora)
    if estado is EstadoToken.VALIDO:
        utilizador_id = id_do_token(token)
        assert utilizador_id is not None
        repositorios.desligar_lembretes(s, utilizador_id)
    return estado
