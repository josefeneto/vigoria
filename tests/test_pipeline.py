"""Pipeline (motor/pipeline.py), CLI --plano e Markdown, com a LLM simulada."""

import contextlib
import io
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from vigoria.llm.base import ErroLLM, RespostaTeste
from vigoria.llm.escolha import ProvedorComReserva
from vigoria.llm.simulado import ler_resposta_simulada
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
from vigoria.motor.verificacao import TipoFalha
from vigoria.regras import textos

RAIZ = Path(__file__).parent.parent
BOA = ler_resposta_simulada()


CINCO_KG = (
    "O texto tem o valor «5 kg»: valores de peso, proteína, hidratação e calorias vêm só "
    "da estratégia (pesos de halteres permitidos: 2 kg)."
)


def _ma(extra: str = "Um chá detox ajuda.") -> str:
    """Resposta com falhas do texto da LLM: halteres de 5 kg (a persona tem 2) e `extra`."""
    dados = json.loads(BOA)
    dados["resumo"] += f" {extra}"
    dados["marcos_forca"]["semana_8"] = "Fazer a remada com halteres de 5 kg."
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
    assert CINCO_KG in motivos
    assert "O texto tem o termo proibido «detox»." in motivos
    primeiro, segundo = provedor.pedidos
    assert segundo.startswith(primeiro)
    assert "# Correção pedida" in segundo
    assert f"- {CINCO_KG}" in segundo
    assert "{motivos}" not in segundo
    plano = resultado.plano  # type: ignore[attr-defined]
    assert plano.versao_prompt == f"7 (correção {carregar_prompt_correcao().versao})"
    assert progresso[0] == (
        "verificação: 2 falha(s) (numero_no_texto: 1, lista_negra: 1); uma regeneração com os "
        "motivos"
    )
    assert "detox" not in "\n".join(progresso)  # progresso só com metadados


def test_falha_duas_vezes_da_erro_claro() -> None:
    with pytest.raises(ErroVerificacao) as erro:
        _correr(_ma(), _ma("Garantimos resultados."))
    assert str(erro.value) == textos.PLANO_NAO_VERIFICADO
    assert "Não foi possível preparar um plano" in str(erro.value)
    assert any("«garantimos»" in m for m in erro.value.motivos)
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
    assert "Plano gerado com falso (prompt versão 7)." in md


def test_cli_plano_mostra_motivos_quando_falha(tmp_path: Path) -> None:
    codigo, saida = _cli_plano(tmp_path, _ma(), _ma())
    assert codigo == 1
    assert textos.PLANO_NAO_VERIFICADO in saida
    assert f"  - {CINCO_KG}" in saida
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


def test_markdown_com_esforco_e_estrutura_da_sessao_dos_yaml(tmp_path: Path) -> None:
    _cli_plano(tmp_path, BOA)
    md = (tmp_path / "plano_persona_teste.md").read_text(encoding="utf-8")
    assert "### Como é cada sessão" in md
    for parte in ("**Aquecimento:**", "**Bloco principal:**", "**Cardio finalizador:**"):
        assert parte in md
    assert "**Retorno à calma:** Retorno à Calma (5 min)" in md  # texto de fases.yaml
    assert md.count("Esforço percebido: 3 a 6, numa escala de 0 a 10.") == 4  # uma por fase


def test_ortografia_so_avisa(tmp_path: Path) -> None:
    dados = json.loads(BOA)
    dados["resumo"] += " Mantenha a durquetura."
    resposta = json.dumps(dados, ensure_ascii=False)
    resultado, _, progresso = _correr(resposta)
    assert resultado.chamadas == 1  # type: ignore[attr-defined]
    assert resultado.palavras_desconhecidas == ("durquetura",)  # type: ignore[attr-defined]
    assert progresso[-1] == "ortografia: 1 palavra(s) desconhecida(s) (só aviso)"
    codigo, saida = _cli_plano(tmp_path, resposta)
    assert codigo == 0
    assert "Ortografia (só aviso)" in saida and "durquetura" in saida


