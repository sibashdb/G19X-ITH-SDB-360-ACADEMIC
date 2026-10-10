"""Copia a la bitácora los eventos de importación y de catálogo que publica proveedores."""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection
from comun.outbox import EXCHANGE_EVENTOS
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from administracion.bitacora import Actor, Objeto, registrar

log = logging.getLogger(__name__)

COLA = "administracion.actividad"
CLAVES = ("importacion.*", "servicio.*")
# ponytail: tras 5 entregas fallidas RabbitMQ descarta el mensaje (no hay cola de fallidos todavía);
# con una espera de REINTENTO_CONEXION_S entre entregas, una caída de la base de datos de unos 25 s
# (5 entregas x 5 s) pierde el registro. El Plan B declara eventos.dlx y la cola de fallidos.
ARGUMENTOS_COLA = {"x-queue-type": "quorum", "x-delivery-limit": 5}
REINTENTO_CONEXION_S = 5
NOMBRES_ENTIDAD = {
    "servicios": "servicios del catálogo",
    "proveedores": "proveedores",
    "tipo_cambio": "tipos de cambio",
    "contratos": "contratos",
    "desempeno": "registros de desempeño",
}
CAMBIOS_SERVICIO = frozenset({"creado", "actualizado", "desactivado", "activado"})


class EventoInvalido(ValueError):
    """El mensaje no tiene la forma esperada: reintentarlo no lo arregla."""


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


async def atender(
    fabrica: async_sessionmaker[AsyncSession], mensaje: AbstractIncomingMessage
) -> None:
    try:
        registro = traducir(json.loads(mensaje.body))
    except ValueError:  # JSON inválido o EventoInvalido
        log.warning("Evento con forma inesperada; se descarta (mensaje %s)", mensaje.message_id)
        await mensaje.reject(requeue=False)
        return
    if registro is not None:
        try:
            await guardar(fabrica, registro)
        except SQLAlchemyError:
            log.exception("No se pudo guardar el evento %s; se reintentará", mensaje.message_id)
            # Sin esta espera el mensaje vuelve de inmediato y agota sus entregas en milisegundos.
            await asyncio.sleep(REINTENTO_CONEXION_S)
            await mensaje.reject(requeue=True)
            return
    await mensaje.ack()


class ConsumidorEventos:
    def __init__(self, fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str) -> None:
        self._fabrica = fabrica
        self._url = url_rabbitmq
        self._conexion: AbstractRobustConnection | None = None
        self._enlazada = False

    def conectado(self) -> bool:
        """Conectado y con la cola ya enlazada: desde aquí no se pierde ningún evento."""
        return self._enlazada and self._conexion is not None and not self._conexion.is_closed

    async def cerrar(self) -> None:
        self._enlazada = False
        if self._conexion is not None:
            await self._conexion.close()
            self._conexion = None

    async def _consumir(self) -> None:
        self._conexion = await aio_pika.connect_robust(self._url)
        canal = await self._conexion.channel()
        await canal.set_qos(prefetch_count=10)
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        cola = await canal.declare_queue(COLA, durable=True, arguments=ARGUMENTOS_COLA)
        for clave in CLAVES:
            await cola.bind(exchange, clave)
        self._enlazada = True
        async with cola.iterator() as mensajes:
            async for mensaje in mensajes:
                await atender(self._fabrica, mensaje)

    async def ejecutar(self) -> None:
        """Consume sin fin; si RabbitMQ no está, reintenta cada pocos segundos."""
        while True:
            try:
                await self._consumir()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception(
                    "Sin conexión con RabbitMQ; se reintentará en %s s", REINTENTO_CONEXION_S
                )
                await self.cerrar()
                await asyncio.sleep(REINTENTO_CONEXION_S)
