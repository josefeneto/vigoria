"""Repositórios (dados/repositorios.py) com SQLite em memória, incluindo o isolamento:
o utilizador A nunca lê nem altera dados do utilizador B."""

from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from vigoria.contas.entrada import Identidade
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.tabelas import (
    Base,
    Consentimento,
    PlanoGuardado,
    QuestionarioGuardado,
    Utilizador,
)
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.pipeline import ResultadoPipeline, gerar_plano_verificado

RAIZ = Path(__file__).resolve().parents[1]
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


def _conta(s: Session, identidade: Identidade) -> int:
    u = r.entrar(s, identidade)
    assert isinstance(u, Utilizador)
    return u.id


def _com_plano(s: Session, identidade: Identidade) -> tuple[int, r.PlanoDaConta]:
    uid = _conta(s, identidade)
    r.guardar_consentimentos(s, uid, "v1")
    qid = r.guardar_questionario(s, uid, _questionario())
    res = _resultado()
    return uid, r.guardar_plano(s, uid, qid, res.plano, res.estrategia, res.modelo)


# ---------------------------------------------------------------- Entrada


def test_primeiro_login_cria_conta_e_o_segundo_reutiliza(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        primeiro = _conta(s, A)
    with fabrica.begin() as s:
        assert _conta(s, A) == primeiro
        u = s.get(Utilizador, primeiro)
        assert u is not None
        assert (u.sub, u.fornecedor, u.email) == ("auth0|aaa", "auth0", "a@exemplo.pt")
        assert s.scalar(select(func.count()).select_from(Utilizador)) == 1


def test_email_por_verificar_nao_cria_conta(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        assert r.entrar(s, A.model_copy(update={"email_verificado": False})) is (
            r.Recusa.EMAIL_POR_VERIFICAR
        )
        assert s.scalar(select(func.count()).select_from(Utilizador)) == 0


def test_mesmo_email_com_outro_metodo_nao_junta_contas(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        _conta(s, A)
    with fabrica.begin() as s:
        google = Identidade(sub="google-oauth2|zzz", email=A.email, email_verificado=True)
        assert r.entrar(s, google) is r.Recusa.EMAIL_NOUTRO_METODO
        assert s.scalar(select(func.count()).select_from(Utilizador)) == 1


def test_email_alterado_no_auth0_e_atualizado(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid = _conta(s, A)
    with fabrica.begin() as s:
        _conta(s, A.model_copy(update={"email": "novo@exemplo.pt"}))
        assert s.get(Utilizador, uid).email == "novo@exemplo.pt"  # type: ignore[union-attr]


# ---------------------------------------------------------------- Questionário e planos


def test_guarda_e_le_o_ultimo_plano(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid, guardado = _com_plano(s, A)
    with fabrica.begin() as s:
        ultimo = r.ultimo_plano(s, uid)
        assert ultimo is not None
        assert ultimo.id == guardado.id
        assert ultimo.plano == _resultado().plano
        assert ultimo.estrategia == _resultado().estrategia
        assert r.ultimo_questionario(s, uid) == _questionario()
        linha = s.get(PlanoGuardado, guardado.id)
        assert linha is not None
        assert (linha.provedor, linha.modelo) == ("simulado", "persona_teste")
        tipos = s.scalars(select(Consentimento.tipo).where(Consentimento.utilizador_id == uid))
        assert sorted(tipos) == sorted(r.TIPOS_CONSENTIMENTO)


def test_lista_planos_do_mais_recente(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid, primeiro = _com_plano(s, A)
        qid = r.guardar_questionario(s, uid, _questionario())
        res = _resultado()
        segundo = r.guardar_plano(s, uid, qid, res.plano, res.estrategia, res.modelo)
        assert [p.id for p in r.listar_planos(s, uid)] == [segundo.id, primeiro.id]


def test_sem_dados_devolve_vazio(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid = _conta(s, A)
        assert r.ultimo_plano(s, uid) is None
        assert r.ultimo_questionario(s, uid) is None
        assert r.listar_planos(s, uid) == []


# ---------------------------------------------------------------- Isolamento A / B


def test_a_nao_le_dados_de_b(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid_a = _conta(s, A)
        _, plano_b = _com_plano(s, B)
    with fabrica.begin() as s:
        assert r.obter_plano(s, uid_a, plano_b.id) is None
        assert r.ultimo_plano(s, uid_a) is None
        assert r.ultimo_questionario(s, uid_a) is None
        assert r.listar_planos(s, uid_a) == []
        exportado = r.exportar_dados(s, uid_a)
        assert exportado["planos"] == [] and exportado["questionarios"] == []
        assert "b@exemplo.pt" not in str(exportado)


def test_a_nao_grava_plano_no_questionario_de_b(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid_a = _conta(s, A)
        uid_b = _conta(s, B)
        qid_b = r.guardar_questionario(s, uid_b, _questionario())
        res = _resultado()
        with pytest.raises(r.PlanoDeOutro):
            r.guardar_plano(s, uid_a, qid_b, res.plano, res.estrategia, res.modelo)


def test_apagar_a_nao_toca_em_b(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid_a, _ = _com_plano(s, A)
        uid_b, plano_b = _com_plano(s, B)
    with fabrica.begin() as s:
        assert r.apagar_utilizador(s, uid_a) == A.sub
    with fabrica.begin() as s:
        for tabela in (Consentimento, QuestionarioGuardado, PlanoGuardado):
            assert not s.scalars(select(tabela).where(tabela.utilizador_id == uid_a)).all()
        assert s.get(Utilizador, uid_a) is None
        assert r.obter_plano(s, uid_b, plano_b.id) is not None
        assert r.ultimo_questionario(s, uid_b) is not None


# ---------------------------------------------------------------- Exportar e apagar


def test_apagar_plano_so_o_proprio_e_mantem_as_respostas(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid_a, plano_a = _com_plano(s, A)
        uid_b, plano_b = _com_plano(s, B)
    with fabrica.begin() as s:
        assert r.apagar_plano(s, uid_a, plano_b.id) is False  # A não apaga o plano de B
        assert r.obter_plano(s, uid_b, plano_b.id) is not None
    with fabrica.begin() as s:
        assert r.apagar_plano(s, uid_a, plano_a.id) is True
        assert r.apagar_plano(s, uid_a, plano_a.id) is False  # já não existe
    with fabrica.begin() as s:
        assert r.listar_planos(s, uid_a) == []
        assert r.ultimo_questionario(s, uid_a) == _questionario()
        assert [p.id for p in r.listar_planos(s, uid_b)] == [plano_b.id]


def test_exportar_traz_tudo_e_e_json(fabrica: sessionmaker[Session]) -> None:
    import json

    with fabrica.begin() as s:
        uid, guardado = _com_plano(s, A)
        dados = r.exportar_dados(s, uid)
    json.dumps(dados)  # serializável
    assert dados["conta"]["email"] == A.email
    assert len(dados["consentimentos"]) == 3
    assert dados["questionarios"][0]["respostas"]["idade"] == _questionario().idade
    assert dados["planos"][0]["id"] == guardado.id
    assert dados["planos"][0]["modelo"] == "persona_teste"
    assert "sub" not in dados["conta"]  # identificador técnico, não é dado da pessoa


def test_apagar_conta_apaga_tudo_e_devolve_o_sub(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid, _ = _com_plano(s, A)
    with fabrica.begin() as s:
        assert r.apagar_utilizador(s, uid) == A.sub
    with fabrica.begin() as s:
        for tabela in (Utilizador, Consentimento, QuestionarioGuardado, PlanoGuardado):
            assert s.scalar(select(func.count()).select_from(tabela)) == 0
        assert r.apagar_utilizador(s, uid) is None  # já não existe
        assert r.exportar_dados(s, uid) == {}


def test_cascata_na_base_de_dados(fabrica: sessionmaker[Session]) -> None:
    """Mesmo apagando só a linha do utilizador, o ON DELETE CASCADE leva o resto."""
    with fabrica.begin() as s:
        uid, _ = _com_plano(s, A)
    with fabrica.begin() as s:
        s.execute(Utilizador.__table__.delete().where(Utilizador.id == uid))
    with fabrica.begin() as s:
        assert s.scalar(select(func.count()).select_from(PlanoGuardado)) == 0


# ---------------------------------------------------------------- Migrações


def test_migracoes_criam_o_esquema_das_tabelas(tmp_path: Path) -> None:
    motor = criar_motor(f"sqlite:///{tmp_path / 'm.db'}")
    migrar(motor)
    migrar(motor)  # repetir não faz nada
    insp = inspect(motor)
    assert set(insp.get_table_names()) - {"alembic_version"} == set(Base.metadata.tables)
    for nome, tabela in Base.metadata.tables.items():
        assert {c["name"] for c in insp.get_columns(nome)} == {c.name for c in tabela.columns}
    motor.dispose()


def test_postgresql_com_limite_de_tempo_e_ligacoes_verificadas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem limite, uma página fica a rodar enquanto o Neon acorda (ou se não responder)."""
    from vigoria.dados import bd

    opcoes: dict[str, object] = {}

    def espiao(_url: str, **o: object) -> object:
        opcoes.update(o)
        return create_engine("sqlite://")

    monkeypatch.setattr(bd, "create_engine", espiao)
    bd.criar_motor("postgresql+psycopg://u:p@exemplo.invalid/bd")
    assert opcoes["connect_args"] == {"connect_timeout": bd.TIMEOUT_LIGACAO_S}
    assert opcoes["pool_pre_ping"] is True
    assert opcoes["pool_recycle"] == bd.POOL_RECYCLE_S == 240
