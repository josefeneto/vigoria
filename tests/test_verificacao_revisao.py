"""Verificações acrescentadas a 30/10/2026, depois dos primeiros planos reais.

Semana-tipo (dias e duração), prescrição igual ao programa, números com unidade só dos
dados (também por extenso), cargas dos halteres, promessas absolutas, «aeróbico» e
ortografia (só aviso).
"""

import json
from pathlib import Path
from typing import Any

import pytest

from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano, PlanoGerado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import montar_plano
from vigoria.motor.ortografia import palavras_desconhecidas
from vigoria.motor.verificacao import TipoFalha, pesos_halteres_permitidos, verificar
from vigoria.motor.voz import inserir_avisos

RAIZ = Path(__file__).parent.parent
RESPOSTA = json.loads(
    (RAIZ / "tests" / "fixtures" / "resposta_gerador_persona_teste.json").read_text("utf-8")
)


def _q(**alteracoes: Any) -> Questionario:
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text(encoding="utf-8"))
    return Questionario.model_validate(dados | alteracoes)


def _resposta() -> dict[str, Any]:
    return json.loads(json.dumps(RESPOSTA))


def _plano(resposta: dict[str, Any], e: Estrategia) -> Plano:
    gerado = PlanoGerado.model_validate(resposta)
    return inserir_avisos(montar_plano(gerado, e, "3", "falso"), e)


def _falhas(resposta: dict[str, Any], q: Questionario | None = None) -> list[tuple[str, str]]:
    q = _q() if q is None else q
    e = gerar_estrategia(q)
    return [(f.tipo.value, f.motivo) for f in verificar(_plano(resposta, e), e, q)]


def _com_texto(extra: str) -> dict[str, Any]:
    resposta = _resposta()
    resposta["resumo"] += f" {extra}"
    return resposta


def test_referencia_passa() -> None:
    assert _falhas(_resposta()) == []


# ---------------------------------------------------------------- Semana-tipo


def test_mais_dias_com_sessao_do_que_a_disponibilidade() -> None:
    resposta = _resposta()
    quinta = next(d for d in resposta["semana_tipo"] if d["dia"] == "quinta")
    quinta |= {"atividade": "Caminhada", "duracao_min": 30}
    assert _falhas(resposta) == [
        (
            "semana",
            "A semana-tipo tem 6 dias com sessão, mas a disponibilidade é de 5 dias "
            "(os outros dias ficam com duração 0).",
        )
    ]


def test_sessao_mais_longa_do_que_minutos_dia() -> None:
    resposta = _resposta()
    resposta["semana_tipo"][0]["duracao_min"] = 45
    assert _falhas(resposta) == [
        ("semana", "Segunda-feira: sessão de 45 min, acima dos 30 min disponíveis.")
    ]


def test_dias_sem_sessao_com_duracao_zero_nao_contam() -> None:
    resposta = _resposta()
    quinta = next(d for d in resposta["semana_tipo"] if d["dia"] == "quinta")
    quinta |= {"atividade": "Caminhada livre", "duracao_min": 0}
    assert _falhas(resposta) == []


# ---------------------------------------------------------------- Prescrição


def test_series_repeticoes_e_descanso_iguais_ao_programa() -> None:
    resposta = _resposta()
    ponte = resposta["treino"]["fase_1"]["exercicios"][0]
    assert ponte["exercicio_id"] == "ponte_gluteos"
    ponte |= {"repeticoes": "12", "descanso": "30 s"}
    assert _falhas(resposta) == [
        (
            "prescricao",
            "Fase 1: «ponte_gluteos» tem de seguir o programa: 3 séries de 15, descanso de 45 s.",
        )
    ]


@pytest.mark.parametrize("descanso", ["45 s", "45s", "45 segundos"])
def test_descanso_escrito_de_varias_formas(descanso: str) -> None:
    resposta = _resposta()
    resposta["treino"]["fase_1"]["exercicios"][0]["descanso"] = descanso
    assert _falhas(resposta) == []


# ---------------------------------------------------------------- Números com unidade


