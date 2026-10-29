"""Personas de exemplo: a estratégia de cada uma bate com o resultado descrito no _nota."""

import json
from pathlib import Path

from vigoria.modelos.estrategia import Estrategia, Zona
from vigoria.modelos.questionario import Intensidade, Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.regras import textos
from vigoria.regras.elegibilidade import Modo
from vigoria.regras.intensidade import Limitador

EXEMPLOS = Path(__file__).parent.parent / "exemplos"


def _estrategia(ficheiro: str) -> Estrategia:
    dados = json.loads((EXEMPLOS / ficheiro).read_text(encoding="utf-8"))
    return gerar_estrategia(Questionario.model_validate(dados))


def _comum(e: Estrategia) -> None:
    """O que as três personas partilham com a persona_teste.json."""
    assert e.pode_gerar_plano
    assert e.avisos[:2] == (textos.AVISO_GERAL, textos.SINAIS_INTERROMPER)
    assert not e.usar_frequencia_cardiaca  # medicação «não sei»
    assert textos.ESFORCO_PERCEBIDO in e.avisos
    assert e.modulo_gordura_visceral
    assert e.restricoes.sem_impacto
    assert not e.restricoes.equilibrio_com_apoio
    assert e.restricoes.zonas_regressao == ()  # limitação ligeira: regra ligeira (§6.6)
    assert e.restricoes.zonas_regressao_ligeira == (Zona.JOELHOS,)


def test_persona_renal() -> None:
    e = _estrategia("persona_renal.json")
    _comum(e)
    assert e.modo is Modo.PRUDENTE
    assert e.motivos == (textos.DOENCA_RENAL,)
    assert e.intensidade_efetiva is Intensidade.MEDIA
    assert e.explicacao_intensidade is None
    assert e.restricoes.sem_intervalos
    assert textos.ORIENTACAO_INDIVIDUALIZADA in e.avisos

    ind = e.indicadores
    assert ind is not None
    assert ind.proteina.minimo_g is None and ind.proteina.maximo_g is None
    assert ind.proteina.nota == textos.PROTEINA_DOENCA_RENAL
    assert ind.hidratacao.central_ml is None
    assert ind.hidratacao.nota == textos.HIDRATACAO_DOENCA_RENAL
    assert ind.perda_peso.alvo_semana_16_kg == 88.0
    assert ind.perda_peso.semana_objetivo == 24


def test_persona_imc36() -> None:
    e = _estrategia("persona_imc36.json")
    _comum(e)
    assert e.modo is Modo.PRUDENTE
    assert e.motivos == (textos.IMC_35_OU_MAIS.format(imc="36,0"),)
    assert e.intensidade_pedida is Intensidade.ALTA
    assert e.intensidade_efetiva is Intensidade.LIGEIRA
    assert e.intensidade_limitada_por == (Limitador.MODO,)
    assert textos.MOTIVO_TETO_IMC in (e.explicacao_intensidade or "")
    assert e.restricoes.sem_intervalos
    assert textos.ORIENTACAO_INDIVIDUALIZADA in e.avisos
    assert textos.INTENSIFICACAO_VALIDACAO_MEDICA in e.avisos

    ind = e.indicadores
    assert ind is not None
    assert ind.imc == 36.0
    assert ind.perda_peso.alvo_semana_16_kg == 99.7
    assert ind.perda_peso.semana_objetivo == 51


def test_persona_50_alta() -> None:
    e = _estrategia("persona_50_alta.json")
    _comum(e)
    assert e.modo is Modo.BASE
    assert e.motivos == ()
    assert e.intensidade_pedida is Intensidade.ALTA
    assert e.intensidade_efetiva is Intensidade.MEDIA
    assert e.intensidade_limitada_por == (Limitador.DISPONIBILIDADE,)
    assert "5 dias por semana e 30 min por dia" in (e.explicacao_intensidade or "")
    assert not e.restricoes.sem_intervalos
    assert textos.ORIENTACAO_INDIVIDUALIZADA not in e.avisos

    ind = e.indicadores
    assert ind is not None
    assert ind.proteina.nota is None  # sem condições: sem a nota dos 1,5 g/kg
    assert ind.perda_peso.ritmo_maximo_kg_semana == 0.47  # 0,5 % de 94 kg
    assert ind.perda_peso.alvo_semana_16_kg == 86.5
    assert ind.perda_peso.semana_objetivo == 20


def test_persona_osteoporose() -> None:
    e = _estrategia("persona_osteoporose.json")
    assert e.pode_gerar_plano
    assert e.modo is Modo.PRUDENTE
    assert e.motivos == (textos.OSTEOPOROSE_COM_RISCO,)
    assert e.intensidade_efetiva is Intensidade.MEDIA
    assert e.usar_frequencia_cardiaca  # medicação «não»
    assert e.modulo_gordura_visceral
    r = e.restricoes
    assert r.sem_impacto and r.sem_intervalos
    assert r.sem_flexao_tronco_com_carga
    assert r.equilibrio_com_apoio
    assert r.zonas_regressao == ()
    assert r.contraindicacoes == ("osteoporose",)
    assert textos.ORIENTACAO_INDIVIDUALIZADA in e.avisos

    ind = e.indicadores
    assert ind is not None
    assert ind.perda_peso.realista
    assert ind.perda_peso.alvo_semana_16_kg == 66.0


def test_contraindicacoes_e_equipamento_da_persona_teste() -> None:
    r = _estrategia("persona_teste.json").restricoes
    assert r.contraindicacoes == ("hipertensao", "joelhos")
    assert [str(x) for x in r.equipamento] == ["cadeira_firme", "halteres", "passadeira"]
