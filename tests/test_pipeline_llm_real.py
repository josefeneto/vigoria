"""Pipeline completo com a LLM real. Só corre com VIGORIA_TESTES_LLM_REAIS=1 (só o José).

Uma ou duas chamadas (geração e, se a verificação falhar, uma regeneração); 300 s no
máximo (conftest.py). É o único teste real com «persona» no nome: «-k persona» corre só este.

PowerShell (o -s mostra o progresso):
    $env:VIGORIA_TESTES_LLM_REAIS = "1"; python -m pytest -m llm -k persona -s
"""

import json
from pathlib import Path

import pytest

from vigoria.exportacao.markdown import plano_para_markdown
from vigoria.llm.escolha import criar_provedor
from vigoria.modelos.questionario import Questionario
from vigoria.motor.pipeline import gerar_plano_verificado
from vigoria.motor.verificacao import verificar
from vigoria.motor.voz import textos_obrigatorios

RAIZ = Path(__file__).parent.parent


@pytest.mark.llm
def test_pipeline_real_persona() -> None:
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text(encoding="utf-8"))
    q = Questionario.model_validate(dados)
    resultado = gerar_plano_verificado(q, criar_provedor())

    plano, e = resultado.plano, resultado.estrategia
    assert resultado.chamadas <= 2
    assert verificar(plano, e, q) == []
    assert plano.avisos[:2] == textos_obrigatorios()
    print(f"\nFornecedor: {plano.provedor} | chamadas: {resultado.chamadas}")
    print("Motivos da regeneração:", resultado.motivos_regeneracao or "nenhum")
    print(plano_para_markdown(plano))
