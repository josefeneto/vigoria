"""Configuração da aplicação, lida de variáveis de ambiente e do ficheiro .env.

É o único sítio do código que lê configuração. As chaves ficam em SecretStr
para nunca aparecerem em logs ou mensagens de erro.
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    """Variáveis definidas em .env.example."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: SecretStr | None = None
    gemini_model: str = ""
    groq_api_key: SecretStr | None = None
    groq_model: str = ""
    database_url: str = "sqlite:///vigoria_local.db"
    brevo_api_key: SecretStr | None = None
    email_remetente: str = ""
    email_nome_remetente: str = "Vigoria"
    app_url: str = "http://localhost:8501"
    ambiente: Literal["local", "demo", "producao"] = "local"


@lru_cache
def obter_configuracao() -> Configuracao:
    """Devolve a configuração, lida uma única vez."""
    return Configuracao()
