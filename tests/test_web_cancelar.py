"""Serviço de cancelamento num clique (vigoria/web/cancelar.py, Fase 10B), com o TestClient
do Starlette e SQLite em memória."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from vigoria.config import Configuracao
from vigoria.conteudo.carregar import carregar_avisos
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.tabelas import Utilizador
from vigoria.motor.voz import encontrar_termos
from vigoria.notificacoes.lembrete import textos_cancelar
from vigoria.notificacoes.token import gerar_token
from vigoria.web.cancelar import criar_app

SEGREDO = "s" * 48
AGORA = datetime(2026, 11, 12, 9, 7, tzinfo=UTC)
UM_CLIQUE = {"List-Unsubscribe": "One-Click"}  # o corpo que o Gmail envia (RFC 8058)


@pytest.fixture
def fabrica() -> Iterator[sessionmaker[Session]]:
    motor = criar_motor("sqlite://")
    migrar(motor)
    yield fabrica_sessoes(motor)
    motor.dispose()


def _config(segredo: str | None = SEGREDO) -> Configuracao:
    return Configuracao(
        _env_file=None,  # type: ignore[call-arg]
        ambiente="producao",
        vigoria_provedor_llm="groq",
        vigoria_segredo_lembretes=segredo,
    )


def _cliente(fabrica: sessionmaker[Session], **opcoes: object) -> TestClient:
    app = criar_app(fabrica, opcoes.get("config") or _config(), lambda: AGORA)  # type: ignore[arg-type]
    return TestClient(app)


def _conta(fabrica: sessionmaker[Session], sub: str, email: str) -> int:
    with fabrica.begin() as s:
        u = Utilizador(sub=sub, fornecedor="auth0", email=email)
        s.add(u)
        s.flush()
        return u.id


def _lembretes(fabrica: sessionmaker[Session], uid: int) -> bool:
    with fabrica.begin() as s:
        return r.obter_preferencias(s, uid).lembretes_email


def _token(uid: int, sub: str, quando: datetime = AGORA) -> str:
    return gerar_token(uid, sub, SecretStr(SEGREDO), quando)


class _Pagina(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.texto: list[str] = []
        self.formularios: list[dict[str, str | None]] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.texto.append(data.strip())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "form":
            self.formularios.append(dict(attrs))


def _ler(html: str) -> _Pagina:
    p = _Pagina()
    p.feed(html)
    return p


def test_abrir_a_ligacao_nao_desliga(fabrica: sessionmaker[Session]) -> None:
    uid = _conta(fabrica, "auth0|ana", "ana@exemplo.pt")
    token = _token(uid, "auth0|ana")
    resposta = _cliente(fabrica).get("/cancelar", params={"t": token})
    assert resposta.status_code == 200
    pagina = _ler(resposta.text)
    assert textos_cancelar().pergunta in " ".join(pagina.texto)
    ((formulario),) = pagina.formularios
    assert formulario["method"] == "post"
    assert formulario["action"] == f"/cancelar?t={token}"
    assert _lembretes(fabrica, uid) is True  # abrir não chega


def test_post_de_um_clique_desliga(fabrica: sessionmaker[Session]) -> None:
    uid = _conta(fabrica, "auth0|ana", "ana@exemplo.pt")
    resposta = _cliente(fabrica).post(f"/cancelar?t={_token(uid, 'auth0|ana')}", data=UM_CLIQUE)
    assert resposta.status_code == 200
    assert textos_cancelar().feito in resposta.text
    assert _lembretes(fabrica, uid) is False


def test_botao_da_pagina_desliga(fabrica: sessionmaker[Session]) -> None:
    """O formulário da página envia o POST sem corpo: também desliga."""
    uid = _conta(fabrica, "auth0|ana", "ana@exemplo.pt")
    cliente = _cliente(fabrica)
    acao = _ler(cliente.get(f"/cancelar?t={_token(uid, 'auth0|ana')}").text).formularios[0]
    assert cliente.post(str(acao["action"])).status_code == 200
    assert _lembretes(fabrica, uid) is False


@pytest.mark.parametrize("token", ["", "abc", "1.2", "1.9999999999.errada"])
@pytest.mark.parametrize("metodo", ["GET", "POST"])
def test_ligacao_invalida(fabrica: sessionmaker[Session], token: str, metodo: str) -> None:
    uid = _conta(fabrica, "auth0|ana", "ana@exemplo.pt")
    resposta = _cliente(fabrica).request(metodo, "/cancelar", params={"t": token})
    assert resposta.status_code == 400
    assert textos_cancelar().invalida in resposta.text
    assert not _ler(resposta.text).formularios
    assert _lembretes(fabrica, uid) is True


def test_ligacao_expirada(fabrica: sessionmaker[Session]) -> None:
    uid = _conta(fabrica, "auth0|ana", "ana@exemplo.pt")
    antiga = _token(uid, "auth0|ana", AGORA - timedelta(days=91))
    cliente = _cliente(fabrica)
    for resposta in (cliente.get(f"/cancelar?t={antiga}"), cliente.post(f"/cancelar?t={antiga}")):
        assert resposta.status_code == 410
        assert "expirou" in resposta.text and "90 dias" in resposta.text
    assert _lembretes(fabrica, uid) is True


def test_a_nunca_desliga_os_lembretes_de_b(fabrica: sessionmaker[Session]) -> None:
    a = _conta(fabrica, "auth0|ana", "ana@exemplo.pt")
    b = _conta(fabrica, "google-oauth2|bea", "bea@exemplo.pt")
    _, expira, assinatura = _token(a, "auth0|ana").split(".")
    cliente = _cliente(fabrica)
    # O token de A com o id de B, e um token assinado para B com o sub de A.
    assert cliente.post(f"/cancelar?t={b}.{expira}.{assinatura}").status_code == 400
    assert cliente.post(f"/cancelar?t={_token(b, 'auth0|ana')}").status_code == 400
    assert _lembretes(fabrica, a) is True and _lembretes(fabrica, b) is True


def test_sem_segredo_configurado_nada_vale(fabrica: sessionmaker[Session]) -> None:
    uid = _conta(fabrica, "auth0|ana", "ana@exemplo.pt")
    cliente = _cliente(fabrica, config=_config(segredo=None))
    assert cliente.post(f"/cancelar?t={_token(uid, 'auth0|ana')}").status_code == 400
    assert _lembretes(fabrica, uid) is True


def test_cabecalhos_e_html_seguro(fabrica: sessionmaker[Session]) -> None:
    resposta = _cliente(fabrica).get("/cancelar", params={"t": '<script>"'})
    assert resposta.headers["cache-control"] == "no-store"
    assert resposta.headers["x-robots-tag"] == "noindex"
    assert "<script>" not in resposta.text
    assert '<html lang="pt-PT">' in resposta.text


def test_so_get_e_post(fabrica: sessionmaker[Session]) -> None:
    assert _cliente(fabrica).put("/cancelar").status_code == 405
    assert _cliente(fabrica).get("/outra").status_code == 404


def test_registos_sem_token_nem_email(
    fabrica: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    uid = _conta(fabrica, "auth0|ana", "ana@exemplo.pt")
    token = _token(uid, "auth0|ana")
    with caplog.at_level("INFO", logger="vigoria.web.cancelar"):
        _cliente(fabrica).post(f"/cancelar?t={token}", data=UM_CLIQUE)
    texto = caplog.text
    assert f"utilizador {uid}" in texto and "valido" in texto
    assert token.split(".")[2] not in texto and "@" not in texto and "auth0|" not in texto


def test_textos_sem_brasileirismos_nem_termos_proibidos() -> None:
    t = textos_cancelar()
    texto = " ".join(t.model_dump().values())
    avisos = carregar_avisos()
    assert encontrar_termos(avisos.lista_negra.promessas, texto) == ()
    assert encontrar_termos(avisos.brasileirismos, texto) == ()
    assert "{dias}" not in t.expirada and "90 dias" in t.expirada
