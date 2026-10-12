"""Outbox transaccional: el evento se guarda en la misma transacción que el cambio
de datos y un relay lo publica después en RabbitMQ (entrega al menos una vez)."""

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractRobustConnection
from aio_pika.exceptions import PublishError
from pydantic_core import to_jsonable_python
from sqlalchemy import DateTime, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from comun.logs import correlation_id

log = logging.getLogger(__name__)

EXCHANGE_EVENTOS = "eventos"
TIMEOUT_PUBLICACION = 10  # segundos para publicar y recibir la confirmación del broker


class ColumnasOutbox:
    """Mixin. Uso: `class Outbox(ColumnasOutbox, Base): __tablename__ = "outbox"`."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tipo: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    correlation_id: Mapped[str] = mapped_column(String(64))
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def registrar_evento(
    sesion: AsyncSession,
    modelo: Callable[..., ColumnasOutbox],
    tipo: str,
    payload: dict[str, Any],
    version: int = 1,
) -> None:
    """Agrega el evento a la transacción en curso; solo existe si la transacción confirma."""
    sesion.add(
        modelo(
            tipo=tipo,
            version=version,
            payload=to_jsonable_python(payload),
            correlation_id=correlation_id.get(),
        )
    )


def sobre_evento(fila: ColumnasOutbox) -> dict[str, Any]:
    return {
        "event_id": str(fila.id),
        "type": fila.tipo,
        "version": fila.version,
        "occurred_at": fila.ocurrido_en.isoformat(),
        "correlation_id": fila.correlation_id,
        "payload": fila.payload,
    }


class RelayOutbox:
    def __init__(
        self,
        fabrica: async_sessionmaker[AsyncSession],
        modelo: type[ColumnasOutbox],
        url_rabbitmq: str,
        lote: int = 100,
    ) -> None:
        self._fabrica = fabrica
        self._modelo = modelo
        self._url = url_rabbitmq
        self._lote = lote
        self._conexion: AbstractRobustConnection | None = None
        self._exchange: AbstractExchange | None = None

    async def conectar(self) -> None:
        self._conexion = await aio_pika.connect_robust(self._url)
        # on_return_raises: un evento que ninguna cola recibe vuelve y publish lanza PublishError.
        canal = await self._conexion.channel(publisher_confirms=True, on_return_raises=True)
        self._exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )

    def conectado(self) -> bool:
        return self._conexion is not None and not self._conexion.is_closed

    async def cerrar(self) -> None:
        if self._conexion is not None:
            await self._conexion.close()

    async def publicar_pendientes(self) -> int:
        if self._exchange is None:
            raise RuntimeError("Llame a conectar() antes de publicar")
        modelo = self._modelo
        async with self._fabrica() as sesion, sesion.begin():
            consulta = (
                select(modelo)
                .where(modelo.publicado_en.is_(None))
                .order_by(modelo.ocurrido_en)
                .limit(self._lote)
                .with_for_update(skip_locked=True)
            )
            filas = (await sesion.scalars(consulta)).all()
            publicados = 0
            for fila in filas:
                mensaje = aio_pika.Message(
                    json.dumps(sobre_evento(fila)).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    message_id=str(fila.id),
                    correlation_id=fila.correlation_id,
                    type=fila.tipo,
                )
                # mandatory=True: si ninguna cola recibe este tipo (topología sin aplicar), RabbitMQ
                # lo devuelve; queda pendiente y se reintenta, sin frenar a los demás.
                # timeout: un broker detenido no debe retener la transacción ni los bloqueos de
                # fila (FOR UPDATE) indefinidamente.
                try:
                    await self._exchange.publish(
                        mensaje,
                        routing_key=fila.tipo,
                        mandatory=True,
                        timeout=TIMEOUT_PUBLICACION,
                    )
                except PublishError:
                    # ponytail: si hay más de `lote` eventos sin cola delante, los que sí tienen
                    # cola esperan detrás de ellos; solo pasa con la topología sin aplicar.
                    log.warning(
                        "Evento %s (%s) sin cola de destino; queda pendiente", fila.id, fila.tipo
                    )
                    continue
                fila.publicado_en = datetime.now(UTC)
                publicados += 1
        return publicados

    async def ejecutar(self, intervalo: float = 1.0) -> None:
        # ponytail: sondeo cada `intervalo` s; cambiar a LISTEN/NOTIFY si la latencia importa.
        while True:
            try:
                publicados = await self.publicar_pendientes()
            except Exception:
                log.exception("No se pudieron publicar eventos del outbox; se reintentará")
                publicados = 0
            if publicados < self._lote:
                await asyncio.sleep(intervalo)
