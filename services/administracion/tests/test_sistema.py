import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from administracion.bitacora import Actor, registrar
from administracion.config import Configuracion
from administracion.identidad_falsa import IdentidadFalsa
from administracion.main import crear_app
from administracion.modelos import CorreoEnviado
from comun.pruebas import ClavesPrueba
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Manejador = Callable[[httpx.Request], Awaitable[httpx.Response]]


async def _ok(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={})


async def _colas(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[{"name": "administracion.actividad", "messages_ready": 0}])


@pytest.fixture
def rutas() -> dict[str, Manejador]:
    """Respuestas de las dependencias por host; cada prueba cambia las que le interesan."""
    return {"prov": _ok, "intel": _ok, "neg": _ok, "kc": _ok, "rmq": _colas, "mail": _ok}


@pytest.fixture
async def cliente_sistema(
    urls_bd: tuple[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    claves: ClavesPrueba,
    identidad: IdentidadFalsa,
    rutas: dict[str, Manejador],
) -> AsyncIterator[httpx.AsyncClient]:
    async def manejar(peticion: httpx.Request) -> httpx.Response:
        return await rutas[peticion.url.host](peticion)

    app = crear_app(
        Configuracion(
            database_url=urls_bd[1],
            consumir_eventos=False,
            proveedores_url="http://prov",
            inteligencia_url="http://intel",
            negociacion_url="http://neg",
            keycloak_url="http://kc/auth",
            rabbitmq_url="amqp://usuario:clave@rmq:5672/",
            rabbitmq_api_url="http://rmq/api",
            mailpit_url="http://mail",
            version_app="abc1234",
        ),
        claves.validador(),
        fabrica,
        identidad,
        transporte_estado=httpx.MockTransport(manejar),
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


async def _estados(cliente: httpx.AsyncClient, admin: dict[str, str]) -> dict[str, Any]:
    respuesta = await cliente.get("/estado", headers=admin)
    assert respuesta.status_code == 200
    return dict(respuesta.json())


async def _por_clave(cliente: httpx.AsyncClient, admin: dict[str, str]) -> dict[str, Any]:
    return {s["clave"]: s for s in (await _estados(cliente, admin))["servicios"]}


async def test_todo_sano(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    vistas: list[httpx.Request] = []

    async def colas(peticion: httpx.Request) -> httpx.Response:
        vistas.append(peticion)
        return await _colas(peticion)

    rutas["rmq"] = colas
    estado = await _estados(cliente_sistema, admin)
    assert estado["version"] == "abc1234"
    servicios = estado["servicios"]
    assert [s["clave"] for s in servicios] == [
        "base_de_datos",
        "proveedores",
        "inteligencia",
        "negociacion",
        "identidad",
        "mensajeria",
        "correo",
    ]
    assert {s["estado"] for s in servicios} == {"sano"}
    [peticion] = vistas
    assert peticion.url.path == "/api/queues"
    assert peticion.headers["authorization"].startswith("Basic ")


async def test_un_servicio_caido_no_tumba_el_estado(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    async def sin_red(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=peticion)

    async def error(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    rutas["prov"] = sin_red
    rutas["intel"] = error
    rutas["kc"] = error
    servicios = await _por_clave(cliente_sistema, admin)
    assert servicios["proveedores"]["estado"] == "caido"
    assert servicios["proveedores"]["tiempo_ms"] is None
    assert servicios["inteligencia"]["estado"] == "caido"
    assert servicios["identidad"]["estado"] == "caido"
    assert servicios["base_de_datos"]["estado"] == "sano"
    assert servicios["correo"]["estado"] == "sano"


async def test_una_cola_atrasada_es_un_problema(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    async def atrasada(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"name": "administracion.actividad", "messages_ready": 150},
                {"name": "otra", "messages_ready": 100},
            ],
        )

    rutas["rmq"] = atrasada
    servicios = await _por_clave(cliente_sistema, admin)
    assert servicios["mensajeria"]["estado"] == "con_problemas"
    assert servicios["mensajeria"]["detalle"] == (
        "Mensajes pendientes en: administracion.actividad (150)."
    )


async def test_un_mensaje_en_una_cola_de_fallidos_es_un_problema(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    async def colas(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"name": "inteligencia.eventos", "messages_ready": 150, "messages": 150},
                {"name": "inteligencia.eventos.dlq", "messages_ready": 120, "messages": 120},
                {"name": "administracion.actividad", "messages_ready": 0, "messages": 0},
                {"name": "administracion.actividad.dlq", "messages_ready": 0, "messages": 0},
            ],
        )

    rutas["rmq"] = colas
    servicios = await _por_clave(cliente_sistema, admin)
    assert servicios["mensajeria"]["estado"] == "con_problemas"
    assert servicios["mensajeria"]["detalle"] == (
        "Mensajes pendientes en: inteligencia.eventos (150). "
        "Mensajes fallidos en: inteligencia.eventos.dlq (120)."
    )


async def test_colas_de_fallidos_vacias_no_son_problema(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    async def colas(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[{"name": "inteligencia.eventos.dlq", "messages_ready": 0, "messages": 0}]
        )

    rutas["rmq"] = colas
    assert (await _por_clave(cliente_sistema, admin))["mensajeria"]["estado"] == "sano"


async def test_lento_y_sin_respuesta(
    cliente_sistema: httpx.AsyncClient,
    admin: dict[str, str],
    rutas: dict[str, Manejador],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("administracion.estado.TIEMPO_LIMITE_S", 0.2)
    monkeypatch.setattr("administracion.estado.UMBRAL_LENTO_S", 0.05)

    async def lento(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.1)
        return httpx.Response(200)

    async def colgado(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200)

    rutas["mail"] = lento
    rutas["kc"] = colgado
    servicios = await _por_clave(cliente_sistema, admin)
    assert servicios["correo"]["estado"] == "con_problemas"
    assert servicios["correo"]["detalle"] == "Responde con lentitud."
    assert servicios["identidad"]["estado"] == "caido"
    assert servicios["identidad"]["detalle"] == "No respondió en 0.2 s."


async def test_resumen(
    cliente_sistema: httpx.AsyncClient,
    admin: dict[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    identidad: IdentidadFalsa,
) -> None:
    identidad.agregar("baja", ["comprador"], activo=False)
    ahora = datetime.now(UTC)
    async with fabrica() as sesion:
        for n, horas in enumerate((1, 5, 30)):
            await registrar(
                sesion,
                "sesion.fallida",
                Actor(None, "fantasma"),
                resultado="fallo",
                origen="keycloak",
                clave_origen=f"k:{n}",
                fecha=ahora - timedelta(hours=horas),
            )
        for dias in (1, 8):
            sesion.add(
                CorreoEnviado(
                    fecha=ahora - timedelta(days=dias),
                    tipo="invitacion",
                    destinatario="ana@x.mx",
                    usuario_id="ana",
                    solicitado_por="admin1",
                    estado="enviado",
                )
            )
        await sesion.commit()
    respuesta = await cliente_sistema.get("/resumen", headers=admin)
    assert respuesta.json() == {
        "usuarios_activos": 2,
        "intentos_fallidos_24h": 2,
        "correos_7d": 1,
    }


async def test_resumen_sin_identidad(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    identidad.caida = True
    respuesta = await cliente_sistema.get("/resumen", headers=admin)
    assert respuesta.status_code == 200
    assert respuesta.json()["usuarios_activos"] is None
