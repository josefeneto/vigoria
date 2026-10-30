"""Provedor Groq (llm/groq.py) com um transporte httpx simulado: nenhuma chamada real."""

import contextlib
import io
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from vigoria.config import Configuracao
from vigoria.llm.base import MAX_TENTATIVAS, PERGUNTA_TESTE, ErroLLM
from vigoria.llm.groq import ProvedorGroq
from vigoria.llm.openai_compat import schema_estrito
from vigoria.modelos.plano import PlanoGerado
from vigoria.motor import cli

RESPOSTA = (Path(__file__).parent / "fixtures" / "resposta_gerador_persona_teste.json").read_text(
    encoding="utf-8"
)
PEDIDO = "Pedido com dados de saúde: hipertensão controlada"
LIMITES = {
    "x-ratelimit-limit-tokens": "8000",
    "x-ratelimit-remaining-tokens": "7990",
    "x-ratelimit-limit-requests": "1000",
    "x-ratelimit-remaining-requests": "999",
}


def _ok(texto: str = RESPOSTA, cabecalhos: dict[str, str] | None = None) -> httpx.Response:
    corpo = {
        "choices": [{"message": {"role": "assistant", "content": texto}}],
        "usage": {"prompt_tokens": 1500, "completion_tokens": 900},
    }
    return httpx.Response(200, json=corpo, headers=cabecalhos or {})


def _erro(codigo: int, mensagem: str = "", retry_after: str | None = None) -> httpx.Response:
    corpo = {"error": {"message": f"{mensagem} {PEDIDO}", "type": "x", "code": "x"}}
    cabecalhos = {"retry-after": retry_after} if retry_after else {}
    return httpx.Response(codigo, json=corpo, headers=cabecalhos)


POR_MINUTO = "Rate limit reached for model `m` on tokens per minute (TPM): Limit 8000."
POR_DIA = "Rate limit reached for model `m` on tokens per day (TPD): Limit 200000."
PEDIDOS_DIA = "Rate limit reached for model `m` on requests per day (RPD): Limit 1000."


class _Registo:
    def __init__(self) -> None:
        self.pedidos: list[httpx.Request] = []
        self.esperas: list[float] = []
        self.progresso: list[str] = []


def _provedor(*respostas: httpx.Response | Exception) -> tuple[ProvedorGroq, _Registo]:
    fila = list(respostas)
    registo = _Registo()

    def responder(pedido: httpx.Request) -> httpx.Response:
        registo.pedidos.append(pedido)
        resposta = fila.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    client = httpx.Client(base_url=ProvedorGroq.url_base, transport=httpx.MockTransport(responder))
    provedor = ProvedorGroq(
        modelo="openai/gpt-oss-120b",
        client=client,
        dormir=registo.esperas.append,
        progresso=registo.progresso.append,
    )
    return provedor, registo


def _corpo(pedido: httpx.Request) -> dict[str, Any]:
    return json.loads(pedido.content)


# ---------------------------------------------------------------- Chamada normal


def test_resposta_valida_com_schema_estrito() -> None:
    provedor, registo = _provedor(_ok())
    assert isinstance(provedor.gerar_json("sistema", PEDIDO, PlanoGerado), PlanoGerado)
    (pedido,) = registo.pedidos
    assert pedido.url.path == "/openai/v1/chat/completions"
    corpo = _corpo(pedido)
    assert corpo["model"] == "openai/gpt-oss-120b"
    assert corpo["messages"] == [
        {"role": "system", "content": "sistema"},
        {"role": "user", "content": PEDIDO},
    ]
    formato = corpo["response_format"]
    assert formato["type"] == "json_schema"
    assert formato["json_schema"]["strict"] is True
    assert formato["json_schema"]["name"] == "PlanoGerado"
    assert pedido.extensions["timeout"]["read"] == 120
    assert provedor.ultimo_provedor == "groq"


