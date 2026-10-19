"""Entidades del servicio de proveedores. La fuente de verdad es el ERP (importación CSV)."""

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
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from proveedores.db import Base

DINERO = Numeric(14, 4)
PORCENTAJE = Numeric(5, 2)


class Proveedor(Base):
    __tablename__ = "proveedor"
    __table_args__ = (
        CheckConstraint("tamano IN ('micro', 'pequena', 'mediana', 'grande')", name="tamano"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rfc: Mapped[str] = mapped_column(String(13), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    tamano: Mapped[str] = mapped_column(String(10))
    categorias: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    contacto_nombre: Mapped[str] = mapped_column(String(120))
    contacto_email: Mapped[str] = mapped_column(String(254))
    activo: Mapped[bool] = mapped_column(default=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ServicioCatalogo(Base):
    __tablename__ = "servicio_catalogo"
    __table_args__ = (
        CheckConstraint(
            "categoria IN ('licencia_saas', 'nube', 'consultoria', 'soporte')", name="categoria"
        ),
        CheckConstraint("moneda IN ('MXN', 'USD')", name="moneda"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(20))
    unidad: Mapped[str] = mapped_column(String(20))
    moneda: Mapped[str] = mapped_column(String(3))
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())


class Contrato(Base):
    __tablename__ = "contrato"
    __table_args__ = (
        CheckConstraint("tipo IN ('nuevo', 'renovacion')", name="tipo"),
        CheckConstraint("moneda IN ('MXN', 'USD')", name="moneda"),
        CheckConstraint("fecha_fin > fecha_inicio", name="vigencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    folio: Mapped[str] = mapped_column(String(30), unique=True)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proveedor.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(10))
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    moneda: Mapped[str] = mapped_column(String(3))
    plazo_pago_dias: Mapped[int]
    sla_disponibilidad: Mapped[Decimal | None] = mapped_column(PORCENTAJE)
    tope_aumento_pct: Mapped[Decimal | None] = mapped_column(PORCENTAJE)
    cuota_implementacion: Mapped[Decimal] = mapped_column(DINERO, default=Decimal(0))

    lineas: Mapped[list["LineaContrato"]] = relationship(
        back_populates="contrato", cascade="all, delete-orphan"
    )


class LineaContrato(Base):
    __tablename__ = "linea_contrato"
    __table_args__ = (CheckConstraint("cantidad > 0 AND precio_unitario > 0", name="positivos"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contrato.id", ondelete="CASCADE"), index=True
    )
    servicio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("servicio_catalogo.id"))
    cantidad: Mapped[Decimal] = mapped_column(DINERO)
    precio_unitario: Mapped[Decimal] = mapped_column(DINERO)

    contrato: Mapped[Contrato] = relationship(back_populates="lineas")
    servicio: Mapped[ServicioCatalogo] = relationship()


class RegistroDesempeno(Base):
    __tablename__ = "registro_desempeno"
    __table_args__ = (UniqueConstraint("proveedor_id", "periodo"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proveedor.id"))
    periodo: Mapped[date] = mapped_column(Date)
    sla_cumplimiento_pct: Mapped[Decimal] = mapped_column(PORCENTAJE)
    tiempo_resolucion_h: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    incidentes_criticos: Mapped[int]
    entregas_a_tiempo_pct: Mapped[Decimal] = mapped_column(PORCENTAJE)
    satisfaccion: Mapped[Decimal] = mapped_column(Numeric(3, 2))


class TipoCambio(Base):
    __tablename__ = "tipo_cambio"

    periodo: Mapped[date] = mapped_column(Date, primary_key=True)
    usd_mxn: Mapped[Decimal] = mapped_column(Numeric(10, 4))


class EventoProcesado(Base):
    """Idempotencia: un evento repetido choca con su event_id y no se aplica dos veces."""

    __tablename__ = "evento_procesado"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100))
    procesado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Outbox(ColumnasOutbox, Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_pendientes", "ocurrido_en", postgresql_where=text("publicado_en IS NULL")),
    )
