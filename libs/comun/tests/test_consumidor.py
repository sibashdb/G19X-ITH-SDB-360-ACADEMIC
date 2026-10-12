import asyncio
import contextlib
import json
import socket
from collections.abc import AsyncIterator, Iterator
from typing import Any, cast

import aio_pika
import pytest
from aio_pika.abc import AbstractIncomingMessage
from comun.consumidor import (
    REINTENTO_S,
    ConsumidorEventos,
    EventoInvalido,
    atender_mensaje,
)
from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import ARGUMENTOS_COLA, Cola
from sqlalchemy.exc import SQLAlchemyError
from testcontainers.community.rabbitmq import RabbitMqContainer

SOBRE = {"event_id": "e-1", "type": "prueba.creada", "payload": {"n": 1}}


class _MensajeFalso:
    """Lo mínimo de un mensaje entrante: anota ack y reject en la lista compartida."""

    message_id = "m-1"

    def __init__(self, cuerpo: bytes, anotaciones: list[tuple[Any, ...]]) -> None:
        self.body = cuerpo
        self._anotaciones = anotaciones

    async def ack(self) -> None:
        self._anotaciones.append(("ack",))

    async def reject(self, requeue: bool = False) -> None:
        self._anotaciones.append(("reject", requeue))


def _mensaje(cuerpo: bytes, anotaciones: list[tuple[Any, ...]]) -> AbstractIncomingMessage:
    return cast(AbstractIncomingMessage, _MensajeFalso(cuerpo, anotaciones))


async def test_un_evento_atendido_se_confirma() -> None:
    anotaciones: list[tuple[Any, ...]] = []
    recibidos: list[dict[str, Any]] = []

    async def atender(sobre: dict[str, Any]) -> None:
        recibidos.append(sobre)

    await atender_mensaje(_mensaje(json.dumps(SOBRE).encode(), anotaciones), atender)
    assert recibidos == [SOBRE]
    assert anotaciones == [("ack",)]


@pytest.mark.parametrize(
    "cuerpo", [b"no es json", b"[1, 2]", b"\xff\xfe"], ids=["texto", "lista", "binario"]
)
async def test_un_mensaje_mal_formado_se_descarta(cuerpo: bytes) -> None:
    anotaciones: list[tuple[Any, ...]] = []

    async def atender(_sobre: dict[str, Any]) -> None:
        pytest.fail("no debe llegar al manejador")

    await atender_mensaje(_mensaje(cuerpo, anotaciones), atender)
    assert anotaciones == [("reject", False)]


async def test_un_evento_invalido_se_descarta() -> None:
    anotaciones: list[tuple[Any, ...]] = []

    async def atender(_sobre: dict[str, Any]) -> None:
        raise EventoInvalido("falta el payload")

    await atender_mensaje(_mensaje(json.dumps(SOBRE).encode(), anotaciones), atender)
    assert anotaciones == [("reject", False)]


@pytest.mark.parametrize(
    "error",
    [
        SQLAlchemyError("la base de datos no responde"),
        # Con PostgreSQL detenido o inalcanzable, asyncpg relanza el error de red tal cual.
        ConnectionRefusedError("conexión rechazada"),
        socket.gaierror("no se resuelve el nombre"),
        TimeoutError("se agotó la espera"),
    ],
    ids=["sqlalchemy", "conexion_rechazada", "dns", "tiempo_agotado"],
)
async def test_si_falla_la_base_espera_y_devuelve_el_mensaje_a_la_cola(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    anotaciones: list[tuple[Any, ...]] = []

    async def dormir(segundos: float) -> None:
        anotaciones.append(("sleep", segundos))

    async def atender(_sobre: dict[str, Any]) -> None:
        raise error

    monkeypatch.setattr(asyncio, "sleep", dormir)
    await atender_mensaje(_mensaje(json.dumps(SOBRE).encode(), anotaciones), atender)
    # Sin la espera, el mensaje volvería de inmediato y agotaría las 5 entregas en milisegundos.
    assert anotaciones == [("sleep", REINTENTO_S), ("reject", True)]


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


COLA_PRUEBA = Cola("prueba.eventos", ("prueba.*",))


@contextlib.asynccontextmanager
async def _consumidor(
    url: str, recibidos: list[dict[str, Any]]
) -> AsyncIterator[ConsumidorEventos]:
    async def atender(sobre: dict[str, Any]) -> None:
        recibidos.append(sobre)

    consumidor = ConsumidorEventos(url, COLA_PRUEBA, atender)
    tarea = asyncio.create_task(consumidor.ejecutar())
    try:
        for _ in range(200):  # que la cola exista y esté enlazada antes de publicar
            if consumidor.conectado():
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("El consumidor no se conectó a RabbitMQ")
        yield consumidor
    finally:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
        await consumidor.cerrar()


async def _publicar(url: str, cuerpo: bytes, clave: str) -> None:
    conexion = await aio_pika.connect_robust(url)
    async with conexion:
        canal = await conexion.channel()
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        await exchange.publish(aio_pika.Message(cuerpo), routing_key=clave)


@pytest.mark.integracion
async def test_consume_su_cola_y_un_mensaje_mal_formado_no_la_detiene(url_rabbitmq: str) -> None:
    recibidos: list[dict[str, Any]] = []
    async with _consumidor(url_rabbitmq, recibidos):
        await _publicar(url_rabbitmq, b"no es json", "prueba.creada")
        await _publicar(url_rabbitmq, json.dumps(SOBRE).encode(), "prueba.creada")
        await _publicar(url_rabbitmq, json.dumps(SOBRE).encode(), "otra.cosa")  # sin enlace
        for _ in range(100):
            if recibidos:
                break
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.3)
    assert recibidos == [SOBRE]


@pytest.mark.integracion
async def test_la_cola_es_durable_de_tipo_quorum(url_rabbitmq: str) -> None:
    async with _consumidor(url_rabbitmq, []):
        conexion = await aio_pika.connect_robust(url_rabbitmq)
        async with conexion:
            canal = await conexion.channel()
            # Redeclarar con argumentos distintos falla (PRECONDITION_FAILED): si pasa, coinciden.
            cola = await canal.declare_queue(
                COLA_PRUEBA.nombre, durable=True, arguments=ARGUMENTOS_COLA
            )
            assert cola.name == COLA_PRUEBA.nombre
