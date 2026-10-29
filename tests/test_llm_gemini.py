"""Provedor Gemini (llm/gemini.py) com um cliente simulado: nenhuma chamada real."""

import contextlib
import io
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai import errors
from pydantic import SecretStr

from vigoria.config import Configuracao
from vigoria.llm.base import MAX_TENTATIVAS, PERGUNTA_TESTE, ErroLLM
from vigoria.llm.gemini import (
    QUOTA_DIARIA,
    ProvedorGemini,
    e_quota_diaria,
    espera_sugerida_s,
)
from vigoria.modelos.plano import PlanoGerado
from vigoria.motor import cli

RESPOSTA = (Path(__file__).parent / "fixtures" / "resposta_gerador_persona_teste.json").read_text(
    encoding="utf-8"
)
PEDIDO = "Pedido com dados de saúde: hipertensão controlada"


def _resposta(texto: str = RESPOSTA) -> SimpleNamespace:
    uso = SimpleNamespace(prompt_token_count=1200, candidates_token_count=800)
    return SimpleNamespace(text=texto, usage_metadata=uso)


def _erro(codigo: int, detalhes: list[dict[str, Any]] | None = None) -> errors.APIError:
    corpo = {"error": {"code": codigo, "message": f"{PEDIDO} (eco)", "status": "X"}}
    if detalhes is not None:
        corpo["error"]["details"] = detalhes
    return (errors.ClientError if codigo < 500 else errors.ServerError)(codigo, corpo)


def _quota(quota_id: str, atraso: str | None = None) -> errors.APIError:
    """429 como o Gemini o devolve: QuotaFailure e, às vezes, RetryInfo."""
    detalhes: list[dict[str, Any]] = [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaMetric": "generate_content", "quotaId": quota_id}],
        }
    ]
    if atraso is not None:
        detalhes.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": atraso})
    return _erro(429, detalhes)


POR_MINUTO = "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
POR_DIA = "GenerateRequestsPerDayPerProjectPerModel-FreeTier"


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


class _Registo:
    """Guarda as esperas pedidas ao tenacity e as linhas de progresso."""

    def __init__(self) -> None:
        self.esperas: list[float] = []
        self.progresso: list[str] = []


def _provedor(*respostas: Any) -> tuple[ProvedorGemini, _Modelos, _Registo]:
    modelos = _Modelos(list(respostas))
    registo = _Registo()
    provedor = ProvedorGemini(
        modelo="modelo-de-teste",
        client=SimpleNamespace(models=modelos),
        dormir=registo.esperas.append,
        progresso=registo.progresso.append,
    )
    return provedor, modelos, registo


# ---------------------------------------------------------------- Chamada normal


def test_resposta_valida() -> None:
    provedor, modelos, _ = _provedor(_resposta())
    plano = provedor.gerar_json("sistema", PEDIDO, PlanoGerado)
    assert isinstance(plano, PlanoGerado)
    (chamada,) = modelos.chamadas
    assert chamada["model"] == "modelo-de-teste"
    assert chamada["contents"] == PEDIDO
    config = chamada["config"]
    assert config.system_instruction == "sistema"
    assert config.response_mime_type == "application/json"
    assert config.response_schema is PlanoGerado
    assert config.http_options.timeout == 120_000  # milissegundos


def test_regista_so_metricas(caplog: pytest.LogCaptureFixture) -> None:
    provedor, _, _ = _provedor(_resposta())
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


def test_progresso_so_com_metadados() -> None:
    provedor, _, registo = _provedor(_quota(POR_MINUTO), _resposta())
    provedor.gerar_json("sistema", PEDIDO, PlanoGerado)
    inicio_1, espera, inicio_2, fim = registo.progresso
    assert "chamada iniciada (tentativa 1/3" in inicio_1
    assert "tempo máximo 120 s" in inicio_1
    assert "429" in espera and "nova tentativa daqui a 2.0 s" in espera
    assert "tentativa 2/3" in inicio_2
    assert "chamada concluída" in fim and "tentativa 2" in fim
    assert "1200 de entrada, 800 de saída" in fim
    tudo = "\n".join(registo.progresso)
    assert "hipertensão" not in tudo and "sistema" not in tudo
    assert "Este plano" not in tudo


