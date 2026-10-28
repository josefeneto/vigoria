"""Intensidade efetiva (REGRAS_DOMINIO §3). Funções puras, sem LLM.

Intensidade efetiva = a menor entre a pedida (5.E), o teto do modo (§1) e a
compatível com a disponibilidade (1.J). Se for reduzida, explica porquê numa frase.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from vigoria.modelos.questionario import Intensidade
from vigoria.regras import textos

ORDEM_INTENSIDADE = (Intensidade.LIGEIRA, Intensidade.MEDIA, Intensidade.ALTA)
MINUTOS_MINIMOS = 30
DIAS_ABAIXO_DO_MINIMO = 2  # 1 ou 2 dias: aviso honesto (§3)
MINUTOS_SESSAO_CURTA = 20  # 15 ou 20 min: sessões concentradas no essencial


class Limitador(StrEnum):
    MODO = "modo"
    DISPONIBILIDADE = "disponibilidade"


class AvaliacaoIntensidade(BaseModel):
    """Intensidade efetiva, o que a limitou e a explicação para o utilizador."""

    model_config = ConfigDict(frozen=True)

    pedida: Intensidade
    efetiva: Intensidade
    limitada_por: tuple[Limitador, ...]  # vazio se não foi reduzida
    explicacao: str | None


def intensidade_por_disponibilidade(dias: int, minutos: int) -> Intensidade:
    """Tabela da §3: 6–7 dias ≥ 30 min ⇒ Alta; 4–5 dias ≥ 30 min ⇒ Média; resto ⇒ Ligeira."""
    if dias < 1 or minutos <= 0:
        raise ValueError("dias e minutos têm de ser positivos")
    if minutos < MINUTOS_MINIMOS or dias <= 3:
        return Intensidade.LIGEIRA
    if dias <= 5:
        return Intensidade.MEDIA
    return Intensidade.ALTA


def abaixo_do_minimo(dias: int) -> bool:
    """1 ou 2 dias por semana: abaixo do mínimo recomendado."""
    return dias <= DIAS_ABAIXO_DO_MINIMO


def sessoes_curtas(minutos: int) -> bool:
    """15 ou 20 min/dia: aquecimento curto, 4 a 5 exercícios de força, retorno à calma."""
    return minutos <= MINUTOS_SESSAO_CURTA


def menor(*intensidades: Intensidade) -> Intensidade:
    """A menor das intensidades indicadas."""
    return min(intensidades, key=ORDEM_INTENSIDADE.index)


def calcular_intensidade_efetiva(
    pedida: Intensidade, teto_modo: Intensidade | None, dias: int, minutos: int
) -> AvaliacaoIntensidade:
    """Aplica o mínimo da §3; teto_modo None = versão-base, sem teto."""
    por_disponibilidade = intensidade_por_disponibilidade(dias, minutos)
    tetos = {Limitador.DISPONIBILIDADE: por_disponibilidade}
    if teto_modo is not None:
        tetos[Limitador.MODO] = teto_modo
    efetiva = menor(pedida, *tetos.values())
    if efetiva is pedida:
        return AvaliacaoIntensidade(
            pedida=pedida, efetiva=efetiva, limitada_por=(), explicacao=None
        )

    # Pode haver dois limitadores com o mesmo teto; o do modo (segurança) vem primeiro.
    limitada_por = tuple(lim for lim in Limitador if tetos.get(lim) is efetiva)
    motivos = [_motivo(lim, teto_modo, dias, minutos) for lim in limitada_por]
    explicacao = textos.INTENSIDADE_REDUZIDA.format(
        pedida=textos.NOMES_INTENSIDADE[pedida],
        efetiva=textos.NOMES_INTENSIDADE[efetiva],
        motivo=" e ".join(motivos),
    )
    return AvaliacaoIntensidade(
        pedida=pedida, efetiva=efetiva, limitada_por=limitada_por, explicacao=explicacao
    )


def _motivo(limitador: Limitador, teto_modo: Intensidade | None, dias: int, minutos: int) -> str:
    if limitador is Limitador.DISPONIBILIDADE:
        return textos.MOTIVO_DISPONIBILIDADE.format(
            dias=dias, palavra_dias="dia" if dias == 1 else "dias", minutos=minutos
        )
    # Só o IMC ≥ 35 leva ao teto «Ligeira»; o restante modo prudente leva a «Média» (§1).
    if teto_modo is Intensidade.LIGEIRA:
        return textos.MOTIVO_TETO_IMC
    return textos.MOTIVO_TETO_PRUDENTE
