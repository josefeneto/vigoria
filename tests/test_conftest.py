"""conftest.py: testes «llm» saltados por omissão; com a variável, 300 s no máximo."""

from typing import Any

import conftest
import pytest


class _Item:
    def __init__(self, *marcadores: str) -> None:
        self.keywords = dict.fromkeys(marcadores, True)
        self.marcadores: list[Any] = []

    def add_marker(self, marcador: Any) -> None:
        self.marcadores.append(marcador.mark)


def _aplicar(*items: _Item) -> None:
    conftest.pytest_collection_modifyitems(None, list(items))  # type: ignore[arg-type]


def test_sem_variavel_salta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIGORIA_TESTES_LLM_REAIS", raising=False)
    llm, normal = _Item("llm"), _Item()
    _aplicar(llm, normal)
    assert [m.name for m in llm.marcadores] == ["skip"]
    assert normal.marcadores == []


def test_com_variavel_tempo_maximo_300_s(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_TESTES_LLM_REAIS", "1")
    llm, normal = _Item("llm"), _Item()
    _aplicar(llm, normal)
    (marcador,) = llm.marcadores
    assert marcador.name == "timeout"
    assert marcador.args == (300,)
    assert normal.marcadores == []
