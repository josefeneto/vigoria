"""Páginas dos lembretes (Fase 8), sem browser (AppTest): deixar de receber pela ligação do
email, sem sessão iniciada, e o interruptor em «A minha conta»."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr
from streamlit.testing.v1 import AppTest

from paginas import sessao
from vigoria import config
from vigoria.config import obter_configuracao
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.tabelas import Utilizador
from vigoria.notificacoes.token import gerar_token

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "app.py")
CANCELAR = "paginas/cancelar_lembretes.py"
CONTA = "paginas/conta.py"
SEGREDO = "s" * 48


@pytest.fixture
def bd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    url = f"sqlite:///{tmp_path / 'vigoria.db'}"
    for nome, valor in {
        "VIGORIA_PROVEDOR_LLM": "simulado",
        "VIGORIA_PROVEDOR_RESERVA": "",
        "AMBIENTE": "local",
        "VIGORIA_UTILIZADOR_LOCAL": "0",
        "DATABASE_URL": url,
        "VIGORIA_SEGREDO_LEMBRETES": SEGREDO,
        "VIGORIA_EMAILS_PERMITIDOS": "",
    }.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setattr(config, "obter_auth0", lambda: None)
    obter_configuracao.cache_clear()
    yield url
    obter_configuracao.cache_clear()


def _criar_conta(url: str, sub: str = "auth0|ana") -> int:
    motor = criar_motor(url)
    migrar(motor)
    with fabrica_sessoes(motor).begin() as s:
        u = Utilizador(sub=sub, fornecedor="auth0", email="ana@exemplo.pt")
        s.add(u)
        s.flush()
        uid = u.id
    motor.dispose()
    return uid


def _preferencias(url: str, uid: int) -> r.Preferencias:
    motor = criar_motor(url)
    with fabrica_sessoes(motor).begin() as s:
        p = r.obter_preferencias(s, uid)
    motor.dispose()
    return p


def _abrir(token: str | None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    if token is not None:
        at.query_params["t"] = token
    at.run()
    at.switch_page(CANCELAR).run()
    assert not at.exception
    return at


def test_abrir_a_ligacao_nao_desliga_so_o_botao(bd: str) -> None:
    uid = _criar_conta(bd)
    at = _abrir(gerar_token(uid, "auth0|ana", SecretStr(SEGREDO)))
    assert _preferencias(bd, uid).lembretes_email is True  # abrir não chega
    (botao,) = [b for b in at.button if b.label == "Deixar de receber lembretes"]
    botao.click().run()
    assert not at.exception
    assert any("já não vai receber lembretes" in s.value for s in at.success)
    assert _preferencias(bd, uid) == r.Preferencias(lembretes_email=False)


@pytest.mark.parametrize("token", [None, "", "abc", "1.assinatura-errada"])
def test_ligacao_invalida(bd: str, token: str | None) -> None:
    _criar_conta(bd)
    at = _abrir(token)
    if not at.button:  # malformado: aviso logo à entrada
        assert any("não é válida" in w.value for w in at.warning)
        return
    at.button[0].click().run()
    assert any("não é válida" in w.value for w in at.warning)


def test_ligacao_de_outra_conta_nao_serve(bd: str) -> None:
    uid = _criar_conta(bd)
    at = _abrir(gerar_token(uid, "auth0|outra", SecretStr(SEGREDO)))
    at.button[0].click().run()
    assert any("não é válida" in w.value for w in at.warning)
    assert _preferencias(bd, uid).lembretes_email is True


def test_conta_desliga_e_liga_os_lembretes(bd: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "1")
    obter_configuracao.cache_clear()
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page(CONTA).run()
    assert not at.exception
    uid = at.session_state[sessao.UTILIZADOR][1]
    interruptor = at.toggle(key="conta_lembretes_email")
    assert interruptor.value is True
    interruptor.set_value(False).run()
    assert _preferencias(bd, uid).lembretes_email is False
    at.toggle(key="conta_acompanhamento_ativo").set_value(False).run()
    assert at.toggle(key="conta_lembretes_email").disabled
