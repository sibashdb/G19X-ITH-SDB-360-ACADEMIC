"""Nombre completo de la restricción única (proveedor_id, periodo) de registro_desempeno.

La convención de nombres solo incluía la primera columna; ahora incluye todas.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE registro_desempeno RENAME CONSTRAINT "
        "uq_registro_desempeno_proveedor_id TO uq_registro_desempeno_proveedor_id_periodo"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE registro_desempeno RENAME CONSTRAINT "
        "uq_registro_desempeno_proveedor_id_periodo TO uq_registro_desempeno_proveedor_id"
    )
