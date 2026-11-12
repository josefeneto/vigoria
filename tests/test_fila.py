"""Fila de geração (motor/fila.py, Fase 10C): um plano de cada vez, no máximo 3 min de espera."""

import threading

import pytest

from paginas import textos as t
from vigoria.interface.erros import TipoErroUtilizador, classificar_erro
from vigoria.motor.fila import ESPERA_MAX_S, FilaOcupada, vez_na_fila


def test_espera_maxima_de_3_minutos() -> None:
    assert ESPERA_MAX_S == 180


def test_sem_ninguem_a_gerar_nao_espera_nem_avisa() -> None:
    tranca = threading.Lock()
    avisos: list[str] = []
    with vez_na_fila(lambda: avisos.append("x"), tranca=tranca):
        assert tranca.locked()
    assert not tranca.locked() and avisos == []


def test_liberta_a_vez_mesmo_com_erro() -> None:
    tranca = threading.Lock()
    with pytest.raises(RuntimeError), vez_na_fila(tranca=tranca):
        raise RuntimeError
    assert not tranca.locked()


def test_segundo_pedido_espera_pelo_primeiro_e_e_avisado() -> None:
    tranca = threading.Lock()
    ordem: list[str] = []
    a_gerar = threading.Event()
    pode_acabar = threading.Event()

    def primeiro() -> None:
        with vez_na_fila(tranca=tranca):
            ordem.append("primeiro começa")
            a_gerar.set()
            pode_acabar.wait(5)
            ordem.append("primeiro acaba")

    def avisar() -> None:
        ordem.append("segundo avisado")
        pode_acabar.set()

    fio = threading.Thread(target=primeiro)
    fio.start()
    assert a_gerar.wait(5)
    with vez_na_fila(avisar, espera_max_s=5, tranca=tranca):
        ordem.append("segundo começa")
    fio.join(5)
    assert ordem == ["primeiro começa", "segundo avisado", "primeiro acaba", "segundo começa"]


def test_ao_fim_da_espera_maxima_desiste() -> None:
    tranca = threading.Lock()
    tranca.acquire()
    avisos: list[str] = []
    try:
        with (
            pytest.raises(FilaOcupada),
            vez_na_fila(lambda: avisos.append("x"), espera_max_s=0.05, tranca=tranca),
        ):
            pass
    finally:
        tranca.release()
    assert avisos == ["x"]


def test_fila_cheia_tem_mensagem_propria_em_pt_pt() -> None:
    tipo = classificar_erro(FilaOcupada())
    assert tipo is TipoErroUtilizador.FILA_CHEIA
    assert "Tente de novo daqui a alguns minutos" in t.ERROS_GERACAO[tipo]
    assert t.A_ESPERA == "Estamos a preparar o seu plano, pode demorar um minuto."


def test_teto_de_gasto_aparece_como_servico_indisponivel() -> None:
    from vigoria.llm.base import ErroLLM, TipoFalha

    tipo = classificar_erro(ErroLLM("x", 429, tipo=TipoFalha.LIMITE_GASTO))
    assert tipo is TipoErroUtilizador.INDISPONIVEL
    assert "não está disponível neste momento" in t.ERROS_GERACAO[tipo]
