"""Textos de produção (Fase 10D): a política de privacidade única e a faixa da demonstração."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from paginas import textos as t
from paginas.textos_privacidade import em_rascunho, privacidade
from vigoria.config import obter_configuracao
from vigoria.conteudo.carregar import carregar_avisos
from vigoria.motor.voz import encontrar_termos

RAIZ = Path(__file__).resolve().parents[1]


def test_privacidade_sem_github_nem_demonstracao() -> None:
    texto = privacidade()
    assert "GitHub" not in texto and "demonstração" not in texto
    assert "Railway" in texto and "Amesterdão" in texto and "Frankfurt" in texto
    assert "Estados Unidos" in texto and "treinar" in texto
    assert "Google" in texto and "Gemini API" in texto and "Groq" in texto
    assert "A CONFIRMAR" not in texto  # a marca fica só no código e no guia
    avisos = carregar_avisos()
    assert encontrar_termos(avisos.brasileirismos, texto) == ()


def test_privacidade_completa_e_em_vigor() -> None:
    texto = privacidade()
    assert not em_rascunho(texto)  # sem «[PREENCHER»: a faixa RASCUNHO desaparece
    assert "privacidade@vigoria.pt" in texto
    assert "a Groq **não as guarda**" in texto
    assert "manutenção" in texto and "45 anos" in texto
    assert "Versão de **20/11/2026**" in texto
    assert "meses" not in texto  # sem a regra de inatividade, que a app ainda não aplica
    assert t.VERSAO_CONSENTIMENTO == "2026-11-20"  # acompanha a versão da política


def test_rascunho_so_com_campos_por_preencher() -> None:
    assert em_rascunho("Responsável: [PREENCHER: nome]")
    assert not em_rascunho("Responsável: Vigoria")


def test_caixa_de_aceitacao_liga_a_privacidade() -> None:
    rotulo = t.ROTULOS_CONSENTIMENTO["aceita_termos"]
    assert rotulo == "Li e aceito a [política de privacidade](/privacidade)."
    assert "termos" not in rotulo  # os termos de utilização ainda não existem
    assert t.ACEITA_AO_CRIAR_CONTA[1] == "política de privacidade"


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
    assert "GitHub" not in texto and "Railway" in texto  # a mesma política em todo o lado
    assert not [w for w in at.warning if "rascunho" in w.value]  # sem «[PREENCHER»
    at.switch_page("paginas/inicio.py").run()  # sem sessão: a frase da privacidade aparece
    html = "\n".join(h.proto.body for h in at.get("html"))
    assert '<a href="/privacidade" target="_self">política de privacidade</a>' in html
