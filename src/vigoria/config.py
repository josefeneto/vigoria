"""Configuração da aplicação, lida de variáveis de ambiente, do ficheiro .env e, em
alternativa, de st.secrets (Streamlit Community Cloud, AMBIENTE=demo, sem .env).

É o único sítio do código que lê configuração. As chaves ficam em SecretStr
para nunca aparecerem em logs ou mensagens de erro.
"""

import re
from collections.abc import Mapping
from functools import lru_cache
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from vigoria.contas.entrada import normalizar_email

# Fornecedores de LLM: cada um tem <nome>_api_key e <nome>_model (llm/escolha.py).
# «simulado» (llm/simulado.py) não tem chave nem modelo e só é aceite com AMBIENTE=local.
NomeProvedor = Literal["gemini", "groq", "mistral", "simulado"]
MINIMO_SEGREDO = 32


def _segredos() -> dict[str, Any]:
    """O .streamlit/secrets.toml como dicionário; vazio sem ficheiro ou sem Streamlit."""
    try:
        import streamlit as st

        if not st.secrets.load_if_toml_exists():
            return {}
        return st.secrets.to_dict()
    except Exception:  # sem Streamlit ou ficheiro inválido: segue sem st.secrets
        return {}


class _FonteSecretsStreamlit(PydanticBaseSettingsSource):
    """Chaves de topo do .streamlit/secrets.toml (as secções, como [auth], ficam de fora).

    Prioridade mais baixa: o ambiente e o .env ganham sempre. Sem o ficheiro, não faz nada.
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        segredos = _segredos()
        campos = self.settings_cls.model_fields
        return {
            k.lower(): v
            for k, v in segredos.items()
            if k.lower() in campos and not isinstance(v, Mapping)
        }


class Configuracao(BaseSettings):
    """Variáveis definidas em .env.example."""

    # hide_input_in_errors: um valor recusado (por exemplo, o DATABASE_URL com a palavra-passe)
    # nunca aparece na mensagem de erro nem nos registos do GitHub Actions.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

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
    # Assina as ligações «Deixar de receber lembretes» (notificacoes/token.py). Igual na app e
    # na tarefa dos lembretes; mudá-lo invalida as ligações dos emails já enviados.
    vigoria_segredo_lembretes: SecretStr | None = None
    ambiente: Literal["local", "demo", "producao"] = "local"
    # Só para testes e desenvolvimento sem Auth0: entra como um utilizador fictício fixo.
    vigoria_utilizador_local: bool = False
    # Fase de testes só por convite: emails separados por vírgulas (ou lista TOML nos secrets).
    # Vazia ou ausente: todos podem entrar.
    vigoria_emails_permitidos: Annotated[frozenset[str], NoDecode] = frozenset()

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

    @field_validator("vigoria_emails_permitidos", mode="before")
    @classmethod
    def _lista_de_emails(cls, valor: object) -> object:
        """«a@x.pt, b@y.pt» ou ["a@x.pt", "b@y.pt"] → conjunto normalizado (sem vazios)."""
        if isinstance(valor, str):
            valor = re.split(r"[,;\n]", valor)
        if isinstance(valor, (list, tuple, set, frozenset)):
            return frozenset(normalizar_email(str(e)) for e in valor if str(e).strip())
        return valor

    @field_validator("vigoria_segredo_lembretes", mode="after")
    @classmethod
    def _segredo_comprido(cls, valor: SecretStr | None) -> SecretStr | None:
        if valor is None or not valor.get_secret_value():
            return None
        if len(valor.get_secret_value()) < MINIMO_SEGREDO:
            raise ValueError(
                f"VIGORIA_SEGREDO_LEMBRETES tem de ter pelo menos {MINIMO_SEGREDO} caracteres"
            )
        return valor

    @field_validator("app_url")
    @classmethod
    def _sem_barra_final(cls, valor: str) -> str:
        return valor.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def _postgresql_com_psycopg(cls, valor: str) -> str:
        """Tira espaços e aspas coladas por engano; o Neon dá «postgresql://…» e o SQLAlchemy
        precisa do controlador (psycopg 3). A mensagem de erro nunca mostra o valor."""
        valor = valor.strip().strip("\"'").strip()
        if not valor:
            raise ValueError("DATABASE_URL está vazio (confirme o nome e o valor do segredo)")
        if not re.match(r"^[a-z][a-z0-9+]*://", valor):
            raise ValueError(
                "DATABASE_URL mal formado: deve ser só o endereço, a começar por "
                "«postgresql://», sem nome da variável, «=», aspas nem «psql»"
            )
        for prefixo in ("postgres://", "postgresql://"):
            if valor.startswith(prefixo):
                return "postgresql+psycopg://" + valor.removeprefix(prefixo)
        return valor

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
        if self.vigoria_utilizador_local and self.ambiente != "local":
            raise ValueError("VIGORIA_UTILIZADOR_LOCAL só é aceite com AMBIENTE=local")
        return self


@lru_cache
def obter_configuracao() -> Configuracao:
    """Devolve a configuração, lida uma única vez."""
    return Configuracao()


# ---------------------------------------------------------------- Auth0 (st.secrets)


class Auth0(BaseModel):
    """O que a app precisa do Auth0 além do st.login: a Management API, para apagar contas."""

    model_config = ConfigDict(frozen=True)

    dominio: str  # por exemplo vigoria.eu.auth0.com
    gestao_client_id: str | None = None  # aplicação Machine to Machine ([auth0_gestao])
    gestao_client_secret: SecretStr | None = None


def obter_auth0() -> Auth0 | None:
    """Lido das secções [auth.auth0] e [auth0_gestao]; None se o login não estiver configurado."""
    segredos = _segredos()
    auth0 = (segredos.get("auth") or {}).get("auth0") or {}
    dominio = urlparse(str(auth0.get("server_metadata_url") or "")).hostname
    if not dominio or not auth0.get("client_id"):
        return None
    gestao = segredos.get("auth0_gestao") or {}
    segredo = gestao.get("client_secret")
    return Auth0(
        dominio=dominio,
        gestao_client_id=gestao.get("client_id") or None,
        gestao_client_secret=SecretStr(segredo) if segredo else None,
    )
