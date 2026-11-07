"""Lembretes por email (Fase 8): a preferência na conta e os lembretes já enviados.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-07 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _copiar_preferencia() -> None:
    """Quem já tem conta fica com o que escolheu nas últimas respostas ao questionário."""
    questionario = sa.table(
        "questionario",
        sa.column("id", sa.Integer()),
        sa.column("utilizador_id", sa.Integer()),
        sa.column("respostas", sa.JSON().with_variant(postgresql.JSONB(), "postgresql")),
    )
    utilizador = sa.table(
        "utilizador", sa.column("id", sa.Integer()), sa.column("lembretes_email", sa.Boolean())
    )
    ligacao = op.get_bind()
    ultimas: dict[int, dict] = {}
    for uid, respostas in ligacao.execute(
        sa.select(questionario.c.utilizador_id, questionario.c.respostas).order_by(
            questionario.c.id
        )
    ):
        ultimas[uid] = respostas
    for uid, respostas in ultimas.items():
        ligacao.execute(
            utilizador.update()
            .where(utilizador.c.id == uid)
            .values(lembretes_email=bool(respostas.get("lembretes_email", True)))
        )


def upgrade() -> None:
    """Upgrade schema."""
    # Sem batch_alter_table em «utilizador»: no SQLite, recriar a tabela apagaria a antiga, e o
    # ON DELETE CASCADE levaria os questionários e os planos (ver 0002).
    op.add_column(
        "utilizador",
        sa.Column("lembretes_email", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    _copiar_preferencia()
    op.create_table(
        "lembrete_enviado",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("utilizador_id", sa.Integer(), nullable=False),
        sa.Column("plano_id", sa.Integer(), nullable=False),
        sa.Column("semana_inicio", sa.Integer(), nullable=False),
        sa.Column("semana_fim", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plano_id"], ["plano.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["utilizador_id"], ["utilizador.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plano_id", "semana_inicio", "semana_fim", "numero", name="uq_lembrete_periodo_numero"
        ),
    )
    op.create_index("ix_lembrete_enviado_plano_id", "lembrete_enviado", ["plano_id"])
    op.create_index("ix_lembrete_enviado_utilizador_id", "lembrete_enviado", ["utilizador_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_lembrete_enviado_utilizador_id", table_name="lembrete_enviado")
    op.drop_index("ix_lembrete_enviado_plano_id", table_name="lembrete_enviado")
    op.drop_table("lembrete_enviado")
    op.drop_column("utilizador", "lembretes_email")
