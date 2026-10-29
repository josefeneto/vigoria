"""Provedor Gemini (llm/gemini.py) com um cliente simulado: nenhuma chamada real."""

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors
from tenacity import wait_none

from vigoria.llm.base import ErroLLM
from vigoria.llm.gemini import MAX_TENTATIVAS, ProvedorGemini
from vigoria.modelos.plano import PlanoGerado

RESPOSTA = (Path(__file__).parent / "fixtures" / "resposta_gerador_persona_teste.json").read_text(
    encoding="utf-8"
)
PEDIDO = "Pedido com dados de saúde: hipertensão controlada"


def _resposta(texto: str = RESPOSTA) -> SimpleNamespace:
    uso = SimpleNamespace(prompt_token_count=1200, candidates_token_count=800)
    return SimpleNamespace(text=texto, usage_metadata=uso)


def _erro(codigo: int) -> errors.APIError:
    corpo = {"error": {"code": codigo, "message": f"{PEDIDO} (eco)", "status": "X"}}
    return (errors.ClientError if codigo < 500 else errors.ServerError)(codigo, corpo)


class _Modelos:
    def __init__(self, respostas: list[Any]) -> None:
        self.respostas = respostas
        self.chamadas: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.chamadas.append(kwargs)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, BaseException):
            raise resposta
        return resposta


def _provedor(*respostas: Any) -> tuple[ProvedorGemini, _Modelos]:
    modelos = _Modelos(list(respostas))
    cliente = SimpleNamespace(models=modelos)
    return ProvedorGemini(modelo="modelo-de-teste", client=cliente, espera=wait_none()), modelos


def test_resposta_valida() -> None:
    provedor, modelos = _provedor(_resposta())
    plano = provedor.gerar_json("sistema", PEDIDO, PlanoGerado)
    assert isinstance(plano, PlanoGerado)
    (chamada,) = modelos.chamadas
    assert chamada["model"] == "modelo-de-teste"
    assert chamada["contents"] == PEDIDO
    config = chamada["config"]
    assert config.system_instruction == "sistema"
    assert config.response_mime_type == "application/json"
    assert config.response_schema is PlanoGerado


def test_regista_so_metricas(caplog: pytest.LogCaptureFixture) -> None:
    provedor, _ = _provedor(_resposta())
    with caplog.at_level(logging.INFO, logger="vigoria.llm"):
        provedor.gerar_json("sistema", PEDIDO, PlanoGerado)
    (registo,) = caplog.records
    metricas = registo.metricas  # type: ignore[attr-defined]
    assert metricas["tokens_entrada"] == 1200
    assert metricas["tokens_saida"] == 800
    assert metricas["tentativas"] == 1
    assert metricas["modelo"] == "modelo-de-teste"
    assert metricas["segundos"] >= 0
    texto = repr(registo.__dict__)
    assert "hipertensão" not in texto
    assert "Este plano de 16 semanas" not in texto


def test_429_repete_e_recupera() -> None:
    provedor, modelos = _provedor(_erro(429), _erro(429), _resposta())
    assert isinstance(provedor.gerar_json("s", PEDIDO, PlanoGerado), PlanoGerado)
    assert len(modelos.chamadas) == 3


def test_429_desiste_ao_fim_de_3_tentativas() -> None:
    provedor, modelos = _provedor(*[_erro(429)] * 5)
    with pytest.raises(ErroLLM, match="429"):
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(modelos.chamadas) == MAX_TENTATIVAS == 3


@pytest.mark.parametrize("codigo", [400, 403, 500, 503])
def test_outros_erros_nao_repetem(codigo: int) -> None:
    provedor, modelos = _provedor(_erro(codigo), _resposta())
    with pytest.raises(ErroLLM, match=f"código {codigo}") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(modelos.chamadas) == 1
    assert "hipertensão" not in str(erro.value)  # a mensagem do serviço não passa
    assert erro.value.__cause__ is None


def test_resposta_fora_do_schema() -> None:
    provedor, _ = _provedor(_resposta('{"resumo": "Texto privado"}'))
    with pytest.raises(ErroLLM, match="formato") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert "Texto privado" not in str(erro.value)
    assert erro.value.__cause__ is None


def test_resposta_vazia() -> None:
    provedor, _ = _provedor(_resposta(""))
    with pytest.raises(ErroLLM, match="formato"):
        provedor.gerar_json("s", PEDIDO, PlanoGerado)


def test_sem_modelo_da_erro() -> None:
    with pytest.raises(ErroLLM, match="GEMINI_MODEL"):
        ProvedorGemini(modelo="", client=SimpleNamespace())