@pytest.mark.parametrize(
    "texto",
    [
        "Limitando a dois copos por dia.",
        "Beba um copo de água ao acordar.",
        "Durma 7 horas.",
        "Caminhe 20 min.",
        "Ande 3 km.",
        "Reduza 10 % do pão.",
        "Faça 20 a 25 minutos.",
    ],
)
def test_numeros_que_nao_vem_dos_dados_chumbam(texto: str) -> None:
    falhas = _falhas(_com_texto(texto))
    assert len(falhas) == 1
    tipo, motivo = falhas[0]
    assert tipo == "numero_no_texto"
    assert "não vem do questionário, da estratégia nem do programa" in motivo


@pytest.mark.parametrize(
    "texto",
    [
        "Hoje bebe 3 copos de vinho.",  # vinho_copos_dia do questionário
        "Sessões de 30 minutos.",  # minutos_dia
        "Meia hora por dia.",  # 30 min
        "Cardio finalizador de 12 min.",  # fases.yaml: 10 a 15 min
        "Aquecimento de 5 a 10 min.",  # estrutura da sessão
    ],
)
def test_numeros_dos_dados_passam(texto: str) -> None:
    assert _falhas(_com_texto(texto)) == []


# ---------------------------------------------------------------- Cargas


def test_halteres_o_menor_entre_programa_e_declarado() -> None:
    assert pesos_halteres_permitidos(_q()) == {2.0}  # programa 2 e 5 kg; declarado 2 kg
    assert pesos_halteres_permitidos(_q(halteres_kg=5)) == {2.0, 5.0}
    assert pesos_halteres_permitidos(_q(halteres_kg=10)) == {2.0, 5.0}
    sem_halteres = _q(equipamento=["cadeira_firme"], halteres_kg=None)
    assert pesos_halteres_permitidos(sem_halteres) == frozenset()


def test_remada_com_5_kg_chumba_com_halteres_de_2_kg() -> None:
    falhas = _falhas(_com_texto("Remada com halteres de 5 kg."))
    assert falhas == [
        (
            "numero_no_texto",
            "O texto tem o valor «5 kg»: valores de peso, proteína, hidratação e calorias vêm "
            "só da estratégia (pesos de halteres permitidos: 2 kg).",
        )
    ]
    assert _falhas(_com_texto("Remada com halteres de 5 kg."), _q(halteres_kg=5)) == []


# ---------------------------------------------------------------- Promessas e brasileirismos


@pytest.mark.parametrize(
    ("texto", "termo"),
    [
        ("Vai garantir resultados.", "garantir"),
        ("Garantindo o sucesso.", "garantindo"),
        ("Recuperação total ao domingo.", "total"),
        ("Fica totalmente seguro.", "totalmente"),
        ("Executa perfeitamente.", "perfeitamente"),
        ("Com segurança absoluta.", "absoluta"),
        ("Um plano rigoroso.", "rigoroso"),
        ("Exercícios sem risco.", "sem risco"),
        ("É risco zero.", "risco zero"),
    ],
)
def test_promessas_absolutas_chumbam(texto: str, termo: str) -> None:
    (falha,) = _falhas(_com_texto(texto))
    assert falha[0] == TipoFalha.PROMESSA.value
    assert f"«{termo}»" in falha[1]


def test_palavras_parecidas_nao_sao_promessas() -> None:
    assert _falhas(_com_texto("A totalidade do treino é feita em casa.")) == []


def test_aeroboco_e_brasileirismo() -> None:
    falhas = _falhas(_com_texto("Exercício aeróbico ligeiro."))
    assert falhas == [
        ("brasileirismo", "O texto tem o brasileirismo «aeróbico»: use português europeu.")
    ]
    assert _falhas(_com_texto("Exercício aeróbio ligeiro.")) == []


# ---------------------------------------------------------------- Ortografia (só aviso)


def test_ortografia_apanha_palavra_inventada() -> None:
    e = gerar_estrategia(_q())
    plano = _plano(_com_texto("Mantenha a durquetura e a acção."), e)
    assert palavras_desconhecidas(plano) == ("durquetura", "acção")  # «acção» é pré-AO90


def test_ortografia_aceita_referencia_e_vocabulario_do_programa() -> None:
    e = gerar_estrategia(_q())
    assert palavras_desconhecidas(_plano(_resposta(), e)) == ()
    texto = "Exercício aeróbio; bird-dog; ultraprocessados; Pequeno-almoço; unipodal."
    assert palavras_desconhecidas(_plano(_com_texto(texto), e)) == ()


def test_ortografia_nao_chumba_o_plano() -> None:
    assert _falhas(_com_texto("Mantenha a durquetura.")) == []
