"""Deixar de receber lembretes pela ligação do email, sem sessão iniciada."""

from pydantic import SecretStr
from sqlalchemy.orm import Session

from vigoria.dados import repositorios
from vigoria.notificacoes.token import id_do_token, token_valido


def cancelar_lembretes(s: Session, token: str, segredo: SecretStr | None) -> bool:
    """Desliga os lembretes da conta do token; False se o token não for válido.

    Sem segredo configurado, nenhum token é válido. Só desliga os lembretes por email: o
    acompanhamento e os registos ficam como estão.
    """
    utilizador_id = id_do_token(token)
    if segredo is None or utilizador_id is None:
        return False
    sub = repositorios.sub_do_utilizador(s, utilizador_id)
    if sub is None or not token_valido(token, sub, segredo):
        return False
    repositorios.desligar_lembretes(s, utilizador_id)
    return True
