"""Copia local de los datos de proveedores (alimentada por eventos) y estado propio del servicio."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from comun.outbox import ColumnasOutbox
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from inteligencia.db import Base

DINERO = Numeric(14, 4)
PORCENTAJE = Numeric(5, 2)
METRICA = Numeric(8, 6)


def _ahora() -> datetime:
    return datetime.now(UTC)


class Proveedor(Base):
    __tablename__ = "proveedor"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    rfc: Mapped[str] = mapped_column(String(13))
    nombre: Mapped[str] = mapped_column(String(200))
    tamano: Mapped[str] = mapped_column(String(10))
    categorias: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    activo: Mapped[bool]


class Servicio(Base):
    __tablename__ = "servicio"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(20))
    unidad: Mapped[str] = mapped_column(String(20))
    moneda: Mapped[str] = mapped_column(String(3))
    activo: Mapped[bool]


class TipoCambio(Base):
    __tablename__ = "tipo_cambio"

    periodo: Mapped[date] = mapped_column(Date, primary_key=True)
    usd_mxn: Mapped[Decimal] = mapped_column(Numeric(10, 4))


class Contrato(Base):
    """Sin llave foránea al proveedor: los eventos pueden llegar en desorden."""

    __tablename__ = "contrato"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    folio: Mapped[str] = mapped_column(String(30))
    proveedor_id: Mapped[uuid.UUID] = mapped_column(index=True)
    tipo: Mapped[str] = mapped_column(String(10))
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    moneda: Mapped[str] = mapped_column(String(3))
    recibido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)

    lineas: Mapped[list["LineaContrato"]] = relationship(lazy="selectin")


class LineaContrato(Base):
    """Categoría y unidad tal como estaban al firmarse el contrato (vienen en el evento)."""

    __tablename__ = "linea_contrato"

    contrato_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contrato.id", ondelete="CASCADE"), primary_key=True
    )
    codigo_servicio: Mapped[str] = mapped_column(String(30), primary_key=True)
    categoria: Mapped[str] = mapped_column(String(20))
    unidad: Mapped[str] = mapped_column(String(20))
    cantidad: Mapped[Decimal] = mapped_column(DINERO)
    precio_unitario: Mapped[Decimal] = mapped_column(DINERO)


class Desempeno(Base):
    __tablename__ = "desempeno"

    proveedor_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    periodo: Mapped[date] = mapped_column(Date, primary_key=True)
    sla_cumplimiento_pct: Mapped[Decimal] = mapped_column(PORCENTAJE)
    tiempo_resolucion_h: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    incidentes_criticos: Mapped[int]
    entregas_a_tiempo_pct: Mapped[Decimal] = mapped_column(PORCENTAJE)
    satisfaccion: Mapped[Decimal] = mapped_column(Numeric(3, 2))


class EventoProcesado(Base):
    """Idempotencia: un evento repetido choca con su event_id y no se aplica dos veces."""

    __tablename__ = "evento_procesado"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100))
    procesado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Configuracion(Base):
    """Una sola fila (id = 1), creada por la migración."""

    __tablename__ = "configuracion"
    __table_args__ = (CheckConstraint("id = 1", name="unica"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    peso_sla: Mapped[int]
    peso_resolucion: Mapped[int]
    peso_incidentes: Mapped[int]
    peso_entregas: Mapped[int]
    peso_satisfaccion: Mapped[int]
    umbral_riesgo: Mapped[int]
    inflacion_anual: Mapped[Decimal] = mapped_column(PORCENTAJE)
    adjudicacion_costo: Mapped[int] = mapped_column(server_default=text("40"))
    adjudicacion_desempeno: Mapped[int] = mapped_column(server_default=text("30"))
    adjudicacion_riesgo: Mapped[int] = mapped_column(server_default=text("15"))
    adjudicacion_sla: Mapped[int] = mapped_column(server_default=text("15"))
    umbral_aprobacion: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default=text("500000.00")
    )
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actualizado_por: Mapped[str | None] = mapped_column(String(200))


class ModeloBenchmark(Base):
    """Registro de entrenamientos del modelo de precios; el activo es el último promovido."""

    __tablename__ = "modelo_benchmark"
    __table_args__ = (CheckConstraint("origen IN ('manual', 'automatico')", name="origen"),)

    version: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    entrenado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    origen: Mapped[str] = mapped_column(String(10))
    actor_nombre: Mapped[str] = mapped_column(String(200))
    observaciones: Mapped[int]
    datos_hasta: Mapped[date] = mapped_column(Date)
    mape: Mapped[Decimal] = mapped_column(METRICA)
    mape_linea_base: Mapped[Decimal] = mapped_column(METRICA)
    cobertura: Mapped[Decimal] = mapped_column(METRICA)
    pinball: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    promovido: Mapped[bool]
    artefacto: Mapped[str | None] = mapped_column(String(300))


class Outbox(ColumnasOutbox, Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_pendientes", "ocurrido_en", postgresql_where=text("publicado_en IS NULL")),
    )
