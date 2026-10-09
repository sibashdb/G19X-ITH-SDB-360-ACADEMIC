"""Copia a la bitácora los eventos de inicio de sesión que Keycloak guarda 30 días."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from administracion.bitacora import Actor, registrar
from administracion.identidad import IdentidadNoDisponible, ProveedorIdentidad
from administracion.modelos import CursorEventos

log = logging.getLogger(__name__)

TIPOS = {"LOGIN": "sesion.iniciada", "LOGIN_ERROR": "sesion.fallida", "LOGOUT": "sesion.cerrada"}
CURSOR = "keycloak"
RETENCION_KEYCLOAK = timedelta(days=30)


async def sincronizar(
    identidad: ProveedorIdentidad, fabrica: async_sessionmaker[AsyncSession]
) -> int:
    """Lee los eventos desde el cursor y los inserta (idempotente). Devuelve cuántos leyó."""
    async with fabrica() as sesion:
        cursor = await sesion.get(CursorEventos, CURSOR)
        desde = cursor.hasta if cursor else datetime.now(UTC) - RETENCION_KEYCLOAK
        eventos = [e for e in await identidad.eventos_de_sesion(desde) if e.tipo in TIPOS]
        nombres: dict[str, str] = {}
        if any(e.usuario is None and e.usuario_id for e in eventos):
            nombres = {u.id: u.usuario for u in await identidad.listar_usuarios()}
        for evento in eventos:
            nombre = evento.usuario or nombres.get(evento.usuario_id or "") or "Usuario desconocido"
            await registrar(
                sesion,
                TIPOS[evento.tipo],
                Actor(evento.usuario_id, nombre, evento.ip),
                detalle={"error": evento.error} if evento.error else {},
                resultado="fallo" if evento.tipo == "LOGIN_ERROR" else "exito",
                origen="keycloak",
                clave_origen=f"keycloak:{evento.id}",
                fecha=evento.fecha,
            )
        if eventos:
            ultimo = max(e.fecha for e in eventos)
            if cursor:
                cursor.hasta = ultimo
            else:
                sesion.add(CursorEventos(nombre=CURSOR, hasta=ultimo))
        await sesion.commit()
        return len(eventos)


async def ejecutar_periodicamente(
    identidad: ProveedorIdentidad, fabrica: async_sessionmaker[AsyncSession], intervalo_s: int
) -> None:
    while True:
        try:
            await sincronizar(identidad, fabrica)
        except IdentidadNoDisponible:
            log.warning("No se pudieron leer los eventos de Keycloak; se reintentará")
        except Exception:
            log.exception("Error al copiar los eventos de inicio de sesión; se reintentará")
        await asyncio.sleep(intervalo_s)
