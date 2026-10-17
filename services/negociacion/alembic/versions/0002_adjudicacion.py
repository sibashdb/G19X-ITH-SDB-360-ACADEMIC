"""Adjudicación: la tabla de propuestas, tres estados de evento nuevos y el actor aprobador.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADOS_ANTES = "estado IN ('borrador', 'abierto', 'en_evaluacion', 'cancelado')"
ESTADOS_AHORA = (
    "estado IN ('borrador', 'abierto', 'en_evaluacion', 'pendiente_aprobacion', 'adjudicado', "
    "'desierto', 'cancelado')"
)
ACTORES_ANTES = "actor_tipo IN ('comprador', 'proveedor', 'agente', 'sistema')"
ACTORES_AHORA = "actor_tipo IN ('comprador', 'aprobador', 'proveedor', 'agente', 'sistema')"


def upgrade() -> None:
    # "pendiente_aprobacion" mide 19 caracteres: la columna crece de 15 a 20.
    op.alter_column("evento", "estado", type_=sa.String(20), existing_nullable=False)
    op.drop_constraint(op.f("ck_evento_estado"), "evento", type_="check")
    op.create_check_constraint(op.f("ck_evento_estado"), "evento", ESTADOS_AHORA)
    op.add_column("evento", sa.Column("motivo_desierta", sa.String(500), nullable=True))
    op.add_column(
        "sesion", sa.Column("resultado_avisado_en", sa.DateTime(timezone=True), nullable=True)
    )
    op.drop_constraint(op.f("ck_bitacora_actor_tipo"), "bitacora", type_="check")
    op.create_check_constraint(op.f("ck_bitacora_actor_tipo"), "bitacora", ACTORES_AHORA)

    op.create_table(
        "adjudicacion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evento_id", sa.Uuid(), nullable=False),
        sa.Column("sesion_id", sa.Uuid(), nullable=False),
        sa.Column("propuesta_por_id", sa.String(64), nullable=False),
        sa.Column("propuesta_por_nombre", sa.String(200), nullable=False),
        sa.Column("propuesta_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recomendada_sesion_id", sa.Uuid(), nullable=False),
        sa.Column("se_aparta", sa.Boolean(), nullable=False),
        sa.Column("justificacion", sa.String(1000), nullable=True),
        sa.Column("costo_total", sa.Numeric(16, 2), nullable=False),
        sa.Column("costo_total_mxn", sa.Numeric(16, 2), nullable=False),
        sa.Column("requiere_aprobacion", sa.Boolean(), nullable=False),
        sa.Column("motivo_aprobacion", postgresql.ARRAY(sa.String(20)), nullable=False),
        sa.Column("recomendacion", postgresql.JSONB(), nullable=False),
        sa.Column("estado", sa.String(10), nullable=False),
        sa.Column("decidida_por_id", sa.String(64), nullable=True),
        sa.Column("decidida_por_nombre", sa.String(200), nullable=True),
        sa.Column("decidida_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_rechazo", sa.String(500), nullable=True),
        sa.Column("contrato_folio", sa.String(30), nullable=True),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'aprobada', 'rechazada', 'directa')",
            name=op.f("ck_adjudicacion_estado"),
        ),
        sa.CheckConstraint(
            "motivo_aprobacion <@ ARRAY['umbral', 'fuera_de_limites']::varchar[]",
            name=op.f("ck_adjudicacion_motivo_aprobacion"),
        ),
        sa.CheckConstraint(
            "NOT se_aparta OR justificacion IS NOT NULL",
            name=op.f("ck_adjudicacion_justificacion"),
        ),
        sa.ForeignKeyConstraint(
            ["evento_id"], ["evento.id"], name=op.f("fk_adjudicacion_evento_id_evento")
        ),
        sa.ForeignKeyConstraint(
            ["sesion_id"], ["sesion.id"], name=op.f("fk_adjudicacion_sesion_id_sesion")
        ),
        sa.ForeignKeyConstraint(
            ["recomendada_sesion_id"],
            ["sesion.id"],
            name=op.f("fk_adjudicacion_recomendada_sesion_id_sesion"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_adjudicacion")),
    )

    # Las propuestas son historial (también las rechazadas): sin DELETE, y la aplicación solo
    # actualiza las columnas de la decisión; lo propuesto y la foto de la recomendación no cambian.
    op.execute("GRANT SELECT, INSERT ON adjudicacion TO negociacion")
    op.execute(
        "GRANT UPDATE (estado, decidida_por_id, decidida_por_nombre, decidida_en, motivo_rechazo, "
        "contrato_folio) ON adjudicacion TO negociacion"
    )


def downgrade() -> None:
    op.drop_table("adjudicacion")
    op.drop_constraint(op.f("ck_bitacora_actor_tipo"), "bitacora", type_="check")
    op.create_check_constraint(op.f("ck_bitacora_actor_tipo"), "bitacora", ACTORES_ANTES)
    op.drop_column("sesion", "resultado_avisado_en")
    op.drop_column("evento", "motivo_desierta")
    op.drop_constraint(op.f("ck_evento_estado"), "evento", type_="check")
    op.create_check_constraint(op.f("ck_evento_estado"), "evento", ESTADOS_ANTES)
    op.alter_column("evento", "estado", type_=sa.String(15), existing_nullable=False)
