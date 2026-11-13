"""Textos de produção (Fase 10D): privacidade por ambiente, ajuda e faixa da demonstração."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from paginas import textos as t
from paginas.textos_privacidade import privacidade
from vigoria.config import obter_configuracao
from vigoria.conteudo.carregar import carregar_avisos
from vigoria.motor.voz import encontrar_termos

RAIZ = Path(__file__).resolve().parents[1]


def test_privacidade_de_producao_sem_github_nem_demonstracao() -> None:
    texto = privacidade("producao")
    assert "GitHub" not in texto and "demonstração" not in texto
    assert "Railway" in texto and "Amesterdão" in texto and "Frankfurt" in texto
    assert "Estados Unidos" in texto and "treinar" in texto
    assert "Google" in texto and "Gemini API" in texto and "Groq" in texto
    assert "A CONFIRMAR" not in texto  # a marca fica só no código e no guia
    avisos = carregar_avisos()
    assert encontrar_termos(avisos.brasileirismos, texto) == ()


def test_privacidade_da_demo_mantem_github_e_aviso() -> None:
    texto = privacidade("demo")
    assert "GitHub" in texto and "não introduza dados reais de saúde" in texto


def test_local_usa_o_texto_de_producao() -> None:
    assert privacidade("local") == privacidade("producao")


@pytest.fixture(params=["producao", "demo"])
def ambiente(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[str]:
    monkeypatch.setenv("AMBIENTE", request.param)
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "groq")
    monkeypatch.setenv("VIGORIA_PROVEDOR_RESERVA", "")
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "0")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vigoria.db'}")
    obter_configuracao.cache_clear()
    yield request.param
    obter_configuracao.cache_clear()


def test_faixa_da_demonstracao_so_na_demo(ambiente: str) -> None:
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert (t.DEMO_AVISO in [w.value for w in at.warning]) is (ambiente == "demo")
    at.switch_page("paginas/privacidade.py").run()
    texto = "\n".join(m.value for m in at.markdown)
    assert ("GitHub" in texto) is (ambiente == "demo")
    assert ("Railway" in texto) is (ambiente == "producao")
