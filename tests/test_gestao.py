"""Gestão (25/11/2026): contagens sem dados pessoais, lista de contas e acesso só para
VIGORIA_ADMINS (pelo `sub`, nunca pelo email); sem limite diário para a administração."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from functools import cache
from importlib.resources import files
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker
from streamlit.testing.v1 import AppTest

from paginas import textos as t
from vigoria.config import Configuracao, obter_configuracao
from vigoria.contas.entrada import Identidade
from vigoria.dados import gestao as g
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.tabelas import ContagemDiaria, Utilizador
from vigoria.interface.estado import para_estado
from vigoria.interface.passos import respostas_de_questionario
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.pipeline import ResultadoPipeline, gerar_plano_verificado

RAIZ = Path(__file__).resolve().parents[1]
A = Identidade(sub="auth0|aaa", email="a@exemplo.pt", email_verificado=True)
B = Identidade(sub="google-oauth2|bbb", email="b@exemplo.pt", email_verificado=True)
SUB_LOCAL = "local|desenvolvimento"  # paginas/sessao.UTILIZADOR_LOCAL
HOJE = date(2026, 11, 25)


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


def _conta(s: Session, identidade: Identidade) -> int:
    u = r.entrar(s, identidade)
    assert isinstance(u, Utilizador)
    return u.id


def _plano(s: Session, uid: int) -> None:
    qid = r.guardar_questionario(s, uid, _questionario())
    res = _resultado()
    r.guardar_plano(s, uid, qid, res.plano, res.estrategia, res.modelo)


def _total(s: Session, tipo: g.TipoContagem) -> int:
    return g.resumo(s, HOJE).contagens[tipo].total


# ---------------------------------------------------------------- Contagens


def test_contar_soma_no_dia_de_lisboa(fabrica: sessionmaker[Session]) -> None:
    pdf = g.TipoContagem.PDF_DESCARREGADO
    with fabrica.begin() as s:
        g.contar(s, pdf, datetime(2026, 11, 25, 10, tzinfo=UTC))
        g.contar(s, pdf, datetime(2026, 11, 25, 23, 30, tzinfo=UTC))  # 23h30 em Lisboa
        g.contar(s, pdf, datetime(2026, 11, 24, 23, 59, tzinfo=UTC))  # ainda dia 24
        g.contar(s, g.TipoContagem.DADOS_DESCARREGADOS, datetime(2026, 11, 25, tzinfo=UTC))
    with fabrica.begin() as s:
        linhas = dict(
            s.execute(
                select(ContagemDiaria.dia, ContagemDiaria.total).where(
                    ContagemDiaria.tipo == pdf.value
                )
            ).all()
        )
        assert linhas == {date(2026, 11, 25): 2, date(2026, 11, 24): 1}
        assert _total(s, g.TipoContagem.DADOS_DESCARREGADOS) == 1


def test_ultimos_7_e_30_dias(fabrica: sessionmaker[Session]) -> None:
    plano = g.TipoContagem.PLANO_GERADO
    with fabrica.begin() as s:
        for dias_atras in (0, 6, 7, 29, 30, 100):
            g.contar(s, plano, datetime(2026, 11, 25, 12, tzinfo=UTC) - timedelta(days=dias_atras))
    with fabrica.begin() as s:
        numeros = g.resumo(s, HOJE).contagens[plano]
        assert numeros.total == 6
        assert numeros.ultimos == {7: 2, 30: 4}  # hoje incluído: 7 dias = de 19 a 25


def test_contas_e_planos_contam_e_nao_descem_ao_apagar_a_conta(
    fabrica: sessionmaker[Session],
) -> None:
    with fabrica.begin() as s:
        a, b = _conta(s, A), _conta(s, B)
        _plano(s, a)
        _plano(s, a)
        _conta(s, A)  # segundo login: não é uma conta nova
    with fabrica.begin() as s:
        resumo = g.resumo(s, HOJE)
        assert (resumo.contas_ativas, resumo.com_plano) == (2, 1)
        assert _total(s, g.TipoContagem.CONTA_CRIADA) == 2
        assert _total(s, g.TipoContagem.PLANO_GERADO) == 2
        r.apagar_utilizador(s, a)
    with fabrica.begin() as s:
        resumo = g.resumo(s, HOJE)
        assert (resumo.contas_ativas, resumo.com_plano) == (1, 0)
        assert _total(s, g.TipoContagem.CONTA_CRIADA) == 2  # acumulado: não desce
        assert _total(s, g.TipoContagem.PLANO_GERADO) == 2
        assert b in {u.id for u in s.scalars(select(Utilizador))}


def test_contagens_sem_dados_pessoais() -> None:
    assert set(ContagemDiaria.__table__.columns.keys()) == {"dia", "tipo", "total"}


# ---------------------------------------------------------------- Lista de contas


def test_lista_de_contas_e_csv(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        a = _conta(s, A)
        _plano(s, a)
        _conta(s, B)
    with fabrica.begin() as s:
        contas = g.contas(s)
    assert [(c.email, c.fornecedor, c.planos) for c in contas] == [
        ("b@exemplo.pt", "google-oauth2", 0),  # a mais recente primeiro
        ("a@exemplo.pt", "auth0", 1),
    ]
    csv = g.contas_csv(contas, t.GESTAO_COLUNAS)
    assert csv.startswith("﻿Email;Entrada;Criada em;Planos\r\n")
    assert "a@exemplo.pt;auth0;" in csv and csv.count("\r\n") == 3


# ---------------------------------------------------------------- Migração


def test_migracao_0005_conta_o_que_ja_existe(tmp_path: Path) -> None:
    motor = criar_motor(f"sqlite:///{tmp_path / 'm.db'}")
    config = Config()
    config.set_main_option("script_location", str(files("vigoria.dados") / "migracoes"))
    with motor.begin() as ligacao:
        config.attributes["connection"] = ligacao
        command.upgrade(config, "0004")
        for uid, criado in ((1, "2026-11-20 10:00:00"), (2, "2026-11-20 23:30:00")):
            ligacao.execute(
                text(
                    "INSERT INTO utilizador (id, sub, fornecedor, email, criado_em, "
                    "acompanhamento_ativo, frequencia_registo, lembretes_email) VALUES "
                    "(:id, :sub, 'auth0', :email, :criado, 1, 'semanal', 1)"
                ),
                {"id": uid, "sub": f"auth0|{uid}", "email": f"{uid}@exemplo.pt", "criado": criado},
            )
    migrar(motor)
    with fabrica_sessoes(motor).begin() as s:
        linhas = set(
            s.execute(select(ContagemDiaria.dia, ContagemDiaria.tipo, ContagemDiaria.total))
        )
        # 23h30 UTC de 20/11 ainda é dia 20 em Lisboa (inverno: UTC+0).
        assert linhas == {(date(2026, 11, 20), "conta_criada", 2)}
        assert s.scalar(select(func.count()).select_from(Utilizador)) == 2
    motor.dispose()


def test_migracao_0006_conta_os_lembretes_ja_enviados(tmp_path: Path) -> None:
    motor = criar_motor(f"sqlite:///{tmp_path / 'm.db'}")
    config = Config()
    config.set_main_option("script_location", str(files("vigoria.dados") / "migracoes"))
    with motor.begin() as ligacao:
        config.attributes["connection"] = ligacao
        command.upgrade(config, "0005")
        for sql in (
            "INSERT INTO utilizador (id, sub, fornecedor, email, criado_em, acompanhamento_ativo, "
            "frequencia_registo, lembretes_email) VALUES (1, 'auth0|1', 'auth0', '1@exemplo.pt', "
            "'2026-11-01 10:00:00', 1, 'semanal', 1)",
            "INSERT INTO questionario (id, utilizador_id, respostas, criado_em) "
            "VALUES (1, 1, '{}', '2026-11-01 10:00:00')",
            "INSERT INTO plano (id, utilizador_id, questionario_id, conteudo, estrategia, "
            "versao_prompt, provedor, modelo, criado_em) VALUES (1, 1, 1, '{}', '{}', 'v', 'p', "
            "'m', '2026-11-01 10:00:00')",
            "INSERT INTO lembrete_enviado (utilizador_id, plano_id, semana_inicio, semana_fim, "
            "numero, enviado_em) VALUES (1, 1, 1, 1, 1, '2026-11-10 09:07:00'), "
            "(1, 1, 1, 1, 2, '2026-11-13 09:07:00')",
        ):
            ligacao.execute(text(sql))
    migrar(motor)
    with fabrica_sessoes(motor).begin() as s:
        lembretes = set(
            s.execute(
                select(ContagemDiaria.dia, ContagemDiaria.total).where(
                    ContagemDiaria.tipo == g.TipoContagem.LEMBRETE_ENVIADO.value
                )
            )
        )
        assert lembretes == {(date(2026, 11, 10), 1), (date(2026, 11, 13), 1)}
    motor.dispose()


# ---------------------------------------------------------------- Configuração


def test_admins_pelo_sub_com_a_barra_vertical() -> None:
    c = Configuracao(vigoria_admins=" google-oauth2|123 , auth0|abc;;")
    assert c.vigoria_admins == frozenset({"google-oauth2|123", "auth0|abc"})
    assert Configuracao(vigoria_admins="").vigoria_admins == frozenset()


# ---------------------------------------------------------------- Página


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[pytest.MonkeyPatch]:
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "simulado")
    monkeypatch.setenv("VIGORIA_PROVEDOR_RESERVA", "")
    monkeypatch.setenv("AMBIENTE", "local")
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "1")
    monkeypatch.setenv("VIGORIA_PLANOS_POR_DIA", "1")
    monkeypatch.setenv("VIGORIA_ADMINS", "")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vigoria.db'}")
    obter_configuracao.cache_clear()
    yield monkeypatch
    obter_configuracao.cache_clear()


def _admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_ADMINS", SUB_LOCAL)
    obter_configuracao.cache_clear()


def _ligacoes(at: AppTest) -> list[str]:
    return [p.proto.label for p in at.get("page_link")]


def test_sem_ser_admin_nao_ha_gestao(app: pytest.MonkeyPatch) -> None:
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert t.PAGINAS["gestao"] not in _ligacoes(at)
    with pytest.raises(ValueError, match="Could not find a navigation page"):
        at.switch_page("paginas/gestao.py")  # a página nem está registada


def test_admin_ve_os_numeros_e_a_lista(app: pytest.MonkeyPatch) -> None:
    _admin(app)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert t.PAGINAS["gestao"] in _ligacoes(at)  # no menu «Conta»
    at.switch_page("paginas/gestao.py").run()
    assert not at.exception
    rotulos = {m.label: m.value for m in at.metric}
    assert rotulos[t.GESTAO_ROTULOS["contas_ativas"]] == "1"  # o utilizador fictício local
    assert rotulos[t.GESTAO_ROTULOS["conta_criada"]] == "1"
    assert set(rotulos) == set(t.GESTAO_ROTULOS.values())
    assert len(at.dataframe) == 1
    assert any(b.label == t.GESTAO_CSV for b in at.get("download_button"))


def test_admin_testa_os_lembretes_sem_envio_real(app: pytest.MonkeyPatch) -> None:
    from vigoria.notificacoes import brevo

    def _nunca(*_a: object, **_k: object) -> str:
        raise AssertionError("os testes nunca enviam emails")

    app.setattr(brevo, "enviar", _nunca)
    app.setenv("BREVO_API_KEY", "")  # mesmo com uma chave no .env
    _admin(app)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()
    at.switch_page("paginas/gestao.py").run()
    rotulos = {m.label: m.value for m in at.metric}
    assert rotulos[t.GESTAO_ROTULOS["envio_diario"]] == t.GESTAO_ENVIO_NUNCA
    (enviar,) = [b for b in at.button if b.label == t.GESTAO_TESTE_ENVIAR]
    enviar.click().run()
    assert not at.exception
    (aviso,) = at.warning
    assert "BREVO_API_KEY" in aviso.value
    (simular,) = [b for b in at.button if b.label == t.GESTAO_SIMULAR]
    simular.click().run()
    assert not at.exception
    assert t.GESTAO_SIMULAR_TITULO in [m.value for m in at.markdown]
    (codigo,) = at.code
    assert "com lembretes ligados" in codigo.value and "@" not in codigo.value


def _no_passo_7() -> AppTest:
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()
    at.switch_page("paginas/questionario.py").run()
    for k, v in para_estado(respostas_de_questionario(_questionario())).items():
        at.session_state[k] = v
    at.session_state["passo"] = "7"
    return at.run()


def test_admin_sem_limite_diario(app: pytest.MonkeyPatch) -> None:
    _admin(app)
    for _ in range(2):  # limite 1: o segundo só é possível sem limite
        at = _no_passo_7()
        next(b for b in at.button if b.label == t.GERAR).click().run(timeout=60)
        assert not at.exception and at.session_state["resultado"].id > 0
    at = _no_passo_7()
    assert t.GERAR in [b.label for b in at.button] and not at.warning


def test_descarga_contada_e_ficheiro_vazio_nao_conta(fabrica: sessionmaker[Session]) -> None:
    from paginas.comum import _gerar_e_contar

    pdf = g.TipoContagem.PDF_DESCARREGADO
    assert _gerar_e_contar(lambda: b"%PDF", fabrica, pdf) == b"%PDF"
    assert _gerar_e_contar(lambda: b"", fabrica, pdf) == b""  # plano apagado entretanto
    with fabrica.begin() as s:
        assert _total(s, pdf) == 1
