"""Páginas Streamlit, sem browser (streamlit.testing.AppTest). Nunca chamam uma LLM real:
a geração usa o fornecedor simulado (VIGORIA_PROVEDOR_LLM=simulado, AMBIENTE=local)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from vigoria.config import obter_configuracao
from vigoria.interface.estado import chave, para_estado
from vigoria.interface.passos import respostas_de_questionario
from vigoria.modelos.questionario import Questionario
from vigoria.regras import textos

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "app.py")
QUESTIONARIO = "paginas/questionario.py"


@pytest.fixture(autouse=True)
def _simulado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "simulado")
    monkeypatch.setenv("VIGORIA_PROVEDOR_RESERVA", "")
    monkeypatch.setenv("AMBIENTE", "local")
    obter_configuracao.cache_clear()
    yield
    obter_configuracao.cache_clear()


def _app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page(QUESTIONARIO).run()
    assert not at.exception
    return at


def _botao(at: AppTest, rotulo: str):  # type: ignore[no-untyped-def]
    return next(b for b in at.button if b.label == rotulo)


def _persona(at: AppTest, **alteracoes: object) -> None:
    q = Questionario.model_validate_json(
        (RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8")
    )
    for k, v in para_estado(respostas_de_questionario(q) | alteracoes).items():
        at.session_state[k] = v


def test_passo_0_nao_avanca_sem_consentimento() -> None:
    at = _app()
    _botao(at, "Seguinte").click().run()
    assert at.session_state["passo"] == "0"
    assert at.error  # mensagem geral e uma por caixa
    for caixa in at.checkbox:
        caixa.check()
    at.run()
    _botao(at, "Seguinte").click().run()
    assert at.session_state["passo"] == "1"
    assert not at.exception


def test_gravidez_termina_sem_guardar_respostas() -> None:
    at = _app()
    _persona(at, condicoes=["gravidez"], condicoes_controladas={})
    at.session_state["passo"] = "2a"
    at.run()
    _botao(at, "Seguinte").click().run()
    assert not at.exception
    assert any(textos.GRAVIDEZ in i.value for i in at.info)
    assert at.session_state[chave("peso_kg")] is None  # respostas apagadas
    assert "resultado" not in at.session_state


def test_articulacoes_so_aparecem_com_dor_articular() -> None:
    at = _app()
    _persona(at)
    at.session_state["passo"] = "2a"
    at.run()
    rotulos = [p.label for p in at.get("button_group")]
    assert "Em que articulações?" not in rotulos
    at.session_state[chave("condicoes")] = ["dor_articular_persistente"]
    at.run()
    assert "Em que articulações?" in [p.label for p in at.get("button_group")]


def test_revisao_mostra_decisoes_e_gera_plano_simulado() -> None:
    at = _app()
    _persona(at)
    at.session_state["passo"] = "7"
    at.run()
    assert not at.exception
    texto = "\n".join(m.value for m in at.markdown)
    assert "à semana 16" in texto  # objetivo ajustado da persona
    _botao(at, "Gerar o meu plano").click().run(timeout=60)
    assert not at.exception
    resultado = at.session_state["resultado"]
    assert resultado.plano.provedor == "simulado"
    assert resultado.chamadas == 1


def test_plano_mostra_faixa_simulado_e_avisos_em_cada_separador() -> None:
    at = _app()
    _persona(at)
    at.session_state["passo"] = "7"
    at.run()
    _botao(at, "Gerar o meu plano").click().run(timeout=60)
    at.switch_page("paginas/plano.py").run()
    assert not at.exception
    titulos = [w.proto.title for w in at.warning]
    assert "Plano simulado (persona de teste)" in titulos
    assert titulos.count("Avisos importantes") == 5  # um por separador
    texto = "\n".join(m.value for m in at.markdown)
    assert "Em vez de:" not in texto  # fase 1: a limitação ligeira só troca nas fases 2 a 4
    at.session_state["plano_fase"] = 2
    at.run()
    assert "Em vez de:" in "\n".join(m.value for m in at.markdown)


def test_plano_sem_resultado_convida_ao_questionario() -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page("paginas/plano.py").run()
    assert not at.exception
    assert at.info
