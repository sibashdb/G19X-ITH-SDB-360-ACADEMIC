"""La bitácora y los correos aceptan lo que publica negociacion.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_actividad_origen"), "actividad", type_="check")
    op.create_check_constraint(
        op.f("ck_actividad_origen"),
        "actividad",
        "origen IN ('keycloak', 'proveedores', 'administracion', 'inteligencia', 'negociacion')",
    )
    op.drop_constraint(op.f("ck_correo_enviado_tipo"), "correo_enviado", type_="check")
    op.create_check_constraint(
        op.f("ck_correo_enviado_tipo"),
        "correo_enviado",
        "tipo IN ('invitacion', 'restablecimiento', 'negociacion')",
    )
    # Las invitaciones a negociar van a proveedores, que no son usuarios de Keycloak.
    op.alter_column("correo_enviado", "usuario_id", existing_type=sa.String(64), nullable=True)


def downgrade() -> None:
    # Falla si ya hay registros de negociación: la bitácora no se borra.
    op.alter_column("correo_enviado", "usuario_id", existing_type=sa.String(64), nullable=False)
    op.drop_constraint(op.f("ck_correo_enviado_tipo"), "correo_enviado", type_="check")
    op.create_check_constraint(
        op.f("ck_correo_enviado_tipo"),
        "correo_enviado",
        "tipo IN ('invitacion', 'restablecimiento')",
    )
    op.drop_constraint(op.f("ck_actividad_origen"), "actividad", type_="check")
    op.create_check_constraint(
        op.f("ck_actividad_origen"),
        "actividad",
        "origen IN ('keycloak', 'proveedores', 'administracion', 'inteligencia')",
    )
