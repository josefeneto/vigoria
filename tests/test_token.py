"""Ligação «Deixar de receber lembretes» (notificacoes/token.py): token v2 com 90 dias."""

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from vigoria.notificacoes.token import (
    VALIDADE,
    EstadoToken,
    gerar_token,
    id_do_token,
    token_valido,
    verificar_token,
)

SEGREDO = SecretStr("s" * 48)
OUTRO_SEGREDO = SecretStr("t" * 48)
SUB = "auth0|aaa"
AGORA = datetime(2026, 11, 12, 9, 7, tzinfo=UTC)


def test_token_valido_para_o_proprio_sem_dados_pessoais() -> None:
    token = gerar_token(12, SUB, SEGREDO, AGORA)
    assert id_do_token(token) == 12
    assert verificar_token(token, SUB, SEGREDO, AGORA) is EstadoToken.VALIDO
    assert SUB not in token and "aaa" not in token and "@" not in token
    assert token.split(".")[1] == str(int((AGORA + VALIDADE).timestamp()))


def test_validade_de_90_dias() -> None:
    assert timedelta(days=90) == VALIDADE
    token = gerar_token(12, SUB, SEGREDO, AGORA)
    assert token_valido(token, SUB, SEGREDO, AGORA + VALIDADE)  # o último segundo ainda vale
    fora = AGORA + VALIDADE + timedelta(seconds=1)
    assert verificar_token(token, SUB, SEGREDO, fora) is EstadoToken.EXPIRADO


def test_prazo_alterado_nao_vale() -> None:
    """Esticar o prazo à mão parte a assinatura: dá inválido, não expirado nem válido."""
    utilizador, expira, assinatura = gerar_token(12, SUB, SEGREDO, AGORA).split(".")
    esticado = f"{utilizador}.{int(expira) + 86_400 * 365}.{assinatura}"
    assert verificar_token(esticado, SUB, SEGREDO, AGORA) is EstadoToken.INVALIDO


def test_token_alterado_nao_vale() -> None:
    token = gerar_token(12, SUB, SEGREDO, AGORA)
    assert not token_valido("13" + token[2:], SUB, SEGREDO, AGORA)
    ultimo = "A" if token[-1] != "A" else "B"
    assert not token_valido(token[:-1] + ultimo, SUB, SEGREDO, AGORA)


def test_outro_segredo_nao_vale() -> None:
    assert not token_valido(gerar_token(12, SUB, OUTRO_SEGREDO, AGORA), SUB, SEGREDO, AGORA)


def test_outro_sub_nao_vale() -> None:
    """Conta apagada e id reutilizado: o token antigo deixa de servir."""
    token = gerar_token(12, SUB, SEGREDO, AGORA)
    assert not token_valido(token, "google-oauth2|bbb", SEGREDO, AGORA)


def test_expirado_de_outra_conta_e_invalido() -> None:
    """A assinatura vem antes do prazo: não se revela se um token alheio já expirou."""
    token = gerar_token(12, SUB, SEGREDO, AGORA)
    depois = AGORA + timedelta(days=200)
    assert verificar_token(token, "google-oauth2|bbb", SEGREDO, depois) is EstadoToken.INVALIDO


def test_token_v1_e_recusado() -> None:
    """O formato da Fase 8 («id.assinatura», sem prazo) deixou de valer (José, 11/11/2026)."""
    mensagem = f"lembretes:v1:12:{SUB}".encode()
    digest = hmac.new(SEGREDO.get_secret_value().encode(), mensagem, hashlib.sha256).digest()
    v1 = "12." + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert id_do_token(v1) is None
    assert verificar_token(v1, SUB, SEGREDO, AGORA) is EstadoToken.INVALIDO


@pytest.mark.parametrize(
    "token", ["", "12", "12.", "12.1", "12.1.", ".1.abc", "abc.1.def", "-1.1.abc", "١٢.1.abc"]
)
def test_token_malformado(token: str) -> None:
    assert id_do_token(token) is None
    assert verificar_token(token, SUB, SEGREDO, AGORA) is EstadoToken.INVALIDO
