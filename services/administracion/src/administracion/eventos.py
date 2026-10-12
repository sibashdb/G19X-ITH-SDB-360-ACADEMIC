"""Copia a la bitácora los eventos que publican los otros servicios."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from comun.consumidor import Atender, EventoInvalido
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from administracion.bitacora import Actor, Objeto, registrar

NOMBRES_ENTIDAD = {
    "servicios": "servicios del catálogo",
    "proveedores": "proveedores",
    "tipo_cambio": "tipos de cambio",
    "contratos": "contratos",
    "desempeno": "registros de desempeño",
}
CAMBIOS_SERVICIO = frozenset({"creado", "actualizado", "desactivado", "activado"})


@dataclass(frozen=True)
class Registro:
    tipo: str
    actor: Actor
    objeto: Objeto
    detalle: dict[str, Any]
    resultado: str
    clave_origen: str
    fecha: datetime


def _actor(payload: dict[str, Any]) -> Actor:
    actor = payload.get("actor") or {}
    return Actor(actor.get("id"), str(actor.get("nombre") or "Sistema"))


def traducir(sobre: dict[str, Any]) -> Registro | None:
    """El registro de bitácora de un sobre de evento; None si el evento no es una acción."""
    try:
        tipo = sobre["type"]
        payload = sobre["payload"]
        clave = f"proveedores:{sobre['event_id']}"
        fecha = datetime.fromisoformat(sobre["occurred_at"])
        if tipo in ("importacion.completada", "importacion.rechazada"):
            entidad = str(payload["entidad"])
            objeto = Objeto("importacion", entidad, NOMBRES_ENTIDAD.get(entidad, entidad))
            if tipo == "importacion.completada":
                detalle: dict[str, Any] = {
                    c: int(payload[c]) for c in ("filas", "registros", "omitidos")
                }
                return Registro(tipo, _actor(payload), objeto, detalle, "exito", clave, fecha)
            detalle = {"errores": int(payload["errores"])}
            return Registro(tipo, _actor(payload), objeto, detalle, "fallo", clave, fecha)
        if tipo == "servicio.actualizado":
            cambio = payload.get("cambio")
            if cambio not in CAMBIOS_SERVICIO or "actor" not in payload:
                return None
            codigo = str(payload["codigo"])
            detalle = (
                {"campos": list(payload.get("campos") or [])} if cambio == "actualizado" else {}
            )
            return Registro(
                f"servicio.{cambio}",
                _actor(payload),
                Objeto("servicio", codigo, codigo),
                detalle,
                "exito",
                clave,
                fecha,
            )
        return None
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise EventoInvalido(str(exc)) from exc


async def guardar(fabrica: async_sessionmaker[AsyncSession], registro: Registro) -> None:
    """Inserta el registro; un evento ya recibido (misma clave de origen) no hace nada."""
    async with fabrica() as sesion:
        await registrar(
            sesion,
            registro.tipo,
            registro.actor,
            objeto=registro.objeto,
            detalle=registro.detalle,
            resultado=registro.resultado,
            origen="proveedores",
            clave_origen=registro.clave_origen,
            fecha=registro.fecha,
        )
        await sesion.commit()


def atendedor(fabrica: async_sessionmaker[AsyncSession]) -> Atender:
    """La función que el consumidor común llama con cada sobre de evento."""

    async def atender(sobre: dict[str, Any]) -> None:
        registro = traducir(sobre)
        if registro is not None:
            await guardar(fabrica, registro)

    return atender
