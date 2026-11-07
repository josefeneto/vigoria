"""Ligação «Deixar de receber lembretes» (notificacoes/token.py)."""

import pytest
from pydantic import SecretStr

from vigoria.notificacoes.token import gerar_token, id_do_token, token_valido

SEGREDO = SecretStr("s" * 48)
OUTRO_SEGREDO = SecretStr("t" * 48)
SUB = "auth0|aaa"


def test_token_valido_para_o_proprio() -> None:
    token = gerar_token(12, SUB, SEGREDO)
    assert id_do_token(token) == 12
    assert token_valido(token, SUB, SEGREDO)
    assert SUB not in token and "aaa" not in token


def test_token_alterado_nao_vale() -> None:
    token = gerar_token(12, SUB, SEGREDO)
    outro_id = "13" + token[2:]
    assert not token_valido(outro_id, SUB, SEGREDO)
    ultimo = "A" if token[-1] != "A" else "B"
    assert not token_valido(token[:-1] + ultimo, SUB, SEGREDO)


def test_outro_segredo_nao_vale() -> None:
    assert not token_valido(gerar_token(12, SUB, OUTRO_SEGREDO), SUB, SEGREDO)


def test_outro_sub_nao_vale() -> None:
    """Conta apagada e id reutilizado: o token antigo deixa de servir."""
    assert not token_valido(gerar_token(12, SUB, SEGREDO), "google-oauth2|bbb", SEGREDO)


@pytest.mark.parametrize("token", ["", "12", "12.", ".abc", "abc.def", "-1.abc", "١٢.abc"])
def test_token_malformado(token: str) -> None:
    assert id_do_token(token) is None
    assert not token_valido(token, SUB, SEGREDO)
