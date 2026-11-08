"""Páginas com conta (Fase 6), sem browser (AppTest) e sem Auth0: utilizador local fictício
(VIGORIA_UTILIZADOR_LOCAL=1, só AMBIENTE=local) e uma base SQLite nova por teste."""

import logging
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from streamlit.testing.v1 import AppTest

from paginas import comum, sessao
from vigoria import config
from vigoria.config import obter_configuracao
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.tabelas import (
    PlanoGuardado,
    QuestionarioGuardado,
    RegistoProgresso,
    Utilizador,
)
from vigoria.interface.estado import chave, para_estado
from vigoria.interface.passos import respostas_de_questionario
from vigoria.llm import escolha
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.questionario import FrequenciaRegisto, Questionario

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


def test_base_de_dados_indisponivel_mostra_mensagem_em_vez_de_rodar(
    bd: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def falha() -> None:
        raise OperationalError("SELECT 1", {}, ConnectionError("timeout"))

    monkeypatch.setattr(sessao, "entrar", falha)
    with caplog.at_level(logging.WARNING):
        at = _nova_sessao()
    assert any("Não foi possível ligar à base de dados" in e.value for e in at.error)
    assert "Tentar de novo" in [b.label for b in at.button]
    assert "Começar o questionário" not in [b.label for b in at.button]
    assert "base de dados indisponível: ConnectionError" in caplog.text


def test_fora_da_lista_de_convidados_so_ve_a_mensagem(
    bd: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGORIA_EMAILS_PERMITIDOS", "ana@exemplo.pt, rui@exemplo.pt")
    obter_configuracao.cache_clear()
    at = _nova_sessao()
    assert any("apenas por convite" in i.value for i in at.info)
    assert [b.label for b in at.button] == ["Terminar sessão"]
    # Nem o Início por baixo: o único html é o dos estilos.
    html = "\n".join(h.proto.body for h in at.get("html"))
    assert "Como funciona" not in html and 'class="v-promessa"' not in html
    assert sessao.UTILIZADOR not in at.session_state
    assert _contar(bd, Utilizador) == 0  # sem registo na base de dados
    at.switch_page(QUESTIONARIO).run()
    assert [b.label for b in at.button] == ["Terminar sessão"]
    assert _contar(bd, Utilizador) == 0


def test_na_lista_de_convidados_entra_sem_ligar_a_maiusculas(
    bd: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGORIA_EMAILS_PERMITIDOS", "ana@exemplo.pt; LOCAL@Vigoria.invalid ")
    obter_configuracao.cache_clear()
    at = _nova_sessao()
    assert not any("apenas por convite" in i.value for i in at.info)
    assert "Começar o questionário" in [b.label for b in at.button]
    assert _contar(bd, Utilizador) == 1


def _demo(monkeypatch: pytest.MonkeyPatch, lista: str) -> None:
    """Demonstração (app pública no Cloud) com uma pessoa já entrada no Auth0."""
    monkeypatch.setenv("AMBIENTE", "demo")
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "gemini")  # o simulado só é aceite em local
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "0")
    monkeypatch.setenv("VIGORIA_EMAILS_PERMITIDOS", lista)
    monkeypatch.setattr(sessao, "identidade", lambda: CONVIDADA)
    obter_configuracao.cache_clear()


CONVIDADA = sessao.Identidade(sub="auth0|demo", email="ana@exemplo.pt", email_verificado=True)


# «Em falta» lê-se como vazia (test_config); aqui não se depende do .env local.
@pytest.mark.parametrize("lista", ["", " , "])
def test_demo_sem_lista_de_convidados_ninguem_entra(
    bd: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, lista: str
) -> None:
    _demo(monkeypatch, lista)
    with caplog.at_level(logging.WARNING):
        at = _nova_sessao()
    assert any("apenas por convite" in i.value for i in at.info)
    assert [b.label for b in at.button] == ["Terminar sessão"]
    assert _contar(bd, Utilizador) == 0
    assert "VIGORIA_EMAILS_PERMITIDOS em falta ou vazia com AMBIENTE=demo" in caplog.text
    assert CONVIDADA.email not in caplog.text


def test_demo_com_lista_entra_quem_esta_nela(bd: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _demo(monkeypatch, "Ana@exemplo.pt")
    at = _nova_sessao()
    assert not any("apenas por convite" in i.value for i in at.info)
    assert "Começar o questionário" in [b.label for b in at.button]
    assert _contar(bd, Utilizador) == 1


def test_local_sem_lista_todos_entram(bd: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_EMAILS_PERMITIDOS", "")
    obter_configuracao.cache_clear()
    at = _nova_sessao()
    assert "Começar o questionário" in [b.label for b in at.button]
    assert _contar(bd, Utilizador) == 1


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
    rotulos = [d.proto.label for d in at.get("download_button")]
    assert rotulos == [
        "Descarregar o plano (PDF)",
        "Descarregar os meus dados (formato técnico, JSON)",
    ]


def test_plano_tem_o_botao_do_pdf(bd: str) -> None:
    at = _nova_sessao()
    _gerar(at)
    at.switch_page("paginas/plano.py").run()
    assert not at.exception
    (botao,) = at.get("download_button")
    assert botao.proto.label == "Descarregar o plano (PDF)"


def test_pdf_de_um_plano_da_conta_so_para_o_dono(bd: str) -> None:
    at = _nova_sessao()
    _gerar(at)
    plano_id = at.session_state["resultado"].id
    motor = criar_motor(bd)
    fabrica = fabrica_sessoes(motor)
    uid = at.session_state[sessao.UTILIZADOR][1]
    assert comum._pdf_guardado(fabrica, uid, plano_id).startswith(b"%PDF-")
    assert comum._pdf_guardado(fabrica, uid + 1, plano_id) == b""  # outro utilizador: nada
    motor.dispose()


def test_apagar_plano_pede_confirmacao_e_abre_o_anterior(bd: str) -> None:
    at = _nova_sessao()
    _gerar(at)
    primeiro = at.session_state["resultado"].id
    _gerar(at)
    segundo = at.session_state["resultado"].id
    at.switch_page(CONTA).run()
    at.button(key=f"apagar_{segundo}").click().run()
    assert _contar(bd, PlanoGuardado) == 2  # ainda só pediu
    at.button(key=f"apagar_nao_{segundo}").click().run()
    assert not [b for b in at.button if b.key == f"apagar_sim_{segundo}"]
    at.button(key=f"apagar_{segundo}").click().run()
    at.button(key=f"apagar_sim_{segundo}").click().run()
    assert not at.exception
    assert _contar(bd, PlanoGuardado) == 1
    assert _contar(bd, QuestionarioGuardado) == 2  # as respostas ficam
    assert at.session_state["resultado"].id == primeiro  # o aberto passa a ser o anterior
    at.button(key=f"apagar_{primeiro}").click().run()
    at.button(key=f"apagar_sim_{primeiro}").click().run()
    assert _contar(bd, PlanoGuardado) == 0
    assert "resultado" not in at.session_state
    assert any("Ainda não tem planos" in c.value for c in at.caption)


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


# ---------------------------------------------------------------- O meu progresso

PROGRESSO = "paginas/progresso.py"


def _com_plano_e_progresso() -> AppTest:
    at = _nova_sessao()
    _gerar(at)
    at.switch_page(PROGRESSO).run()
    assert not at.exception
    return at


def _guardar_registo(at: AppTest, **campos: float) -> None:
    for sufixo, valor in campos.items():
        next(n for n in at.number_input if n.key.endswith(f"_{sufixo}")).set_value(valor)
    _botao(at, "Guardar o registo").click().run()
    assert not at.exception


def test_progresso_sem_plano_convida_ao_questionario(bd: str) -> None:
    at = _nova_sessao()
    at.switch_page(PROGRESSO).run()
    assert not at.exception
    assert any("responder ao questionário" in i.value for i in at.info)
    assert not at.number_input


def test_progresso_regista_edita_e_apaga(bd: str) -> None:
    at = _com_plano_e_progresso()
    assert any("Está na semana 1 de 16" in m.value for m in at.markdown)
    assert any("Próximo marco: semana 4" in m.value for m in at.markdown)

    _guardar_registo(at, peso=93.5, energia=7)
    motor = criar_motor(bd)
    assert _contar(bd, RegistoProgresso) == 1
    motor.dispose()
    assert any("Peso (kg): 93,5" in m.value for m in at.markdown)

    # Só um registo por período: o formulário fica guardado num expansor e a repetição é recusada.
    _guardar_registo(at, peso=93.0)
    assert any("Já tem um registo para a semana 1" in e.value for e in at.error)
    assert _contar(bd, RegistoProgresso) == 1

    at.button(key="editar_1").click().run()
    assert not at.exception
    next(n for n in at.number_input if n.key == "registo_1_peso").set_value(93.2)
    next(b for b in at.button if b.label == "Guardar o registo" and "registo_1" in b.key).click()
    at.run()
    assert any("Peso (kg): 93,2" in m.value for m in at.markdown)

    at.button(key="apagar_1").click().run()
    at.button(key="apagar_sim_1").click().run()
    assert not at.exception
    assert _contar(bd, RegistoProgresso) == 0


def test_progresso_registo_vazio_nao_guarda(bd: str) -> None:
    at = _com_plano_e_progresso()
    _botao(at, "Guardar o registo").click().run()
    assert any("pelo menos um campo" in e.value for e in at.error)
    assert _contar(bd, RegistoProgresso) == 0


def test_progresso_desligado_sem_formulario_mas_com_os_registos(bd: str) -> None:
    at = _com_plano_e_progresso()
    _guardar_registo(at, peso=93.5)
    at.switch_page(CONTA).run()
    at.toggle(key="conta_acompanhamento_ativo").set_value(False).run()
    assert not at.exception
    at.switch_page(PROGRESSO).run()
    assert any("acompanhamento está desligado" in i.value for i in at.info)
    assert not at.number_input
    assert any("Peso (kg): 93,5" in m.value for m in at.markdown)


def test_conta_muda_a_frequencia_e_o_formulario_acompanha(bd: str) -> None:
    at = _com_plano_e_progresso()
    assert "Sessões feitas" in [n.label for n in at.number_input]
    at.switch_page(CONTA).run()
    at.radio(key="conta_frequencia").set_value(FrequenciaRegisto.A_CADA_4_SEMANAS).run()
    assert not at.exception
    at.switch_page(PROGRESSO).run()
    assert "Sessões feitas (numa semana normal)" in [n.label for n in at.number_input]


def test_o_plano_so_convida_a_responder_de_novo_na_semana_16(
    bd: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    at = _nova_sessao()
    _gerar(at)
    at.switch_page("paginas/plano.py").run()
    assert not any("Chegou à semana 16" in i.value for i in at.info)
    futuro = comum.hoje() + timedelta(days=7 * 15)
    monkeypatch.setattr(comum, "hoje", lambda: futuro)
    at.run()
    assert any("Chegou à semana 16" in i.value for i in at.info)


# ---------------------------------------------------------------- Ajuda (Fase 8B)


def _ligacao_ajuda(at: AppTest) -> str:
    """O tema da ligação «Como funciona?» da página (tem de haver exatamente uma)."""
    ligacoes = [p.proto for p in at.get("page_link") if p.proto.label == "Como funciona?"]
    assert len(ligacoes) == 1
    assert ligacoes[0].page.endswith("ajuda")
    return ligacoes[0].query_string


def test_progresso_e_conta_ligam_a_ajuda_no_tema_certo(bd: str) -> None:
    at = _com_plano_e_progresso()
    assert _ligacao_ajuda(at) == "tema=registo"
    at.switch_page(CONTA).run()
    assert not at.exception
    assert _ligacao_ajuda(at) == "tema=lembretes"
