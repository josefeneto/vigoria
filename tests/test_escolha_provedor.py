"""Escolha do fornecedor e uso da reserva (llm/escolha.py), com provedores simulados."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, SecretStr, ValidationError

from vigoria.config import Configuracao
from vigoria.llm.base import ErroLLM, RespostaTeste
from vigoria.llm.escolha import ProvedorComReserva, criar_provedor
from vigoria.llm.gemini import ProvedorGemini
from vigoria.llm.groq import ProvedorGroq
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import gerar_plano

RAIZ = Path(__file__).parent.parent
RESPOSTA = (RAIZ / "tests" / "fixtures" / "resposta_gerador_persona_teste.json").read_text(
    encoding="utf-8"
)


class _Falso:
    """Fornecedor simulado: devolve RESPOSTA ou levanta o erro indicado."""

    modelo = "modelo-falso"

    def __init__(self, nome: str, erro: ErroLLM | None = None) -> None:
        self.nome = nome
        self.erro = erro
        self.chamadas = 0
        self.ultimo_provedor: str | None = None

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        self.chamadas += 1
        if self.erro is not None:
            raise self.erro
        self.ultimo_provedor = self.nome
        return schema.model_validate_json(RESPOSTA)

    def testar_ligacao(self) -> RespostaTeste:
        return RespostaTeste(texto="ok")


def _par(
    erro: ErroLLM | None, erro_reserva: ErroLLM | None = None
) -> tuple[ProvedorComReserva, _Falso, _Falso, list[str]]:
    principal, reserva = _Falso("gemini", erro), _Falso("groq", erro_reserva)
    progresso: list[str] = []
    return ProvedorComReserva(principal, reserva, progresso.append), principal, reserva, progresso


def _plano(provedor: ProvedorComReserva) -> str:
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text(encoding="utf-8"))
    q = Questionario.model_validate(dados)
    return gerar_plano(q, gerar_estrategia(q), provedor).provedor


# ---------------------------------------------------------------- Troca de fornecedor


def test_principal_responde_sem_reserva() -> None:
    provedor, principal, reserva, progresso = _par(None)
    assert _plano(provedor) == "gemini"
    assert (principal.chamadas, reserva.chamadas) == (1, 0)
    assert progresso == ["resposta gerada por: gemini (modelo modelo-falso)"]


@pytest.mark.parametrize(
    "erro",
    [
        ErroLLM("indisponível depois das repetições", 503, permite_reserva=True),
        ErroLLM("indisponível depois das repetições", 504, permite_reserva=True),
        ErroLLM("não respondeu em 120 s", None, permite_reserva=True),
        ErroLLM("quota diária esgotada", 429, permite_reserva=True),
        ErroLLM("pedido demasiado grande", 413, permite_reserva=True),
    ],
)
def test_falha_definitiva_usa_reserva(erro: ErroLLM) -> None:
    provedor, principal, reserva, progresso = _par(erro)
    assert _plano(provedor) == "groq"
    assert (principal.chamadas, reserva.chamadas) == (1, 1)
    assert provedor.ultimo_provedor == "groq"
    assert "a usar a reserva groq" in progresso[0]
    assert progresso[-1] == "resposta gerada por: groq (modelo modelo-falso)"


@pytest.mark.parametrize(
    "erro",
    [
        ErroLLM("429 por minuto, 3 tentativas", 429),
        ErroLLM("formato inválido"),
        ErroLLM("chave recusada", 401),
        ErroLLM("sem rede"),
    ],
)
def test_outras_falhas_nao_usam_reserva(erro: ErroLLM) -> None:
    provedor, _, reserva, _ = _par(erro)
    with pytest.raises(ErroLLM) as levantado:
        _plano(provedor)
    assert levantado.value is erro
    assert reserva.chamadas == 0


def test_sem_reserva_configurada_levanta_o_erro() -> None:
    erro = ErroLLM("quota diária esgotada", 429, permite_reserva=True)
    provedor = ProvedorComReserva(_Falso("gemini", erro), None, lambda _: None)
    with pytest.raises(ErroLLM) as levantado:
        _plano(provedor)
    assert levantado.value is erro


def test_reserva_tambem_falha() -> None:
    provedor, _, _, _ = _par(
        ErroLLM("O Gemini não respondeu.", permite_reserva=True),
        ErroLLM("O Groq recusou.", 413, permite_reserva=True),
    )
    with pytest.raises(ErroLLM, match="O Gemini não respondeu. A reserva \\(groq\\)") as erro:
        _plano(provedor)
    assert "O Groq recusou." in str(erro.value)
    assert erro.value.codigo == 413
    assert not erro.value.permite_reserva


# ---------------------------------------------------------------- Configuração


def _config(**valores: object) -> Configuracao:
    base: dict[str, object] = {
        "gemini_api_key": SecretStr("g"),
        "gemini_model": "modelo-gemini",
        "groq_api_key": SecretStr("q"),
        "groq_model": "modelo-groq",
    }
    return Configuracao(_env_file=None, **(base | valores))  # type: ignore[call-arg, arg-type]


def test_por_omissao_gemini_sem_reserva() -> None:
    provedor = criar_provedor(_config())
    assert isinstance(provedor.principal, ProvedorGemini)
    assert provedor.reserva is None
    assert provedor.nome == "gemini" and provedor.modelo == "modelo-gemini"


def test_groq_principal_e_gemini_reserva() -> None:
    config = _config(vigoria_provedor_llm="groq", vigoria_provedor_reserva="gemini")
    provedor = criar_provedor(config)
    assert isinstance(provedor.principal, ProvedorGroq)
    assert isinstance(provedor.reserva, ProvedorGemini)
    assert provedor.principal.modelo == "modelo-groq"


def test_reserva_vazia_e_none() -> None:
    assert _config(vigoria_provedor_reserva="").vigoria_provedor_reserva is None


def test_reserva_igual_ao_principal_e_recusada() -> None:
    with pytest.raises(ValidationError, match="diferente"):
        _config(vigoria_provedor_llm="groq", vigoria_provedor_reserva="groq")


def test_fornecedor_desconhecido_e_recusado() -> None:
    with pytest.raises(ValidationError):
        _config(vigoria_provedor_llm="outro")


def test_variaveis_de_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "groq")
    monkeypatch.setenv("VIGORIA_PROVEDOR_RESERVA", "gemini")
    config = Configuracao(_env_file=None)  # type: ignore[call-arg]
    assert (config.vigoria_provedor_llm, config.vigoria_provedor_reserva) == ("groq", "gemini")
