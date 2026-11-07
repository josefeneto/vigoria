"""Ligação «Deixar de receber lembretes»: um token assinado, válido sem sessão iniciada.

Token = id do utilizador + HMAC-SHA256 (segredo próprio) sobre «lembretes:v1:id:sub». O `sub`
não aparece na ligação, mas entra na assinatura: se a conta for apagada e o id reutilizado, o
token antigo deixa de valer. Sem prazo de validade (a ligação de um email antigo continua a
servir para desligar os lembretes).
"""

import base64
import hashlib
import hmac

from pydantic import SecretStr

_PREFIXO = "lembretes:v1"


def _assinatura(utilizador_id: int, sub: str, segredo: SecretStr) -> str:
    mensagem = f"{_PREFIXO}:{utilizador_id}:{sub}".encode()
    digest = hmac.new(segredo.get_secret_value().encode(), mensagem, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def gerar_token(utilizador_id: int, sub: str, segredo: SecretStr) -> str:
    return f"{utilizador_id}.{_assinatura(utilizador_id, sub, segredo)}"


def id_do_token(token: str) -> int | None:
    """O id do utilizador que o token indica (ainda por verificar); None se estiver malformado."""
    id_texto, separador, assinatura = token.strip().partition(".")
    if not separador or not assinatura or not id_texto.isascii() or not id_texto.isdigit():
        return None
    return int(id_texto)


def token_valido(token: str, sub: str, segredo: SecretStr) -> bool:
    """O token foi gerado para este utilizador (id e `sub`) com este segredo."""
    utilizador_id = id_do_token(token)
    if utilizador_id is None:
        return False
    esperado = gerar_token(utilizador_id, sub, segredo)
    return hmac.compare_digest(token.strip().encode(), esperado.encode())
