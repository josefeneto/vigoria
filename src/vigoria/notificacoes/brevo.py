"""Envio de emails pela API transacional do Brevo (https://developers.brevo.com), com httpx.

Nos registos ficam só metadados técnicos (estado HTTP, messageId, tipo de erro): nunca o
endereço, o assunto nem o conteúdo. Sem novas tentativas: a tarefa do dia seguinte trata disso.
"""

import logging
from enum import StrEnum

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr

registo = logging.getLogger(__name__)

URL_ENVIO = "https://api.brevo.com/v3/smtp/email"
TEMPO_MAXIMO_S = 10.0


class TipoErroEnvio(StrEnum):
    AUTENTICACAO = "autenticacao"  # 401/403: chave errada ou remetente por validar
    PEDIDO_INVALIDO = "pedido_invalido"  # 400 e outros 4xx
    LIMITE = "limite"  # 429: limite de envios (300/dia no plano gratuito)
    INDISPONIVEL = "indisponivel"  # 5xx
    REDE = "rede"  # sem ligação ou tempo máximo excedido


class ErroEnvio(Exception):
    def __init__(self, tipo: TipoErroEnvio, estado: int | None = None) -> None:
        super().__init__(f"envio falhou: {tipo}" + (f" (HTTP {estado})" if estado else ""))
        self.tipo = tipo
        self.estado = estado


class Email(BaseModel):
    model_config = ConfigDict(frozen=True)

    para: str
    assunto: str
    html: str
    texto: str
    cabecalhos: dict[str, str] = {}
    etiqueta: str = "lembrete"


def _tipo_do_estado(estado: int) -> TipoErroEnvio:
    if estado in (401, 403):
        return TipoErroEnvio.AUTENTICACAO
    if estado == 429:
        return TipoErroEnvio.LIMITE
    if estado >= 500:
        return TipoErroEnvio.INDISPONIVEL
    return TipoErroEnvio.PEDIDO_INVALIDO


def enviar(
    email: Email,
    *,
    chave: SecretStr,
    remetente: str,
    nome_remetente: str,
    client: httpx.Client | None = None,
) -> str:
    """Envia um email; devolve o messageId do Brevo. Falhas → ErroEnvio."""
    corpo = {
        "sender": {"email": remetente, "name": nome_remetente},
        "to": [{"email": email.para}],
        "subject": email.assunto,
        "htmlContent": email.html,
        "textContent": email.texto,
        "headers": email.cabecalhos,
        "tags": [email.etiqueta],
    }
    cabecalhos = {
        "api-key": chave.get_secret_value(),
        "accept": "application/json",
        "content-type": "application/json",
    }
    proprio = client is None
    cliente = client or httpx.Client(timeout=TEMPO_MAXIMO_S)
    try:
        resposta = cliente.post(URL_ENVIO, json=corpo, headers=cabecalhos, timeout=TEMPO_MAXIMO_S)
    except httpx.HTTPError as erro:
        registo.warning("brevo: sem resposta (%s)", type(erro).__name__)
        raise ErroEnvio(TipoErroEnvio.REDE) from None
    finally:
        if proprio:
            cliente.close()
    if resposta.status_code >= 400:
        tipo = _tipo_do_estado(resposta.status_code)
        registo.warning("brevo: HTTP %s (%s)", resposta.status_code, tipo)
        raise ErroEnvio(tipo, resposta.status_code)
    try:
        identificador = str(resposta.json().get("messageId", ""))
    except ValueError:
        identificador = ""
    registo.info("brevo: enviado, HTTP %s, messageId %s", resposta.status_code, identificador)
    return identificador
