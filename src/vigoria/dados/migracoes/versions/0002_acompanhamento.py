"""Acompanhamento (Fase 7): preferências na conta e registos ligados à semana de um plano.

A tabela registo_progresso estava vazia desde a Fase 6 (nenhum código lhe escrevia). Se
houvesse linhas, seriam removidas: não têm plano nem semana a que se ligar.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _copiar_preferencias() -> None:
    """Quem já tem conta fica com o que escolheu nas últimas respostas ao questionário."""
    questionario = sa.table(
        "questionario",
        sa.column("id", sa.Integer()),
        sa.column("utilizador_id", sa.Integer()),
        sa.column("respostas", sa.JSON().with_variant(postgresql.JSONB(), "postgresql")),
    )
    utilizador = sa.table(
        "utilizador",
        sa.column("id", sa.Integer()),
        sa.column("acompanhamento_ativo", sa.Boolean()),
        sa.column("frequencia_registo", sa.String()),
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
            .values(
                acompanhamento_ativo=respostas.get("acompanhamento_ativo", True),
                frequencia_registo=respostas.get("frequencia_registo", "semanal"),
            )
        )


def upgrade() -> None:
    """Upgrade schema."""
    # Sem batch_alter_table em «utilizador»: no SQLite, recriar a tabela apagaria a antiga, e o
    # ON DELETE CASCADE levaria os questionários e os planos (testado em tests/test_dados.py).
    op.add_column(
        "utilizador",
        sa.Column("acompanhamento_ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "utilizador",
        sa.Column(
            "frequencia_registo", sa.String(length=20), server_default="semanal", nullable=False
        ),
    )
    _copiar_preferencias()

    op.execute("DELETE FROM registo_progresso")
    with op.batch_alter_table("registo_progresso", schema=None) as batch_op:
        batch_op.add_column(sa.Column("plano_id", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("semana", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("alterado_em", sa.DateTime(timezone=True), nullable=False))
        batch_op.create_foreign_key(
            "fk_registo_progresso_plano", "plano", ["plano_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index(batch_op.f("ix_registo_progresso_plano_id"), ["plano_id"])
        batch_op.create_unique_constraint("uq_registo_plano_semana", ["plano_id", "semana"])


def downgrade() -> None:
    """Downgrade schema. Os registos não sobrevivem: sem plano nem semana perdem o sentido."""
    op.execute("DELETE FROM registo_progresso")
    with op.batch_alter_table("registo_progresso", schema=None) as batch_op:
        batch_op.drop_constraint("uq_registo_plano_semana", type_="unique")
        batch_op.drop_index(batch_op.f("ix_registo_progresso_plano_id"))
        batch_op.drop_constraint("fk_registo_progresso_plano", type_="foreignkey")
        batch_op.drop_column("alterado_em")
        batch_op.drop_column("semana")
        batch_op.drop_column("plano_id")
    op.drop_column("utilizador", "frequencia_registo")
    op.drop_column("utilizador", "acompanhamento_ativo")
