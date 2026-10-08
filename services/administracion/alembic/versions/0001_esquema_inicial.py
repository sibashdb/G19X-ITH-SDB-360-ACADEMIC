"""Esquema inicial de administracion: bitácora, correos enviados y cursor de eventos.

Revision ID: 0001
Revises:
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "actividad",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("actor_nombre", sa.String(200), nullable=False),
        sa.Column("tipo", sa.String(60), nullable=False),
        sa.Column("objeto_tipo", sa.String(30), nullable=True),
        sa.Column("objeto_id", sa.String(64), nullable=True),
        sa.Column("objeto_nombre", sa.String(200), nullable=True),
        sa.Column("detalle", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resultado", sa.String(10), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("origen", sa.String(20), nullable=False),
        sa.Column("clave_origen", sa.String(200), nullable=False),
        sa.CheckConstraint("resultado IN ('exito', 'fallo')", name=op.f("ck_actividad_resultado")),
        sa.CheckConstraint(
            "origen IN ('keycloak', 'proveedores', 'administracion')",
            name=op.f("ck_actividad_origen"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actividad")),
        sa.UniqueConstraint("clave_origen", name=op.f("uq_actividad_clave_origen")),
    )
    op.create_index("ix_actividad_fecha", "actividad", ["fecha"])
    op.create_index("ix_actividad_actor_id", "actividad", ["actor_id"])
    op.create_index("ix_actividad_objeto_id", "actividad", ["objeto_id"])

    op.create_table(
        "correo_enviado",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("destinatario", sa.String(254), nullable=False),
        sa.Column("usuario_id", sa.String(64), nullable=False),
        sa.Column("solicitado_por", sa.String(200), nullable=False),
        sa.Column("estado", sa.String(10), nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('invitacion', 'restablecimiento')", name=op.f("ck_correo_enviado_tipo")
        ),
        sa.CheckConstraint(
            "estado IN ('enviado', 'fallido')", name=op.f("ck_correo_enviado_estado")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_correo_enviado")),
    )
    op.create_index("ix_correo_enviado_fecha", "correo_enviado", ["fecha"])

    op.create_table(
        "cursor_eventos",
        sa.Column("nombre", sa.String(30), nullable=False),
        sa.Column("hasta", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("nombre", name=op.f("pk_cursor_eventos")),
    )

    # El rol "administracion" (usuario de la aplicación) lo crea infra/postgres/administracion.sh.
    # La bitácora y el registro de correos son de solo inserción para la aplicación.
    op.execute("GRANT SELECT, INSERT ON actividad, correo_enviado TO administracion")
    op.execute("GRANT SELECT, INSERT, UPDATE ON cursor_eventos TO administracion")


def downgrade() -> None:
    op.drop_table("cursor_eventos")
    op.drop_index("ix_correo_enviado_fecha", table_name="correo_enviado")
    op.drop_table("correo_enviado")
    op.drop_index("ix_actividad_objeto_id", table_name="actividad")
    op.drop_index("ix_actividad_actor_id", table_name="actividad")
    op.drop_index("ix_actividad_fecha", table_name="actividad")
    op.drop_table("actividad")
