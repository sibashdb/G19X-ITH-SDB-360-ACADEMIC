"""La bitácora acepta registros que vienen de inteligencia.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_actividad_origen"), "actividad", type_="check")
    op.create_check_constraint(
        op.f("ck_actividad_origen"),
        "actividad",
        "origen IN ('keycloak', 'proveedores', 'administracion', 'inteligencia')",
    )


def downgrade() -> None:
    # Falla si ya hay registros de inteligencia: la bitácora no se borra.
    op.drop_constraint(op.f("ck_actividad_origen"), "actividad", type_="check")
    op.create_check_constraint(
        op.f("ck_actividad_origen"),
        "actividad",
        "origen IN ('keycloak', 'proveedores', 'administracion')",
    )
