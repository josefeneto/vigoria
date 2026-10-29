"""Gerador (motor/gerador.py): pedido à LLM e montagem do plano, com a LLM simulada."""

import contextlib
import io
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

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
from vigoria.motor.selecao import selecionar_exercicios

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

    def __init__(self, resposta: str = RESPOSTA) -> None:
        self.resposta = resposta
        self.chamadas: list[tuple[str, str, type[BaseModel]]] = []

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        self.chamadas.append((sistema, pedido, schema))
        return schema.model_validate_json(self.resposta)


# ---------------------------------------------------------------- Prompt de sistema


def test_prompt_versao_e_texto() -> None:
    prompt = carregar_prompt_sistema()
    assert prompt.versao == "1"
    assert not prompt.texto.startswith("<!--")
    assert prompt.texto.startswith("# Papel")
    for essencial in ("exercicios_permitidos", "nunca em meses", "sem_intervalos", "Texto livre"):
        assert essencial in prompt.texto


# ---------------------------------------------------------------- Pedido


def test_pedido_partes() -> None:
    c = conteudo_pedido(*_persona())
    assert set(c) == {
        "estrategia",
        "questionario",
        "exercicios_permitidos",
        "fases",
        "estrutura_sessao",
        "alimentacao",
    }
    assert set(c["alimentacao"]) == {"principios", "refeicao_simples"}
    assert len(c["fases"]) == 4


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


def test_exercicios_permitidos_iguais_a_selecao() -> None:
    q, e = _persona()
    c = conteudo_pedido(q, e)
    for fase in (1, 2, 3, 4):
        ids = [x["id"] for x in c["exercicios_permitidos"][f"fase_{fase}"]]
        assert ids == [p.id for p in selecionar_exercicios(e, fase)]


def test_exercicios_de_referencia_so_permitidos() -> None:
    for ficheiro in ("persona_teste.json", "persona_osteoporose.json"):
        c = conteudo_pedido(*_persona(ficheiro))
        for fase in c["fases"]:
            permitidos = {x["id"] for x in c["exercicios_permitidos"][f"fase_{fase['numero']}"]}
            for ref in fase["exercicios_referencia"]:
                assert ref["id"] in permitidos
                assert set(ref.get("alternativas", [])) <= permitidos


def test_referencia_troca_regressoes() -> None:
    c = conteudo_pedido(*_persona())
    fase_1 = c["fases"][0]["exercicios_referencia"]
    assert fase_1[0]["id"] == "agachamento_cadeira"  # limitação ligeira: fase 1 mantém-se
    assert "em_vez_de" not in fase_1[0]
    fase_2 = c["fases"][1]["exercicios_referencia"]
    assert {"id": "agachamento_cadeira", "em_vez_de": "lunge_atras_apoio"}.items() <= fase_2[
        0
    ].items()


def test_osteoporose_bird_dog_em_vez_de_crunch() -> None:
    c = conteudo_pedido(*_persona("persona_osteoporose.json"))
    fase_2 = c["fases"][1]["exercicios_referencia"]
    assert {"id": "bird_dog", "em_vez_de": "abdominal_crunch"}.items() <= fase_2[-1].items()


def test_variante_halteres_so_com_halteres() -> None:
    com = conteudo_pedido(*_persona())["exercicios_permitidos"]["fase_1"]
    sem = conteudo_pedido(*_persona("persona_osteoporose.json"))["exercicios_permitidos"]["fase_1"]
    assert any("variante_halteres" in x for x in com)
    assert not any("variante_halteres" in x for x in sem)


def test_pedido_em_texto() -> None:
    pedido = montar_pedido(*_persona())
    assert pedido.versao_prompt == "1"
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


def test_resposta_simulada_so_usa_exercicios_permitidos() -> None:
    _, e = _persona()
    gerado = PlanoGerado.model_validate_json(RESPOSTA)
    for fase in (1, 2, 3, 4):
        permitidos = {p.id for p in selecionar_exercicios(e, fase)}
        treino = getattr(gerado.treino, f"fase_{fase}")
        assert {x.exercicio_id for x in treino.exercicios} <= permitidos


def test_gerar_plano_com_provedor_falso() -> None:
    q, e = _persona()
    provedor = ProvedorFalso()
    plano = gerar_plano(q, e, provedor)

    assert len(provedor.chamadas) == 1
    sistema, pedido, schema = provedor.chamadas[0]
    assert sistema == carregar_prompt_sistema().texto
    assert pedido == montar_pedido(q, e).conteudo
    assert schema is PlanoGerado

    assert plano.versao_prompt == "1"
    assert plano.avisos == e.avisos
    assert [m.semana for m in plano.marcos] == [4, 8, 12, 16]
    assert [m.peso_indicativo_kg for m in plano.marcos] == [92.5, 91.0, 89.5, 88.0]
    assert plano.marcos[0].forca_resistencia.startswith("Fazer as 3 séries")
    assert plano.marcos[0].cintura == e.marcos[0].cintura
    assert e.indicadores is not None
    assert plano.proteina == e.indicadores.proteina
    assert plano.hidratacao.valores == e.indicadores.hidratacao
    assert plano.hidratacao.dicas[0].startswith("Tenha uma garrafa")


def test_plano_renal_sem_valores() -> None:
    q, e = _persona("persona_renal.json")
    plano = gerar_plano(q, e, ProvedorFalso())
    assert plano.proteina.minimo_g is None
    assert plano.hidratacao.valores.central_ml is None


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
    assert texto.startswith("=== PROMPT DE SISTEMA (versão 1) ===")
    assert "=== PEDIDO ===" in texto


def test_cli_sem_opcao_nao_chama_llm() -> None:
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        assert cli.main([str(RAIZ / "exemplos" / "persona_teste.json")]) == 2