def test_schema_estrito_sem_referencias_e_fechado() -> None:
    schema = schema_estrito(PlanoGerado)
    texto = json.dumps(schema)
    assert "$ref" not in texto and "$defs" not in texto

    def objetos(no: Any) -> list[dict[str, Any]]:
        if isinstance(no, list):
            return [o for x in no for o in objetos(x)]
        if not isinstance(no, dict):
            return []
        proprios = [no] if no.get("type") == "object" else []
        return proprios + [o for v in no.values() for o in objetos(v)]

    todos = objetos(schema)
    assert len(todos) >= 3  # PlanoGerado, MarcosForca e AjusteRefeicao
    for objeto in todos:
        assert objeto["additionalProperties"] is False
        assert objeto["required"] == list(objeto["properties"])


def test_progresso_so_com_metadados() -> None:
    provedor, registo = _provedor(_erro(429, POR_MINUTO, "3"), _ok())
    provedor.gerar_json("sistema", PEDIDO, PlanoGerado)
    inicio_1, espera, inicio_2, fim = registo.progresso
    assert inicio_1.startswith("groq: chamada iniciada (tentativa 1/3")
    assert "nova tentativa daqui a 3.0 s" in espera
    assert "tentativa 2/3" in inicio_2
    assert "1500 de entrada, 900 de saída" in fim
    tudo = "\n".join(registo.progresso)
    assert "hipertensão" not in tudo and "Este plano" not in tudo


# ---------------------------------------------------------------- Erros


def test_429_por_minuto_repete_com_retry_after() -> None:
    provedor, registo = _provedor(_erro(429, POR_MINUTO, "7"), _erro(429, POR_MINUTO), _ok())
    provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(registo.pedidos) == 3
    assert registo.esperas == [7.0, 4.0]


def test_429_por_minuto_desiste_sem_reserva() -> None:
    provedor, registo = _provedor(*[_erro(429, POR_MINUTO)] * 5)
    with pytest.raises(ErroLLM, match="por minuto") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(registo.pedidos) == MAX_TENTATIVAS
    assert not erro.value.permite_reserva


@pytest.mark.parametrize("mensagem", [POR_DIA, PEDIDOS_DIA])
def test_quota_diaria_nao_repete(mensagem: str) -> None:
    provedor, registo = _provedor(_erro(429, mensagem, "430"), _ok())
    with pytest.raises(ErroLLM, match="quota diária esgotada, tenta daqui a 8 min") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(registo.pedidos) == 1
    assert erro.value.permite_reserva
    assert "hipertensão" not in str(erro.value)


def test_quota_diaria_sem_retry_after() -> None:
    provedor, _ = _provedor(_erro(429, POR_DIA))
    with pytest.raises(ErroLLM, match="tenta mais tarde"):
        provedor.gerar_json("s", PEDIDO, PlanoGerado)


def test_413_pedido_demasiado_grande_permite_reserva() -> None:
    provedor, registo = _provedor(_erro(413, "Request too large"), _ok())
    with pytest.raises(ErroLLM, match="demasiado grande") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(registo.pedidos) == 1
    assert erro.value.codigo == 413
    assert erro.value.permite_reserva


@pytest.mark.parametrize("codigo", [503, 504])
def test_indisponivel_repete_e_no_fim_permite_reserva(codigo: int) -> None:
    provedor, registo = _provedor(*[_erro(codigo)] * 3)
    with pytest.raises(ErroLLM, match="indisponível") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(registo.pedidos) == 3
    assert registo.esperas == [2.0, 4.0]
    assert erro.value.permite_reserva


@pytest.mark.parametrize("codigo", [400, 401, 404, 500])
def test_outros_erros_nao_repetem_nem_reserva(codigo: int) -> None:
    provedor, registo = _provedor(_erro(codigo), _ok())
    with pytest.raises(ErroLLM, match=f"código {codigo}") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(registo.pedidos) == 1
    assert not erro.value.permite_reserva
    assert "hipertensão" not in str(erro.value)


