"""Configuração comum dos testes."""

import os

import pytest

TEMPO_MAXIMO_LLM_S = 300


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Salta os testes marcados «llm», salvo se VIGORIA_TESTES_LLM_REAIS=1.

    A variável é lida só de os.environ, nunca do .env nem do config.py.
    Quando correm, cada um tem um tempo máximo de 300 s (pytest-timeout).
    """
    if os.environ.get("VIGORIA_TESTES_LLM_REAIS") == "1":
        for item in items:
            if "llm" in item.keywords:
                item.add_marker(pytest.mark.timeout(TEMPO_MAXIMO_LLM_S))
        return
    saltar = pytest.mark.skip(reason="teste com LLM real; defina VIGORIA_TESTES_LLM_REAIS=1")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(saltar)
