"""A passagem dos textos para conteudo/avisos.yaml não muda nenhuma palavra.

As fotografias em tests/fixtures/ foram guardadas antes da passagem (Fase 3, parte 2).
"""

import contextlib
import io
import json
from pathlib import Path

import pytest

from vigoria.motor import cli
from vigoria.regras import textos

RAIZ = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
PERSONAS = sorted((RAIZ / "exemplos").glob("*.json"))
TEXTOS_FASE2 = json.loads((FIXTURES / "textos_fase2.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("persona", PERSONAS, ids=lambda p: p.stem)
def test_cli_igual_a_fotografia(persona: Path) -> None:
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        assert cli.main(["--so-estrategia", str(persona)]) == 0
    esperado = (FIXTURES / f"cli_{persona.stem}.txt").read_text(encoding="utf-8")
    assert saida.getvalue() == esperado


@pytest.mark.parametrize("nome", [n for n in TEXTOS_FASE2 if not n.startswith("_")])
def test_texto_igual_a_fotografia(nome: str) -> None:
    valor = getattr(textos, nome)
    if isinstance(valor, dict):
        valor = {str(k): v for k, v in valor.items()}
    elif isinstance(valor, tuple):
        valor = list(valor)
    assert valor == TEXTOS_FASE2[nome]
