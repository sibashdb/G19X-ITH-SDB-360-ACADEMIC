import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import aio_pika
import pytest
from administracion.bitacora import Actor, Objeto
from administracion.eventos import (
    COLA,
    ConsumidorEventos,
    EventoInvalido,
    Registro,
    traducir,
)
from comun.outbox import EXCHANGE_EVENTOS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.rabbitmq import RabbitMqContainer

ADMIN = {"id": "admin-1", "nombre": "admin1"}
FECHA = "2026-10-09T15:00:00+00:00"


def _sobre(tipo: str, payload: dict[str, Any], event_id: str | None = None) -> dict[str, Any]:
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "type": tipo,
        "version": 1,
        "occurred_at": FECHA,
        "correlation_id": "c-1",
        "payload": payload,
    }


def test_traduce_una_importacion_completada() -> None:
    sobre = _sobre(
        "importacion.completada",
        {"entidad": "proveedores", "filas": 60, "registros": 60, "omitidos": 0, "actor": ADMIN},
        "e-1",
    )
    assert traducir(sobre) == Registro(
        tipo="importacion.completada",
        actor=Actor("admin-1", "admin1"),
        objeto=Objeto("importacion", "proveedores", "proveedores"),
        detalle={"filas": 60, "registros": 60, "omitidos": 0},
        resultado="exito",
        clave_origen="proveedores:e-1",
        fecha=datetime(2026, 10, 9, 15, tzinfo=UTC),
    )


def test_traduce_una_importacion_rechazada_de_la_linea_de_comandos() -> None:
    sobre = _sobre(
        "importacion.rechazada",
        {
            "entidad": "tipo_cambio",
            "errores": 3,
            "actor": {"id": None, "nombre": "Sistema (línea de comandos)"},
        },
    )
    registro = traducir(sobre)
    assert registro is not None
    assert registro.resultado == "fallo"
    assert registro.detalle == {"errores": 3}
    assert registro.objeto.nombre == "tipos de cambio"
    assert registro.actor == Actor(None, "Sistema (línea de comandos)")


@pytest.mark.parametrize(
    ("cambio", "detalle"),
    [
        ("creado", {}),
        ("actualizado", {"campos": ["nombre"]}),
        ("desactivado", {}),
        ("activado", {}),
    ],
)
def test_traduce_los_cambios_del_catalogo(cambio: str, detalle: dict[str, Any]) -> None:
    sobre = _sobre(
        "servicio.actualizado",
        {"codigo": "SOP-MESA-TK", "cambio": cambio, "campos": ["nombre"], "actor": ADMIN},
    )
    registro = traducir(sobre)
    assert registro is not None
    assert registro.tipo == f"servicio.{cambio}"
    assert registro.objeto == Objeto("servicio", "SOP-MESA-TK", "SOP-MESA-TK")
    assert registro.detalle == detalle


def test_ignora_lo_que_no_va_a_la_bitacora() -> None:
    assert traducir(_sobre("proveedor.actualizado", {"id": "x"})) is None
    # Un servicio.actualizado sin cambio ni actor (p. ej. una instantánea del Plan B): no es acción.
    assert traducir(_sobre("servicio.actualizado", {"codigo": "X"})) is None


def test_un_sobre_mal_formado_es_invalido() -> None:
    with pytest.raises(EventoInvalido):
        traducir({"type": "importacion.completada", "payload": {}})
    with pytest.raises(EventoInvalido):  # un payload que no es un objeto tampoco debe escapar
        traducir(_sobre("servicio.actualizado", "no es un objeto"))  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


async def _publicar(url: str, cuerpo: bytes, clave: str) -> None:
    conexion = await aio_pika.connect_robust(url)
    async with conexion:
        canal = await conexion.channel()
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        await exchange.publish(aio_pika.Message(cuerpo), routing_key=clave)


async def _tipos(fabrica: async_sessionmaker[AsyncSession]) -> list[str]:
    async with fabrica() as sesion:
        return list(
            (await sesion.scalars(text("SELECT tipo FROM actividad ORDER BY fecha, tipo"))).all()
        )


async def _esperar(fabrica: async_sessionmaker[AsyncSession], cuantos: int) -> list[str]:
    for _ in range(200):
        tipos = await _tipos(fabrica)
        if len(tipos) >= cuantos:
            return tipos
        await asyncio.sleep(0.05)
    pytest.fail(f"No llegaron {cuantos} registros a la bitácora")


@contextlib.asynccontextmanager
async def _consumidor(
    fabrica: async_sessionmaker[AsyncSession], url: str
) -> AsyncIterator[ConsumidorEventos]:
    consumidor = ConsumidorEventos(fabrica, url)
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


@pytest.mark.integracion
async def test_un_evento_repetido_deja_un_solo_registro(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    sobre = _sobre(
        "servicio.actualizado",
        {"codigo": "NUBE-VM-2", "cambio": "creado", "campos": [], "actor": ADMIN},
        "repetido",
    )
    async with _consumidor(fabrica, url_rabbitmq):
        await _publicar(url_rabbitmq, json.dumps(sobre).encode(), "servicio.actualizado")
        await _publicar(url_rabbitmq, json.dumps(sobre).encode(), "servicio.actualizado")
        await _esperar(fabrica, 1)
        await asyncio.sleep(0.5)  # tiempo para que la segunda entrega llegue si se fuera a duplicar
    assert await _tipos(fabrica) == ["servicio.creado"]


@pytest.mark.integracion
async def test_un_mensaje_mal_formado_no_detiene_la_cola(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    valido = _sobre(
        "importacion.completada",
        {"entidad": "contratos", "filas": 5, "registros": 2, "omitidos": 0, "actor": ADMIN},
    )
    async with _consumidor(fabrica, url_rabbitmq):
        await _publicar(url_rabbitmq, b"no es json", "importacion.completada")
        await _publicar(url_rabbitmq, json.dumps(valido).encode(), "importacion.completada")
        assert await _esperar(fabrica, 1) == ["importacion.completada"]


@pytest.mark.integracion
async def test_la_cola_es_durable_de_tipo_quorum(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    async with _consumidor(fabrica, url_rabbitmq):
        conexion = await aio_pika.connect_robust(url_rabbitmq)
        async with conexion:
            canal = await conexion.channel()
            # Redeclarar con argumentos distintos falla (PRECONDITION_FAILED): si pasa, coinciden.
            cola = await canal.declare_queue(
                COLA, durable=True, arguments={"x-queue-type": "quorum", "x-delivery-limit": 5}
            )
            assert cola.name == COLA
