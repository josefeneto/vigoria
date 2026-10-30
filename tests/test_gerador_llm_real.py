"""Só o gerador (sem verificação) com a LLM real: persona com osteoporose.

Só corre com VIGORIA_TESTES_LLM_REAIS=1 (só o José). Uma chamada, 300 s no máximo.
A persona de teste corre o pipeline completo em test_pipeline_llm_real.py; o nome
deste teste não contém «persona», para o «-k persona» escolher só aquele.

PowerShell (o -s mostra o progresso das chamadas):
    $env:VIGORIA_TESTES_LLM_REAIS = "1"; python -m pytest -m llm -k osteoporose -s
"""

import json
from pathlib import Path

import pytest

from vigoria.llm.escolha import criar_provedor
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import gerar_plano
from vigoria.motor.selecao import selecionar_exercicios

EXEMPLOS = Path(__file__).parent.parent / "exemplos"


def _gerar_e_confirmar(ficheiro: str) -> Plano:
    q = Questionario.model_validate(json.loads((EXEMPLOS / ficheiro).read_text(encoding="utf-8")))
    e = gerar_estrategia(q)
    plano = gerar_plano(q, e, criar_provedor())

    assert plano.avisos == e.avisos
    assert plano.provedor in ("gemini", "groq", "mistral")
    assert len(plano.semana_tipo) == 7
    for fase in (1, 2, 3, 4):
        permitidos = {p.id for p in selecionar_exercicios(e, fase)}
        treino = getattr(plano.treino, f"fase_{fase}")
        assert treino.exercicios
        assert {x.exercicio_id for x in treino.exercicios} <= permitidos
    return plano


@pytest.mark.llm
def test_plano_real_osteoporose() -> None:
    """Osteoporose com risco elevado: modo prudente e equilíbrio com apoio."""
    print(_gerar_e_confirmar("persona_osteoporose.json").model_dump_json(indent=2))
