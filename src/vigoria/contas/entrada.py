"""Quem entrou: a identidade a partir das claims do token do Auth0 (st.user), sem Streamlit.

O utilizador é o `sub` (permanente); o email serve só para contacto e para detetar a
mesma pessoa com outro método de entrada.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

GOOGLE = "google-oauth2"


class Identidade(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: str
    email: str  # em minúsculas
    email_verificado: bool

    @property
    def fornecedor(self) -> str:
        """«google-oauth2», «auth0» (email e palavra-passe), …: o que vem antes de «|»."""
        return self.sub.split("|", 1)[0]


def normalizar_email(email: str) -> str:
    """Para comparar: sem maiúsculas nem espaços (incluindo os do meio)."""
    return "".join(email.split()).lower()


def convidado(
    identidade: Identidade, permitidos: frozenset[str], *, lista_obrigatoria: bool = False
) -> bool:
    """Lista de convidados (fase de testes): só emails verificados da lista.

    Lista vazia: todos entram, exceto com `lista_obrigatoria` (demonstração pública), em que
    ninguém entra. `permitidos` já vem normalizado (config.py).
    """
    return identidade.email_verificado and email_convidado(
        identidade.email, permitidos, lista_obrigatoria=lista_obrigatoria
    )


def email_convidado(
    email: str, permitidos: frozenset[str], *, lista_obrigatoria: bool = False
) -> bool:
    """A mesma regra para um email já verificado (por exemplo, na tarefa dos lembretes)."""
    if not permitidos:
        return not lista_obrigatoria
    return normalizar_email(email) in permitidos


def identidade_de(claims: Mapping[str, Any]) -> Identidade:
    """Levanta ValueError se faltar o sub ou o email (configuração errada no Auth0)."""
    sub = str(claims.get("sub") or "")
    email = str(claims.get("email") or "").strip().lower()
    if not sub or not email:
        raise ValueError("O token não traz sub ou email: confirmar o scope «openid email».")
    verificado = claims.get("email_verified") is True or sub.startswith(f"{GOOGLE}|")
    return Identidade(sub=sub, email=email, email_verificado=verificado)
