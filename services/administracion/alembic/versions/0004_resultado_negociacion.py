"""Los correos aceptan el resultado de una negociación.

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
    # «resultado_negociacion» mide 21 caracteres y la columna, 20.
    op.alter_column("correo_enviado", "tipo", existing_type=sa.String(20), type_=sa.String(30))
    op.drop_constraint(op.f("ck_correo_enviado_tipo"), "correo_enviado", type_="check")
    op.create_check_constraint(
        op.f("ck_correo_enviado_tipo"),
        "correo_enviado",
        "tipo IN ('invitacion', 'restablecimiento', 'negociacion', 'resultado_negociacion')",
    )


def downgrade() -> None:
    # Falla si ya hay avisos de resultado: los correos no se borran.
    op.drop_constraint(op.f("ck_correo_enviado_tipo"), "correo_enviado", type_="check")
    op.create_check_constraint(
        op.f("ck_correo_enviado_tipo"),
        "correo_enviado",
        "tipo IN ('invitacion', 'restablecimiento', 'negociacion')",
    )
    op.alter_column("correo_enviado", "tipo", existing_type=sa.String(30), type_=sa.String(20))
