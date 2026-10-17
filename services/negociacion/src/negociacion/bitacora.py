"""Bitácora de auditoría de solo inserción (spec §12): quién hizo qué en cada evento y sesión."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from comun.auth import Usuario
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion.modelos import Bitacora

MAX_NOMBRE = 200


@dataclass(frozen=True)
class Actor:
    tipo: str  # comprador, aprobador, proveedor, agente o sistema
    id: str | None
    nombre: str

    def para_evento(self) -> dict[str, str | None]:
        """El actor como lo esperan los consumidores de eventos (administracion)."""
        return {"id": self.id, "nombre": self.nombre}


AGENTE = Actor("agente", None, "Agente")
SISTEMA = Actor("sistema", None, "Sistema")


def de_usuario(usuario: Usuario, tipo: str = "comprador") -> Actor:
    return Actor(tipo, usuario.id, usuario.nombre)


def registrar(
    bd: AsyncSession,
    accion: str,
    actor: Actor,
    *,
    evento_id: uuid.UUID | None = None,
    sesion_id: uuid.UUID | None = None,
    detalle: dict[str, Any] | None = None,
    fecha: datetime | None = None,
) -> None:
    """Agrega el registro a la transacción en curso."""
    fila = Bitacora(
        actor_tipo=actor.tipo,
        actor_id=actor.id,
        actor_nombre=actor.nombre[:MAX_NOMBRE],
        accion=accion,
        evento_id=evento_id,
        sesion_id=sesion_id,
        detalle=detalle or {},
    )
    if fecha is not None:
        fila.fecha = fecha
    bd.add(fila)
