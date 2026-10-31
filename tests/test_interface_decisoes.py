"""Decisões mostradas antes de gerar (passos 1, 5 e 7) e mensagens de erro da geração."""

from pathlib import Path

import pytest

from vigoria.interface.decisoes import avisos_passo_objetivo, decisoes_estrategia, imc_com_classe
from vigoria.interface.erros import TipoErroUtilizador, classificar_erro
from vigoria.interface.passos import respostas_de_questionario
from vigoria.llm.base import ErroLLM, TipoFalha
from vigoria.modelos.questionario import Intensidade, Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import ErroGeracao
from vigoria.motor.pipeline import ErroMotor, ErroVerificacao
from vigoria.regras import textos
from vigoria.regras.calculos import ClasseImc
from vigoria.regras.elegibilidade import Modo

RAIZ = Path(__file__).resolve().parents[1]


def _q(ficheiro: str = "persona_teste.json") -> Questionario:
    return Questionario.model_validate_json((RAIZ / "exemplos" / ficheiro).read_text("utf-8"))


def test_decisoes_da_persona_de_teste() -> None:
    q = _q()
    d = decisoes_estrategia(gerar_estrategia(q), q)
    assert d.pode_gerar_plano and d.modo is Modo.BASE and d.motivos == ()
    assert d.intensidade_efetiva is Intensidade.MEDIA
    assert (d.peso_atual_kg, d.peso_alvo_kg) == (94.0, 85.0)
    assert not d.objetivo_realista
    assert d.alvo_semana_16_kg == pytest.approx(88, abs=0.5)
    assert d.semana_objetivo == 24
    assert d.modulo_gordura_visceral and not d.usar_frequencia_cardiaca
    assert d.avisos_obrigatorios == (textos.AVISO_GERAL, textos.SINAIS_INTERROMPER)
    assert textos.ESFORCO_PERCEBIDO in d.avisos_condicionais
    assert textos.AVISO_GERAL not in d.avisos_condicionais


def test_decisoes_em_modo_prudente_com_teto() -> None:
    q = _q("persona_imc36.json")
    d = decisoes_estrategia(gerar_estrategia(q), q)
    assert d.modo is Modo.PRUDENTE
    assert textos.IMC_35_OU_MAIS.format(imc="36,0") in d.motivos
    assert d.intensidade_efetiva is Intensidade.LIGEIRA
    assert d.explicacao_intensidade


def test_imc_com_classe() -> None:
    assert imc_com_classe(94, 172) == (31.8, ClasseImc.OBESIDADE_I)
    assert imc_com_classe(60, 170)[1] is ClasseImc.NORMAL


def test_avisos_imediatos_do_passo_5() -> None:
    respostas = respostas_de_questionario(_q())
    avisos = avisos_passo_objetivo(respostas)
    assert len(avisos) == 1 and "semana 16" in avisos[0]
    assert avisos_passo_objetivo(respostas | {"peso_alvo_kg": 92.0}) == ()
    sem_perda = avisos_passo_objetivo(respostas | {"peso_alvo_kg": 96.0})
    assert sem_perda == (textos.PESO_ALVO_SEM_PERDA,)


def test_avisos_do_passo_5_sem_as_outras_respostas_do_passo() -> None:
    respostas = respostas_de_questionario(_q())
    del respostas["intensidade_pedida"], respostas["objetivo_muscular"]
    assert len(avisos_passo_objetivo(respostas)) == 1
    assert avisos_passo_objetivo(respostas | {"peso_alvo_kg": None}) == ()


# ---------------------------------------------------------------- Erros da geração


@pytest.mark.parametrize(
    ("erro", "tipo"),
    [
        (ErroLLM("q", 429, True, TipoFalha.QUOTA_DIARIA), TipoErroUtilizador.QUOTA_DIARIA),
        (ErroLLM("m", 429, False, TipoFalha.POR_MINUTO), TipoErroUtilizador.MUITOS_PEDIDOS),
        (ErroLLM("i", 503, True, TipoFalha.INDISPONIVEL), TipoErroUtilizador.INDISPONIVEL),
        (ErroLLM("sem resposta em 120 s", permite_reserva=True), TipoErroUtilizador.INDISPONIVEL),
        (ErroLLM("formato"), TipoErroUtilizador.INDISPONIVEL),
        (ErroLLM("x", 400, False, TipoFalha.OUTRA), TipoErroUtilizador.OUTRO),
        (ErroVerificacao(("motivo",)), TipoErroUtilizador.RECUSADO),
        (ErroMotor(("motivo",)), TipoErroUtilizador.RECUSADO),
        (ErroGeracao("estratégia"), TipoErroUtilizador.OUTRO),
        (RuntimeError("inesperado"), TipoErroUtilizador.OUTRO),
    ],
)
def test_classificar_erro(erro: Exception, tipo: TipoErroUtilizador) -> None:
    assert classificar_erro(erro) is tipo
