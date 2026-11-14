"""Quem entrou: a identidade a partir das claims do token do Auth0 (st.user), sem Streamlit.

O utilizador é o `sub` (permanente); o email serve só para contacto e para detetar a
mesma pessoa com outro método de entrada.
"""

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

GOOGLE = "google-oauth2"

# VIGORIA_ACESSO: «convidados» (beta fechado, por omissão) ou «aberto».
type Acesso = Literal["convidados", "aberto"]
AVISO_LISTA_VAZIA = "VIGORIA_ACESSO=convidados com VIGORIA_EMAILS_PERMITIDOS vazia: ninguém entra"


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
    identidade: Identidade, permitidos: frozenset[str], acesso: Acesso = "convidados"
) -> bool:
    """Quem pode entrar (VIGORIA_ACESSO): sempre só com o email verificado.

    «convidados»: só os emails da lista; lista vazia, ninguém entra (falha fechada).
    «aberto»: todos. `permitidos` já vem normalizado (config.py).
    """
    return identidade.email_verificado and email_convidado(identidade.email, permitidos, acesso)


def email_convidado(email: str, permitidos: frozenset[str], acesso: Acesso = "convidados") -> bool:
    """A mesma regra para um email já verificado (por exemplo, na tarefa dos lembretes)."""
    if acesso == "aberto":
        return True
    return normalizar_email(email) in permitidos


def ninguem_entra(permitidos: frozenset[str], acesso: Acesso) -> bool:
    """Só convidados e a lista vazia: configuração quase de certeza esquecida (avisar)."""
    return acesso == "convidados" and not permitidos


def identidade_de(claims: Mapping[str, Any]) -> Identidade:
    """Levanta ValueError se faltar o sub ou o email (configuração errada no Auth0)."""
    sub = str(claims.get("sub") or "")
    email = str(claims.get("email") or "").strip().lower()
    if not sub or not email:
        raise ValueError("O token não traz sub ou email: confirmar o scope «openid email».")
    verificado = claims.get("email_verified") is True or sub.startswith(f"{GOOGLE}|")
    return Identidade(sub=sub, email=email, email_verificado=verificado)
