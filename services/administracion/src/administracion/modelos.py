import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from administracion.db import Base


def _ahora() -> datetime:
    return datetime.now(UTC)


class Actividad(Base):
    """Bitácora de solo inserción: el usuario de la aplicación no tiene UPDATE ni DELETE."""

    __tablename__ = "actividad"
    __table_args__ = (
        CheckConstraint("resultado IN ('exito', 'fallo')", name="resultado"),
        CheckConstraint(
            "origen IN ('keycloak', 'proveedores', 'administracion', 'inteligencia')",
            name="origen",
        ),
        Index("ix_actividad_fecha", "fecha"),
        Index("ix_actividad_actor_id", "actor_id"),
        Index("ix_actividad_objeto_id", "objeto_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    actor_id: Mapped[str | None] = mapped_column(String(64))
    actor_nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(60))
    objeto_tipo: Mapped[str | None] = mapped_column(String(30))
    objeto_id: Mapped[str | None] = mapped_column(String(64))
    objeto_nombre: Mapped[str | None] = mapped_column(String(200))
    detalle: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    resultado: Mapped[str] = mapped_column(String(10), default="exito")
    ip: Mapped[str | None] = mapped_column(String(64))
    origen: Mapped[str] = mapped_column(String(20))
    clave_origen: Mapped[str] = mapped_column(String(200), unique=True)


class CorreoEnviado(Base):
    __tablename__ = "correo_enviado"
    __table_args__ = (
        CheckConstraint("tipo IN ('invitacion', 'restablecimiento')", name="tipo"),
        CheckConstraint("estado IN ('enviado', 'fallido')", name="estado"),
        Index("ix_correo_enviado_fecha", "fecha"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    tipo: Mapped[str] = mapped_column(String(20))
    destinatario: Mapped[str] = mapped_column(String(254))
    usuario_id: Mapped[str] = mapped_column(String(64))
    solicitado_por: Mapped[str] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(10))
    error: Mapped[str | None] = mapped_column(String(500))


class CursorEventos(Base):
    """Hasta qué momento se copiaron a la bitácora los eventos de una fuente."""

    __tablename__ = "cursor_eventos"

    nombre: Mapped[str] = mapped_column(String(30), primary_key=True)
    hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True))
