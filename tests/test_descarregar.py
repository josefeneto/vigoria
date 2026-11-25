"""Descargas na app instalada (25/11/2026): token curto (exportacao/ligacao.py), rota
/descarregar (web/descarregar.py) e a ligação que a app mostra em produção (comum.descarga)."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient
from streamlit.testing.v1 import AppTest

from paginas import textos as t
from vigoria.config import Configuracao, obter_configuracao
from vigoria.contas.entrada import Identidade
from vigoria.dados import gestao as g
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.tabelas import Utilizador
from vigoria.exportacao import ligacao
from vigoria.exportacao.ligacao import EstadoLigacao, TipoDescarga
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.pipeline import ResultadoPipeline, gerar_plano_verificado
from vigoria.notificacoes.token import gerar_token
from vigoria.web.cancelar import criar_app
from vigoria.web.descarregar import textos_descarregar

RAIZ = Path(__file__).resolve().parents[1]
SEGREDO = SecretStr("s" * 48)
AGORA = datetime(2026, 11, 25, 10, tzinfo=UTC)
A = Identidade(sub="auth0|aaa", email="a@exemplo.pt", email_verificado=True)
B = Identidade(sub="google-oauth2|bbb", email="b@exemplo.pt", email_verificado=True)


@cache
def _questionario() -> Questionario:
    return Questionario.model_validate_json(
        (RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8")
    )


@cache
def _resultado() -> ResultadoPipeline:
    return gerar_plano_verificado(_questionario(), ProvedorSimulado(), progresso=lambda _: None)


@pytest.fixture
def fabrica() -> Iterator[sessionmaker[Session]]:
    motor = criar_motor("sqlite://")
    migrar(motor)
    yield fabrica_sessoes(motor)
    motor.dispose()


def _config(segredo: SecretStr | None = SEGREDO) -> Configuracao:
    return Configuracao(
        _env_file=None,  # type: ignore[call-arg]
        ambiente="producao",
        vigoria_provedor_llm="groq",
        vigoria_segredo_lembretes=segredo,
    )


def _cliente(
    fabrica: sessionmaker[Session], config: Configuracao | None = None, agora: datetime = AGORA
) -> TestClient:
    return TestClient(criar_app(fabrica, config or _config(), lambda: agora))


def _com_plano(fabrica: sessionmaker[Session], identidade: Identidade) -> tuple[int, int]:
    with fabrica.begin() as s:
        u = r.entrar(s, identidade)
        assert isinstance(u, Utilizador)
        qid = r.guardar_questionario(s, u.id, _questionario())
        res = _resultado()
        plano = r.guardar_plano(s, u.id, qid, res.plano, res.estrategia, res.modelo)
        return u.id, plano.id


def _token(tipo: TipoDescarga, uid: int, sub: str, plano_id: int = 0, **opcoes: object) -> str:
    agora = opcoes.get("agora", AGORA)
    return ligacao.gerar(tipo, uid, sub, SEGREDO, agora, plano_id)  # type: ignore[arg-type]


# ---------------------------------------------------------------- Token


def test_token_valido_e_sem_dados_pessoais() -> None:
    token = _token(TipoDescarga.PDF, 7, A.sub, 3)
    assert A.sub not in token and "@" not in token
    pedido = ligacao.ler(token)
    assert pedido is not None and (pedido.tipo, pedido.utilizador_id, pedido.plano_id) == (
        TipoDescarga.PDF,
        7,
        3,
    )
    assert ligacao.verificar(pedido, A.sub, SEGREDO, AGORA) is EstadoLigacao.VALIDA
    fim = AGORA + ligacao.VALIDADE
    assert ligacao.verificar(pedido, A.sub, SEGREDO, fim) is EstadoLigacao.VALIDA
    depois = fim + timedelta(seconds=1)
    assert ligacao.verificar(pedido, A.sub, SEGREDO, depois) is EstadoLigacao.EXPIRADA


@pytest.mark.parametrize(
    "mudar",
    [
        lambda tk: tk.replace("pdf.", "dados.", 1),  # outro tipo
        lambda tk: tk.replace(".3.", ".4.", 1),  # outro plano
        lambda tk: tk[:-2] + ("AA" if not tk.endswith("AA") else "BB"),  # assinatura
    ],
)
def test_token_adulterado_recusado(mudar) -> None:  # type: ignore[no-untyped-def]
    pedido = ligacao.ler(mudar(_token(TipoDescarga.PDF, 7, A.sub, 3)))
    assert pedido is not None
    assert ligacao.verificar(pedido, A.sub, SEGREDO, AGORA) is EstadoLigacao.INVALIDA


def test_token_de_outra_conta_ou_de_lembretes_recusado() -> None:
    pedido = ligacao.ler(_token(TipoDescarga.PDF, 7, A.sub, 3))
    assert pedido is not None
    assert ligacao.verificar(pedido, B.sub, SEGREDO, AGORA) is EstadoLigacao.INVALIDA
    outro = SecretStr("o" * 48)
    assert ligacao.verificar(pedido, A.sub, outro, AGORA) is EstadoLigacao.INVALIDA
    assert ligacao.ler(gerar_token(7, A.sub, SEGREDO, AGORA)) is None  # o dos lembretes


@pytest.mark.parametrize("token", ["", "pdf.1.2.3", "zip.1.2.3.x", "pdf.a.2.3.x", "pdf.1.2.3."])
def test_token_malformado(token: str) -> None:
    assert ligacao.ler(token) is None


# ---------------------------------------------------------------- Rota


def _contagem(fabrica: sessionmaker[Session], tipo: g.TipoContagem) -> int:
    with fabrica.begin() as s:
        return g.resumo(s, AGORA.date()).contagens[tipo].total


def test_pdf_para_ver_no_ecra_e_contado(fabrica: sessionmaker[Session]) -> None:
    uid, pid = _com_plano(fabrica, A)
    resposta = _cliente(fabrica).get(ligacao.url(_token(TipoDescarga.PDF, uid, A.sub, pid)))
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.headers["content-disposition"].startswith('inline; filename="vigoria_plano_')
    assert resposta.headers["cache-control"] == "no-store"
    assert resposta.content.startswith(b"%PDF")
    assert _contagem(fabrica, g.TipoContagem.PDF_DESCARREGADO) == 1


def test_dados_em_json(fabrica: sessionmaker[Session]) -> None:
    uid, _ = _com_plano(fabrica, A)
    resposta = _cliente(fabrica).get(ligacao.url(_token(TipoDescarga.DADOS, uid, A.sub)))
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/json")
    assert json.loads(resposta.content)["conta"]["email"] == A.email
    assert _contagem(fabrica, g.TipoContagem.DADOS_DESCARREGADOS) == 1


def test_a_nunca_descarrega_o_plano_de_b(fabrica: sessionmaker[Session]) -> None:
    a, _ = _com_plano(fabrica, A)
    _, plano_b = _com_plano(fabrica, B)
    resposta = _cliente(fabrica).get(ligacao.url(_token(TipoDescarga.PDF, a, A.sub, plano_b)))
    assert resposta.status_code == 400 and b"%PDF" not in resposta.content
    assert _contagem(fabrica, g.TipoContagem.PDF_DESCARREGADO) == 0


def test_ligacao_expirada_ou_sem_segredo(fabrica: sessionmaker[Session]) -> None:
    uid, pid = _com_plano(fabrica, A)
    caminho = ligacao.url(_token(TipoDescarga.PDF, uid, A.sub, pid))
    tarde = AGORA + ligacao.VALIDADE + timedelta(minutes=1)
    expirada = _cliente(fabrica, agora=tarde).get(caminho)
    assert expirada.status_code == 410
    assert "30 minutos" in expirada.text and "OK" in expirada.text
    assert _cliente(fabrica, _config(None)).get(caminho).status_code == 400
    assert _cliente(fabrica).get("/descarregar?t=lixo").status_code == 400


def test_conta_apagada_invalida_a_ligacao(fabrica: sessionmaker[Session]) -> None:
    uid, _ = _com_plano(fabrica, A)
    caminho = ligacao.url(_token(TipoDescarga.DADOS, uid, A.sub))
    with fabrica.begin() as s:
        r.apagar_utilizador(s, uid)
    assert _cliente(fabrica).get(caminho).status_code == 400


def test_textos_da_pagina_de_aviso() -> None:
    from vigoria.conteudo.carregar import carregar_avisos
    from vigoria.motor.voz import encontrar_termos

    textos = textos_descarregar()
    for texto in textos.model_dump().values():
        assert encontrar_termos(carregar_avisos().brasileirismos, texto) == ()
    assert "30 minutos" in textos.expirada


def test_caddy_encaminha_descarregar() -> None:
    caddy = (RAIZ / "pwa" / "Caddyfile").read_text("utf-8")
    assert "handle /descarregar {\n\t\treverse_proxy 127.0.0.1:8001" in caddy


# ---------------------------------------------------------------- App


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[pytest.MonkeyPatch]:
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "simulado")
    monkeypatch.setenv("VIGORIA_PROVEDOR_RESERVA", "")
    monkeypatch.setenv("AMBIENTE", "local")
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vigoria.db'}")
    obter_configuracao.cache_clear()
    yield monkeypatch
    obter_configuracao.cache_clear()


def _conta_page(producao: bool, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """A Conta; com `producao`, comum.descarga vê a configuração de produção."""
    from paginas import comum

    if producao:
        base = obter_configuracao()
        falsa = base.model_copy(
            update={"ambiente": "producao", "vigoria_segredo_lembretes": SEGREDO}
        )
        monkeypatch.setattr(comum.config, "obter_configuracao", lambda: falsa)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()
    at.switch_page("paginas/conta.py").run()
    assert not at.exception
    return at


def test_em_local_so_o_botao(app: pytest.MonkeyPatch) -> None:
    at = _conta_page(False, app)
    assert not at.get("link_button")
    assert any(b.label == t.CONTA_EXPORTAR for b in at.get("download_button"))


def test_em_producao_o_botao_e_a_ligacao_para_a_app_instalada(app: pytest.MonkeyPatch) -> None:
    at = _conta_page(True, app)
    (botao,) = at.get("link_button")
    assert botao.proto.label == t.CONTA_EXPORTAR
    assert botao.proto.url.startswith("/descarregar?t=dados.")
    assert any(b.label == t.CONTA_EXPORTAR for b in at.get("download_button"))


def test_css_troca_o_botao_pela_ligacao_so_na_app_instalada() -> None:
    css = (RAIZ / "paginas" / "estilos.css").read_text("utf-8")
    fora_da_app = "@media not all and (display-mode: standalone) {\n"
    assert fora_da_app + '  [class*="st-key-descarga_app_"]' in css
    assert '@media (display-mode: standalone) {\n  [class*="st-key-descarga_navegador_"]' in css