def test_tempo_esgotado() -> None:
    provedor, registo = _provedor(httpx.ReadTimeout("x"), _ok())
    with pytest.raises(ErroLLM, match="O Groq não respondeu em 120 s") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(registo.pedidos) == 1
    assert erro.value.permite_reserva


def test_falha_de_rede_sem_reserva() -> None:
    provedor, _ = _provedor(httpx.ConnectError("x"))
    with pytest.raises(ErroLLM, match="Não foi possível ligar ao Groq") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert not erro.value.permite_reserva


def test_resposta_fora_do_schema() -> None:
    provedor, _ = _provedor(_ok('{"resumo": "Texto privado"}'))
    with pytest.raises(ErroLLM, match="A resposta do Groq não respeita") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert "Texto privado" not in str(erro.value)
    assert not erro.value.permite_reserva


def test_sem_modelo_ou_chave() -> None:
    sem_nada = Configuracao(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(ErroLLM, match="GROQ_MODEL"):
        ProvedorGroq(config=sem_nada)
    so_modelo = Configuracao(_env_file=None, groq_model="m")  # type: ignore[call-arg]
    with pytest.raises(ErroLLM, match="GROQ_API_KEY"):
        ProvedorGroq(config=so_modelo)


# ---------------------------------------------------------------- Testar ligação


def test_testar_ligacao_mostra_limites() -> None:
    provedor, registo = _provedor(_ok(" ok ", LIMITES))
    resposta = provedor.testar_ligacao()
    assert resposta.texto == "ok"
    assert resposta.limites[:4] == (
        "Tokens por minuto (limite): 8000",
        "Tokens por minuto (disponíveis agora): 7990",
        "Pedidos por dia (limite): 1000",
        "Pedidos por dia (disponíveis): 999",
    )
    assert "Tokens por dia" in resposta.limites[4]
    (pedido,) = registo.pedidos
    assert _corpo(pedido)["messages"] == [{"role": "user", "content": PERGUNTA_TESTE}]
    assert "response_format" not in _corpo(pedido)
    assert pedido.extensions["timeout"]["read"] == 30


def test_testar_ligacao_nao_repete() -> None:
    provedor, registo = _provedor(_erro(503), _ok())
    with pytest.raises(ErroLLM):
        provedor.testar_ligacao()
    assert len(registo.pedidos) == 1


def test_cli_testa_principal_e_reserva() -> None:
    config = Configuracao(
        _env_file=None,  # type: ignore[call-arg]  # nunca ler o .env nos testes
        vigoria_provedor_llm="gemini",
        vigoria_provedor_reserva="groq",
        gemini_api_key=SecretStr("chave-gemini-falsa"),
        gemini_model="modelo-gemini",
        groq_api_key=SecretStr("chave-groq-falsa"),
        groq_model="openai/gpt-oss-120b",
    )
    groq, _ = _provedor(_ok("ok", LIMITES))
    gemini, _ = _provedor(_erro(401))  # «gemini» simulado com o mesmo transporte

    def criar(nome: str, c: Configuracao) -> ProvedorGroq:
        return groq if nome == "groq" else gemini

    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        codigo = cli.testar_ligacao(config, criar)  # type: ignore[arg-type]
    texto = saida.getvalue()
    assert codigo == 1  # o principal falhou
    principal, reserva = texto.split("\n\n== groq (reserva) ==\n")
    assert principal.startswith("== gemini (principal) ==")
    assert "confirme o GEMINI_API_KEY" in principal
    assert "Modelo (GROQ_MODEL): openai/gpt-oss-120b" in reserva
    assert "Tokens por minuto (limite): 8000" in reserva
    assert "Pedidos por dia (limite): 1000" in reserva
    assert "a funcionar" in reserva
    assert "chave-groq-falsa" not in texto and "chave-gemini-falsa" not in texto