def test_falha_do_motor_nao_regenera(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um erro no que o código monta não se corrige a pedir outro texto à LLM."""
    from vigoria.motor import pipeline

    falha = pipeline.Falha(tipo=TipoFalha.EXERCICIO, motivo="Erro.")
    monkeypatch.setattr(pipeline, "verificar", lambda plano, e, q: [falha])
    provedor = _Sequencia(BOA, BOA)
    with pytest.raises(pipeline.ErroMotor) as erro:
        gerar_plano_verificado(_q(), provedor, lambda _: None)
    assert erro.value.motivos == ("Erro.",)
    assert len(provedor.pedidos) == 1


# ---------------------------------------------------------------- Reserva na verificação


def _com_reserva(
    principal: _Sequencia, reserva: _Sequencia
) -> tuple[ProvedorComReserva, list[str]]:
    progresso: list[str] = []
    return ProvedorComReserva(principal, reserva, lambda _: None), progresso


def test_terceira_chamada_vai_para_a_reserva() -> None:
    principal, reserva = _Sequencia(_ma(), _ma()), _Sequencia(BOA)
    reserva.nome = "groq"
    provedor, progresso = _com_reserva(principal, reserva)
    resultado = gerar_plano_verificado(_q(), provedor, progresso.append)
    assert resultado.chamadas == 3
    assert resultado.reserva_na_verificacao
    assert resultado.plano.provedor == "groq"
    assert (len(principal.pedidos), len(reserva.pedidos)) == (2, 1)
    assert "# Correção pedida" in reserva.pedidos[0]  # leva os motivos da 2.ª verificação
    assert "terceira chamada para a reserva groq" in progresso[1]
    assert progresso[2] == "verificação: aprovado na reserva"


def test_reserva_tambem_falha_e_recusa() -> None:
    principal, reserva = _Sequencia(_ma(), _ma()), _Sequencia(_ma())
    provedor, _ = _com_reserva(principal, reserva)
    with pytest.raises(ErroVerificacao):
        gerar_plano_verificado(_q(), provedor, lambda _: None)
    assert (len(principal.pedidos), len(reserva.pedidos)) == (2, 1)  # 3 chamadas no total


def test_sem_reserva_recusa_depois_de_2_chamadas() -> None:
    principal = _Sequencia(_ma(), _ma(), BOA)
    provedor = ProvedorComReserva(principal, None, lambda _: None)
    with pytest.raises(ErroVerificacao):
        gerar_plano_verificado(_q(), provedor, lambda _: None)
    assert len(principal.pedidos) == 2


def test_reserva_nao_e_usada_se_a_regeneracao_passar() -> None:
    principal, reserva = _Sequencia(_ma(), BOA), _Sequencia(BOA)
    provedor, _ = _com_reserva(principal, reserva)
    resultado = gerar_plano_verificado(_q(), provedor, lambda _: None)
    assert resultado.chamadas == 2 and not resultado.reserva_na_verificacao
    assert reserva.pedidos == []


# ---------------------------------------------------------------- Estilo no pipeline


def test_estilo_corrigido_sem_chamar_a_llm(tmp_path: Path) -> None:
    dados = json.loads(BOA)
    dados["resumo"] += " Vai garantir a regularidade, veja no celular. Recuperação total."
    resposta = json.dumps(dados, ensure_ascii=False)
    resultado, provedor, progresso = _correr(resposta)
    assert resultado.chamadas == 1  # type: ignore[attr-defined]
    plano = resultado.plano  # type: ignore[attr-defined]
    assert "assegurar a regularidade, veja no telemóvel" in plano.resumo
    assert resultado.correcoes_estilo == (  # type: ignore[attr-defined]
        "garantir → assegurar",
        "celular → telemóvel",
    )
    assert resultado.avisos_estilo == ("total",)  # type: ignore[attr-defined]
    assert progresso[-1] == (
        "estilo: 2 correção(ões) automática(s); 1 aviso(s) sem correção (não bloqueiam)"
    )
    assert "celular" not in "\n".join(progresso)  # só metadados
    codigo, saida = _cli_plano(tmp_path, resposta)
    assert codigo == 0
    assert "Estilo corrigido pelo motor: garantir → assegurar; celular → telemóvel" in saida
    assert "Estilo sem correção conhecida (só aviso): total" in saida


def test_acentos_em_falta_corrigidos_sem_chamar_a_llm() -> None:
    dados = json.loads(BOA)
    dados["resumo"] += " Faça os exercicios com calma."
    resultado, _, _ = _correr(json.dumps(dados, ensure_ascii=False))
    assert resultado.chamadas == 1  # type: ignore[attr-defined]
    assert "exercicios → exercícios" in resultado.correcoes_estilo  # type: ignore[attr-defined]
    assert "Faça os exercícios com calma." in resultado.plano.resumo  # type: ignore[attr-defined]
    assert resultado.palavras_desconhecidas == ()  # type: ignore[attr-defined]
