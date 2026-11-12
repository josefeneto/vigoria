"""Envio pelo Brevo (notificacoes/brevo.py), sempre simulado com httpx.MockTransport."""

import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from vigoria.notificacoes import brevo
from vigoria.notificacoes.brevo import Email, ErroEnvio, TipoErroEnvio
from vigoria.notificacoes.lembrete import email_lembrete

CHAVE = SecretStr("xkeysib-teste")
PARA = "ana.silva@exemplo.pt"


def _email() -> Email:
    return email_lembrete(PARA, 1, "https://vigoria.exemplo", "12.assinatura")


def _cliente(resposta: httpx.Response, pedidos: list[httpx.Request]) -> httpx.Client:
    def tratar(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return resposta

    return httpx.Client(transport=httpx.MockTransport(tratar))


def _enviar(client: httpx.Client) -> str:
    return brevo.enviar(
        _email(), chave=CHAVE, remetente="geral@vigoria.pt", nome_remetente="Vigoria", client=client
    )


def test_pedido_ao_brevo() -> None:
    pedidos: list[httpx.Request] = []
    resposta = httpx.Response(201, json={"messageId": "<abc@smtp-relay>"})
    assert _enviar(_cliente(resposta, pedidos)) == "<abc@smtp-relay>"
    (pedido,) = pedidos
    assert str(pedido.url) == brevo.URL_ENVIO
    assert pedido.headers["api-key"] == "xkeysib-teste"
    corpo = json.loads(pedido.content)
    assert corpo["sender"] == {"email": "geral@vigoria.pt", "name": "Vigoria"}
    assert corpo["to"] == [{"email": PARA}]
    assert corpo["subject"] == "Tem um registo por fazer na Vigoria"
    assert corpo["htmlContent"] and corpo["textContent"]
    assert corpo["headers"] == {
        "List-Unsubscribe": "<https://vigoria.exemplo/cancelar-lembretes?t=12.assinatura>"
    }
    # Os cabeçalhos passam tal como vêm do email (o List-Unsubscribe-Post só em produção).


@pytest.mark.parametrize(
    ("estado", "tipo"),
    [
        (400, TipoErroEnvio.PEDIDO_INVALIDO),
        (401, TipoErroEnvio.AUTENTICACAO),
        (403, TipoErroEnvio.AUTENTICACAO),
        (429, TipoErroEnvio.LIMITE),
        (500, TipoErroEnvio.INDISPONIVEL),
        (503, TipoErroEnvio.INDISPONIVEL),
    ],
)
def test_erros_do_brevo(estado: int, tipo: TipoErroEnvio) -> None:
    pedidos: list[httpx.Request] = []
    with pytest.raises(ErroEnvio) as erro:
        _enviar(_cliente(httpx.Response(estado, json={"message": "x"}), pedidos))
    assert erro.value.tipo is tipo
    assert erro.value.estado == estado
    assert len(pedidos) == 1  # sem novas tentativas


def test_tempo_esgotado_e_rede() -> None:
    def esgotado(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento", request=pedido)

    with pytest.raises(ErroEnvio) as erro:
        _enviar(httpx.Client(transport=httpx.MockTransport(esgotado)))
    assert erro.value.tipo is TipoErroEnvio.REDE


def test_tempo_maximo_definido(monkeypatch: pytest.MonkeyPatch) -> None:
    opcoes: dict[str, object] = {}

    def post(_self: httpx.Client, _url: str, **o: object) -> httpx.Response:
        opcoes.update(o)
        return httpx.Response(201, json={"messageId": "x"})

    monkeypatch.setattr(httpx.Client, "post", post)
    brevo.enviar(_email(), chave=CHAVE, remetente="geral@vigoria.pt", nome_remetente="Vigoria")
    assert opcoes["timeout"] == brevo.TEMPO_MAXIMO_S


def test_registos_sem_email_nem_conteudo(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    _enviar(_cliente(httpx.Response(201, json={"messageId": "m1"}), []))
    with pytest.raises(ErroEnvio):
        _enviar(_cliente(httpx.Response(400, json={"message": PARA}), []))
    texto = caplog.text
    assert "m1" in texto and "400" in texto
    for proibido in (PARA, "ana.silva", "registo por fazer", "xkeysib", "assinatura"):
        assert proibido not in texto
