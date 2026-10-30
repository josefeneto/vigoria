"""Pipeline (motor/pipeline.py), CLI --plano e Markdown, com a LLM simulada."""

import contextlib
import io
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from vigoria.llm.base import ErroLLM, RespostaTeste
from vigoria.modelos.plano import PlanoGerado
from vigoria.modelos.questionario import Questionario
from vigoria.motor import cli
from vigoria.motor.gerador import ErroGeracao, carregar_prompt_correcao
from vigoria.motor.pipeline import (
    MAX_CHAMADAS,
    ErroVerificacao,
    _ProvedorContado,
    gerar_plano_verificado,
)
from vigoria.regras import textos

RAIZ = Path(__file__).parent.parent
BOA = (RAIZ / "tests" / "fixtures" / "resposta_gerador_persona_teste.json").read_text("utf-8")


def _ma(extra: str = "Um chá detox ajuda.") -> str:
    dados = json.loads(BOA)
    dados["resumo"] += f" {extra}"
    dados["treino"]["fase_2"]["exercicios"][0]["exercicio_id"] = "burpee_turbo"
    return json.dumps(dados, ensure_ascii=False)


def _q(ficheiro: str = "persona_teste.json") -> Questionario:
    dados = json.loads((RAIZ / "exemplos" / ficheiro).read_text(encoding="utf-8"))
    return Questionario.model_validate(dados)


class _Sequencia:
    """Devolve as respostas pela ordem e guarda os pedidos recebidos."""

    nome = "falso"
    modelo = "modelo-falso"

    def __init__(self, *respostas: str) -> None:
        self.respostas = list(respostas)
        self.pedidos: list[str] = []
        self.ultimo_provedor: str | None = None

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        self.pedidos.append(pedido)
        self.ultimo_provedor = self.nome
        return schema.model_validate_json(self.respostas.pop(0))

    def testar_ligacao(self) -> RespostaTeste:
        return RespostaTeste(texto="ok")


def _correr(*respostas: str) -> tuple[object, _Sequencia, list[str]]:
    provedor = _Sequencia(*respostas)
    progresso: list[str] = []
    return gerar_plano_verificado(_q(), provedor, progresso.append), provedor, progresso


# ---------------------------------------------------------------- Pipeline


def test_aprovado_a_primeira() -> None:
    resultado, provedor, progresso = _correr(BOA)
    assert resultado.chamadas == 1  # type: ignore[attr-defined]
    assert resultado.motivos_regeneracao == ()  # type: ignore[attr-defined]
    plano = resultado.plano  # type: ignore[attr-defined]
    assert plano.avisos[:2] == (textos.AVISO_GERAL, textos.SINAIS_INTERROMPER)
    assert plano.provedor == "falso"
    assert progresso == ["verificação: aprovado à primeira"]


def test_regenera_uma_vez_com_os_motivos() -> None:
    resultado, provedor, progresso = _correr(_ma(), BOA)
    assert resultado.chamadas == 2  # type: ignore[attr-defined]
    motivos = resultado.motivos_regeneracao  # type: ignore[attr-defined]
    assert "Fase 2: «burpee_turbo» não existe na biblioteca." in motivos
    assert "O texto tem o termo proibido «detox»." in motivos
    primeiro, segundo = provedor.pedidos
    assert segundo.startswith(primeiro)
    assert "# Correção pedida" in segundo
    assert "- Fase 2: «burpee_turbo» não existe na biblioteca." in segundo
    assert "{motivos}" not in segundo
    plano = resultado.plano  # type: ignore[attr-defined]
    assert plano.versao_prompt == f"2 (correção {carregar_prompt_correcao().versao})"
    assert progresso[0] == (
        "verificação: 2 falha(s) (exercicio: 1, lista_negra: 1); uma regeneração com os motivos"
    )
    assert "detox" not in "\n".join(progresso)  # progresso só com metadados


def test_falha_duas_vezes_da_erro_claro() -> None:
    with pytest.raises(ErroVerificacao) as erro:
        _correr(_ma(), _ma("Registe no celular."))
    assert str(erro.value) == textos.PLANO_NAO_VERIFICADO
    assert "Não foi possível preparar um plano" in str(erro.value)
    assert "O texto tem o brasileirismo «celular»: use português europeu." in erro.value.motivos
    assert isinstance(erro.value, ErroGeracao)


def test_nunca_mais_de_3_chamadas() -> None:
    contado = _ProvedorContado(_Sequencia(*[BOA] * 5))
    for _ in range(MAX_CHAMADAS):
        contado.gerar_json("s", "p", PlanoGerado)
    with pytest.raises(ErroGeracao, match="Máximo de 3 chamadas"):
        contado.gerar_json("s", "p", PlanoGerado)
    assert MAX_CHAMADAS == 3


def test_sem_plano_possivel_nao_chama_a_llm() -> None:
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text(encoding="utf-8"))
    dados |= {"condicoes": ["gravidez"], "condicoes_controladas": {}}
    provedor = _Sequencia(BOA)
    with pytest.raises(ErroGeracao):
        gerar_plano_verificado(Questionario.model_validate(dados), provedor, lambda _: None)
    assert provedor.pedidos == []


def test_erro_da_llm_nao_regenera() -> None:
    class _Falha(_Sequencia):
        def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
            self.pedidos.append(pedido)
            raise ErroLLM("O Gemini não respondeu em 120 s.")

    provedor = _Falha()
    with pytest.raises(ErroLLM):
        gerar_plano_verificado(_q(), provedor, lambda _: None)
    assert len(provedor.pedidos) == 1


# ---------------------------------------------------------------- CLI --plano e Markdown


def _cli_plano(tmp_path: Path, *respostas: str) -> tuple[int, str]:
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(io.StringIO()):
        codigo = cli.gerar_plano_em_markdown(
            _q(), "persona_teste", _Sequencia(*respostas), tmp_path
        )
    return codigo, saida.getvalue()


def test_cli_plano_grava_markdown(tmp_path: Path) -> None:
    codigo, saida = _cli_plano(tmp_path, BOA)
    assert codigo == 0
    assert "Chamadas à LLM: 1" in saida
    md = (tmp_path / "plano_persona_teste.md").read_text(encoding="utf-8")
    assert md.startswith("# O seu plano Vigoria de 16 semanas\n")
    for titulo in ("## Marcos", "## Semana-tipo", "### Fase 1:", "## Alimentação", "## Avisos"):
        assert titulo in md
    assert "| Ponte de glúteos |" in md  # nome da biblioteca, não o id
    assert "| Segunda-feira |" in md
    assert "**Pequeno-almoço:**" in md
    assert textos.AVISO_GERAL in md and textos.SINAIS_INTERROMPER in md
    assert "Plano gerado com falso (prompt versão 2)." in md


def test_cli_plano_mostra_motivos_quando_falha(tmp_path: Path) -> None:
    codigo, saida = _cli_plano(tmp_path, _ma(), _ma())
    assert codigo == 1
    assert textos.PLANO_NAO_VERIFICADO in saida
    assert "  - Fase 2: «burpee_turbo» não existe na biblioteca." in saida
    assert not (tmp_path / "plano_persona_teste.md").exists()


def test_cli_plano_mostra_regeneracao(tmp_path: Path) -> None:
    codigo, saida = _cli_plano(tmp_path, _ma(), BOA)
    assert codigo == 0
    assert "Chamadas à LLM: 2" in saida
    assert "Regenerado uma vez" in saida


def test_cli_sem_opcao() -> None:
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        assert cli.main([str(RAIZ / "exemplos" / "persona_teste.json")]) == 2
    assert "--plano" in saida.getvalue()
