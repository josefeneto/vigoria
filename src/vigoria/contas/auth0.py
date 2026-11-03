"""Auth0 fora do st.login: endereço de logout e apagar a conta de entrada (Management API).

A aplicação Machine to Machine tem só a permissão delete:users (docs/GUIA_AUTH0.md, §8).
Se o Auth0 falhar, regista-se só o `sub` (identificador técnico, nunca o email) para o
José apagar a conta à mão no painel.
"""

import logging
from urllib.parse import quote, urlencode

import httpx

from vigoria.config import Auth0

registo = logging.getLogger(__name__)

TIMEOUT_S = 15


def url_logout(auth0: Auth0, regresso: str) -> str:
    """Termina a sessão no Auth0 e volta a `regresso` (tem de estar nas Allowed Logout URLs)."""
    consulta = urlencode({"client_id": auth0.client_id, "returnTo": regresso})
    return f"https://{auth0.dominio}/v2/logout?{consulta}"


def apagar_conta_auth0(sub: str, auth0: Auth0 | None, cliente: httpx.Client | None = None) -> bool:
    """Apaga o utilizador no Auth0. False (e regista o `sub`) se não for possível."""
    if auth0 is None or not auth0.gestao_client_id or auth0.gestao_client_secret is None:
        registo.warning("conta Auth0 por apagar (sem [auth0_gestao]): %s", sub)
        return False
    base = f"https://{auth0.dominio}"
    try:
        with cliente or httpx.Client(timeout=TIMEOUT_S) as http:
            token = http.post(
                f"{base}/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": auth0.gestao_client_id,
                    "client_secret": auth0.gestao_client_secret.get_secret_value(),
                    "audience": f"{base}/api/v2/",
                },
            )
            token.raise_for_status()
            resposta = http.delete(
                f"{base}/api/v2/users/{quote(sub, safe='')}",
                headers={"Authorization": f"Bearer {token.json()['access_token']}"},
            )
            resposta.raise_for_status()
    except (httpx.HTTPError, KeyError, ValueError) as erro:
        codigo = erro.response.status_code if isinstance(erro, httpx.HTTPStatusError) else "-"
        registo.warning(
            "conta Auth0 por apagar (%s, código %s): %s", type(erro).__name__, codigo, sub
        )
        return False
    return True
