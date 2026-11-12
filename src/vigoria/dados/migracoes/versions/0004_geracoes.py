"""Pedidos de geração de plano (Fase 10D): limite de planos por utilizador e por dia.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "geracao_plano",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("utilizador_id", sa.Integer(), nullable=False),
        sa.Column("pedido_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["utilizador_id"], ["utilizador.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_geracao_plano_utilizador_id", "geracao_plano", ["utilizador_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_geracao_plano_utilizador_id", table_name="geracao_plano")
    op.drop_table("geracao_plano")
