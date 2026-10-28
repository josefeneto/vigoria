"""Elegibilidade e modo do plano (REGRAS_DOMINIO §1 e tabela 1.1). Funções puras, sem LLM.

Só usa as escolhas fechadas do questionário: o texto livre nunca é interpretado.
As consequências adicionais de cada linha da tabela 1.1 ficam para a estratégia.
"""

from enum import StrEnum
from typing import assert_never

from pydantic import BaseModel, ConfigDict

from vigoria.modelos.questionario import (
    Condicao,
    Gravidade,
    Intensidade,
    Limitacao,
    Questionario,
    SimNaoNaoSei,
)
from vigoria.regras import textos
from vigoria.regras.calculos import calcular_imc, imc_leva_a_prudente

IDADE_MINIMA = 18


class Modo(StrEnum):
    NAO_ELEGIVEL = "nao_elegivel"
    PRUDENTE = "prudente"
    BASE = "base"


class Elegibilidade(BaseModel):
    """Modo do plano, motivos e teto de intensidade da secção 1."""

    model_config = ConfigDict(frozen=True)

    modo: Modo
    motivos: tuple[str, ...]  # porque não é elegível ou porque está em modo prudente
    intensidade_maxima: Intensidade | None  # None = sem teto (versão-base) ou sem plano
    usar_frequencia_cardiaca: bool  # falso com medicação «sim» ou «não sei»


def avaliar_elegibilidade(q: Questionario) -> Elegibilidade:
    """Aplica a secção 1 e a tabela 1.1; vale sempre a situação mais restritiva."""
    usar_fc = q.medicacao_afeta_fc is SimNaoNaoSei.NAO

    impedimentos = motivos_nao_elegivel(q)
    if impedimentos:
        return Elegibilidade(
            modo=Modo.NAO_ELEGIVEL,
            motivos=tuple(impedimentos),
            intensidade_maxima=None,
            usar_frequencia_cardiaca=usar_fc,
        )

    motivos = [*motivos_condicoes(q), *motivos_limitacoes(q)]
    imc = calcular_imc(q.peso_kg, q.altura_cm)
    if imc_leva_a_prudente(imc):
        motivo_imc = textos.IMC_35_OU_MAIS.format(imc=f"{imc:.1f}".replace(".", ","))
        return Elegibilidade(
            modo=Modo.PRUDENTE,
            motivos=(motivo_imc, *motivos),
            intensidade_maxima=Intensidade.LIGEIRA,
            usar_frequencia_cardiaca=usar_fc,
        )
    if motivos:
        return Elegibilidade(
            modo=Modo.PRUDENTE,
            motivos=tuple(motivos),
            intensidade_maxima=Intensidade.MEDIA,
            usar_frequencia_cardiaca=usar_fc,
        )
    return Elegibilidade(
        modo=Modo.BASE, motivos=(), intensidade_maxima=None, usar_frequencia_cardiaca=usar_fc
    )


def motivos_nao_elegivel(q: Questionario) -> list[str]:
    """Idade < 18 ou gravidez: não gera plano."""
    motivos = []
    if q.idade < IDADE_MINIMA:
        motivos.append(textos.MENOR_IDADE)
    if Condicao.GRAVIDEZ in q.condicoes:
        motivos.append(textos.GRAVIDEZ)
    return motivos


def motivos_condicoes(q: Questionario) -> list[str]:
    """Condições da tabela 1.1 que levam a modo prudente, linha a linha."""
    motivos = []
    for condicao in q.condicoes:
        match condicao:
            case Condicao.HIPERTENSAO:
                if not q.condicoes_controladas[condicao]:
                    motivos.append(textos.HIPERTENSAO_NAO_CONTROLADA)
            case Condicao.DIABETES:
                if q.condicoes_controladas[condicao]:
                    motivos.append(textos.DIABETES_CONTROLADA)
                else:
                    motivos.append(textos.DIABETES_NAO_CONTROLADA)
            case Condicao.DOENCA_CARDIOVASCULAR:
                motivos.append(textos.DOENCA_CARDIOVASCULAR)
            case Condicao.DOENCA_RESPIRATORIA:
                motivos.append(textos.DOENCA_RESPIRATORIA)
            case Condicao.DOENCA_RENAL:
                motivos.append(textos.DOENCA_RENAL)
            case Condicao.OSTEOPOROSE:
                if q.osteoporose_risco is SimNaoNaoSei.SIM:
                    motivos.append(textos.OSTEOPOROSE_COM_RISCO)
                elif q.osteoporose_risco is SimNaoNaoSei.NAO_SEI:
                    motivos.append(textos.OSTEOPOROSE_RISCO_DESCONHECIDO)
            case Condicao.DOENCA_INFLAMATORIA_INTESTINAL:
                if not q.condicoes_controladas[condicao]:
                    motivos.append(textos.DII_NAO_CONTROLADA)
            case Condicao.DOR_ARTICULAR_PERSISTENTE:
                motivos.append(textos.DOR_ARTICULAR_PERSISTENTE)
            case Condicao.PROTESE_OU_CIRURGIA_RECENTE:
                motivos.append(textos.PROTESE_OU_CIRURGIA_RECENTE)
            case Condicao.OUTRA:
                motivos.append(textos.CONDICAO_OUTRA)
            case Condicao.GRAVIDEZ | Condicao.NENHUMA:
                pass  # gravidez: tratada em motivos_nao_elegivel
            case _:
                assert_never(condicao)
    return motivos


def motivos_limitacoes(q: Questionario) -> list[str]:
    """Limitações (1.H): prudente se importante; «outra» é sempre prudente."""
    motivos = []
    for limitacao in q.limitacoes:
        match limitacao:
            case (
                Limitacao.JOELHOS
                | Limitacao.ANCAS
                | Limitacao.OMBROS
                | Limitacao.COLUNA
                | Limitacao.EQUILIBRIO
            ):
                if q.limitacoes_gravidade[limitacao] is Gravidade.IMPORTANTE:
                    zona = textos.ZONAS_LIMITACAO[limitacao]
                    motivos.append(textos.LIMITACAO_IMPORTANTE.format(zona=zona))
            case Limitacao.OUTRA:
                motivos.append(textos.LIMITACAO_OUTRA)
            case Limitacao.NENHUMA:
                pass
            case _:
                assert_never(limitacao)
    return motivos
