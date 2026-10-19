"""Eventos ya aplicados, para que uno repetido no se aplique dos veces (negociacion.adjudicada).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evento_procesado",
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_evento_procesado")),
    )


def downgrade() -> None:
    op.drop_table("evento_procesado")
