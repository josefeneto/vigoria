"""Ligação «Deixar de receber lembretes»: um token assinado, válido sem sessão iniciada.

Token v2 (Fase 10) = «id.expira.assinatura»: id do utilizador, fim da validade (segundos Unix,
UTC) e HMAC-SHA256 (segredo próprio) sobre «lembretes:v2:id:sub:expira». O `sub` não aparece
na ligação, mas entra na assinatura: se a conta for apagada e o id reutilizado, o token antigo
deixa de valer. Vale 90 dias a contar do envio (decisão do José, 11/11/2026). Os tokens v1
(«id.assinatura», sem prazo, Fase 8) são recusados.
"""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import SecretStr

_PREFIXO = "lembretes:v2"
VALIDADE = timedelta(days=90)


class EstadoToken(StrEnum):
    VALIDO = "valido"
    INVALIDO = "invalido"  # malformado, adulterado, de outra conta ou v1
    EXPIRADO = "expirado"  # assinatura certa, mas fora do prazo


def _assinatura(utilizador_id: int, sub: str, expira: int, segredo: SecretStr) -> str:
    mensagem = f"{_PREFIXO}:{utilizador_id}:{sub}:{expira}".encode()
    digest = hmac.new(segredo.get_secret_value().encode(), mensagem, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def gerar_token(utilizador_id: int, sub: str, segredo: SecretStr, agora: datetime) -> str:
    """Token válido até `agora` + 90 dias (`agora` com fuso)."""
    expira = int((agora + VALIDADE).timestamp())
    return f"{utilizador_id}.{expira}.{_assinatura(utilizador_id, sub, expira, segredo)}"


def _partes(token: str) -> tuple[int, int, str] | None:
    partes = token.strip().split(".")
    if len(partes) != 3 or not partes[2]:
        return None
    id_texto, expira_texto, assinatura = partes
    for texto in (id_texto, expira_texto):
        if not texto.isascii() or not texto.isdigit():
            return None
    return int(id_texto), int(expira_texto), assinatura


def id_do_token(token: str) -> int | None:
    """O id do utilizador que o token indica (ainda por verificar); None se estiver malformado."""
    partes = _partes(token)
    return None if partes is None else partes[0]


def verificar_token(token: str, sub: str, segredo: SecretStr, agora: datetime) -> EstadoToken:
    """Primeiro a assinatura (id, `sub`, prazo e segredo), depois o prazo."""
    partes = _partes(token)
    if partes is None:
        return EstadoToken.INVALIDO
    utilizador_id, expira, assinatura = partes
    esperada = _assinatura(utilizador_id, sub, expira, segredo)
    if not hmac.compare_digest(assinatura.encode(), esperada.encode()):
        return EstadoToken.INVALIDO
    if agora.timestamp() > expira:
        return EstadoToken.EXPIRADO
    return EstadoToken.VALIDO


def token_valido(token: str, sub: str, segredo: SecretStr, agora: datetime) -> bool:
    return verificar_token(token, sub, segredo, agora) is EstadoToken.VALIDO
