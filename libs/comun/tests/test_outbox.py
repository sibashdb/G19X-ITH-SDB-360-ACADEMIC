import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from typing import Any

import aio_pika
import pytest
from comun.logs import correlation_id
from comun.outbox import EXCHANGE_EVENTOS, ColumnasOutbox, RelayOutbox, registrar_evento
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.rabbitmq import RabbitMqContainer

pytestmark = pytest.mark.integracion


class Base(DeclarativeBase):
    pass


class OutboxPrueba(ColumnasOutbox, Base):
    __tablename__ = "outbox"


@pytest.fixture(scope="module")
def url_postgres() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as contenedor:
        yield contenedor.get_connection_url()


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


@pytest.fixture
async def fabrica(url_postgres: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    motor = create_async_engine(url_postgres, poolclass=NullPool)
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
        await conexion.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(motor, expire_on_commit=False)
    await motor.dispose()


async def _todas(fabrica: async_sessionmaker[AsyncSession]) -> list[OutboxPrueba]:
    async with fabrica() as sesion:
        return list((await sesion.scalars(select(OutboxPrueba))).all())


async def test_registrar_evento_serializa_payload_y_guarda_correlation_id(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    token = correlation_id.set("req-77")
    try:
        async with fabrica() as sesion, sesion.begin():
            registrar_evento(
                sesion,
                OutboxPrueba,
                "proveedor.actualizado",
                {"precio": Decimal("12.5000"), "id": uuid.UUID(int=1)},
            )
    finally:
        correlation_id.reset(token)
    [fila] = await _todas(fabrica)
    assert fila.payload == {"precio": "12.5000", "id": "00000000-0000-0000-0000-000000000001"}
    assert fila.correlation_id == "req-77"
    assert fila.publicado_en is None


async def test_evento_no_se_guarda_si_la_transaccion_falla(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    with contextlib.suppress(RuntimeError):
        async with fabrica() as sesion, sesion.begin():
            registrar_evento(sesion, OutboxPrueba, "proveedor.actualizado", {"n": 1})
            raise RuntimeError("falla del negocio")
    assert await _todas(fabrica) == []


async def test_relay_publica_cada_pendiente_una_sola_vez(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    async with fabrica() as sesion, sesion.begin():
        for n in range(3):
            registrar_evento(sesion, OutboxPrueba, "contrato.registrado", {"n": n})

    relay = RelayOutbox(fabrica, OutboxPrueba, url_rabbitmq)
    await relay.conectar()
    conexion = await aio_pika.connect_robust(url_rabbitmq)
    recibidos: list[dict[str, Any]] = []
    try:
        canal = await conexion.channel()
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        cola = await canal.declare_queue(exclusive=True)
        await cola.bind(exchange, routing_key="#")

        assert relay.conectado()
        assert await relay.publicar_pendientes() == 3
        assert await relay.publicar_pendientes() == 0
        for _ in range(3):
            mensaje = await cola.get(timeout=5)
            await mensaje.ack()
            recibidos.append(json.loads(mensaje.body))
    finally:
        await conexion.close()
        await relay.cerrar()

    assert sorted(r["payload"]["n"] for r in recibidos) == [0, 1, 2]
    assert {r["type"] for r in recibidos} == {"contrato.registrado"}
    assert set(recibidos[0]) == {
        "event_id",
        "type",
        "version",
        "occurred_at",
        "correlation_id",
        "payload",
    }
    assert all(fila.publicado_en is not None for fila in await _todas(fabrica))


async def test_ejecutar_publica_en_segundo_plano(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    relay = RelayOutbox(fabrica, OutboxPrueba, url_rabbitmq)
    await relay.conectar()
    async with fabrica() as sesion, sesion.begin():
        registrar_evento(sesion, OutboxPrueba, "desempeno.registrado", {"n": 1})
    tarea = asyncio.create_task(relay.ejecutar(intervalo=0.05))
    try:
        for _ in range(100):
            [fila] = await _todas(fabrica)
            if fila.publicado_en is not None:
                break
            await asyncio.sleep(0.05)
        assert fila.publicado_en is not None
    finally:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
        await relay.cerrar()


async def test_publicar_sin_conectar_es_un_error(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(RuntimeError, match="conectar"):
        await RelayOutbox(fabrica, OutboxPrueba, "amqp://nadie").publicar_pendientes()
