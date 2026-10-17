"""Tablas de negociacion: eventos, sesiones, mensajes, ofertas, bitácora y copias locales.

Los estados se guardan en minúsculas (`borrador`, `acuerdo_tentativo`…). Los mensajes y las
ofertas se ordenan por `secuencia` (de la secuencia `orden`): dos registros del mismo turno
comparten la hora, pero nunca la secuencia.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from comun.outbox import ColumnasOutbox
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from negociacion.db import Base

DINERO = Numeric(14, 4)
UTILIDAD = Numeric(6, 4)
MONTO = Numeric(16, 2)
SIGUIENTE_ORDEN = text("nextval('orden')")

ESTADOS_EVENTO = (
    "borrador",
    "abierto",
    "en_evaluacion",
    "pendiente_aprobacion",
    "adjudicado",
    "desierto",
    "cancelado",
)
ESTADOS_ADJUDICACION = ("pendiente", "aprobada", "rechazada", "directa")
MOTIVOS_APROBACION = ("umbral", "fuera_de_limites")
ACTORES = ("comprador", "aprobador", "proveedor", "agente", "sistema")
ESTADOS_SESION = (
    "invitada",
    "activa",
    "acuerdo_tentativo",
    "sin_acuerdo",
    "expirada",
    "escalada",
)
FINALES = ("acuerdo_tentativo", "sin_acuerdo", "expirada")
CLAVES_PALANCA = (
    "precio",
    "plazo_meses",
    "plazo_pago_dias",
    "sla_disponibilidad",
    "tope_aumento_pct",
    "cuota_implementacion",
)


def _ahora() -> datetime:
    return datetime.now(UTC)


def _en(columna: str, valores: tuple[str, ...]) -> str:
    return f"{columna} IN ({', '.join(repr(v) for v in valores)})"


class Evento(Base):
    __tablename__ = "evento"
    __table_args__ = (
        CheckConstraint(_en("tipo", ("compra", "renovacion")), name="tipo"),
        CheckConstraint(_en("estado", ESTADOS_EVENTO), name="estado"),
        CheckConstraint(_en("estilo", ("firme", "balanceado", "flexible")), name="estilo"),
        CheckConstraint("rondas_max BETWEEN 2 AND 12", name="rondas"),
        CheckConstraint("plazo_meses BETWEEN 1 AND 60", name="plazo"),
        Index("ix_evento_estado", "estado"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    folio: Mapped[str] = mapped_column(String(20), unique=True)
    tipo: Mapped[str] = mapped_column(String(12))
    titulo: Mapped[str] = mapped_column(String(120))
    moneda: Mapped[str] = mapped_column(String(3))
    plazo_meses: Mapped[int]
    estado: Mapped[str] = mapped_column(String(20), default="borrador")
    fecha_limite: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rondas_max: Mapped[int] = mapped_column(default=6)
    estilo: Mapped[str] = mapped_column(String(10), default="balanceado")
    contrato_origen_id: Mapped[uuid.UUID | None]
    proveedor_vigente_id: Mapped[uuid.UUID | None]
    # Los proveedores elegidos en el borrador; las sesiones se crean al publicar.
    invitados: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    # La fecha de la foto y, en renovación, los términos vigentes del contrato.
    foto: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(500))
    motivo_desierta: Mapped[str | None] = mapped_column(String(500))
    creado_por_id: Mapped[str] = mapped_column(String(64))
    creado_por_nombre: Mapped[str] = mapped_column(String(200))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)


class Linea(Base):
    __tablename__ = "linea"
    __table_args__ = (
        UniqueConstraint("evento_id", "orden"),
        CheckConstraint("cantidad > 0", name="cantidad"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evento.id"))
    orden: Mapped[int]
    codigo_servicio: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(200))
    unidad: Mapped[str] = mapped_column(String(20))
    cantidad: Mapped[Decimal] = mapped_column(DINERO)
    precio_vigente: Mapped[Decimal | None] = mapped_column(DINERO)
    ideal: Mapped[Decimal | None] = mapped_column(DINERO)
    limite: Mapped[Decimal | None] = mapped_column(DINERO)
    # La parte de la foto de esta línea: P25/P50/P75 de inteligencia o None si no hay referencia.
    referencia: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Palanca(Base):
    """Una fila por palanca activa; la del precio no lleva ideal ni límite (van por línea)."""

    __tablename__ = "palanca"
    __table_args__ = (
        CheckConstraint(_en("clave", CLAVES_PALANCA), name="clave"),
        CheckConstraint("peso BETWEEN 0 AND 100", name="peso"),
    )

    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evento.id"), primary_key=True)
    clave: Mapped[str] = mapped_column(String(30), primary_key=True)
    peso: Mapped[int]
    ideal: Mapped[Decimal | None] = mapped_column(DINERO)
    limite: Mapped[Decimal | None] = mapped_column(DINERO)


class SesionNegociacion(Base):
    """La negociación con un proveedor; su token de invitación solo se guarda como SHA-256."""

    __tablename__ = "sesion"
    __table_args__ = (
        UniqueConstraint("evento_id", "proveedor_id"),
        CheckConstraint(_en("estado", ESTADOS_SESION), name="estado"),
        CheckConstraint(_en("modo", ("agente", "comprador")), name="modo"),
        CheckConstraint(
            _en("correo_estado", ("pendiente", "enviado", "fallido")), name="correo_estado"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evento.id"))
    proveedor_id: Mapped[uuid.UUID]
    proveedor_nombre: Mapped[str] = mapped_column(String(200))
    destinatario: Mapped[str] = mapped_column(String(254))
    estado: Mapped[str] = mapped_column(String(20), default="invitada")
    modo: Mapped[str] = mapped_column(String(10), default="agente")
    ronda: Mapped[int] = mapped_column(default=0)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    correo_estado: Mapped[str] = mapped_column(String(10), default="pendiente")
    correo_error: Mapped[str | None] = mapped_column(String(500))
    correo_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fuera_de_limites: Mapped[bool] = mapped_column(default=False)
    # Cuándo se le avisó el resultado de la negociación (adjudicada o desierta).
    resultado_avisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Oferta(Base):
    """Solo inserción: una oferta del proveedor, una contraoferta del agente o del comprador."""

    __tablename__ = "oferta"
    __table_args__ = (
        CheckConstraint(_en("autor", ("proveedor", "agente", "comprador")), name="autor"),
        CheckConstraint(_en("origen", ("formulario", "texto")), name="origen"),
        Index("ix_oferta_sesion_id_secuencia", "sesion_id", "secuencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sesion.id"))
    secuencia: Mapped[int] = mapped_column(BigInteger, server_default=SIGUIENTE_ORDEN)
    autor: Mapped[str] = mapped_column(String(10))
    ronda: Mapped[int]
    # {"precios": {id de línea: "30.80"}, "palancas": {clave: "45"}}
    valores: Mapped[dict[str, Any]] = mapped_column(JSONB)
    utilidad: Mapped[Decimal] = mapped_column(UTILIDAD)
    valida: Mapped[bool]
    origen: Mapped[str] = mapped_column(String(12), default="formulario")
    fuera_de_limites_confirmada: Mapped[bool] = mapped_column(default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Mensaje(Base):
    """Solo inserción. Una clave de idempotencia repetida en la misma sesión choca."""

    __tablename__ = "mensaje"
    __table_args__ = (
        UniqueConstraint("sesion_id", "clave_idempotencia"),
        CheckConstraint(
            _en("autor", ("proveedor", "agente", "comprador", "sistema")), name="autor"
        ),
        Index("ix_mensaje_sesion_id_secuencia", "sesion_id", "secuencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sesion.id"))
    secuencia: Mapped[int] = mapped_column(BigInteger, server_default=SIGUIENTE_ORDEN)
    autor: Mapped[str] = mapped_column(String(10))
    texto: Mapped[str] = mapped_column(Text)
    ronda: Mapped[int]
    oferta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("oferta.id"))
    clave_idempotencia: Mapped[str | None] = mapped_column(String(64))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Bitacora(Base):
    """Solo inserción: el usuario de la aplicación no tiene UPDATE ni DELETE (spec §12)."""

    __tablename__ = "bitacora"
    __table_args__ = (
        CheckConstraint(_en("actor_tipo", ACTORES), name="actor_tipo"),
        Index("ix_bitacora_evento_id", "evento_id"),
        Index("ix_bitacora_sesion_id", "sesion_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    actor_tipo: Mapped[str] = mapped_column(String(10))
    actor_id: Mapped[str | None] = mapped_column(String(64))
    actor_nombre: Mapped[str] = mapped_column(String(200))
    accion: Mapped[str] = mapped_column(String(60))
    evento_id: Mapped[uuid.UUID | None]
    sesion_id: Mapped[uuid.UUID | None]
    detalle: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Adjudicacion(Base):
    """Una fila por propuesta: las rechazadas quedan como historial.

    El usuario de la aplicación solo actualiza las columnas de la decisión (GRANT por columna):
    lo propuesto, el monto y la foto de la recomendación no se reescriben.
    """

    __tablename__ = "adjudicacion"
    __table_args__ = (
        CheckConstraint(_en("estado", ESTADOS_ADJUDICACION), name="estado"),
        CheckConstraint(
            "motivo_aprobacion <@ ARRAY["
            + ", ".join(repr(m) for m in MOTIVOS_APROBACION)
            + "]::varchar[]",
            name="motivo_aprobacion",
        ),
        CheckConstraint("NOT se_aparta OR justificacion IS NOT NULL", name="justificacion"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evento.id"))
    sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sesion.id"))  # la elegida
    propuesta_por_id: Mapped[str] = mapped_column(String(64))
    propuesta_por_nombre: Mapped[str] = mapped_column(String(200))
    propuesta_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    recomendada_sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sesion.id"))
    se_aparta: Mapped[bool]
    justificacion: Mapped[str | None] = mapped_column(String(1000))
    costo_total: Mapped[Decimal] = mapped_column(MONTO)  # en la moneda del evento
    costo_total_mxn: Mapped[Decimal] = mapped_column(MONTO)
    requiere_aprobacion: Mapped[bool]
    motivo_aprobacion: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list)
    # La respuesta completa de inteligencia, con los pesos usados.
    recomendacion: Mapped[dict[str, Any]] = mapped_column(JSONB)
    estado: Mapped[str] = mapped_column(String(10))
    decidida_por_id: Mapped[str | None] = mapped_column(String(64))
    decidida_por_nombre: Mapped[str | None] = mapped_column(String(200))
    decidida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_rechazo: Mapped[str | None] = mapped_column(String(500))
    contrato_folio: Mapped[str | None] = mapped_column(String(30))


class Proveedor(Base):
    """Copia local, alimentada por proveedor.actualizado."""

    __tablename__ = "proveedor"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    categorias: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    contacto_nombre: Mapped[str] = mapped_column(String(120))
    contacto_email: Mapped[str] = mapped_column(String(254))
    activo: Mapped[bool]
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Servicio(Base):
    """Copia local del catálogo, alimentada por servicio.actualizado."""

    __tablename__ = "servicio"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(20))
    unidad: Mapped[str] = mapped_column(String(20))
    moneda: Mapped[str] = mapped_column(String(3))
    activo: Mapped[bool]


class EventoProcesado(Base):
    """Idempotencia: un evento repetido choca con su event_id y no se aplica dos veces."""

    __tablename__ = "evento_procesado"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100))
    procesado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Outbox(ColumnasOutbox, Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_pendientes", "ocurrido_en", postgresql_where=text("publicado_en IS NULL")),
    )
