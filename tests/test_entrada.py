"""Identidade a partir das claims do Auth0 (contas/entrada.py)."""

import pytest

from vigoria.contas.entrada import (
    Identidade,
    convidado,
    email_convidado,
    identidade_de,
    ninguem_entra,
    normalizar_email,
)


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


# ---------------------------------------------------------------- Lista de convidados

ANA = Identidade(sub="auth0|1", email="ana@exemplo.pt", email_verificado=True)
LISTA = frozenset({"ana@exemplo.pt", "rui@exemplo.pt"})


def test_por_omissao_so_convidados_e_lista_vazia_ninguem_entra() -> None:
    assert not convidado(ANA, frozenset())
    assert not email_convidado(ANA.email, frozenset())
    assert ninguem_entra(frozenset(), "convidados")
    assert not ninguem_entra(LISTA, "convidados")


def test_acesso_aberto_todos_entram_com_ou_sem_lista() -> None:
    outro = ANA.model_copy(update={"email": "outro@exemplo.pt"})
    assert convidado(ANA, frozenset(), "aberto")
    assert convidado(outro, LISTA, "aberto")
    assert email_convidado("outro@exemplo.pt", frozenset(), "aberto")
    assert not ninguem_entra(frozenset(), "aberto")


def test_acesso_aberto_exige_email_verificado() -> None:
    assert not convidado(ANA.model_copy(update={"email_verificado": False}), frozenset(), "aberto")


def test_so_entra_quem_esta_na_lista() -> None:
    assert convidado(ANA, LISTA)
    assert not convidado(ANA.model_copy(update={"email": "outro@exemplo.pt"}), LISTA)


def test_lista_exige_email_verificado() -> None:
    assert not convidado(ANA.model_copy(update={"email_verificado": False}), LISTA)


def test_comparacao_sem_maiusculas_nem_espacos() -> None:
    assert normalizar_email("  Ana @Exemplo.PT ") == "ana@exemplo.pt"
    assert convidado(ANA.model_copy(update={"email": "ANA@exemplo.pt "}), LISTA)


def test_convidados_com_lista_entra_quem_esta_nela() -> None:
    assert convidado(ANA, LISTA, "convidados")
    assert email_convidado(" ANA@exemplo.pt", LISTA, "convidados")
    assert not email_convidado("outro@exemplo.pt", LISTA, "convidados")
