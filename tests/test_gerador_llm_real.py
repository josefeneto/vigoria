"""Geração com o Gemini real. Só corre com VIGORIA_TESTES_LLM_REAIS=1 (só o José).

Cada teste faz uma geração (uma chamada) e tem 300 s no máximo (conftest.py).
O «-k persona» escolhe só o primeiro: os nomes dos outros não contêm «persona».

PowerShell (o -s mostra o progresso das chamadas):
    $env:VIGORIA_TESTES_LLM_REAIS = "1"; python -m pytest -m llm -k persona -s
    $env:VIGORIA_TESTES_LLM_REAIS = "1"; python -m pytest -m llm -k osteoporose -s
"""

import json
from pathlib import Path

import pytest

from vigoria.llm.gemini import ProvedorGemini
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import gerar_plano
from vigoria.motor.selecao import selecionar_exercicios

EXEMPLOS = Path(__file__).parent.parent / "exemplos"


def _gerar_e_confirmar(ficheiro: str) -> Plano:
    q = Questionario.model_validate(json.loads((EXEMPLOS / ficheiro).read_text(encoding="utf-8")))
    e = gerar_estrategia(q)
    plano = gerar_plano(q, e, ProvedorGemini())

    assert plano.avisos == e.avisos
    assert len(plano.semana_tipo) == 7
    for fase in (1, 2, 3, 4):
        permitidos = {p.id for p in selecionar_exercicios(e, fase)}
        treino = getattr(plano.treino, f"fase_{fase}")
        assert treino.exercicios
        assert {x.exercicio_id for x in treino.exercicios} <= permitidos
    return plano


@pytest.mark.llm
def test_plano_real_persona() -> None:
    """Persona de teste (exemplos/persona_teste.json)."""
    print(_gerar_e_confirmar("persona_teste.json").model_dump_json(indent=2))


@pytest.mark.llm
def test_plano_real_osteoporose() -> None:
    """Osteoporose com risco elevado: modo prudente e equilíbrio com apoio."""
    print(_gerar_e_confirmar("persona_osteoporose.json").model_dump_json(indent=2))
