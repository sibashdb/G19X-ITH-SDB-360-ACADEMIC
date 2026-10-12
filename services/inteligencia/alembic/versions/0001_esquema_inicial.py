"""Esquema inicial de inteligencia: copia local, idempotencia, configuración, modelos y outbox.

Revision ID: 0001
Revises:
Create Date: 2026-10-10
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
        "proveedor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rfc", sa.String(13), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("tamano", sa.String(10), nullable=False),
        sa.Column("categorias", postgresql.ARRAY(sa.String(20)), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proveedor")),
    )
    op.create_table(
        "servicio",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_servicio")),
        sa.UniqueConstraint("codigo", name=op.f("uq_servicio_codigo")),
    )
    op.create_table(
        "tipo_cambio",
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("usd_mxn", sa.Numeric(10, 4), nullable=False),
        sa.PrimaryKeyConstraint("periodo", name=op.f("pk_tipo_cambio")),
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
        sa.Column("recibido_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato")),
    )
    op.create_index(op.f("ix_contrato_proveedor_id"), "contrato", ["proveedor_id"])
    op.create_table(
        "linea_contrato",
        sa.Column("contrato_id", sa.Uuid(), nullable=False),
        sa.Column("codigo_servicio", sa.String(30), nullable=False),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(14, 4), nullable=False),
        sa.ForeignKeyConstraint(
            ["contrato_id"],
            ["contrato.id"],
            name=op.f("fk_linea_contrato_contrato_id_contrato"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("contrato_id", "codigo_servicio", name=op.f("pk_linea_contrato")),
    )
    op.create_table(
        "desempeno",
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("sla_cumplimiento_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("tiempo_resolucion_h", sa.Numeric(8, 2), nullable=False),
        sa.Column("incidentes_criticos", sa.Integer(), nullable=False),
        sa.Column("entregas_a_tiempo_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("satisfaccion", sa.Numeric(3, 2), nullable=False),
        sa.PrimaryKeyConstraint("proveedor_id", "periodo", name=op.f("pk_desempeno")),
    )
    op.create_table(
        "evento_procesado",
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_evento_procesado")),
    )
    op.create_table(
        "configuracion",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("peso_sla", sa.Integer(), nullable=False),
        sa.Column("peso_resolucion", sa.Integer(), nullable=False),
        sa.Column("peso_incidentes", sa.Integer(), nullable=False),
        sa.Column("peso_entregas", sa.Integer(), nullable=False),
        sa.Column("peso_satisfaccion", sa.Integer(), nullable=False),
        sa.Column("umbral_riesgo", sa.Integer(), nullable=False),
        sa.Column("inflacion_anual", sa.Numeric(5, 2), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actualizado_por", sa.String(200), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_configuracion_unica")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuracion")),
    )
    op.create_table(
        "modelo_benchmark",
        sa.Column("version", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("entrenado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("origen", sa.String(10), nullable=False),
        sa.Column("actor_nombre", sa.String(200), nullable=False),
        sa.Column("observaciones", sa.Integer(), nullable=False),
        sa.Column("datos_hasta", sa.Date(), nullable=False),
        sa.Column("mape", sa.Numeric(8, 6), nullable=False),
        sa.Column("mape_linea_base", sa.Numeric(8, 6), nullable=False),
        sa.Column("cobertura", sa.Numeric(8, 6), nullable=False),
        sa.Column("pinball", sa.Numeric(10, 6), nullable=False),
        sa.Column("promovido", sa.Boolean(), nullable=False),
        sa.Column("artefacto", sa.String(300), nullable=True),
        sa.CheckConstraint(
            "origen IN ('manual', 'automatico')", name=op.f("ck_modelo_benchmark_origen")
        ),
        sa.PrimaryKeyConstraint("version", name=op.f("pk_modelo_benchmark")),
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

    op.execute(
        "INSERT INTO configuracion (id, peso_sla, peso_resolucion, peso_incidentes, "
        "peso_entregas, peso_satisfaccion, umbral_riesgo, inflacion_anual) "
        "VALUES (1, 30, 20, 20, 15, 15, 40, 4.50)"
    )
    # El rol "inteligencia" (usuario de la aplicación) lo crea infra/postgres/inteligencia.sh.
    # La aplicación nunca borra: la copia local solo se inserta o se actualiza.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON proveedor, servicio, tipo_cambio, contrato, "
        "linea_contrato, desempeno, modelo_benchmark, outbox TO inteligencia"
    )
    op.execute("GRANT SELECT, UPDATE ON configuracion TO inteligencia")
    op.execute("GRANT SELECT, INSERT ON evento_procesado TO inteligencia")


def downgrade() -> None:
    op.drop_index("ix_outbox_pendientes", table_name="outbox")
    op.drop_table("outbox")
    op.drop_table("modelo_benchmark")
    op.drop_table("configuracion")
    op.drop_table("evento_procesado")
    op.drop_table("desempeno")
    op.drop_table("linea_contrato")
    op.drop_index(op.f("ix_contrato_proveedor_id"), table_name="contrato")
    op.drop_table("contrato")
    op.drop_table("tipo_cambio")
    op.drop_table("servicio")
    op.drop_table("proveedor")
