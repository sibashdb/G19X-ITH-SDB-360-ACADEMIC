"""Esquema inicial del servicio de proveedores.

Revision ID: 0001
Revises:
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DINERO = sa.Numeric(14, 4)
PORCENTAJE = sa.Numeric(5, 2)


def upgrade() -> None:
    op.create_table(
        "proveedor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rfc", sa.String(13), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("tamano", sa.String(10), nullable=False),
        sa.Column("categorias", postgresql.ARRAY(sa.String(20)), nullable=False),
        sa.Column("contacto_nombre", sa.String(120), nullable=False),
        sa.Column("contacto_email", sa.String(254), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tamano IN ('micro', 'pequena', 'mediana', 'grande')",
            name=op.f("ck_proveedor_tamano"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proveedor")),
        sa.UniqueConstraint("rfc", name=op.f("uq_proveedor_rfc")),
    )
    op.create_table(
        "servicio_catalogo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.CheckConstraint(
            "categoria IN ('licencia_saas', 'nube', 'consultoria', 'soporte')",
            name=op.f("ck_servicio_catalogo_categoria"),
        ),
        sa.CheckConstraint("moneda IN ('MXN', 'USD')", name=op.f("ck_servicio_catalogo_moneda")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_servicio_catalogo")),
        sa.UniqueConstraint("codigo", name=op.f("uq_servicio_catalogo_codigo")),
    )
    op.create_table(
        "contrato",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("folio", sa.String(30), nullable=False),
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("plazo_pago_dias", sa.Integer(), nullable=False),
        sa.Column("sla_disponibilidad", PORCENTAJE, nullable=True),
        sa.Column("tope_aumento_pct", PORCENTAJE, nullable=True),
        sa.Column("cuota_implementacion", DINERO, nullable=False),
        sa.CheckConstraint("tipo IN ('nuevo', 'renovacion')", name=op.f("ck_contrato_tipo")),
        sa.CheckConstraint("moneda IN ('MXN', 'USD')", name=op.f("ck_contrato_moneda")),
        sa.CheckConstraint("fecha_fin > fecha_inicio", name=op.f("ck_contrato_vigencia")),
        sa.ForeignKeyConstraint(
            ["proveedor_id"], ["proveedor.id"], name=op.f("fk_contrato_proveedor_id_proveedor")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato")),
        sa.UniqueConstraint("folio", name=op.f("uq_contrato_folio")),
    )
    op.create_index(op.f("ix_contrato_proveedor_id"), "contrato", ["proveedor_id"])
    op.create_table(
        "linea_contrato",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contrato_id", sa.Uuid(), nullable=False),
        sa.Column("servicio_id", sa.Uuid(), nullable=False),
        sa.Column("cantidad", DINERO, nullable=False),
        sa.Column("precio_unitario", DINERO, nullable=False),
        sa.CheckConstraint(
            "cantidad > 0 AND precio_unitario > 0", name=op.f("ck_linea_contrato_positivos")
        ),
        sa.ForeignKeyConstraint(
            ["contrato_id"],
            ["contrato.id"],
            name=op.f("fk_linea_contrato_contrato_id_contrato"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["servicio_id"],
            ["servicio_catalogo.id"],
            name=op.f("fk_linea_contrato_servicio_id_servicio_catalogo"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_linea_contrato")),
    )
    op.create_index(op.f("ix_linea_contrato_contrato_id"), "linea_contrato", ["contrato_id"])
    op.create_table(
        "registro_desempeno",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("sla_cumplimiento_pct", PORCENTAJE, nullable=False),
        sa.Column("tiempo_resolucion_h", sa.Numeric(8, 2), nullable=False),
        sa.Column("incidentes_criticos", sa.Integer(), nullable=False),
        sa.Column("entregas_a_tiempo_pct", PORCENTAJE, nullable=False),
        sa.Column("satisfaccion", sa.Numeric(3, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["proveedor_id"],
            ["proveedor.id"],
            name=op.f("fk_registro_desempeno_proveedor_id_proveedor"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registro_desempeno")),
        sa.UniqueConstraint(
            "proveedor_id", "periodo", name=op.f("uq_registro_desempeno_proveedor_id")
        ),
    )
    op.create_table(
        "tipo_cambio",
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("usd_mxn", sa.Numeric(10, 4), nullable=False),
        sa.PrimaryKeyConstraint("periodo", name=op.f("pk_tipo_cambio")),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("ocurrido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
    )
    op.create_index(
        "ix_outbox_pendientes",
        "outbox",
        ["ocurrido_en"],
        postgresql_where=sa.text("publicado_en IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_pendientes", table_name="outbox")
    op.drop_table("outbox")
    op.drop_table("tipo_cambio")
    op.drop_table("registro_desempeno")
    op.drop_index(op.f("ix_linea_contrato_contrato_id"), table_name="linea_contrato")
    op.drop_table("linea_contrato")
    op.drop_index(op.f("ix_contrato_proveedor_id"), table_name="contrato")
    op.drop_table("contrato")
    op.drop_table("servicio_catalogo")
    op.drop_table("proveedor")
