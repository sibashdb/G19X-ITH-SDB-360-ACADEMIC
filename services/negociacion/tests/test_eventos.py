import asyncio
import json
import uuid
from collections.abc import Iterator
from typing import Any

import aio_pika
import pytest
from comun.consumidor import ConsumidorEventos, EventoInvalido
from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import COLA_NEGOCIACION
from negociacion.eventos import aplicar, atendedor
from negociacion.modelos import EventoProcesado, Proveedor, Servicio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.rabbitmq import RabbitMqContainer

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]

PROVEEDOR = {
    "id": "00000000-0000-4000-8000-000000000001",
    "rfc": "NNO010101AB1",
    "nombre": "Nube Norte S.A. de C.V.",
    "tamano": "mediana",
    "categorias": ["nube"],
    "contacto_nombre": "Lucía Pérez",
    "contacto_email": "lucia@nubenorte.example",
    "activo": True,
}
SERVICIO = {
    "id": "00000000-0000-4000-8000-000000000101",
    "codigo": "NUBE-VM-STD",
    "nombre": "Máquina virtual estándar",
    "categoria": "nube",
    "unidad": "vcpu_mes",
    "moneda": "MXN",
    "activo": True,
}


def _sobre(tipo: str, payload: Any, event_id: str | None = None) -> dict[str, Any]:
    return {"event_id": event_id or str(uuid.uuid4()), "type": tipo, "payload": payload}


async def _contar(fabrica: Fabrica, modelo: type[Any]) -> int:
    async with fabrica() as bd:
        return int(await bd.scalar(select(func.count()).select_from(modelo)) or 0)


async def test_cada_evento_actualiza_la_copia(fabrica: Fabrica) -> None:
    async with fabrica() as bd, bd.begin():
        assert await aplicar(bd, _sobre("proveedor.actualizado", PROVEEDOR))
        assert await aplicar(bd, _sobre("servicio.actualizado", SERVICIO))
        assert await aplicar(
            bd, _sobre("proveedor.actualizado", PROVEEDOR | {"contacto_email": "nuevo@x.example"})
        )
    async with fabrica() as bd:
        proveedor = await bd.get(Proveedor, uuid.UUID(PROVEEDOR["id"]))
        servicio = await bd.scalar(select(Servicio).where(Servicio.codigo == "NUBE-VM-STD"))
    assert proveedor is not None
    assert proveedor.contacto_email == "nuevo@x.example"
    assert proveedor.categorias == ["nube"]
    assert servicio is not None
    assert (servicio.moneda, servicio.unidad) == ("MXN", "vcpu_mes")


async def test_un_evento_repetido_no_se_aplica_dos_veces(fabrica: Fabrica) -> None:
    async with fabrica() as bd, bd.begin():
        assert await aplicar(bd, _sobre("proveedor.actualizado", PROVEEDOR, "e-1"))
        assert not await aplicar(
            bd, _sobre("proveedor.actualizado", PROVEEDOR | {"nombre": "Otro"}, "e-1")
        )
    async with fabrica() as bd:
        proveedor = await bd.get(Proveedor, uuid.UUID(PROVEEDOR["id"]))
    assert proveedor is not None and proveedor.nombre == "Nube Norte S.A. de C.V."


async def test_un_tipo_que_no_le_importa_solo_se_anota(fabrica: Fabrica) -> None:
    async with fabrica() as bd, bd.begin():
        assert await aplicar(bd, _sobre("contrato.registrado", {"id": "x"}))
    assert await _contar(fabrica, EventoProcesado) == 1


async def test_un_evento_mal_formado_es_invalido_y_no_deja_rastro(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    with pytest.raises(EventoInvalido):
        await atender(_sobre("proveedor.actualizado", {"id": PROVEEDOR["id"]}))
    with pytest.raises(ValueError):
        await atender(_sobre("servicio.actualizado", SERVICIO | {"id": "no-es-uuid"}))
    assert await _contar(fabrica, EventoProcesado) == 0


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


async def test_consume_los_eventos_de_su_cola(fabrica: Fabrica, url_rabbitmq: str) -> None:
    consumidor = ConsumidorEventos(url_rabbitmq, COLA_NEGOCIACION, atendedor(fabrica))
    tarea = asyncio.create_task(consumidor.ejecutar())
    try:
        for _ in range(200):
            if consumidor.conectado():
                break
            await asyncio.sleep(0.05)
        conexion = await aio_pika.connect_robust(url_rabbitmq)
        async with conexion:
            canal = await conexion.channel()
            exchange = await canal.declare_exchange(
                EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
            )
            for tipo, payload in (
                ("proveedor.actualizado", PROVEEDOR),
                ("servicio.actualizado", SERVICIO),
            ):
                await exchange.publish(
                    aio_pika.Message(json.dumps(_sobre(tipo, payload)).encode()),
                    routing_key=tipo,
                )
        for _ in range(200):
            if await _contar(fabrica, Servicio) and await _contar(fabrica, Proveedor):
                break
            await asyncio.sleep(0.05)
        assert await _contar(fabrica, Proveedor) == 1
        assert await _contar(fabrica, Servicio) == 1
    finally:
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea
        await consumidor.cerrar()
