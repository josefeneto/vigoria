"""Configuração: st.secrets como alternativa ao ambiente e ao .env (Community Cloud)."""

from typing import Any

import pytest
import streamlit as st

from vigoria.config import Configuracao, obter_auth0

SEGREDOS = {
    "AMBIENTE": "demo",
    "GEMINI_MODEL": "modelo-dos-secrets",
    "GROQ_MODEL": "reserva-dos-secrets",
    "VIGORIA_PROVEDOR_RESERVA": "groq",
    "auth": {"redirect_uri": "https://exemplo.streamlit.app/oauth2callback"},
    "DESCONHECIDA": "ignorada",
}


def _secrets(monkeypatch: pytest.MonkeyPatch, segredos: dict[str, Any] | None) -> None:
    # Na classe: o objeto st.secrets não aceita atribuição de atributos.
    classe = type(st.secrets)
    monkeypatch.setattr(classe, "load_if_toml_exists", lambda self: segredos is not None)
    monkeypatch.setattr(classe, "to_dict", lambda self: dict(segredos or {}))


def test_le_chaves_de_topo_do_st_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    _secrets(monkeypatch, SEGREDOS)
    for nome in ("AMBIENTE", "GEMINI_MODEL", "GROQ_MODEL", "VIGORIA_PROVEDOR_RESERVA"):
        monkeypatch.delenv(nome, raising=False)
    config = Configuracao(_env_file=None)  # type: ignore[call-arg]
    assert config.ambiente == "demo"
    assert (config.gemini_model, config.groq_model) == ("modelo-dos-secrets", "reserva-dos-secrets")
    assert config.vigoria_provedor_reserva == "groq"


def test_ambiente_ganha_ao_st_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    _secrets(monkeypatch, SEGREDOS)
    monkeypatch.setenv("GEMINI_MODEL", "modelo-do-ambiente")
    monkeypatch.delenv("AMBIENTE", raising=False)
    config = Configuracao(_env_file=None)  # type: ignore[call-arg]
    assert config.gemini_model == "modelo-do-ambiente"
    assert config.ambiente == "demo"


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


def test_utilizador_local_so_em_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "1")
    monkeypatch.setenv("AMBIENTE", "local")
    assert Configuracao(_env_file=None).vigoria_utilizador_local  # type: ignore[call-arg]
    for ambiente in ("demo", "producao"):
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
    assert (auth0.dominio, auth0.client_id) == ("vigoria.eu.auth0.com", "app")
    assert auth0.gestao_client_id is None and auth0.gestao_client_secret is None
    _secrets(monkeypatch, AUTH | {"auth0_gestao": {"client_id": "m2m", "client_secret": "seg"}})
    auth0 = obter_auth0()
    assert auth0 is not None and auth0.gestao_client_secret is not None
    assert auth0.gestao_client_id == "m2m"
    assert auth0.gestao_client_secret.get_secret_value() == "seg"
    assert "seg" not in repr(auth0)
