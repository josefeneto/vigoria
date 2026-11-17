"""Configuração: ambiente e .env; o .streamlit/secrets.toml só serve o login (Auth0)."""

from typing import Any

import pytest
import streamlit as st
from pydantic import ValidationError

from vigoria.config import Configuracao, obter_auth0

SEGREDOS = {
    "AMBIENTE": "producao",
    "GEMINI_MODEL": "modelo-dos-secrets",
    "auth": {"redirect_uri": "https://app.vigoria.pt/oauth2callback"},
}


def _secrets(monkeypatch: pytest.MonkeyPatch, segredos: dict[str, Any] | None) -> None:
    # Na classe: o objeto st.secrets não aceita atribuição de atributos.
    classe = type(st.secrets)
    monkeypatch.setattr(classe, "load_if_toml_exists", lambda self: segredos is not None)
    monkeypatch.setattr(classe, "to_dict", lambda self: dict(segredos or {}))


def test_chaves_de_topo_do_secrets_toml_sao_ignoradas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o Streamlit Community Cloud, a configuração vem só do ambiente e do .env."""
    _secrets(monkeypatch, SEGREDOS)
    for nome in ("AMBIENTE", "GEMINI_MODEL"):
        monkeypatch.delenv(nome, raising=False)
    config = Configuracao(_env_file=None)  # type: ignore[call-arg]
    assert config.ambiente == "local"
    assert config.gemini_model != "modelo-dos-secrets"


def test_demo_deixou_de_ser_um_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AMBIENTE", "demo")
    with pytest.raises(ValidationError, match="ambiente"):
        Configuracao(_env_file=None)  # type: ignore[call-arg]


def test_sem_secrets_toml_usa_os_valores_por_omissao(monkeypatch: pytest.MonkeyPatch) -> None:
    _secrets(monkeypatch, None)
    monkeypatch.delenv("AMBIENTE", raising=False)
    assert Configuracao(_env_file=None).ambiente == "local"  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        (
            "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/vigoria?sslmode=require",
            "postgresql+psycopg://u:p@ep-x.eu-central-1.aws.neon.tech/vigoria?sslmode=require",
        ),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///vigoria_local.db", "sqlite:///vigoria_local.db"),
    ],
)
def test_database_url_do_neon_usa_psycopg(
    monkeypatch: pytest.MonkeyPatch, url: str, esperado: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    assert Configuracao().database_url == esperado


@pytest.mark.parametrize(
    "url",
    [
        '  "postgresql://u:p@h/db"  ',
        "'postgresql://u:p@h/db'",
        " postgresql://u:p@h/db\n",
    ],
)
def test_database_url_sem_aspas_nem_espacos(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    assert Configuracao().database_url == "postgresql+psycopg://u:p@h/db"


@pytest.mark.parametrize(
    ("url", "mensagem"),
    [
        ("", "vazio"),
        ('""', "vazio"),
        ('DATABASE_URL = "postgresql://u:segredo123@h/db"', "mal formado"),
        ("psql 'postgresql://u:segredo123@h/db'", "mal formado"),
        ("u:segredo123@h/db", "mal formado"),
    ],
)
def test_database_url_errado_da_mensagem_clara_sem_o_valor(
    monkeypatch: pytest.MonkeyPatch, url: str, mensagem: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(ValidationError) as erro:
        Configuracao()
    assert mensagem in str(erro.value)
    assert "segredo123" not in str(erro.value)


def test_utilizador_local_so_em_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "1")
    monkeypatch.setenv("AMBIENTE", "local")
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "groq")  # o Gemini é recusado em produção
    assert Configuracao(_env_file=None).vigoria_utilizador_local  # type: ignore[call-arg]
    for ambiente in ("producao",):
        monkeypatch.setenv("AMBIENTE", ambiente)
        with pytest.raises(ValueError, match="VIGORIA_UTILIZADOR_LOCAL"):
            Configuracao(_env_file=None)  # type: ignore[call-arg]


AUTH = {
    "auth": {
        "redirect_uri": "http://localhost:8501/oauth2callback",
        "cookie_secret": "x",
        "auth0": {
            "client_id": "app",
            "client_secret": "s",
            "server_metadata_url": "https://vigoria.eu.auth0.com/.well-known/openid-configuration",
        },
    }
}


def test_obter_auth0_sem_login_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    _secrets(monkeypatch, None)
    assert obter_auth0() is None
    _secrets(monkeypatch, {"auth": {"auth0": {"client_id": "app"}}})
    assert obter_auth0() is None


def test_obter_auth0_sem_e_com_gestao(monkeypatch: pytest.MonkeyPatch) -> None:
    _secrets(monkeypatch, AUTH)
    auth0 = obter_auth0()
    assert auth0 is not None
    assert auth0.dominio == "vigoria.eu.auth0.com"
    assert auth0.gestao_client_id is None and auth0.gestao_client_secret is None
    _secrets(monkeypatch, AUTH | {"auth0_gestao": {"client_id": "m2m", "client_secret": "seg"}})
    auth0 = obter_auth0()
    assert auth0 is not None and auth0.gestao_client_secret is not None
    assert auth0.gestao_client_id == "m2m"
    assert auth0.gestao_client_secret.get_secret_value() == "seg"
    assert "seg" not in repr(auth0)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (" Ana@Exemplo.PT , rui@exemplo.pt;;", {"ana@exemplo.pt", "rui@exemplo.pt"}),
        ("", set()),
        (",  ,", set()),
    ],
)
def test_emails_permitidos_do_ambiente(
    monkeypatch: pytest.MonkeyPatch, valor: str, esperado: set[str]
) -> None:
    _secrets(monkeypatch, None)
    monkeypatch.setenv("VIGORIA_EMAILS_PERMITIDOS", valor)
    config = Configuracao(_env_file=None)  # type: ignore[call-arg]
    assert config.vigoria_emails_permitidos == frozenset(esperado)


def test_emails_permitidos_em_lista_ou_texto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIGORIA_EMAILS_PERMITIDOS", raising=False)
    for valor in (["Ana@exemplo.pt", " rui@exemplo.pt "], "ana@exemplo.pt,\nrui@exemplo.pt"):
        config = Configuracao(_env_file=None, vigoria_emails_permitidos=valor)  # type: ignore[call-arg]
        assert config.vigoria_emails_permitidos == {"ana@exemplo.pt", "rui@exemplo.pt"}


def test_sem_lista_de_emails_todos_permitidos(monkeypatch: pytest.MonkeyPatch) -> None:
    _secrets(monkeypatch, None)
    monkeypatch.delenv("VIGORIA_EMAILS_PERMITIDOS", raising=False)
    assert Configuracao(_env_file=None).vigoria_emails_permitidos == frozenset()  # type: ignore[call-arg]
