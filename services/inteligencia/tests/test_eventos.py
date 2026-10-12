import asyncio
import json
import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import aio_pika
import pytest
from comun.consumidor import ConsumidorEventos
from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import COLA_INTELIGENCIA
from inteligencia.eventos import atendedor
from inteligencia.modelos import (
    Contrato,
    Desempeno,
    EventoProcesado,
    Proveedor,
    Servicio,
    TipoCambio,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.rabbitmq import RabbitMqContainer

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
ID_PROVEEDOR = "6f1c2c1e-0000-4000-8000-000000000001"
ID_SERVICIO = "6f1c2c1e-0000-4000-8000-000000000002"
ID_CONTRATO = "6f1c2c1e-0000-4000-8000-000000000003"
PROVEEDOR = {
    "id": ID_PROVEEDOR,
    "rfc": "NAZ210315AB1",
    "nombre": "Nube Azteca S.A. de C.V.",
    "tamano": "mediana",
    "categorias": ["licencia_saas"],
    "contacto_nombre": "Laura Méndez",
    "contacto_email": "ventas01@proveedor01.example",
    "activo": True,
}
SERVICIO = {
    "id": ID_SERVICIO,
    "codigo": "SAAS-OFI-EMP",
    "nombre": "Suite de productividad",
    "categoria": "licencia_saas",
    "unidad": "usuario_mes",
    "moneda": "USD",
    "activo": True,
}
CONTRATO = {
    "id": ID_CONTRATO,
    "proveedor_id": ID_PROVEEDOR,
    "folio": "C-0001",
    "rfc_proveedor": "NAZ210315AB1",
    "tipo": "nuevo",
    "fecha_inicio": "2025-01-01",
    "fecha_fin": "2025-12-31",
    "moneda": "USD",
    "plazo_pago_dias": 30,
    "sla_disponibilidad": "99.90",
    "tope_aumento_pct": "5.00",
    "cuota_implementacion": "0",
    "lineas": [
        {
            "codigo_servicio": "SAAS-OFI-EMP",
            "nombre_servicio": "Suite de productividad",
            "categoria": "licencia_saas",
            "unidad": "usuario_mes",
            "cantidad": "250",
            "precio_unitario": "21.5",
        }
    ],
}
DESEMPENO = {
    "proveedor_id": ID_PROVEEDOR,
    "periodo": "2025-01-01",
    "sla_cumplimiento_pct": "99.50",
    "tiempo_resolucion_h": "4.25",
    "incidentes_criticos": 0,
    "entregas_a_tiempo_pct": "97.00",
    "satisfaccion": "4.60",
}


def _sobre(tipo: str, payload: Any, event_id: str | None = None) -> dict[str, Any]:
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "type": tipo,
        "version": 1,
        "occurred_at": "2026-10-10T15:00:00+00:00",
        "correlation_id": "c-1",
        "payload": payload,
    }


async def _contar(fabrica: Fabrica, modelo: type[object]) -> int:
    async with fabrica() as sesion:
        return int(await sesion.scalar(select(func.count()).select_from(modelo)) or 0)


