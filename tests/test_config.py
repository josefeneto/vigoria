"""Configuração: st.secrets como alternativa ao ambiente e ao .env (Community Cloud)."""

from typing import Any

import pytest
import streamlit as st

from vigoria.config import Configuracao

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
