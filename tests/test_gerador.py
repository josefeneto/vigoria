"""Gerador (motor/gerador.py): pedido à LLM e montagem do plano, com a LLM simulada."""

import contextlib
import io
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from vigoria.conteudo.carregar import carregar_alimentacao
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import PlanoGerado
from vigoria.modelos.questionario import Questionario
from vigoria.motor import cli
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import (
    CAMPOS_QUESTIONARIO,
    MAX_TEXTO_LIVRE,
    ErroGeracao,
    carregar_prompt_sistema,
    conteudo_pedido,
    gerar_plano,
    limpar_texto_livre,
    montar_pedido,
)
from vigoria.motor.semana import construir_semana
from vigoria.motor.treino import construir_treino

RAIZ = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
RESPOSTA = (FIXTURES / "resposta_gerador_persona_teste.json").read_text(encoding="utf-8")


def _dados(ficheiro: str) -> dict[str, Any]:
    return json.loads((RAIZ / "exemplos" / ficheiro).read_text(encoding="utf-8"))


def _persona(ficheiro: str = "persona_teste.json") -> tuple[Questionario, Estrategia]:
    q = Questionario.model_validate(_dados(ficheiro))
    return q, gerar_estrategia(q)


class ProvedorFalso:
    """Devolve sempre a mesma resposta JSON e guarda o que recebeu."""

    nome = "falso"
    modelo = "modelo-falso"

    def __init__(self, resposta: str = RESPOSTA, ultimo: str | None = None) -> None:
        self.resposta = resposta
        self.ultimo_provedor = ultimo
        self.chamadas: list[tuple[str, str, type[BaseModel]]] = []

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        self.chamadas.append((sistema, pedido, schema))
        return schema.model_validate_json(self.resposta)


# ---------------------------------------------------------------- Prompt de sistema


def test_prompt_versao_e_texto() -> None:
    prompt = carregar_prompt_sistema()
    assert prompt.versao == "7"
    assert not prompt.texto.startswith("<!--")
    assert prompt.texto.startswith("# Papel")
    # Versão 4 (30/10/2026): só os campos do novo PlanoGerado; v5: promessas e Tai Chi;
    # v6: resultados no futuro, sem intervalos, marcos no presente, «tem em conta».
    for essencial in (
        "`treino_resumo`",
        "Semanas, nunca meses",
        "Sem números com unidade",
        "Sem promessas de resultados ou de segurança",
        "Só o podes mencionar se `questionario.preferencias` incluir `tai_chi`",
        "aeróbico",
        "exatamente quatro frases",
        "no máximo três notas",
        "Texto livre",
        "Nada de resultados no futuro",
        "`estrategia.restricoes.sem_intervalos`",
        "no presente",
        "«tem em conta»",
    ):
        assert essencial in prompt.texto
    for campo in PlanoGerado.model_fields:
        assert f"`{campo}`" in prompt.texto
    assert len(prompt.texto) < 6000  # mais curto do que a v3 (cerca de 9 600 caracteres)


# ---------------------------------------------------------------- Pedido


def test_pedido_partes() -> None:
    c = conteudo_pedido(*_persona())
    assert set(c) == {"estrategia", "questionario", "alimentacao", "treino_resumo"}
    assert set(c["alimentacao"]) == {"principios", "foco_por_fase"}
    assert [f["fase"] for f in c["alimentacao"]["foco_por_fase"]] == [1, 2, 3, 4]
    assert set(c["treino_resumo"]) == {"fase_1", "fase_2", "fase_3", "fase_4"}


def test_resumo_do_treino_so_com_nomes() -> None:
    q, e = _persona()
    resumo = conteudo_pedido(q, e)["treino_resumo"]
    treino = construir_treino(e, q)
    for fase in treino.fases:
        r = resumo[f"fase_{fase.numero}"]
        assert r["nome"] == fase.nome
        assert r["forca"] == [x.nome for x in fase.forca]
        assert set(r) == {"nome", "forca", "cardio_finalizador"}  # sem séries nem notas


def test_pedido_mais_pequeno() -> None:
    pedido = montar_pedido(*_persona())
    assert len(pedido.sistema) + len(pedido.conteudo) < 15_000  # v3: cerca de 31 800


