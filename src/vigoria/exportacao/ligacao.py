"""Ligação curta para descarregar o plano (PDF) ou os dados (JSON) na app instalada (25/11/2026).

No iPhone, com a Vigoria instalada no ecrã principal, um ficheiro descarregado abre por cima
da app sem forma de voltar. Por isso, aí, o botão abre /descarregar?t=… no Safari por cima
da app (com «OK»), servido pelo Starlette (web/cancelar.py). O endereço não leva sessão:
leva este token.

Token = «tipo.id.plano.expira.assinatura»: tipo («pdf» ou «dados»), id do utilizador, id do
plano (0 nos dados), fim da validade (segundos Unix, UTC) e HMAC-SHA256 sobre
«descarregar:v1:tipo:id:sub:plano:expira», com VIGORIA_SEGREDO_LEMBRETES. O prefixo próprio
impede que um token de lembretes sirva aqui (e vice-versa). O `sub` entra na assinatura sem
aparecer no endereço. Vale 30 minutos: chega para ler a página antes de carregar no botão.
"""

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import SecretStr

_PREFIXO = "descarregar:v1"
VALIDADE = timedelta(minutes=30)
CAMINHO = "/descarregar"


class TipoDescarga(StrEnum):
    PDF = "pdf"
    DADOS = "dados"


class EstadoLigacao(StrEnum):
    VALIDA = "valida"
    INVALIDA = "invalida"  # malformada, adulterada ou de outra conta
    EXPIRADA = "expirada"


@dataclass(frozen=True)
class PedidoDescarga:
    """O que o token diz (ainda por verificar, salvo depois de `verificar`)."""

    tipo: TipoDescarga
    utilizador_id: int
    plano_id: int
    expira: int
    assinatura: str


def _assinatura(
    tipo: TipoDescarga, utilizador_id: int, sub: str, plano_id: int, expira: int, segredo: SecretStr
) -> str:
    mensagem = f"{_PREFIXO}:{tipo}:{utilizador_id}:{sub}:{plano_id}:{expira}".encode()
    digest = hmac.new(segredo.get_secret_value().encode(), mensagem, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def gerar(
    tipo: TipoDescarga,
    utilizador_id: int,
    sub: str,
    segredo: SecretStr,
    agora: datetime,
    plano_id: int = 0,
) -> str:
    """Token válido até `agora` + 30 minutos (`agora` com fuso)."""
    expira = int((agora + VALIDADE).timestamp())
    assinatura = _assinatura(tipo, utilizador_id, sub, plano_id, expira, segredo)
    return f"{tipo}.{utilizador_id}.{plano_id}.{expira}.{assinatura}"


def ler(token: str) -> PedidoDescarga | None:
    """As partes do token; None se estiver malformado (nada verificado ainda)."""
    partes = token.strip().split(".")
    if len(partes) != 5 or not partes[4]:
        return None
    tipo, *numeros, assinatura = partes
    if tipo not in set(TipoDescarga) or not all(n.isascii() and n.isdigit() for n in numeros):
        return None
    utilizador_id, plano_id, expira = (int(n) for n in numeros)
    return PedidoDescarga(TipoDescarga(tipo), utilizador_id, plano_id, expira, assinatura)


def verificar(
    pedido: PedidoDescarga, sub: str, segredo: SecretStr, agora: datetime
) -> EstadoLigacao:
    """Primeiro a assinatura (com o `sub` da conta), depois o prazo."""
    esperada = _assinatura(
        pedido.tipo, pedido.utilizador_id, sub, pedido.plano_id, pedido.expira, segredo
    )
    if not hmac.compare_digest(pedido.assinatura.encode(), esperada.encode()):
        return EstadoLigacao.INVALIDA
    if agora.timestamp() > pedido.expira:
        return EstadoLigacao.EXPIRADA
    return EstadoLigacao.VALIDA


def url(token: str) -> str:
    """Endereço relativo: a app e o Starlette estão no mesmo domínio (Caddy)."""
    return f"{CAMINHO}?t={token}"
