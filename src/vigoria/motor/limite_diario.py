"""Limite de planos por utilizador e por dia (Fase 10D; VIGORIA_PLANOS_POR_DIA, 3 por omissão).

O dia é o de Lisboa (a meia-noite em Portugal), não o UTC. Conta cada pedido de geração,
mesmo que falhe ou que o plano seja apagado depois (dados/repositorios.py: geracoes_desde).
Funções puras: a data de «agora» entra sempre como argumento.
"""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

LISBOA = ZoneInfo("Europe/Lisbon")


def inicio_do_dia(agora: datetime) -> datetime:
    """A meia-noite de hoje em Lisboa, em UTC (para comparar com as datas guardadas)."""
    hoje = agora.astimezone(LISBOA).date()
    return datetime.combine(hoje, time(0), tzinfo=LISBOA).astimezone(UTC)


def pode_gerar(feitas_hoje: int, limite: int) -> bool:
    """`limite` 0: sem limite."""
    return limite == 0 or feitas_hoje < limite
