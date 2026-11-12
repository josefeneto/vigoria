"""Limite de planos por utilizador e por dia (Fase 10D): regra, base de dados e página."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker
from streamlit.testing.v1 import AppTest

from paginas import textos as t
from vigoria.config import Configuracao, obter_configuracao
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.tabelas import Utilizador
from vigoria.interface.estado import para_estado
from vigoria.interface.passos import respostas_de_questionario
from vigoria.modelos.questionario import Questionario
from vigoria.motor.limite_diario import inicio_do_dia, pode_gerar

RAIZ = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- Regra


@pytest.mark.parametrize(
    ("agora", "meia_noite_utc"),
    [
        # Inverno (WET = UTC): a meia-noite de Lisboa é a meia-noite UTC.
        (datetime(2026, 11, 12, 0, 0, tzinfo=UTC), datetime(2026, 11, 12, 0, 0, tzinfo=UTC)),
        (datetime(2026, 11, 12, 23, 59, tzinfo=UTC), datetime(2026, 11, 12, 0, 0, tzinfo=UTC)),
        # Verão (WEST = UTC+1): às 23h30 UTC já é o dia seguinte em Lisboa.
        (datetime(2026, 7, 1, 23, 30, tzinfo=UTC), datetime(2026, 7, 1, 23, 0, tzinfo=UTC)),
        (datetime(2026, 7, 1, 22, 59, tzinfo=UTC), datetime(2026, 6, 30, 23, 0, tzinfo=UTC)),
    ],
)
def test_inicio_do_dia_de_lisboa(agora: datetime, meia_noite_utc: datetime) -> None:
    assert inicio_do_dia(agora) == meia_noite_utc


@pytest.mark.parametrize(
    ("feitas", "limite", "pode"),
    [(0, 3, True), (2, 3, True), (3, 3, False), (4, 3, False), (99, 0, True), (0, 1, True)],
)
def test_pode_gerar(feitas: int, limite: int, pode: bool) -> None:
    assert pode_gerar(feitas, limite) is pode


def test_limite_configuravel_e_nunca_negativo() -> None:
    assert Configuracao(_env_file=None).vigoria_planos_por_dia == 3  # type: ignore[call-arg]
    assert Configuracao(_env_file=None, vigoria_planos_por_dia=0).vigoria_planos_por_dia == 0  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Configuracao(_env_file=None, vigoria_planos_por_dia=-1)  # type: ignore[call-arg]


# ---------------------------------------------------------------- Base de dados

AGORA = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)


@pytest.fixture
def fabrica() -> Iterator[sessionmaker[Session]]:
    motor = criar_motor("sqlite://")
    migrar(motor)
    yield fabrica_sessoes(motor)
    motor.dispose()


def _conta(fabrica: sessionmaker[Session], sub: str) -> int:
    with fabrica.begin() as s:
        u = Utilizador(sub=sub, fornecedor="auth0", email=f"{sub[-3:]}@exemplo.pt")
        s.add(u)
        s.flush()
        return u.id


def test_conta_so_os_pedidos_de_hoje_e_so_do_proprio(fabrica: sessionmaker[Session]) -> None:
    a, b = _conta(fabrica, "auth0|ana"), _conta(fabrica, "auth0|bea")
    with fabrica.begin() as s:
        r.registar_geracao(s, a, AGORA - timedelta(days=1))  # ontem: não conta
        r.registar_geracao(s, a, AGORA - timedelta(hours=2))
        r.registar_geracao(s, a, AGORA)
        r.registar_geracao(s, b, AGORA)
    with fabrica.begin() as s:
        assert r.geracoes_desde(s, a, inicio_do_dia(AGORA)) == 2
        assert r.geracoes_desde(s, b, inicio_do_dia(AGORA)) == 1  # A nunca conta para B


def test_apagar_a_conta_apaga_os_pedidos_e_exportar_inclui_os(
    fabrica: sessionmaker[Session],
) -> None:
    a = _conta(fabrica, "auth0|ana")
    with fabrica.begin() as s:
        r.registar_geracao(s, a, AGORA)
    with fabrica.begin() as s:
        (pedido,) = r.exportar_dados(s, a)["pedidos_de_plano"]
        assert pedido.startswith("2026-11-12T10:00:00")  # o SQLite guarda sem fuso
        r.apagar_utilizador(s, a)
    with fabrica.begin() as s:
        assert r.geracoes_desde(s, a, AGORA - timedelta(days=1)) == 0


# ---------------------------------------------------------------- Página


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "simulado")
    monkeypatch.setenv("VIGORIA_PROVEDOR_RESERVA", "")
    monkeypatch.setenv("AMBIENTE", "local")
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "1")
    monkeypatch.setenv("VIGORIA_PLANOS_POR_DIA", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vigoria.db'}")
    obter_configuracao.cache_clear()
    yield
    obter_configuracao.cache_clear()


def _no_passo_7() -> AppTest:
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()
    at.switch_page("paginas/questionario.py").run()
    q = Questionario.model_validate_json(
        (RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8")
    )
    for k, v in para_estado(respostas_de_questionario(q)).items():
        at.session_state[k] = v
    at.session_state["passo"] = "7"
    return at.run()


def test_ao_chegar_ao_limite_nao_ha_botao_e_explica_porque(app: None) -> None:
    at = _no_passo_7()
    next(b for b in at.button if b.label == t.GERAR).click().run(timeout=60)
    assert not at.exception and at.session_state["resultado"].id > 0
    at = _no_passo_7()  # nova sessão, mesma conta, mesmo dia
    assert not at.exception
    assert t.GERAR not in [b.label for b in at.button]
    assert t.LIMITE_DIARIO.format(n=1) in [i.value for i in at.info]


def test_texto_do_limite_sem_brasileirismos() -> None:
    from vigoria.conteudo.carregar import carregar_avisos
    from vigoria.motor.voz import encontrar_termos

    assert encontrar_termos(carregar_avisos().brasileirismos, t.LIMITE_DIARIO) == ()
