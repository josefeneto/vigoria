"""Comparação de fornecedores (motor/comparacao.py e --comparar), com provedores simulados."""

import contextlib
import io
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, SecretStr

from vigoria.config import Configuracao
from vigoria.llm.base import ErroLLM, Metricas, RespostaTeste
from vigoria.llm.simulado import ler_resposta_simulada
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario
from vigoria.motor import cli
from vigoria.motor.comparacao import avaliar_plano, comparar, formatar_comparacao
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import gerar_plano
from vigoria.motor.voz import aplicar_voz, textos_da_llm

RAIZ = Path(__file__).parent.parent
RESPOSTA = ler_resposta_simulada()


def _persona() -> tuple[Questionario, Estrategia]:
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text(encoding="utf-8"))
    q = Questionario.model_validate(dados)
    return q, gerar_estrategia(q)


class _Falso:
    """Fornecedor simulado, com métricas como as dos provedores reais."""

    def __init__(self, nome: str, resposta: str = RESPOSTA, erro: ErroLLM | None = None) -> None:
        self.nome = nome
        self.modelo = f"modelo-{nome}"
        self.resposta = resposta
        self.erro = erro
        self.ultimo_provedor: str | None = None
        self.ultimas_metricas: Metricas | None = None

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        if self.erro is not None:
            raise self.erro
        self.ultimo_provedor = self.nome
        self.ultimas_metricas = Metricas(
            provedor=self.nome,
            modelo=self.modelo,
            segundos=12.5,
            tentativas=1,
            tokens_entrada=9000,
            tokens_saida=4000,
        )
        return schema.model_validate_json(self.resposta)

    def testar_ligacao(self) -> RespostaTeste:
        return RespostaTeste(texto="ok")


def _resposta_com(extra: str) -> str:
    """A resposta de referência com texto acrescentado ao resumo."""
    dados = json.loads(RESPOSTA)
    dados["resumo"] += f" {extra}"
    return json.dumps(dados, ensure_ascii=False)


# ---------------------------------------------------------------- Avaliação


def test_plano_de_referencia_sem_problemas() -> None:
    q, e = _persona()
    plano = aplicar_voz(gerar_plano(q, e, _Falso("gemini")), e)
    a = avaliar_plano(plano, e, q, None)
    assert a.provedor == "gemini"
    assert a.falhas == ()
    assert a.mencoes_meses == 0
    assert a.palavras_desconhecidas == ()
    assert a.caracteres_texto > 1000


def test_deteta_falhas_meses_e_ortografia() -> None:
    q, e = _persona()
    resposta = _resposta_com("Em 3 meses, veja no celular. Evite o chá detox. A durquetura.")
    plano = aplicar_voz(gerar_plano(q, e, _Falso("mistral", resposta)), e)
    a = avaliar_plano(plano, e, q, None)
    assert a.mencoes_meses == 1
    assert set(a.falhas) == {"lista_negra"}  # «celular» foi corrigido pela voz
    assert a.palavras_desconhecidas == ("durquetura",)


def test_textos_sem_avisos_fixos() -> None:
    q, e = _persona()
    plano = gerar_plano(q, e, _Falso("gemini"))
    textos = "\n".join(textos_da_llm(plano))
    assert e.avisos[0] not in textos
    assert plano.marcos[0].forca_resistencia in textos


# ---------------------------------------------------------------- Comparação


def test_comparar_continua_depois_de_uma_falha() -> None:
    q, e = _persona()
    guardados: list[str] = []
    avaliacoes = comparar(
        q,
        e,
        [_Falso("gemini", erro=ErroLLM("O Gemini não respondeu em 120 s.")), _Falso("mistral")],
        lambda nome, plano: guardados.append(nome),
    )
    falha, ok = avaliacoes
    assert falha.erro == "O Gemini não respondeu em 120 s." and falha.modelo == "modelo-gemini"
    assert ok.erro is None and ok.tokens_entrada == 9000 and ok.segundos == 12.5
    assert guardados == ["mistral"]
    tabela = formatar_comparacao(avaliacoes)
    assert tabela.splitlines()[0].split() == ["|", "gemini", "|", "mistral"]
    assert "gemini falhou: O Gemini não respondeu" in tabela


def test_cli_comparar_guarda_planos(tmp_path: Path) -> None:
    q, e = _persona()
    config = Configuracao(
        _env_file=None,  # type: ignore[call-arg]  # nunca ler o .env nos testes
        gemini_api_key=SecretStr("g"),
        gemini_model="mg",
        mistral_api_key=SecretStr("m"),
        mistral_model="mm",
    )
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        codigo = cli.comparar_fornecedores(
            q,
            e,
            ["gemini", "mistral"],
            "persona_teste",
            config,
            lambda nome, c: _Falso(nome),  # type: ignore[arg-type, return-value]
            tmp_path,
        )
    assert codigo == 0
    for nome in ("gemini", "mistral"):
        ficheiro = tmp_path / f"persona_teste_{nome}.json"
        plano = Plano.model_validate_json(ficheiro.read_text("utf-8"))
        assert plano.provedor == nome
    texto = saida.getvalue()
    assert "COMPARAÇÃO - persona_teste" in texto
    assert "Tokens de entrada" in texto and "9000" in texto


def test_cli_comparar_fornecedor_desconhecido() -> None:
    with pytest.raises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
        cli.main(["--comparar", "gemini,openai", str(RAIZ / "exemplos" / "persona_teste.json")])