def test_questionario_sem_consentimentos_nem_lembretes() -> None:
    dados = conteudo_pedido(*_persona())["questionario"]
    assert set(dados) <= CAMPOS_QUESTIONARIO
    for campo in (
        "aceita_termos",
        "consentimento_saude",
        "confirma_maior_idade",
        "acompanhamento_ativo",
        "lembretes_email",
    ):
        assert campo not in dados
    assert "contexto_texto_livre" not in dados  # a persona não tem texto livre


def test_campos_do_questionario_estao_todos_classificados() -> None:
    """Um campo novo no Questionario obriga a decidir se segue ou não para a LLM."""
    fora = {
        "aceita_termos",
        "consentimento_saude",
        "confirma_maior_idade",
        "acompanhamento_ativo",
        "lembretes_email",
        "condicoes_outras",
        "dor_articular_outra",
        "medicacao_notas",
        "limitacoes_outra",
        "restricoes_outra",
    }
    assert set(Questionario.model_fields) == CAMPOS_QUESTIONARIO | fora


def test_texto_livre_segue_a_parte() -> None:
    dados = _dados("persona_teste.json")
    dados |= {
        "condicoes": ["outra"],
        "condicoes_controladas": {},
        "condicoes_outras": "asma ligeira",
    }
    q = Questionario.model_validate(dados)
    pedido = conteudo_pedido(q, gerar_estrategia(q))["questionario"]
    assert pedido["contexto_texto_livre"] == {"condicoes_outras": "asma ligeira"}
    assert "condicoes_outras" not in pedido


def test_pedido_em_json_compacto() -> None:
    corpo = montar_pedido(*_persona()).conteudo.split("\n", 1)[1]
    assert "\n" not in corpo
    assert corpo == json.dumps(json.loads(corpo), ensure_ascii=False, separators=(",", ":"))


def test_pedido_em_texto() -> None:
    pedido = montar_pedido(*_persona())
    assert pedido.versao_prompt == "7"
    assert pedido.sistema == carregar_prompt_sistema().texto
    json.loads(pedido.conteudo.split("\n", 1)[1])  # JSON válido depois da 1.ª linha


def test_sem_plano_da_erro() -> None:
    q, e = _persona()
    e = e.model_copy(update={"pode_gerar_plano": False, "motivos": ("Motivo.",)})
    with pytest.raises(ErroGeracao, match="Motivo."):
        montar_pedido(q, e)


def test_texto_livre_sem_email_nem_telefone() -> None:
    dados = _dados("persona_teste.json")
    dados |= {
        "condicoes": ["outra"],
        "condicoes_controladas": {},
        "condicoes_outras": "Asma. Contacto: ana.silva@exemplo.pt ou 912 345 678",
        "medicacao_notas": "Médico: +351 21 123 4567; tensão 135/85 em 29.10.2026",
    }
    q = Questionario.model_validate(dados)
    livre = conteudo_pedido(q, gerar_estrategia(q))["questionario"]["contexto_texto_livre"]
    assert livre == {
        "condicoes_outras": "Asma. Contacto: [removido] ou [removido]",
        "medicacao_notas": "Médico: [removido]; tensão 135/85 em 29.10.2026",
    }


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("joao@mail.com", "[removido]"),
        ("Nome.Apelido+tag@sub.dominio.pt!", "[removido]!"),
        ("+351912345678", "[removido]"),
        ("00 44 20 7946 0958", "[removido]"),
        ("(+44) 20-7946-0958", "([removido]"),
        ("21-123-4567", "[removido]"),
        ("tomo 2,5 mg de 12 em 12 h", "tomo 2,5 mg de 12 em 12 h"),
        ("desde 2019; 3 vezes por semana", "desde 2019; 3 vezes por semana"),
        ("12345678", "12345678"),  # 8 algarismos: não é telefone
    ],
)
def test_limpar_texto_livre(texto: str, esperado: str) -> None:
    assert limpar_texto_livre(texto) == esperado


