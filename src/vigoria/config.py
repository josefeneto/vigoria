"""Configuração da aplicação, lida de variáveis de ambiente, do ficheiro .env e, em
alternativa, de st.secrets (Streamlit Community Cloud, AMBIENTE=demo, sem .env).

É o único sítio do código que lê configuração. As chaves ficam em SecretStr
para nunca aparecerem em logs ou mensagens de erro.
"""

from collections.abc import Mapping
from functools import lru_cache
from typing import Any, Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# Fornecedores de LLM: cada um tem <nome>_api_key e <nome>_model (llm/escolha.py).
# «simulado» (llm/simulado.py) não tem chave nem modelo e só é aceite com AMBIENTE=local.
NomeProvedor = Literal["gemini", "groq", "mistral", "simulado"]


class _FonteSecretsStreamlit(PydanticBaseSettingsSource):
    """Chaves de topo do .streamlit/secrets.toml (as secções, como [auth], ficam de fora).

    Prioridade mais baixa: o ambiente e o .env ganham sempre. Sem o ficheiro, não faz nada.
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        try:
            import streamlit as st

            if not st.secrets.load_if_toml_exists():
                return {}
            segredos = st.secrets.to_dict()
        except Exception:  # sem Streamlit ou ficheiro inválido: segue sem st.secrets
            return {}
        campos = self.settings_cls.model_fields
        return {
            k.lower(): v
            for k, v in segredos.items()
            if k.lower() in campos and not isinstance(v, Mapping)
        }


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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _FonteSecretsStreamlit(settings_cls),
            file_secret_settings,
        )

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
        if self.vigoria_provedor_reserva == "simulado":
            raise ValueError("O fornecedor simulado não pode ser a reserva")
        if self.vigoria_provedor_llm == "simulado" and self.ambiente != "local":
            raise ValueError("O fornecedor simulado só é aceite com AMBIENTE=local")
        return self


@lru_cache
def obter_configuracao() -> Configuracao:
    """Devolve a configuração, lida uma única vez."""
    return Configuracao()
