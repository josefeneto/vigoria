"""Navegação (Fase 8D: barra própria) e rodapé, sem browser (AppTest).

O menu verifica-se com um espião sobre st.navigation (o AppTest não expõe as secções); os
endereços, com as páginas que a app regista.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from paginas import textos as t
from vigoria import config
from vigoria.config import obter_configuracao

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "app.py")
BARRA = ["Início", "Plano", "Progresso", "Ajuda"]
MENU_CONTA = ["A minha conta", "Ajuda", "Privacidade", "Terminar sessão"]
OCULTAS = {"privacidade", "cancelar-lembretes"}


@pytest.fixture
def menu(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Cada chamada a st.navigation: (páginas, argumentos com nome)."""
    vistos: list[Any] = []
    original: Callable[..., Any] = st.navigation

    def espiao(paginas: Any, **kwargs: Any) -> Any:
        vistos.append((paginas, kwargs))
        return original(paginas, **kwargs)

    monkeypatch.setattr(st, "navigation", espiao)
    return vistos


@pytest.fixture
def com_sessao(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Utilizador local fictício e uma base SQLite nova (como em test_paginas_conta.py)."""
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "simulado")
    monkeypatch.setenv("VIGORIA_PROVEDOR_RESERVA", "")
    monkeypatch.setenv("AMBIENTE", "local")
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vigoria.db'}")
    obter_configuracao.cache_clear()
    yield
    obter_configuracao.cache_clear()


@pytest.fixture
def sem_sessao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "0")
    monkeypatch.setattr(config, "obter_auth0", lambda: None)
    obter_configuracao.cache_clear()
    yield
    obter_configuracao.cache_clear()


def _rodape(at: AppTest) -> tuple[list[str], str]:
    rodape = at.get_by_key("rodape")
    ligacoes = [p.proto.label for p in rodape.get("page_link")]
    texto = "\n".join(m.value for m in rodape.markdown)
    return ligacoes, texto


def _ligacoes(at: AppTest, chave: str) -> list[str]:
    return [p.proto.label for p in at.get_by_key(chave).get("page_link")]


def test_com_sessao_barra_com_o_menu_conta(menu: list[Any], com_sessao: None) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    # O menu do Streamlit fica escondido: a navegação é a de paginas/navegacao.py.
    paginas, opcoes = menu[-1]
    assert opcoes["position"] == "hidden"
    assert {p.url_path for p in paginas} >= {"questionario", "plano", "conta", "sair"} | OCULTAS
    # Barra: Início, Plano, Progresso e Ajuda; «Conta» abre A minha conta, Ajuda, Privacidade
    # e Terminar sessão (no telemóvel, a Ajuda da barra esconde-se por CSS).
    assert _ligacoes(at, "barra_nav") == [*BARRA, *MENU_CONTA]
    assert _ligacoes(at, "nav_conta_menu") == MENU_CONTA
    assert "Questionário" not in _ligacoes(at, "barra_nav")


@pytest.mark.parametrize(
    ("pagina", "ativa"),
    [
        ("paginas/inicio.py", "inicio"),
        ("paginas/plano.py", "plano"),
        ("paginas/progresso.py", "progresso"),
        ("paginas/ajuda.py", "ajuda"),
        ("paginas/conta.py", "conta"),
        ("paginas/privacidade.py", "conta"),
    ],
)
def test_pagina_atual_marcada_na_barra(pagina: str, ativa: str, com_sessao: None) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page(pagina).run()
    assert not at.exception
    ativas = [
        n
        for n in ("inicio", "plano", "progresso", "ajuda", "conta")
        if _tem_chave(at, f"nav_ativo_{n}")
    ]
    assert ativas == [ativa]


def test_questionario_sem_pagina_ativa_na_barra(com_sessao: None) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page("paginas/questionario.py").run()
    assert not any(
        _tem_chave(at, f"nav_ativo_{n}") for n in ("inicio", "plano", "progresso", "ajuda", "conta")
    )


def _tem_chave(at: AppTest, chave: str) -> bool:
    try:
        at.get_by_key(chave)
    except KeyError:
        return False
    return True


def test_sem_sessao_so_inicio_e_entrar(menu: list[Any], sem_sessao: None) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    paginas, opcoes = menu[-1]
    assert opcoes["position"] == "hidden"
    assert [p.url_path for p in paginas if p.url_path not in OCULTAS] == ["", "ajuda"]
    assert not _tem_chave(at, "barra_nav")
    assert at.button(key="topo_entrar").label == "Entrar"
    assert "Entrar ou criar conta" in [b.label for b in at.button]


def _ocultas_abrem(at: AppTest) -> set[str]:
    enderecos = {info["url_pathname"] for info in at._registered_pages.values()}
    assert enderecos >= OCULTAS
    at.switch_page("paginas/privacidade.py").run()
    assert not at.exception
    assert at.title[0].value == "Política de privacidade"
    return enderecos


def test_paginas_ocultas_abrem_pelo_endereco_com_sessao(com_sessao: None) -> None:
    assert "sair" in _ocultas_abrem(AppTest.from_file(APP, default_timeout=30).run())


def test_paginas_ocultas_abrem_pelo_endereco_sem_sessao(sem_sessao: None) -> None:
    assert "sair" not in _ocultas_abrem(AppTest.from_file(APP, default_timeout=30).run())


@pytest.mark.parametrize(
    "pagina",
    [
        "paginas/inicio.py",
        "paginas/questionario.py",
        "paginas/plano.py",  # sem plano: para a meio, com comum.parar()
        "paginas/progresso.py",  # idem
        "paginas/conta.py",
        "paginas/ajuda.py",
        "paginas/privacidade.py",
    ],
)
def test_rodape_em_todas_as_paginas(pagina: str, com_sessao: None) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page(pagina).run()
    assert not at.exception
    ligacoes, texto = _rodape(at)
    assert ligacoes == ["Privacidade", "Ajuda"]
    assert "[geral@vigoria.pt](mailto:geral@vigoria.pt)" in texto


def test_rodape_sem_sessao(sem_sessao: None) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert _rodape(at)[0] == ["Privacidade", "Ajuda"]


def test_consentimento_mantem_a_ligacao_a_privacidade(com_sessao: None) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page("paginas/questionario.py").run()
    rotulos = [p.proto.label for p in at.get("page_link")]
    assert t.LER_PRIVACIDADE in rotulos


def test_mensagens_sem_menu_tem_o_contacto() -> None:
    assert t.SO_POR_CONVITE == (
        "A Vigoria está em fase de testes, apenas por convite. Se quiser participar, escreva "
        "para geral@vigoria.pt."
    )
    assert t.BD_INDISPONIVEL.endswith("Se o problema continuar, escreva para geral@vigoria.pt.")
