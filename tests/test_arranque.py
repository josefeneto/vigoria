"""Arranque no contentor (Fase 10A): secrets.toml a partir do ambiente e migrações."""

import os
import tomllib
from pathlib import Path

import pytest

from vigoria import arranque
from vigoria.arranque import CABECALHO, ErroArranque, escrever_secrets, secrets_toml
from vigoria.config import Configuracao

AMBIENTE = {
    "AMBIENTE": "producao",
    "AUTH_REDIRECT_URI": "https://app.vigoria.pt/oauth2callback",
    "AUTH_COOKIE_SECRET": "segredo-do-cookie-0123456789abcdef",
    "AUTH0_CLIENT_ID": "id-cliente",
    "AUTH0_CLIENT_SECRET": 'segredo"com\\aspas',
    "AUTH0_SERVER_METADATA_URL": "https://t.eu.auth0.com/.well-known/openid-configuration",
}
GESTAO = {"AUTH0_GESTAO_CLIENT_ID": "id-gestao", "AUTH0_GESTAO_CLIENT_SECRET": "seg-gestao"}


def test_toml_valido_com_as_secoes_do_streamlit() -> None:
    dados = tomllib.loads(secrets_toml(AMBIENTE | GESTAO))
    assert dados["auth"]["redirect_uri"] == AMBIENTE["AUTH_REDIRECT_URI"]
    assert dados["auth"]["cookie_secret"] == AMBIENTE["AUTH_COOKIE_SECRET"]
    auth0 = dados["auth"]["auth0"]
    assert auth0["client_secret"] == 'segredo"com\\aspas'  # aspas e barras escapadas
    assert auth0["server_metadata_url"] == AMBIENTE["AUTH0_SERVER_METADATA_URL"]
    assert auth0["client_kwargs"] == {"prompt": "login"}
    assert dados["auth0_gestao"] == {"client_id": "id-gestao", "client_secret": "seg-gestao"}


def test_sem_gestao_nao_ha_secao() -> None:
    assert "auth0_gestao" not in tomllib.loads(secrets_toml(AMBIENTE))


def test_gestao_pela_metade_e_recusada() -> None:
    with pytest.raises(ErroArranque, match="as duas ou nenhuma"):
        secrets_toml(AMBIENTE | {"AUTH0_GESTAO_CLIENT_ID": "x"})


def test_variaveis_em_falta_pelo_nome_sem_valores() -> None:
    incompleto = {k: v for k, v in AMBIENTE.items() if k != "AUTH0_CLIENT_SECRET"}
    incompleto["AUTH_COOKIE_SECRET"] = "   "
    with pytest.raises(ErroArranque) as erro:
        secrets_toml(incompleto)
    mensagem = str(erro.value)
    assert "AUTH0_CLIENT_SECRET" in mensagem and "AUTH_COOKIE_SECRET" in mensagem
    assert "id-cliente" not in mensagem


def test_quebra_de_linha_num_valor_e_recusada_sem_o_mostrar() -> None:
    with pytest.raises(ErroArranque) as erro:
        secrets_toml(AMBIENTE | {"AUTH0_CLIENT_ID": "abc\ninjetado = 1"})
    assert "injetado" not in str(erro.value)


def test_escreve_com_permissao_do_dono(tmp_path: Path) -> None:
    destino = tmp_path / ".streamlit" / "secrets.toml"
    escrever_secrets(destino, AMBIENTE)
    assert destino.read_text(encoding="utf-8").startswith(CABECALHO)
    if os.name == "posix":  # no Windows, as permissões Unix não se aplicam
        assert destino.stat().st_mode & 0o777 == 0o600
    escrever_secrets(destino, AMBIENTE | {"AUTH0_CLIENT_ID": "outro"})  # o seu: substitui
    assert "outro" in destino.read_text(encoding="utf-8")


def test_nunca_substitui_um_secrets_feito_a_mao(tmp_path: Path) -> None:
    destino = tmp_path / "secrets.toml"
    destino.write_text('[auth]\nredirect_uri = "local"\n', encoding="utf-8")
    with pytest.raises(ErroArranque, match="não foi gerado"):
        escrever_secrets(destino, AMBIENTE)
    assert destino.read_text(encoding="utf-8") == '[auth]\nredirect_uri = "local"\n'


def _config(url: str) -> Configuracao:
    return Configuracao(
        _env_file=None, ambiente="producao", vigoria_provedor_llm="groq", database_url=url
    )


def test_principal_gera_e_migra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "v.db"
    monkeypatch.setattr(arranque, "obter_configuracao", lambda: _config(f"sqlite:///{base}"))
    destino = tmp_path / "secrets.toml"
    assert arranque.principal(AMBIENTE, destino) == 0
    assert destino.exists() and base.exists()
    saida = capsys.readouterr()
    assert "segredo" not in saida.out + saida.err


def test_migracao_falhada_da_erro_claro_sem_o_endereco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    url = "postgresql+psycopg://utilizador:palavra-passe@127.0.0.1:1/base"
    monkeypatch.setattr(arranque, "obter_configuracao", lambda: _config(url))
    assert arranque.principal(AMBIENTE, tmp_path / "secrets.toml") == 1
    erro = capsys.readouterr().err
    assert "A migração da base de dados falhou" in erro
    assert "palavra-passe" not in erro and "127.0.0.1" not in erro


def test_sem_ambiente_nao_arranca(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sem = {k: v for k, v in AMBIENTE.items() if k != "AMBIENTE"}
    assert arranque.principal(sem, tmp_path / "secrets.toml") == 1
    assert "AMBIENTE" in capsys.readouterr().err
    assert not (tmp_path / "secrets.toml").exists()


# ---------------------------------------------------------------- Endereços (Fase 10C)


@pytest.mark.parametrize(
    "metadados",
    [
        "t.eu.auth0.com/.well-known/openid-configuration",  # sem https://
        "https://t.eu.auth0.com",  # sem o fim
        "http://t.eu.auth0.com/.well-known/openid-configuration",
    ],
)
def test_endereco_do_auth0_mal_copiado_para_o_arranque(metadados: str) -> None:
    with pytest.raises(ErroArranque, match="AUTH0_SERVER_METADATA_URL") as erro:
        secrets_toml(AMBIENTE | {"AUTH0_SERVER_METADATA_URL": metadados})
    assert "t.eu.auth0.com" not in str(erro.value)  # o nome, nunca o valor


@pytest.mark.parametrize("regresso", ["https://app.vigoria.pt", "app.vigoria.pt/oauth2callback"])
def test_regresso_sem_oauth2callback_para_o_arranque(regresso: str) -> None:
    with pytest.raises(ErroArranque, match="AUTH_REDIRECT_URI"):
        secrets_toml(AMBIENTE | {"AUTH_REDIRECT_URI": regresso})


def test_regresso_local_em_http_e_aceite() -> None:
    secrets_toml(AMBIENTE | {"AUTH_REDIRECT_URI": "http://localhost:8080/oauth2callback"})
