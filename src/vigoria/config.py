"""Configuração da aplicação, lida de variáveis de ambiente e do ficheiro .env.

É o único sítio do código que lê configuração. As chaves ficam em SecretStr
para nunca aparecerem em logs ou mensagens de erro.
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Fornecedores de LLM: cada um tem <nome>_api_key e <nome>_model (llm/escolha.py).
NomeProvedor = Literal["gemini", "groq", "mistral"]


class Configuracao(BaseSettings):
    """Variáveis definidas em .env.example."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    vigoria_provedor_llm: NomeProvedor = "gemini"
    vigoria_provedor_reserva: NomeProvedor | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str = ""
    groq_api_key: SecretStr | None = None
    groq_model: str = ""
    mistral_api_key: SecretStr | None = None
    mistral_model: str = ""
    database_url: str = "sqlite:///vigoria_local.db"
    brevo_api_key: SecretStr | None = None
    email_remetente: str = ""
    email_nome_remetente: str = "Vigoria"
    app_url: str = "http://localhost:8501"
    ambiente: Literal["local", "demo", "producao"] = "local"

    @field_validator("vigoria_provedor_reserva", mode="before")
    @classmethod
    def _reserva_vazia(cls, valor: object) -> object:
        return None if valor == "" else valor

    @model_validator(mode="after")
    def _reserva_diferente(self) -> Configuracao:
        if self.vigoria_provedor_reserva == self.vigoria_provedor_llm:
            raise ValueError(
                "VIGORIA_PROVEDOR_RESERVA tem de ser diferente de VIGORIA_PROVEDOR_LLM"
            )
        return self


@lru_cache
def obter_configuracao() -> Configuracao:
    """Devolve a configuração, lida uma única vez."""
    return Configuracao()