def test_texto_livre_limitado_a_500_caracteres() -> None:
    dados = _dados("persona_teste.json")
    dados |= {
        "condicoes": ["outra"],
        "condicoes_controladas": {},
        "condicoes_outras": "a" * 200,
        "medicacao_notas": "b" * 200,
        "limitacoes": ["outra"],
        "limitacoes_gravidade": {"outra": "ligeira"},
        "limitacoes_outra": "c" * 200,
    }
    q = Questionario.model_validate(dados)
    livre = conteudo_pedido(q, gerar_estrategia(q))["questionario"]["contexto_texto_livre"]
    assert sum(len(v) for v in livre.values()) == MAX_TEXTO_LIVRE == 500
    assert livre["limitacoes_outra"] == "c" * 100


# ---------------------------------------------------------------- Plano


def test_gerar_plano_com_provedor_falso() -> None:
    q, e = _persona()
    provedor = ProvedorFalso()
    plano = gerar_plano(q, e, provedor)

    assert len(provedor.chamadas) == 1
    sistema, pedido, schema = provedor.chamadas[0]
    assert sistema == carregar_prompt_sistema().texto
    assert pedido == montar_pedido(q, e).conteudo
    assert schema is PlanoGerado

    assert plano.versao_prompt == "7"
    assert plano.provedor == "falso"
    assert plano.avisos == e.avisos
    assert [m.semana for m in plano.marcos] == [4, 8, 12, 16]
    assert [m.peso_indicativo_kg for m in plano.marcos] == [92.5, 91.0, 89.5, 88.0]
    assert plano.marcos[0].forca_resistencia.startswith("Fazer o circuito completo")
    assert plano.marcos[0].cintura == e.marcos[0].cintura
    assert e.indicadores is not None
    assert plano.proteina == e.indicadores.proteina
    assert plano.hidratacao.valores == e.indicadores.hidratacao
    # Do motor e dos YAML, não da LLM.
    assert plano.treino == construir_treino(e, q)
    assert plano.semana_tipo == construir_semana(e, q)
    alimentacao = carregar_alimentacao()
    assert plano.hidratacao.dicas == alimentacao.hidratacao_dicas
    assert [h.titulo for h in plano.habitos] == [h.titulo for h in alimentacao.habitos]
    assert plano.acompanhamento.indicadores == alimentacao.acompanhamento.semanal
    assert plano.acompanhamento.perguntas_revisao == ()
    assert len(plano.alimentacao.prioridades_por_fase) == 4


def test_acompanhamento_a_cada_4_semanas() -> None:
    dados = _dados("persona_teste.json") | {"frequencia_registo": "a_cada_4_semanas"}
    q = Questionario.model_validate(dados)
    plano = gerar_plano(q, gerar_estrategia(q), ProvedorFalso())
    a = carregar_alimentacao().acompanhamento
    assert plano.acompanhamento.indicadores == a.quatro_semanas
    assert plano.acompanhamento.perguntas_revisao == a.perguntas_revisao


def test_plano_renal_sem_valores() -> None:
    q, e = _persona("persona_renal.json")
    plano = gerar_plano(q, e, ProvedorFalso())
    assert plano.proteina.minimo_g is None
    assert plano.hidratacao.valores.central_ml is None
    assert plano.hidratacao.dicas == ()  # sem dicas genéricas sobre beber mais


def test_resposta_fora_do_schema() -> None:
    q, e = _persona()
    with pytest.raises(ValueError):
        gerar_plano(q, e, ProvedorFalso(resposta='{"resumo": "só isto"}'))


# ---------------------------------------------------------------- CLI


def test_cli_so_pedido() -> None:
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        assert cli.main(["--so-pedido", str(RAIZ / "exemplos" / "persona_teste.json")]) == 0
    texto = saida.getvalue()
    assert texto.startswith("=== PROMPT DE SISTEMA (versão 7) ===")
    assert "=== PEDIDO (indentado para leitura; segue em JSON compacto) ===" in texto
    assert '\n  "treino_resumo": {' in texto  # indentado
    assert "Tamanho enviado:" in texto


def test_cli_sem_opcao_nao_chama_llm() -> None:
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        assert cli.main([str(RAIZ / "exemplos" / "persona_teste.json")]) == 2
