"""Pesos de la adjudicación y umbral de aprobación en la configuración.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PESOS = {
    "adjudicacion_costo": "40",
    "adjudicacion_desempeno": "30",
    "adjudicacion_riesgo": "15",
    "adjudicacion_sla": "15",
}


def upgrade() -> None:
    # El server_default rellena la fila única (id = 1) que ya existe.
    for columna, defecto in PESOS.items():
        op.add_column(
            "configuracion",
            sa.Column(columna, sa.Integer(), server_default=sa.text(defecto), nullable=False),
        )
    op.add_column(
        "configuracion",
        sa.Column(
            "umbral_aprobacion",
            sa.Numeric(14, 2),
            server_default=sa.text("500000.00"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("configuracion", "umbral_aprobacion")
    for columna in reversed(PESOS):
        op.drop_column("configuracion", columna)
