"""Geração com o Gemini real. Só corre com VIGORIA_TESTES_LLM_REAIS=1 (só o José).

PowerShell:
    $env:VIGORIA_TESTES_LLM_REAIS = "1"; python -m pytest -m llm -k persona -s
"""

import json
from pathlib import Path

import pytest

from vigoria.llm.gemini import ProvedorGemini
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import gerar_plano
from vigoria.motor.selecao import selecionar_exercicios

EXEMPLOS = Path(__file__).parent.parent / "exemplos"


@pytest.mark.llm
@pytest.mark.parametrize("ficheiro", ["persona_teste.json", "persona_osteoporose.json"])
def test_plano_real_persona(ficheiro: str) -> None:
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
    print(plano.model_dump_json(indent=2))
