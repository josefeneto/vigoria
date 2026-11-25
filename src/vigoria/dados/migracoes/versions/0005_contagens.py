"""Contagens por dia, sem dados pessoais, para a página Gestão (25/11/2026).

As contas e os planos que já existem entram nas contagens pelo dia em que foram criados
(os de contas já apagadas perderam-se: não há como os recuperar).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-25 12:00:00

"""

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LISBOA = ZoneInfo("Europe/Lisbon")


def _dia(instante: datetime) -> object:
    if instante.tzinfo is None:  # o SQLite devolve sem fuso
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone(LISBOA).date()


def upgrade() -> None:
    """Upgrade schema."""
    contagem = op.create_table(
        "contagem_diaria",
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("dia", "tipo"),
    )
    ligacao = op.get_bind()
    totais: Counter[tuple[object, str]] = Counter()
    for tabela, tipo in (("utilizador", "conta_criada"), ("plano", "plano_gerado")):
        criado_em = sa.table(tabela, sa.column("criado_em", sa.DateTime(timezone=True)))
        for (instante,) in ligacao.execute(sa.select(criado_em.c.criado_em)):
            if instante is not None:
                totais[(_dia(instante), tipo)] += 1
    if totais:
        op.bulk_insert(
            contagem, [{"dia": d, "tipo": t, "total": n} for (d, t), n in sorted(totais.items())]
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("contagem_diaria")
