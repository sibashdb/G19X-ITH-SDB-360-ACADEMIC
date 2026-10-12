"""Consumidor de eventos de RabbitMQ con reconexión.

Cada mensaje se entrega como sobre (un dict) a la función `atender` del servicio:
- Un mensaje mal formado (`ValueError`, incluido `EventoInvalido`) se rechaza sin reintentarlo,
  porque no se arregla solo: la política de la topología lo manda a la cola de fallidos
  (`<cola>.dlq`).
- Una falla de la base de datos (`SQLAlchemyError`, u `OSError`: asyncpg relanza los errores de red
  sin envolverlos) espera `REINTENTO_S` y devuelve el mensaje a la cola. Tras 5 entregas fallidas,
  RabbitMQ lo manda a la cola de fallidos (ver comun.topologia).
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection
from sqlalchemy.exc import SQLAlchemyError

from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import ARGUMENTOS_COLA, Cola

log = logging.getLogger(__name__)

REINTENTO_S = 5
Atender = Callable[[dict[str, Any]], Awaitable[None]]


class EventoInvalido(ValueError):
    """El mensaje no tiene la forma esperada: reintentarlo no lo arregla."""


async def atender_mensaje(mensaje: AbstractIncomingMessage, atender: Atender) -> None:
    try:
        sobre = json.loads(mensaje.body)
        if not isinstance(sobre, dict):
            raise EventoInvalido("El sobre no es un objeto JSON")
        await atender(sobre)
    except ValueError as exc:  # JSON inválido o EventoInvalido
        log.warning(
            "Evento con forma inesperada; va a la cola de fallidos (mensaje %s): %r",
            mensaje.message_id,
            exc,
        )
        await mensaje.reject(requeue=False)
        return
    except (SQLAlchemyError, OSError):
        log.exception("No se pudo procesar el evento %s; se reintentará", mensaje.message_id)
        # Sin esta espera el mensaje vuelve de inmediato y agota sus entregas en milisegundos.
        await asyncio.sleep(REINTENTO_S)
        await mensaje.reject(requeue=True)
        return
    await mensaje.ack()


class ConsumidorEventos:
    def __init__(self, url_rabbitmq: str, cola: Cola, atender: Atender, prefetch: int = 10) -> None:
        self._url = url_rabbitmq
        self._cola = cola
        self._atender = atender
        self._prefetch = prefetch
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
        await canal.set_qos(prefetch_count=self._prefetch)
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        cola = await canal.declare_queue(self._cola.nombre, durable=True, arguments=ARGUMENTOS_COLA)
        for clave in self._cola.claves:
            await cola.bind(exchange, clave)
        self._enlazada = True
        async with cola.iterator() as mensajes:
            async for mensaje in mensajes:
                await atender_mensaje(mensaje, self._atender)

    async def ejecutar(self) -> None:
        """Consume sin fin; si la conexión se cae, reintenta cada REINTENTO_S segundos."""
        while True:
            try:
                await self._consumir()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception(
                    "Se interrumpió el consumo de eventos; se reintentará en %s s", REINTENTO_S
                )
                # Cerrar una conexión rota puede fallar; el bucle no debe terminar por eso.
                with contextlib.suppress(Exception):
                    await self.cerrar()
                await asyncio.sleep(REINTENTO_S)