async def test_cada_evento_actualiza_la_copia(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    for tipo, payload in (
        ("proveedor.actualizado", PROVEEDOR),
        ("servicio.actualizado", SERVICIO),
        ("tipo_cambio.registrado", {"periodo": "2025-01-01", "usd_mxn": "20.4512"}),
        ("contrato.registrado", CONTRATO),
        ("desempeno.registrado", DESEMPENO),
    ):
        await atender(_sobre(tipo, payload))
    async with fabrica() as sesion:
        proveedor = await sesion.get(Proveedor, uuid.UUID(ID_PROVEEDOR))
        servicio = await sesion.get(Servicio, uuid.UUID(ID_SERVICIO))
        contrato = await sesion.get(Contrato, uuid.UUID(ID_CONTRATO))
        tipo_cambio = await sesion.scalar(select(TipoCambio.usd_mxn))
        satisfaccion = await sesion.scalar(select(Desempeno.satisfaccion))
    assert proveedor is not None and proveedor.categorias == ["licencia_saas"]
    assert servicio is not None and servicio.unidad == "usuario_mes"
    assert contrato is not None and contrato.folio == "C-0001"
    [linea] = contrato.lineas
    assert (linea.codigo_servicio, linea.cantidad, linea.precio_unitario) == (
        "SAAS-OFI-EMP",
        Decimal("250"),
        Decimal("21.5"),
    )
    assert tipo_cambio == Decimal("20.4512")
    assert satisfaccion == Decimal("4.60")
    assert await _contar(fabrica, EventoProcesado) == 5


async def test_un_evento_repetido_no_se_aplica_dos_veces(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    await atender(_sobre("desempeno.registrado", DESEMPENO, "repetido"))
    # Mismo event_id con otro contenido: es el mismo evento entregado otra vez, se ignora.
    await atender(_sobre("desempeno.registrado", DESEMPENO | {"satisfaccion": "4.90"}, "repetido"))
    async with fabrica() as sesion:
        assert await sesion.scalar(select(Desempeno.satisfaccion)) == Decimal("4.60")
    # Un evento nuevo del mismo periodo sí actualiza.
    await atender(_sobre("desempeno.registrado", DESEMPENO | {"satisfaccion": "4.90"}))
    async with fabrica() as sesion:
        assert await sesion.scalar(select(Desempeno.satisfaccion)) == Decimal("4.90")
    await atender(_sobre("contrato.registrado", CONTRATO))
    await atender(_sobre("contrato.registrado", CONTRATO))  # reproceso: otro event_id
    assert await _contar(fabrica, Contrato) == 1


async def test_un_contrato_de_un_proveedor_desconocido_se_guarda(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    await atender(_sobre("contrato.registrado", CONTRATO))
    assert await _contar(fabrica, Contrato) == 1
    await atender(_sobre("proveedor.actualizado", PROVEEDOR))
    assert await _contar(fabrica, Proveedor) == 1


async def test_la_edicion_del_catalogo_actualiza_el_servicio(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    await atender(_sobre("servicio.actualizado", SERVICIO))
    edicion = SERVICIO | {
        "nombre": "Suite de oficina",
        "activo": False,
        "cambio": "desactivado",
        "campos": [],
        "actor": {"id": "admin-1", "nombre": "admin1"},
    }
    await atender(_sobre("servicio.actualizado", edicion))
    async with fabrica() as sesion:
        servicio = await sesion.get(Servicio, uuid.UUID(ID_SERVICIO))
    assert servicio is not None
    assert (servicio.nombre, servicio.activo) == ("Suite de oficina", False)


async def test_un_tipo_que_no_le_importa_solo_se_anota(fabrica: Fabrica) -> None:
    await atendedor(fabrica)(_sobre("importacion.completada", {"entidad": "contratos"}))
    assert await _contar(fabrica, EventoProcesado) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        "no es un objeto",
        CONTRATO | {"fecha_inicio": "no es fecha"},
        CONTRATO | {"lineas": [{"codigo_servicio": "SAAS-OFI-EMP"}]},
        CONTRATO | {"lineas": [CONTRATO["lineas"][0] | {"cantidad": "mucho"}]},  # type: ignore[index]
    ],
    ids=["vacio", "texto", "fecha", "linea_incompleta", "cantidad"],
)
async def test_un_evento_mal_formado_es_invalido_y_no_deja_rastro(
    fabrica: Fabrica, payload: Any
) -> None:
    with pytest.raises(ValueError):  # EventoInvalido también es ValueError
        await atendedor(fabrica)(_sobre("contrato.registrado", payload))
    assert await _contar(fabrica, Contrato) == 0
    assert await _contar(fabrica, EventoProcesado) == 0


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


async def test_consume_los_eventos_de_su_cola(fabrica: Fabrica, url_rabbitmq: str) -> None:
    consumidor = ConsumidorEventos(url_rabbitmq, COLA_INTELIGENCIA, atendedor(fabrica))
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
            await exchange.publish(
                aio_pika.Message(json.dumps(_sobre("proveedor.actualizado", PROVEEDOR)).encode()),
                routing_key="proveedor.actualizado",
            )
        for _ in range(200):
            if await _contar(fabrica, Proveedor):
                break
            await asyncio.sleep(0.05)
        assert await _contar(fabrica, Proveedor) == 1
    finally:
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea
        await consumidor.cerrar()
