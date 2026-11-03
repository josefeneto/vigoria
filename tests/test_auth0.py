"""Auth0: logout e apagar a conta pela Management API (sem rede: httpx.MockTransport)."""

import logging
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import SecretStr

from vigoria.config import Auth0
from vigoria.contas.auth0 import apagar_conta_auth0, url_logout

AUTH0 = Auth0(
    dominio="vigoria.eu.auth0.com",
    client_id="cliente-app",
    gestao_client_id="cliente-m2m",
    gestao_client_secret=SecretStr("segredo-m2m"),
)
SUB = "google-oauth2|123/456"
EMAIL = "pessoa@exemplo.pt"


def _cliente(pedidos: list[httpx.Request], estado_delete: int = 204) -> httpx.Client:
    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        if pedido.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "tok", "token_type": "Bearer"})
        return httpx.Response(estado_delete)

    return httpx.Client(transport=httpx.MockTransport(responder))


def test_url_logout() -> None:
    url = urlparse(url_logout(AUTH0, "http://localhost:8501/sair"))
    assert (url.scheme, url.hostname, url.path) == ("https", "vigoria.eu.auth0.com", "/v2/logout")
    assert parse_qs(url.query) == {
        "client_id": ["cliente-app"],
        "returnTo": ["http://localhost:8501/sair"],
    }


def test_apaga_com_token_e_sub_codificado() -> None:
    pedidos: list[httpx.Request] = []
    assert apagar_conta_auth0(SUB, AUTH0, _cliente(pedidos))
    token, apagar = pedidos
    assert token.method == "POST"
    corpo = httpx.Response(200, content=token.content).json()
    assert corpo["audience"] == "https://vigoria.eu.auth0.com/api/v2/"
    assert corpo["grant_type"] == "client_credentials"
    assert apagar.method == "DELETE"
    # «|» e «/» codificados: o sub inteiro é um único segmento do caminho.
    assert apagar.url.raw_path == b"/api/v2/users/google-oauth2%7C123%2F456"
    assert apagar.headers["Authorization"] == "Bearer tok"


@pytest.mark.parametrize("estado", [403, 404, 429, 500])
def test_falha_do_auth0_regista_so_o_sub(estado: int, caplog: pytest.LogCaptureFixture) -> None:
    pedidos: list[httpx.Request] = []
    with caplog.at_level(logging.WARNING):
        assert not apagar_conta_auth0(SUB, AUTH0, _cliente(pedidos, estado))
    assert SUB in caplog.text
    assert str(estado) in caplog.text
    assert "segredo-m2m" not in caplog.text and "tok" not in caplog.text


def test_erro_de_rede(caplog: pytest.LogCaptureFixture) -> None:
    def falhar(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    with caplog.at_level(logging.WARNING):
        assert not apagar_conta_auth0(
            SUB, AUTH0, httpx.Client(transport=httpx.MockTransport(falhar))
        )
    assert SUB in caplog.text


@pytest.mark.parametrize(
    "auth0",
    [None, AUTH0.model_copy(update={"gestao_client_id": None, "gestao_client_secret": None})],
)
def test_sem_aplicacao_de_gestao_nao_chama_o_auth0(
    auth0: Auth0 | None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert not apagar_conta_auth0(SUB, auth0)
    assert SUB in caplog.text
    assert EMAIL not in caplog.text
