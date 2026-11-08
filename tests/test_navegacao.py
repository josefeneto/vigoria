"""Navegação e rodapé (arrumação antes da Fase 10), sem browser (AppTest).

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
MENU_COM_SESSAO = {
    "": ["Início", "Questionário", "O meu plano", "O meu progresso", "Ajuda"],
    "Conta": ["A minha conta", "Terminar sessão"],
}
OCULTAS = {"privacidade", "cancelar-lembretes"}


@pytest.fixture
def menu(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """O último menu passado a st.navigation (lista ou dicionário de secções)."""
    vistos: list[Any] = []
    original: Callable[..., Any] = st.navigation

    def espiao(paginas: Any, **kwargs: Any) -> Any:
        vistos.append(paginas)
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


def _visiveis(paginas: list[Any]) -> list[str]:
    return [p.title for p in paginas if p.visibility == "visible"]


def _rodape(at: AppTest) -> tuple[list[str], str]:
    rodape = at.get_by_key("rodape")
    ligacoes = [p.proto.label for p in rodape.get("page_link")]
    texto = "\n".join(m.value for m in rodape.markdown)
    return ligacoes, texto


def test_com_sessao_menu_com_o_grupo_conta(menu: list[Any], com_sessao: None) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    seccoes = menu[-1]
    assert isinstance(seccoes, dict)
    assert {s: _visiveis(p) for s, p in seccoes.items()} == MENU_COM_SESSAO
    assert list(seccoes) == ["", t.SECCAO_CONTA]  # a conta é a última entrada
    ocultas = {p.url_path for p in seccoes[""] if p.visibility == "hidden"}
    assert ocultas == OCULTAS


def test_sem_sessao_so_inicio_e_ajuda(menu: list[Any], sem_sessao: None) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert _visiveis(menu[-1]) == ["Início", "Ajuda"]
    assert {p.url_path for p in menu[-1] if p.visibility == "hidden"} == OCULTAS
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
