"""O que o plano prevê para hoje (cartão «Hoje» da página do plano, Fase 8D). Sem LLM.

O dia chega já na hora de Portugal continental (paginas/comum.hoje). Pela data, a semana do
plano diz se ainda está nas 16 semanas; pelo dia da semana, a entrada da semana-tipo diz se
há sessão (duração > 0) ou não.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from vigoria.modelos.plano import DiaSemana, SessaoDia
from vigoria.regras.progresso import em_manutencao, fase_da_semana, semana_do_plano


class TipoHoje(StrEnum):
    SESSAO = "sessao"
    DESCANSO = "descanso"  # dia sem sessão na semana-tipo (duração 0)
    MANUTENCAO = "manutencao"  # depois da semana 16


@dataclass(frozen=True)
class Hoje:
    tipo: TipoHoje
    dia: DiaSemana
    semana: int
    fase: int | None  # None na manutenção
    sessao: SessaoDia | None  # a entrada da semana-tipo deste dia, se existir


def dia_da_semana(dia: date) -> DiaSemana:
    """Segunda-feira = DiaSemana.SEGUNDA (a ordem do enum é a de date.weekday)."""
    return list(DiaSemana)[dia.weekday()]


def sessao_de_hoje(semana_tipo: Sequence[SessaoDia], inicio: date, dia: date) -> Hoje:
    """O que fazer em `dia`, num plano que começou em `inicio`.

    Um dia anterior ao início (relógio do servidor adiantado) conta como a semana 1.
    """
    semana = semana_do_plano(inicio, max(dia, inicio))
    nome = dia_da_semana(dia)
    sessao = next((s for s in semana_tipo if s.dia is nome), None)
    if em_manutencao(semana):
        return Hoje(TipoHoje.MANUTENCAO, nome, semana, None, sessao)
    tipo = TipoHoje.SESSAO if sessao is not None and sessao.duracao_min > 0 else TipoHoje.DESCANSO
    return Hoje(tipo, nome, semana, fase_da_semana(semana), sessao)
