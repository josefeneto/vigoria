"""Treino determinístico (motor/treino.py, Fase 4C): prescrição igual ao programa."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from vigoria.conteudo.carregar import Grupo, carregar_exercicios, carregar_programa
from vigoria.modelos.plano import Treino
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.selecao import selecionar_exercicios
from vigoria.motor.treino import construir_treino, repeticoes_proprias, variante_halteres
from vigoria.regras import textos

EXEMPLOS = Path(__file__).parent.parent / "exemplos"
PERSONAS = sorted(p.name for p in EXEMPLOS.glob("persona_*.json"))


def _q(ficheiro: str = "persona_teste.json", **alteracoes: Any) -> Questionario:
    dados = json.loads((EXEMPLOS / ficheiro).read_text(encoding="utf-8"))
    return Questionario.model_validate(dados | alteracoes)


def _treino(ficheiro: str = "persona_teste.json", **alteracoes: Any) -> Treino:
    q = _q(ficheiro, **alteracoes)
    e = gerar_estrategia(q)
    return construir_treino(e, q)


def _forca(treino: Treino, fase: int) -> dict[str, Any]:
    return {x.id: x for x in treino.fases[fase - 1].forca}


# ---------------------------------------------------------------- Todas as personas


@pytest.mark.parametrize("ficheiro", PERSONAS)
def test_prescricao_igual_ao_programa(ficheiro: str) -> None:
    q = _q(ficheiro)
    e = gerar_estrategia(q)
    if not e.pode_gerar_plano:
        pytest.skip("persona sem plano")
    treino = construir_treino(e, q)
    programa = carregar_programa()
    for fase, fase_programa in zip(treino.fases, programa.fases, strict=True):
        posicoes = {p.id: p for p in fase_programa.exercicios}
        permitidos = {p.id for p in selecionar_exercicios(e, fase.numero)}
        ids = [x.id for x in fase.forca]
        assert len(ids) == len(set(ids)), "exercício repetido na fase"
        assert len(ids) <= len(fase_programa.exercicios)
        for x in fase.forca:
            assert x.id in permitidos
            posicao = posicoes[x.em_vez_de or x.id]
            assert x.series == posicao.series
            assert x.descanso_s == (posicao.descanso_s.min, posicao.descanso_s.max)
            if x.em_vez_de is None:
                assert x.repeticoes == posicao.repeticoes
            else:
                proprias = repeticoes_proprias(x.id, fase.numero)
                sem_lado = re.sub(r"\s*\(por (?:perna|braço)\)", "", posicao.repeticoes)
                assert x.repeticoes == (proprias or sem_lado)
        todos = [*fase.forca, *fase.mobilidade_equilibrio]
        if fase.cardio_finalizador:
            todos.append(fase.cardio_finalizador)
        assert {x.id for x in todos} <= permitidos
        assert fase.esforco == (fase_programa.esforco.min, fase_programa.esforco.max)


# ---------------------------------------------------------------- Regras novas (§6.6)


def test_substituto_usa_as_repeticoes_da_sua_posicao() -> None:
    # Persona: limitação ligeira nos joelhos; na fase 2, o lunge (10 por perna) passa a
    # agachamento para cadeira: séries e descanso da posição, repetições da sua (fase 1).
    agachamento = _forca(_treino(), 2)["agachamento_cadeira"]
    assert agachamento.em_vez_de == "lunge_atras_apoio"
    assert (agachamento.series, agachamento.repeticoes, agachamento.descanso_s) == (
        3,
        "12-15",
        (45, 45),
    )


def test_repeticoes_proprias_ordem_de_procura() -> None:
    assert repeticoes_proprias("agachamento_cadeira", 2) == "12-15"  # fase anterior
    assert repeticoes_proprias("remada_unilateral_apoio", 1) == "12 (por braço)"  # seguinte
    assert repeticoes_proprias("remada_unilateral_apoio", 4) == "12 (por braço)"  # mesma
    assert repeticoes_proprias("transferencias_peso", 2) is None  # sem posição


def test_sem_posicao_tira_por_perna() -> None:
    # Um substituto sem posição no programa: repetições do original sem «(por perna)».
    from vigoria.motor import treino as modulo

    assert modulo._sem_lado("10 (por perna)") == "10"
    assert modulo._sem_lado("12 (por braço)") == "12"
    assert modulo._sem_lado("30s (cada lado)") == "30s (cada lado)"


def test_mesmo_exercicio_nunca_duas_vezes_na_fase() -> None:
    # Fase 4 da persona: antes, o agachamento para cadeira substituía várias posições.
    fase_4 = _treino().fases[3]
    ids = [x.id for x in fase_4.forca]
    assert ids.count("agachamento_cadeira") == 1
    assert len(ids) < len(carregar_programa().fases[3].exercicios)  # uma posição saiu
    assert _forca(_treino(), 4)["ponte_gluteos"].em_vez_de == "subida_degrau_apoio"


def test_regressao_por_contraindicacao() -> None:
    # Osteoporose: sem flexão do tronco com carga, o crunch passa a bird-dog.
    bird_dog = _forca(_treino("persona_osteoporose.json"), 2)["bird_dog"]
    assert bird_dog.em_vez_de == "abdominal_crunch"
    assert (bird_dog.series, bird_dog.repeticoes, bird_dog.descanso_s) == (3, "30-45s", (30, 30))


# ---------------------------------------------------------------- Notas


def test_notas_da_selecao() -> None:
    agachamento = _forca(_treino(), 1)["agachamento_cadeira"]
    assert textos.AMPLITUDE_CONFORTAVEL in agachamento.notas
    osteoporose = _treino("persona_osteoporose.json")
    for x in osteoporose.fases[0].forca:
        if carregar_exercicios()[x.id].de_pe:
            assert textos.APOIO_POR_PERTO in x.notas


def test_alternativa_da_posicao() -> None:
    bird_dog = _forca(_treino(), 1)["bird_dog"]
    assert "Alternativa: Prancha." in bird_dog.notas


@pytest.mark.parametrize(("declarado", "esperado"), [(2, "2 kg"), (5, "5 kg"), (10, "5 kg")])
def test_halteres_o_menor_entre_programa_e_declarado(declarado: int, esperado: str) -> None:
    remada = carregar_exercicios()["remada_halteres"]  # programa: 5 kg
    texto = variante_halteres(remada, _q(halteres_kg=declarado))
    assert texto is not None
    assert re.findall(r"\d+ kg", texto) == [esperado]


def test_halteres_repetidos_juntam_se() -> None:
    prensa = carregar_exercicios()["prensa_ombros"]
    texto = variante_halteres(prensa, _q())  # 2 kg declarados
    assert texto is not None and " ou " not in texto


def test_sem_halteres_sem_variante() -> None:
    sem = _q(equipamento=["cadeira_firme"], halteres_kg=None)
    assert variante_halteres(carregar_exercicios()["remada_halteres"], sem) is None


# ---------------------------------------------------------------- Cardio, mobilidade e estrutura


def test_cardio_finalizador_conforme_equipamento() -> None:
    persona = _treino()  # tem passadeira
    assert {f.cardio_finalizador.id for f in persona.fases if f.cardio_finalizador} == {
        "passadeira"
    }
    osteoporose = _treino("persona_osteoporose.json")  # só cadeira
    ids = [f.cardio_finalizador.id for f in osteoporose.fases if f.cardio_finalizador]
    assert ids == ["marcha_rapida_lugar"] * 3 + ["caminhada"]  # a fase 4 já tem a marcha
    assert all(f.cardio_duracao_min == (10, 15) for f in osteoporose.fases)


def test_cardio_continuo_com_sem_intervalos() -> None:
    osteoporose = _treino("persona_osteoporose.json")
    assert osteoporose.fases[0].cardio_finalizador is not None
    assert textos.CARDIO_RITMO_CONTINUO in osteoporose.fases[0].cardio_finalizador.notas
    persona = _treino()
    assert persona.fases[0].cardio_finalizador is not None
    assert textos.CARDIO_RITMO_CONTINUO not in persona.fases[0].cardio_finalizador.notas


def test_mobilidade_e_equilibrio_permitidos() -> None:
    for fase in _treino().fases:
        assert fase.mobilidade_equilibrio
        for x in fase.mobilidade_equilibrio:
            assert carregar_exercicios()[x.id].grupo in (Grupo.MOBILIDADE, Grupo.EQUILIBRIO)
            assert x.series is None and x.repeticoes is None


def test_estrutura_da_sessao_do_programa() -> None:
    s = carregar_programa().estrutura_sessao
    e = _treino().estrutura_sessao
    assert (e.aquecimento, e.bloco_principal, e.cardio_finalizador, e.retorno_calma) == (
        s.aquecimento,
        s.bloco_principal,
        s.cardio_finalizador,
        s.retorno_calma,
    )
