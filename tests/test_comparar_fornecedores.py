"""scripts/comparar_fornecedores.py (Fase 10C), sem LLM real: fornecedores falsos."""

import importlib.util
from datetime import datetime
from pathlib import Path
from types import ModuleType

from pydantic import BaseModel

from vigoria.llm.base import ErroLLM
from vigoria.llm.simulado import ler_resposta_simulada

RAIZ = Path(__file__).resolve().parents[1]


def _script() -> ModuleType:
    caminho = RAIZ / "scripts" / "comparar_fornecedores.py"
    spec = importlib.util.spec_from_file_location("comparar_fornecedores", caminho)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _Falso:
    def __init__(self, nome: str, modelo: str, falha: bool = False) -> None:
        self.nome, self.modelo, self.falha = nome, modelo, falha
        self.ultimo_provedor: str | None = None

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        if self.falha:
            raise ErroLLM("O Groq recusou o pedido (código 429).", 429)
        self.ultimo_provedor = self.nome
        return schema.model_validate_json(ler_resposta_simulada())


def test_as_cinco_personas_existem() -> None:
    m = _script()
    assert len(m.PERSONAS) == 5 and all(p.is_file() for p in m.PERSONAS)


def test_tabela_com_uma_linha_por_persona_e_fornecedor() -> None:
    m = _script()
    esperas: list[float] = []
    provedores = [_Falso("gemini", "g"), _Falso("groq", "q120", falha=True)]
    resultados = m.correr(list(m.PERSONAS[:2]), provedores, pausa_s=5, dormir=esperas.append)
    assert esperas == [5]  # pausa só entre personas
    assert [(p, a.provedor) for p, a in resultados] == [
        ("teste", "gemini"),
        ("teste", "groq"),
        ("50_alta", "gemini"),
        ("50_alta", "groq"),
    ]
    texto = m.markdown(resultados, datetime(2026, 11, 12, 10, 0))
    assert "| teste | groq (q120) |" in texto
    assert "**groq (q120)**: 0/2 planos gerados" in texto
    assert "**gemini**: 2/2 planos gerados" in texto  # sem métricas, o falso não diz o modelo
    assert "código 429" in texto


def test_ctrl_c_guarda_as_personas_ja_completas() -> None:
    m = _script()

    def interromper(_: float) -> None:
        raise KeyboardInterrupt

    provedores = [_Falso("gemini", "g")]
    resultados = m.correr(list(m.PERSONAS[:3]), provedores, pausa_s=1, dormir=interromper)
    assert [p for p, _ in resultados] == ["teste"]
