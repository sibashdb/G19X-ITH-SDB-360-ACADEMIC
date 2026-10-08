"""Escritura y consulta de la bitácora de actividad (tabla de solo inserción)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from administracion.modelos import Actividad

GrupoTipo = Literal["sesiones", "usuarios", "importaciones", "catalogo"]
PREFIJOS_GRUPO: dict[str, str] = {
    "sesiones": "sesion.",
    "usuarios": "usuario.",
    "importaciones": "importacion.",
    "catalogo": "servicio.",
}


@dataclass(frozen=True)
class Actor:
    id: str | None
    nombre: str
    ip: str | None = None


@dataclass(frozen=True)
class Objeto:
    tipo: str
    id: str
    nombre: str


@dataclass(frozen=True)
class FiltroActividad:
    persona: str | None = None  # quien actuó o sobre quien se actuó
    tipo: GrupoTipo | None = None
    desde: datetime | None = None
    hasta: datetime | None = None  # exclusivo


async def registrar(
    sesion: AsyncSession,
    tipo: str,
    actor: Actor,
    *,
    objeto: Objeto | None = None,
    detalle: dict[str, Any] | None = None,
    resultado: str = "exito",
    origen: str = "administracion",
    clave_origen: str | None = None,
    fecha: datetime | None = None,
) -> None:
    """Agrega un registro a la transacción en curso; una clave de origen repetida no hace nada."""
    valores: dict[str, Any] = {
        "actor_id": actor.id,
        "actor_nombre": actor.nombre,
        "tipo": tipo,
        "objeto_tipo": objeto.tipo if objeto else None,
        "objeto_id": objeto.id if objeto else None,
        "objeto_nombre": objeto.nombre if objeto else None,
        "detalle": detalle or {},
        "resultado": resultado,
        "ip": actor.ip,
        "origen": origen,
        "clave_origen": clave_origen or f"{origen}:{uuid.uuid4()}",
    }
    if fecha is not None:
        valores["fecha"] = fecha
    await sesion.execute(
        insert(Actividad).values(**valores).on_conflict_do_nothing(index_elements=["clave_origen"])
    )


def _filtrada(filtro: FiltroActividad) -> Select[Actividad]:
    consulta = select(Actividad)
    if filtro.persona:
        consulta = consulta.where(
            or_(Actividad.actor_id == filtro.persona, Actividad.objeto_id == filtro.persona)
        )
    if filtro.tipo:
        consulta = consulta.where(Actividad.tipo.startswith(PREFIJOS_GRUPO[filtro.tipo]))
    if filtro.desde:
        consulta = consulta.where(Actividad.fecha >= filtro.desde)
    if filtro.hasta:
        consulta = consulta.where(Actividad.fecha < filtro.hasta)
    return consulta


async def consultar(
    sesion: AsyncSession, filtro: FiltroActividad, desplazamiento: int, limite: int
) -> tuple[int, list[Actividad]]:
    total = await sesion.scalar(select(func.count()).select_from(_filtrada(filtro).subquery()))
    filas = await sesion.scalars(
        _filtrada(filtro)
        .order_by(Actividad.fecha.desc(), Actividad.id)
        .offset(desplazamiento)
        .limit(limite)
    )
    return total or 0, list(filas)


async def ultimos_accesos(sesion: AsyncSession, ids: list[str]) -> dict[str, datetime]:
    if not ids:
        return {}
    filas = await sesion.execute(
        select(Actividad.actor_id, func.max(Actividad.fecha))
        .where(Actividad.tipo == "sesion.iniciada", Actividad.actor_id.in_(ids))
        .group_by(Actividad.actor_id)
    )
    return {actor_id: fecha for actor_id, fecha in filas if actor_id is not None}
