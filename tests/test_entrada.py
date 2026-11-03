"""Identidade a partir das claims do Auth0 (contas/entrada.py)."""

import pytest

from vigoria.contas.entrada import identidade_de


def test_email_e_palavra_passe_verificado() -> None:
    i = identidade_de({"sub": "auth0|1", "email": " Ana@Exemplo.PT ", "email_verified": True})
    assert (i.sub, i.email, i.email_verificado, i.fornecedor) == (
        "auth0|1",
        "ana@exemplo.pt",
        True,
        "auth0",
    )


@pytest.mark.parametrize("valor", [False, None, "true", 1])
def test_email_por_verificar(valor: object) -> None:
    claims = {"sub": "auth0|1", "email": "a@exemplo.pt", "email_verified": valor}
    assert not identidade_de(claims).email_verificado


def test_google_conta_como_verificado() -> None:
    i = identidade_de({"sub": "google-oauth2|9", "email": "a@gmail.com"})
    assert i.email_verificado
    assert i.fornecedor == "google-oauth2"


@pytest.mark.parametrize("claims", [{}, {"sub": "auth0|1"}, {"email": "a@exemplo.pt"}])
def test_sem_sub_ou_email_e_erro_de_configuracao(claims: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="sub ou email"):
        identidade_de(claims)
