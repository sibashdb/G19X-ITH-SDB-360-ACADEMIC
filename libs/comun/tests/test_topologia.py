"""La topología de infra/rabbitmq/definitions.json: coincide con comun.topologia, cubre todo evento
que se publica y RabbitMQ la acepta."""

import asyncio
import json
import re
from collections.abc import Iterator
from pathlib import Path

import aio_pika
import httpx
import pytest
from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import (
    ARGUMENTOS_COLA,
    COLA_ADMINISTRACION,
    COLA_INTELIGENCIA,
    TIPOS_EVENTO,
    coincide,
    colas_de,
    definiciones,
)
from testcontainers.community.rabbitmq import RabbitMqContainer

RAIZ = Path(__file__).resolve().parents[3]
ARCHIVO = RAIZ / "infra" / "rabbitmq" / "definitions.json"
# registrar_evento(sesion, Modelo, "tipo.evento", …): el tipo siempre se escribe como literal.
PUBLICACION = re.compile(r'registrar_evento\(\s*\w+,\s*\w+,\s*"([a-z_]+\.[a-z_]+)"')


def test_el_archivo_coincide_con_el_modulo() -> None:
    assert json.loads(ARCHIVO.read_text(encoding="utf-8")) == definiciones()


def test_las_claves_comparan_palabra_por_palabra() -> None:
    assert coincide("servicio.*", "servicio.actualizado")
    assert not coincide("servicio.*", "contrato.registrado")
    assert not coincide("servicio.*", "servicio.actualizado.extra")
    assert colas_de("servicio.actualizado") == [
        COLA_INTELIGENCIA.nombre,
        COLA_ADMINISTRACION.nombre,
    ]
    assert colas_de("importacion.completada") == [COLA_ADMINISTRACION.nombre]
    assert colas_de("modelo.entrenado") == [COLA_ADMINISTRACION.nombre]


def _tipos_publicados() -> set[str]:
    tipos: set[str] = set()
    for ruta in RAIZ.glob("services/*/src/**/*.py"):
        tipos.update(PUBLICACION.findall(ruta.read_text(encoding="utf-8")))
    return tipos


def test_cada_evento_publicado_esta_declarado_y_tiene_cola() -> None:
    publicados = _tipos_publicados()
    assert "contrato.registrado" in publicados  # que la búsqueda no quede vacía
    assert publicados <= TIPOS_EVENTO, sorted(publicados - TIPOS_EVENTO)
    assert sorted(t for t in TIPOS_EVENTO if not colas_de(t)) == []


@pytest.fixture(scope="module")
def rabbitmq() -> Iterator[tuple[str, str]]:
    """(URL AMQP, URL de la API de administración) de un RabbitMQ con ese plugin."""
    contenedor = RabbitMqContainer(
        "rabbitmq:4.1-management-alpine", username="prueba", password="prueba"
    ).with_exposed_ports(15672)
    with contenedor as rmq:
        host = rmq.get_container_host_ip()
        yield (
            f"amqp://prueba:prueba@{host}:{rmq.get_exposed_port(5672)}/",
            f"http://{host}:{rmq.get_exposed_port(15672)}/api",
        )


async def _aplicar(api: str) -> None:
    contenido = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    async with httpx.AsyncClient(auth=("prueba", "prueba"), timeout=5) as http:
        for _ in range(120):  # la API de administración arranca unos segundos después que AMQP
            try:
                respuesta = await http.post(f"{api}/definitions", json=contenido)
                if respuesta.is_success:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.5)
    pytest.fail("RabbitMQ no aceptó las definiciones")


@pytest.mark.integracion
async def test_rabbitmq_acepta_la_topologia_y_manda_a_fallidos_tras_5_entregas(
    rabbitmq: tuple[str, str],
) -> None:
    amqp, api = rabbitmq
    conexion = await aio_pika.connect_robust(amqp)
    async with conexion:
        canal = await conexion.channel()
        # Un entorno existente: la cola de administración ya la había declarado su consumidor.
        await canal.declare_queue(
            COLA_ADMINISTRACION.nombre, durable=True, arguments=ARGUMENTOS_COLA
        )
        await _aplicar(api)
        await _aplicar(api)  # aplicarla de nuevo no cambia nada

        exchange = await canal.get_exchange(EXCHANGE_EVENTOS)
        await exchange.publish(
            aio_pika.Message(b'{"prueba": 1}'), routing_key="contrato.registrado"
        )
        cola = await canal.get_queue(COLA_INTELIGENCIA.nombre)
        for _ in range(10):  # se rechaza cada entrega hasta que RabbitMQ la manda a fallidos
            mensaje = await cola.get(timeout=5, fail=False)
            if mensaje is None:
                break
            await mensaje.reject(requeue=True)

        fallidos = await canal.get_queue(COLA_INTELIGENCIA.fallidos)
        muerto = None
        for _ in range(50):
            muerto = await fallidos.get(timeout=5, fail=False)
            if muerto is not None:
                break
            await asyncio.sleep(0.1)
        assert muerto is not None
        await muerto.ack()
        assert muerto.body == b'{"prueba": 1}'
        # contrato.* no va a administración.
        administracion = await canal.get_queue(COLA_ADMINISTRACION.nombre)
        assert await administracion.get(timeout=5, fail=False) is None
