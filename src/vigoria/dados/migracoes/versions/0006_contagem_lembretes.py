"""Lembretes já enviados nas contagens da Gestão (26/11/2026).

Sem mudar tabelas: os lembretes que ficaram gravados (lembrete_enviado) entram em
contagem_diaria pelo dia (Lisboa) do envio. Os de planos ou contas já apagados perderam-se.
As falhas, os cancelamentos e as execuções do envio diário só contam daqui para a frente.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-26 12:00:00

"""

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LISBOA = ZoneInfo("Europe/Lisbon")
TIPO = "lembrete_enviado"  # dados/gestao.py, TipoContagem.LEMBRETE_ENVIADO

contagem = sa.table(
    "contagem_diaria",
    sa.column("dia", sa.Date()),
    sa.column("tipo", sa.String(30)),
    sa.column("total", sa.Integer()),
)


def _dia(instante: datetime) -> date:
    if instante.tzinfo is None:  # o SQLite devolve sem fuso
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone(LISBOA).date()


def upgrade() -> None:
    """Upgrade schema."""
    ligacao = op.get_bind()
    enviado = sa.table("lembrete_enviado", sa.column("enviado_em", sa.DateTime(timezone=True)))
    totais: Counter[date] = Counter(
        _dia(instante)
        for (instante,) in ligacao.execute(sa.select(enviado.c.enviado_em))
        if instante is not None
    )
    # Algum já contado pelo código novo (por exemplo, a migração corre depois de um envio)?
    ja = {
        d: n
        for d, n in ligacao.execute(
            sa.select(contagem.c.dia, contagem.c.total).where(contagem.c.tipo == TIPO)
        )
    }
    novos = [{"dia": d, "tipo": TIPO, "total": n} for d, n in sorted(totais.items()) if d not in ja]
    if novos:
        op.bulk_insert(contagem, novos)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        contagem.delete().where(
            contagem.c.tipo.in_(
                ["lembrete_enviado", "lembrete_falhado", "lembretes_cancelados", "envio_diario"]
            )
        )
    )
