"""Arranque no contentor (Fase 10): gera o .streamlit/secrets.toml e aplica as migrações.

Uso (docker/arrancar.sh, antes do Streamlit): python -m vigoria.arranque

O st.login lê o Auth0 do .streamlit/secrets.toml. No Railway, os valores vêm das variáveis do
serviço e o ficheiro é escrito só dentro do contentor (nunca entra na imagem nem no Git). As
mensagens dizem o nome da variável em falta, nunca um valor.
"""

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from vigoria.config import obter_configuracao
from vigoria.dados.bd import criar_motor, migrar

DESTINO = Path(".streamlit") / "secrets.toml"
CABECALHO = "# Gerado por python -m vigoria.arranque a partir das variáveis de ambiente.\n"

OBRIGATORIAS = (
    "AUTH_REDIRECT_URI",
    "AUTH_COOKIE_SECRET",
    "AUTH0_CLIENT_ID",
    "AUTH0_CLIENT_SECRET",
    "AUTH0_SERVER_METADATA_URL",
)
GESTAO = ("AUTH0_GESTAO_CLIENT_ID", "AUTH0_GESTAO_CLIENT_SECRET")


class ErroArranque(Exception):
    """Falha que impede o arranque; a mensagem nunca contém valores."""


def _texto_toml(valor: str) -> str:
    """Cadeia básica TOML (aspas e barras escapadas; sem caracteres de controlo)."""
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in valor):
        raise ErroArranque("Um valor do Auth0 tem caracteres de controlo (quebra de linha?).")
    return '"' + valor.replace("\\", "\\\\").replace('"', '\\"') + '"'


def secrets_toml(ambiente: Mapping[str, str]) -> str:
    """O conteúdo do secrets.toml; ErroArranque com os nomes das variáveis em falta."""
    valores = {nome: ambiente.get(nome, "").strip() for nome in (*OBRIGATORIAS, *GESTAO)}
    em_falta = [nome for nome in OBRIGATORIAS if not valores[nome]]
    if em_falta:
        raise ErroArranque("Variáveis em falta: " + ", ".join(em_falta))
    gestao = [valores[nome] for nome in GESTAO]
    if any(gestao) and not all(gestao):
        raise ErroArranque(
            "AUTH0_GESTAO_CLIENT_ID e AUTH0_GESTAO_CLIENT_SECRET definem-se as duas ou nenhuma."
        )
    linhas = [
        CABECALHO,
        "[auth]",
        f"redirect_uri = {_texto_toml(valores['AUTH_REDIRECT_URI'])}",
        f"cookie_secret = {_texto_toml(valores['AUTH_COOKIE_SECRET'])}",
        "",
        "[auth.auth0]",
        f"client_id = {_texto_toml(valores['AUTH0_CLIENT_ID'])}",
        f"client_secret = {_texto_toml(valores['AUTH0_CLIENT_SECRET'])}",
        f"server_metadata_url = {_texto_toml(valores['AUTH0_SERVER_METADATA_URL'])}",
        # Obriga a escolher a conta em cada entrada (computadores partilhados).
        'client_kwargs = { "prompt" = "login" }',
    ]
    if all(gestao):
        linhas += [
            "",
            "[auth0_gestao]",
            f"client_id = {_texto_toml(valores['AUTH0_GESTAO_CLIENT_ID'])}",
            f"client_secret = {_texto_toml(valores['AUTH0_GESTAO_CLIENT_SECRET'])}",
        ]
    return "\n".join(linhas) + "\n"


def escrever_secrets(destino: Path, ambiente: Mapping[str, str]) -> None:
    """Escreve o ficheiro só com permissão do dono (600).

    Recusa substituir um secrets.toml que não tenha sido gerado por aqui: em local, o ficheiro
    do José nunca é apagado por engano.
    """
    conteudo = secrets_toml(ambiente)
    if destino.exists() and not destino.read_text(encoding="utf-8").startswith(CABECALHO):
        raise ErroArranque(f"{destino} já existe e não foi gerado pelo arranque: não o substituo.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    descritor = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as ficheiro:
        ficheiro.write(conteudo)


def migrar_base() -> None:
    """Equivale a «python -m alembic upgrade head», com o DATABASE_URL da configuração.

    Em caso de erro, só o tipo da exceção: a mensagem do controlador pode citar o endereço.
    """
    try:
        motor = criar_motor(obter_configuracao().database_url)
        try:
            migrar(motor)
        finally:
            motor.dispose()
    except Exception as erro:
        raise ErroArranque(
            f"A migração da base de dados falhou ({type(erro).__name__}). Confirme o "
            "DATABASE_URL e se a base de dados está acessível."
        ) from None


def principal(ambiente: Mapping[str, str] | None = None, destino: Path = DESTINO) -> int:
    ambiente = os.environ if ambiente is None else ambiente
    try:
        if not ambiente.get("AMBIENTE", "").strip():
            raise ErroArranque("Variável em falta: AMBIENTE (demo ou producao).")
        try:
            config = obter_configuracao()  # falha já se a configuração for inválida
        except Exception as erro:
            raise ErroArranque(f"Configuração inválida: {erro}") from None
        escrever_secrets(destino, ambiente)
        print(f"arranque: {destino} gerado (AMBIENTE={config.ambiente})", flush=True)
        migrar_base()
        print("arranque: base de dados atualizada (alembic upgrade head)", flush=True)
    except ErroArranque as erro:
        print(f"arranque: ERRO: {erro}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(principal())
