"""Páginas com conta (Fase 6), sem browser (AppTest) e sem Auth0: utilizador local fictício
(VIGORIA_UTILIZADOR_LOCAL=1, só AMBIENTE=local) e uma base SQLite nova por teste."""

import logging
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select
from streamlit.testing.v1 import AppTest

from paginas import sessao
from vigoria import config
from vigoria.config import obter_configuracao
from vigoria.dados.bd import criar_motor, migrar
from vigoria.dados.tabelas import PlanoGuardado, QuestionarioGuardado, Utilizador
from vigoria.interface.estado import chave, para_estado
from vigoria.interface.passos import respostas_de_questionario
from vigoria.llm import escolha
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.questionario import Questionario

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "app.py")
QUESTIONARIO = "paginas/questionario.py"
CONTA = "paginas/conta.py"
NOTAS = "Tomo bisoprolol; ligue-me para o 912 345 678 ou escreva para ana.silva@exemplo.pt"


@pytest.fixture
def bd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'vigoria.db'}"
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "simulado")
    monkeypatch.setenv("VIGORIA_PROVEDOR_RESERVA", "")
    monkeypatch.setenv("AMBIENTE", "local")
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "1")
    monkeypatch.setenv("DATABASE_URL", url)
    obter_configuracao.cache_clear()
    yield url
    obter_configuracao.cache_clear()


def _contar(url: str, tabela: type) -> int:
    motor = criar_motor(url)
    migrar(motor)  # sem sessão iniciada, a app nem cria a base
    with motor.connect() as ligacao:
        n = ligacao.scalar(select(func.count()).select_from(tabela))
    motor.dispose()
    return int(n or 0)


def _botao(at: AppTest, rotulo: str):  # type: ignore[no-untyped-def]
    return next(b for b in at.button if b.label == rotulo)


def _gerar(at: AppTest, **alteracoes: object) -> None:
    at.switch_page(QUESTIONARIO).run()
    q = Questionario.model_validate_json(
        (RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8")
    )
    for k, v in para_estado(respostas_de_questionario(q) | alteracoes).items():
        at.session_state[k] = v
    at.session_state["passo"] = "7"
    at.run()
    _botao(at, "Gerar o meu plano").click().run(timeout=60)
    assert not at.exception


def _nova_sessao() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    return at


# ---------------------------------------------------------------- Sem sessão


def test_sem_sessao_so_paginas_publicas(bd: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "0")
    # Sem login configurado, mesmo que exista um .streamlit/secrets.toml local.
    monkeypatch.setattr(config, "obter_auth0", lambda: None)
    obter_configuracao.cache_clear()
    at = _nova_sessao()
    assert sessao.UTILIZADOR not in at.session_state
    rotulos = [b.label for b in at.button]
    assert "Entrar ou criar conta" in rotulos
    assert "Começar o questionário" not in rotulos
    _botao(at, "Entrar ou criar conta").click().run()
    assert any("não está configurada" in e.value for e in at.error)
    assert _contar(bd, Utilizador) == 0


# ---------------------------------------------------------------- Guardar e voltar


def test_plano_fica_guardado_e_volta_numa_nova_sessao(bd: str) -> None:
    at = _nova_sessao()
    assert _contar(bd, Utilizador) == 1  # conta criada no primeiro login
    _gerar(at)
    guardado = at.session_state["resultado"]
    assert _contar(bd, PlanoGuardado) == 1
    assert _contar(bd, QuestionarioGuardado) == 1

    outra = _nova_sessao()
    assert outra.session_state["resultado"].id == guardado.id
    assert outra.session_state["resultado"].plano == guardado.plano
    outra.switch_page("paginas/plano.py").run()
    assert not outra.exception
    assert any("guardado na sua conta" in c.value for c in outra.caption)
    assert _contar(bd, PlanoGuardado) == 1  # não gerou de novo
    # Respostas preenchidas com as últimas; consentimentos por marcar.
    q = Questionario.model_validate_json(
        (RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8")
    )
    assert outra.session_state[chave("idade")] == q.idade
    for campo in ("aceita_termos", "consentimento_saude", "confirma_maior_idade"):
        assert outra.session_state[chave(campo)] is False


# ---------------------------------------------------------------- A minha conta


def test_conta_lista_planos_e_exporta(bd: str) -> None:
    at = _nova_sessao()
    _gerar(at)
    at.switch_page(CONTA).run()
    assert not at.exception
    assert any("local@vigoria.invalid" in m.value for m in at.markdown)
    assert any(m.value.startswith("Plano de ") for m in at.markdown)
    assert _botao(at, "Aberto").disabled  # o plano que se está a ver
    assert len(at.get("download_button")) == 1


def test_apagar_conta_exige_confirmacao_dupla_e_apaga_tudo(bd: str) -> None:
    at = _nova_sessao()
    _gerar(at)
    at.switch_page(CONTA).run()
    apagar = "Apagar a conta e os dados"
    assert _botao(at, apagar).disabled
    at.checkbox(key="conta_apagar_confirma").check().run()
    assert _botao(at, apagar).disabled  # falta escrever APAGAR
    at.text_input(key="conta_apagar_palavra").input("apagar").run()
    assert not _botao(at, apagar).disabled
    _botao(at, apagar).click().run()
    assert not at.exception
    for tabela in (Utilizador, QuestionarioGuardado, PlanoGuardado):
        assert _contar(bd, tabela) == 0
    assert any("foram apagados" in s.value for s in at.success)
    at.run()  # outra execução não volta a criar a conta
    assert _contar(bd, Utilizador) == 0


# ---------------------------------------------------------------- RGPD


class _Espiao(ProvedorSimulado):
    """Simulado que guarda o que seria enviado à LLM."""

    enviados: list[str] = []

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        _Espiao.enviados.append(sistema + pedido)
        return super().gerar_json(sistema, pedido, schema)


def test_llm_sem_identificadores_e_logs_sem_saude(
    bd: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _Espiao.enviados = []
    monkeypatch.setattr(escolha, "criar_provedor", lambda *a, **k: _Espiao())
    at = _nova_sessao()
    with caplog.at_level(logging.DEBUG):
        _gerar(at, medicacao_notas=NOTAS)
    assert at.session_state["resultado"].id > 0
    (enviado,) = _Espiao.enviados
    assert "bisoprolol" in enviado  # o texto livre segue, já filtrado
    for proibido in (
        "912 345 678",  # filtro de contactos do gerador (Fase 4A)
        "ana.silva@exemplo.pt",
        sessao.UTILIZADOR_LOCAL.sub,  # identificadores da conta
        sessao.UTILIZADOR_LOCAL.email,
    ):
        assert proibido not in enviado
    for valor in ("bisoprolol", "912 345 678", "ana.silva", sessao.UTILIZADOR_LOCAL.email):
        assert valor not in caplog.text