def test_progresso_vai_para_stderr() -> None:
    modelos = _Modelos([_resposta()])
    provedor = ProvedorGemini(modelo="m", client=SimpleNamespace(models=modelos))
    erro, saida = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(erro), contextlib.redirect_stdout(saida):
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert "[vigoria.llm] gemini: chamada iniciada" in erro.getvalue()
    assert saida.getvalue() == ""


# ---------------------------------------------------------------- Tempo máximo e rede


def test_tempo_esgotado_da_erro_claro_sem_repetir() -> None:
    provedor, modelos, registo = _provedor(httpx.ReadTimeout("x"), _resposta())
    with pytest.raises(ErroLLM, match="não respondeu em 120 s") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert erro.value.codigo is None
    assert len(modelos.chamadas) == 1
    assert "sem resposta" in registo.progresso[-1]


def test_falha_de_rede() -> None:
    provedor, _, _ = _provedor(httpx.ConnectError("x"))
    with pytest.raises(ErroLLM, match="Não foi possível ligar"):
        provedor.gerar_json("s", PEDIDO, PlanoGerado)


def test_timeout_configuravel() -> None:
    modelos = _Modelos([_resposta()])
    provedor = ProvedorGemini(
        modelo="m", client=SimpleNamespace(models=modelos), timeout_s=5, progresso=print
    )
    provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert modelos.chamadas[0]["config"].http_options.timeout == 5_000


# ---------------------------------------------------------------- Erro 429


def test_classificacao_do_429() -> None:
    assert e_quota_diaria(_quota(POR_DIA))
    assert not e_quota_diaria(_quota(POR_MINUTO))
    assert not e_quota_diaria(_erro(429))  # sem detalhes: tratado como por minuto
    assert not e_quota_diaria(_erro(500))
    assert espera_sugerida_s(_quota(POR_MINUTO, "39s")) == 39.0
    assert espera_sugerida_s(_quota(POR_MINUTO, "1.5s")) == 1.5
    assert espera_sugerida_s(_quota(POR_MINUTO)) is None


def test_429_por_minuto_repete_e_recupera() -> None:
    provedor, modelos, registo = _provedor(_quota(POR_MINUTO), _erro(429), _resposta())
    assert isinstance(provedor.gerar_json("s", PEDIDO, PlanoGerado), PlanoGerado)
    assert len(modelos.chamadas) == 3
    assert registo.esperas == [2.0, 4.0]  # exponencial


def test_429_usa_a_espera_sugerida_ate_60_s() -> None:
    provedor, _, registo = _provedor(
        _quota(POR_MINUTO, "39s"), _quota(POR_MINUTO, "300s"), _resposta()
    )
    provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert registo.esperas == [39.0, 60.0]


def test_429_por_minuto_desiste_ao_fim_de_3_tentativas() -> None:
    provedor, modelos, registo = _provedor(*[_quota(POR_MINUTO)] * 5)
    with pytest.raises(ErroLLM, match="por minuto") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert erro.value.codigo == 429
    assert len(modelos.chamadas) == MAX_TENTATIVAS == 3
    assert len(registo.esperas) == 2


def test_quota_diaria_nao_repete() -> None:
    provedor, modelos, registo = _provedor(_quota(POR_DIA, "39s"), _resposta())
    with pytest.raises(ErroLLM) as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert QUOTA_DIARIA == "quota diária esgotada, tenta depois das 8h00"
    assert QUOTA_DIARIA in str(erro.value)
    assert erro.value.permite_reserva
    assert len(modelos.chamadas) == 1
    assert registo.esperas == []


@pytest.mark.parametrize("codigo", [503, 504])
def test_indisponivel_repete_e_recupera(codigo: int) -> None:
    provedor, modelos, registo = _provedor(_erro(codigo), _resposta())
    assert isinstance(provedor.gerar_json("s", PEDIDO, PlanoGerado), PlanoGerado)
    assert len(modelos.chamadas) == 2
    assert registo.esperas == [2.0]
    assert f"serviço indisponível ({codigo})" in registo.progresso[1]


def test_indisponivel_desiste_e_permite_reserva() -> None:
    provedor, modelos, _ = _provedor(*[_erro(503)] * 5)
    with pytest.raises(ErroLLM, match="indisponível") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(modelos.chamadas) == MAX_TENTATIVAS
    assert erro.value.codigo == 503
    assert erro.value.permite_reserva


