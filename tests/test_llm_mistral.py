"""Provedor Mistral (llm/mistral.py) com um transporte httpx simulado: nenhuma chamada real."""

import json

import httpx
import pytest
from pydantic import SecretStr

from vigoria.config import Configuracao
from vigoria.llm.base import ErroLLM
from vigoria.llm.escolha import criar_provedor
from vigoria.llm.mistral import ProvedorMistral
from vigoria.llm.simulado import ler_resposta_simulada
from vigoria.modelos.plano import PlanoGerado

RESPOSTA = ler_resposta_simulada()


def _provedor(resposta: httpx.Response) -> tuple[ProvedorMistral, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return resposta

    client = httpx.Client(
        base_url=ProvedorMistral.url_base, transport=httpx.MockTransport(responder)
    )
    provedor = ProvedorMistral(
        modelo="mistral-medium-latest", client=client, dormir=lambda _: None, progresso=print
    )
    return provedor, pedidos


def _ok(texto: str, cabecalhos: dict[str, str] | None = None) -> httpx.Response:
    corpo = {
        "choices": [{"message": {"content": texto}}],
        "usage": {"prompt_tokens": 9000, "completion_tokens": 4000},
    }
    return httpx.Response(200, json=corpo, headers=cabecalhos or {})


def test_endereco_europeu_e_schema_estrito() -> None:
    provedor, pedidos = _provedor(_ok(RESPOSTA))
    assert isinstance(provedor.gerar_json("s", "pedido", PlanoGerado), PlanoGerado)
    (pedido,) = pedidos
    assert str(pedido.url) == "https://api.eu.mistral.ai/v1/chat/completions"
    corpo = json.loads(pedido.content)
    assert corpo["model"] == "mistral-medium-latest"
    assert corpo["response_format"]["json_schema"]["strict"] is True
    assert provedor.ultimas_metricas is not None
    assert provedor.ultimas_metricas.tokens_entrada == 9000
    assert provedor.ultimo_provedor == "mistral"


def test_limites_mostra_cabecalhos_ratelimit() -> None:
    cabecalhos = {
        "x-ratelimit-limit-tokens-minute": "500000",
        "x-ratelimit-remaining-tokens-month": "999000000",
        "content-type": "application/json",
    }
    provedor, _ = _provedor(_ok("ok", cabecalhos))
    resposta = provedor.testar_ligacao()
    assert resposta.texto == "ok"
    assert resposta.limites == (
        "x-ratelimit-limit-tokens-minute: 500000",
        "x-ratelimit-remaining-tokens-month: 999000000",
    )


def test_limites_sem_cabecalhos() -> None:
    provedor, _ = _provedor(_ok("ok"))
    assert "não trouxe" in provedor.testar_ligacao().limites[0]


def test_erros_seguem_a_logica_comum() -> None:
    provedor, _ = _provedor(httpx.Response(401, json={"message": "Unauthorized"}))
    with pytest.raises(ErroLLM, match="O Mistral devolveu um erro \\(código 401\\)"):
        provedor.gerar_json("s", "pedido", PlanoGerado)


def test_configuracao_e_escolha() -> None:
    config = Configuracao(
        _env_file=None,  # type: ignore[call-arg]  # nunca ler o .env nos testes
        vigoria_provedor_llm="mistral",
        vigoria_provedor_reserva="gemini",
        mistral_api_key=SecretStr("m"),
        mistral_model="mistral-medium-latest",
        gemini_api_key=SecretStr("g"),
        gemini_model="modelo-gemini",
    )
    provedor = criar_provedor(config)
    assert isinstance(provedor.principal, ProvedorMistral)
    assert provedor.modelo == "mistral-medium-latest"


def test_sem_chave() -> None:
    config = Configuracao(_env_file=None, mistral_model="m")  # type: ignore[call-arg]
    with pytest.raises(ErroLLM, match="MISTRAL_API_KEY"):
        ProvedorMistral(config=config)
