"""Esquema inicial de negociacion: eventos, sesiones, historial, bitácora, copias y outbox.

Revision ID: 0001
Revises:
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDEN = sa.text("nextval('orden')")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE folio_evento")
    op.execute("CREATE SEQUENCE orden")
    op.create_table(
        "proveedor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("categorias", postgresql.ARRAY(sa.String(20)), nullable=False),
        sa.Column("contacto_nombre", sa.String(120), nullable=False),
        sa.Column("contacto_email", sa.String(254), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
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
        "evento",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("folio", sa.String(20), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("titulo", sa.String(120), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("plazo_meses", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("fecha_limite", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rondas_max", sa.Integer(), nullable=False),
        sa.Column("estilo", sa.String(10), nullable=False),
        sa.Column("contrato_origen_id", sa.Uuid(), nullable=True),
        sa.Column("proveedor_vigente_id", sa.Uuid(), nullable=True),
        sa.Column("invitados", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("foto", postgresql.JSONB(), nullable=False),
        sa.Column("motivo_cancelacion", sa.String(500), nullable=True),
        sa.Column("creado_por_id", sa.String(64), nullable=False),
        sa.Column("creado_por_nombre", sa.String(200), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cerrado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("tipo IN ('compra', 'renovacion')", name=op.f("ck_evento_tipo")),
        sa.CheckConstraint(
            "estado IN ('borrador', 'abierto', 'en_evaluacion', 'cancelado')",
            name=op.f("ck_evento_estado"),
        ),
        sa.CheckConstraint(
            "estilo IN ('firme', 'balanceado', 'flexible')", name=op.f("ck_evento_estilo")
        ),
        sa.CheckConstraint("rondas_max BETWEEN 2 AND 12", name=op.f("ck_evento_rondas")),
        sa.CheckConstraint("plazo_meses BETWEEN 1 AND 60", name=op.f("ck_evento_plazo")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evento")),
        sa.UniqueConstraint("folio", name=op.f("uq_evento_folio")),
    )
    op.create_index("ix_evento_estado", "evento", ["estado"])
    op.create_table(
        "linea",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evento_id", sa.Uuid(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("codigo_servicio", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=False),
        sa.Column("precio_vigente", sa.Numeric(14, 4), nullable=True),
        sa.Column("ideal", sa.Numeric(14, 4), nullable=True),
        sa.Column("limite", sa.Numeric(14, 4), nullable=True),
        sa.Column("referencia", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint("cantidad > 0", name=op.f("ck_linea_cantidad")),
        sa.ForeignKeyConstraint(
            ["evento_id"], ["evento.id"], name=op.f("fk_linea_evento_id_evento")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_linea")),
        sa.UniqueConstraint("evento_id", "orden", name=op.f("uq_linea_evento_id_orden")),
    )
    op.create_table(
        "palanca",
        sa.Column("evento_id", sa.Uuid(), nullable=False),
        sa.Column("clave", sa.String(30), nullable=False),
        sa.Column("peso", sa.Integer(), nullable=False),
        sa.Column("ideal", sa.Numeric(14, 4), nullable=True),
        sa.Column("limite", sa.Numeric(14, 4), nullable=True),
        sa.CheckConstraint(
            "clave IN ('precio', 'plazo_meses', 'plazo_pago_dias', 'sla_disponibilidad', "
            "'tope_aumento_pct', 'cuota_implementacion')",
            name=op.f("ck_palanca_clave"),
        ),
        sa.CheckConstraint("peso BETWEEN 0 AND 100", name=op.f("ck_palanca_peso")),
        sa.ForeignKeyConstraint(
            ["evento_id"], ["evento.id"], name=op.f("fk_palanca_evento_id_evento")
        ),
        sa.PrimaryKeyConstraint("evento_id", "clave", name=op.f("pk_palanca")),
    )
    op.create_table(
        "sesion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evento_id", sa.Uuid(), nullable=False),
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("proveedor_nombre", sa.String(200), nullable=False),
        sa.Column("destinatario", sa.String(254), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("modo", sa.String(10), nullable=False),
        sa.Column("ronda", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("correo_estado", sa.String(10), nullable=False),
        sa.Column("correo_error", sa.String(500), nullable=True),
        sa.Column("correo_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fuera_de_limites", sa.Boolean(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "estado IN ('invitada', 'activa', 'acuerdo_tentativo', 'sin_acuerdo', 'expirada', "
            "'escalada')",
            name=op.f("ck_sesion_estado"),
        ),
        sa.CheckConstraint("modo IN ('agente', 'comprador')", name=op.f("ck_sesion_modo")),
        sa.CheckConstraint(
            "correo_estado IN ('pendiente', 'enviado', 'fallido')",
            name=op.f("ck_sesion_correo_estado"),
        ),
        sa.ForeignKeyConstraint(
            ["evento_id"], ["evento.id"], name=op.f("fk_sesion_evento_id_evento")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sesion")),
        sa.UniqueConstraint(
            "evento_id", "proveedor_id", name=op.f("uq_sesion_evento_id_proveedor_id")
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sesion_token_hash")),
    )
    op.create_table(
        "oferta",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sesion_id", sa.Uuid(), nullable=False),
        sa.Column("secuencia", sa.BigInteger(), server_default=ORDEN, nullable=False),
        sa.Column("autor", sa.String(10), nullable=False),
        sa.Column("ronda", sa.Integer(), nullable=False),
        sa.Column("valores", postgresql.JSONB(), nullable=False),
        sa.Column("utilidad", sa.Numeric(6, 4), nullable=False),
        sa.Column("valida", sa.Boolean(), nullable=False),
        sa.Column("origen", sa.String(12), nullable=False),
        sa.Column("fuera_de_limites_confirmada", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "autor IN ('proveedor', 'agente', 'comprador')", name=op.f("ck_oferta_autor")
        ),
        sa.CheckConstraint("origen IN ('formulario', 'texto')", name=op.f("ck_oferta_origen")),
        sa.ForeignKeyConstraint(
            ["sesion_id"], ["sesion.id"], name=op.f("fk_oferta_sesion_id_sesion")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oferta")),
    )
    op.create_index("ix_oferta_sesion_id_secuencia", "oferta", ["sesion_id", "secuencia"])
    op.create_table(
        "mensaje",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sesion_id", sa.Uuid(), nullable=False),
        sa.Column("secuencia", sa.BigInteger(), server_default=ORDEN, nullable=False),
        sa.Column("autor", sa.String(10), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("ronda", sa.Integer(), nullable=False),
        sa.Column("oferta_id", sa.Uuid(), nullable=True),
        sa.Column("clave_idempotencia", sa.String(64), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "autor IN ('proveedor', 'agente', 'comprador', 'sistema')",
            name=op.f("ck_mensaje_autor"),
        ),
        sa.ForeignKeyConstraint(
            ["sesion_id"], ["sesion.id"], name=op.f("fk_mensaje_sesion_id_sesion")
        ),
        sa.ForeignKeyConstraint(
            ["oferta_id"], ["oferta.id"], name=op.f("fk_mensaje_oferta_id_oferta")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mensaje")),
        sa.UniqueConstraint(
            "sesion_id",
            "clave_idempotencia",
            name=op.f("uq_mensaje_sesion_id_clave_idempotencia"),
        ),
    )
    op.create_index("ix_mensaje_sesion_id_secuencia", "mensaje", ["sesion_id", "secuencia"])
    op.create_table(
        "bitacora",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_tipo", sa.String(10), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("actor_nombre", sa.String(200), nullable=False),
        sa.Column("accion", sa.String(60), nullable=False),
        sa.Column("evento_id", sa.Uuid(), nullable=True),
        sa.Column("sesion_id", sa.Uuid(), nullable=True),
        sa.Column("detalle", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "actor_tipo IN ('comprador', 'proveedor', 'agente', 'sistema')",
            name=op.f("ck_bitacora_actor_tipo"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bitacora")),
    )
    op.create_index("ix_bitacora_evento_id", "bitacora", ["evento_id"])
    op.create_index("ix_bitacora_sesion_id", "bitacora", ["sesion_id"])
    op.create_table(
        "evento_procesado",
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_evento_procesado")),
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

    # El rol "negociacion" (usuario de la aplicación) lo crea infra/postgres/negociacion.sh.
    # El historial (bitácora, mensajes y ofertas) es de solo inserción; el borrador reemplaza sus
    # líneas y palancas, y por eso solo ahí hay DELETE.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON evento, sesion, proveedor, servicio, outbox TO negociacion"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON linea, palanca TO negociacion")
    op.execute("GRANT SELECT, INSERT ON mensaje, oferta, bitacora, evento_procesado TO negociacion")
    op.execute("GRANT USAGE ON SEQUENCE folio_evento, orden TO negociacion")


def downgrade() -> None:
    op.drop_index("ix_outbox_pendientes", table_name="outbox")
    op.drop_table("outbox")
    op.drop_table("evento_procesado")
    op.drop_index("ix_bitacora_sesion_id", table_name="bitacora")
    op.drop_index("ix_bitacora_evento_id", table_name="bitacora")
    op.drop_table("bitacora")
    op.drop_index("ix_mensaje_sesion_id_secuencia", table_name="mensaje")
    op.drop_table("mensaje")
    op.drop_index("ix_oferta_sesion_id_secuencia", table_name="oferta")
    op.drop_table("oferta")
    op.drop_table("sesion")
    op.drop_table("palanca")
    op.drop_table("linea")
    op.drop_index("ix_evento_estado", table_name="evento")
    op.drop_table("evento")
    op.drop_table("servicio")
    op.drop_table("proveedor")
    op.execute("DROP SEQUENCE orden")
    op.execute("DROP SEQUENCE folio_evento")