def test_429_por_minuto_nao_permite_reserva() -> None:
    provedor, _, _ = _provedor(*[_quota(POR_MINUTO)] * 3)
    with pytest.raises(ErroLLM) as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert not erro.value.permite_reserva


def test_tempo_esgotado_permite_reserva() -> None:
    provedor, _, _ = _provedor(httpx.ReadTimeout("x"))
    with pytest.raises(ErroLLM) as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert erro.value.permite_reserva


@pytest.mark.parametrize("codigo", [400, 403, 404, 500])
def test_outros_erros_nao_repetem(codigo: int) -> None:
    provedor, modelos, _ = _provedor(_erro(codigo), _resposta())
    with pytest.raises(ErroLLM, match=f"código {codigo}") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert len(modelos.chamadas) == 1
    assert erro.value.codigo == codigo
    assert not erro.value.permite_reserva
    assert "hipertensão" not in str(erro.value)  # a mensagem do serviço não passa
    assert erro.value.__cause__ is None


# ---------------------------------------------------------------- Formato


def test_resposta_fora_do_schema() -> None:
    provedor, _, _ = _provedor(_resposta('{"resumo": "Texto privado"}'))
    with pytest.raises(ErroLLM, match="formato") as erro:
        provedor.gerar_json("s", PEDIDO, PlanoGerado)
    assert "Texto privado" not in str(erro.value)
    assert erro.value.__cause__ is None


def test_resposta_vazia() -> None:
    provedor, _, _ = _provedor(_resposta(""))
    with pytest.raises(ErroLLM, match="formato"):
        provedor.gerar_json("s", PEDIDO, PlanoGerado)


def test_sem_modelo_da_erro() -> None:
    with pytest.raises(ErroLLM, match="GEMINI_MODEL"):
        ProvedorGemini(modelo="", client=SimpleNamespace())


# ---------------------------------------------------------------- Testar ligação


def test_testar_ligacao_pergunta_minima_com_30_s() -> None:
    provedor, modelos, _ = _provedor(_resposta(" ok \n"))
    assert provedor.testar_ligacao().texto == "ok"
    (chamada,) = modelos.chamadas
    assert chamada["contents"] == PERGUNTA_TESTE == "Responde só: ok"
    assert chamada["config"].http_options.timeout == 30_000
    assert chamada["config"].response_schema is None


def test_testar_ligacao_nao_repete_429() -> None:
    provedor, modelos, _ = _provedor(_quota(POR_MINUTO), _resposta("ok"))
    with pytest.raises(ErroLLM):
        provedor.testar_ligacao()
    assert len(modelos.chamadas) == 1


def _config(chave: str | None = "chave-falsa", modelo: str = "modelo-x") -> Configuracao:
    return Configuracao(
        _env_file=None,  # type: ignore[call-arg]  # nunca ler o .env nos testes
        gemini_api_key=SecretStr(chave) if chave else None,
        gemini_model=modelo,
    )


def _cli_testar(config: Configuracao, *respostas: Any) -> tuple[int, str]:
    provedor, _, _ = _provedor(*respostas)
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        codigo = cli.testar_ligacao(config, lambda nome, c: provedor)
    return codigo, saida.getvalue()


def test_cli_testar_ligacao_ok() -> None:
    codigo, saida = _cli_testar(_config(), _resposta("ok"))
    assert codigo == 0
    assert saida.startswith("== gemini (principal) ==")
    assert "Chave (GEMINI_API_KEY): definida" in saida
    assert "Modelo (GEMINI_MODEL): modelo-x" in saida
    assert "a funcionar" in saida
    assert "chave-falsa" not in saida  # a chave nunca aparece


def test_cli_testar_ligacao_sem_chave() -> None:
    codigo, saida = _cli_testar(_config(chave=None))
    assert codigo == 1
    assert "em falta" in saida


@pytest.mark.parametrize(
    ("falha", "diagnostico"),
    [
        (_erro(400), "a chave foi recusada"),
        (_erro(404), "o modelo «modelo-x» não existe"),
        (_quota(POR_DIA), "quota está esgotada"),
        (httpx.ReadTimeout("x"), "rede ou tempo esgotado"),
    ],
)
def test_cli_testar_ligacao_diagnostico(falha: BaseException, diagnostico: str) -> None:
    codigo, saida = _cli_testar(_config(), falha)
    assert codigo == 1
    assert diagnostico in saida


def test_cli_sem_questionario_nem_teste() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--so-estrategia"])
