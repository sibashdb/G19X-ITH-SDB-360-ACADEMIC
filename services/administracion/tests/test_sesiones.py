import asyncio
import contextlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from administracion.config import Configuracion
from administracion.identidad import EventoSesion
from administracion.identidad_falsa import IdentidadFalsa
from administracion.main import crear_app
from administracion.sesiones import ejecutar_periodicamente, sincronizar
from comun.pruebas import ClavesPrueba
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

AHORA = datetime.now(UTC).replace(microsecond=0)


def _evento(
    id_: str,
    tipo: str,
    minutos: int,
    *,
    usuario_id: str | None = "ana",
    usuario: str | None = "ana",
    error: str | None = None,
) -> EventoSesion:
    return EventoSesion(
        id_, tipo, AHORA - timedelta(minutes=minutos), usuario_id, usuario, "10.0.0.7", error
    )


async def _filas(
    fabrica: async_sessionmaker[AsyncSession],
) -> list[tuple[str, str, str | None, str]]:
    async with fabrica() as sesion:
        filas = await sesion.execute(
            text("SELECT tipo, actor_nombre, actor_id, resultado FROM actividad ORDER BY fecha")
        )
        return [(f.tipo, f.actor_nombre, f.actor_id, f.resultado) for f in filas]


async def test_traduce_los_tres_tipos(fabrica: async_sessionmaker[AsyncSession]) -> None:
    falsa = IdentidadFalsa()
    falsa.eventos = [
        _evento("e1", "LOGIN", 30),
        _evento("e2", "LOGIN_ERROR", 20, error="invalid_user_credentials"),
        _evento("e3", "LOGOUT", 10),
    ]
    assert await sincronizar(falsa, fabrica) == 3
    assert await _filas(fabrica) == [
        ("sesion.iniciada", "ana", "ana", "exito"),
        ("sesion.fallida", "ana", "ana", "fallo"),
        ("sesion.cerrada", "ana", "ana", "exito"),
    ]


async def test_releer_no_duplica(fabrica: async_sessionmaker[AsyncSession]) -> None:
    falsa = IdentidadFalsa()
    falsa.eventos = [_evento("e1", "LOGIN", 30)]
    await sincronizar(falsa, fabrica)
    falsa.eventos.append(_evento("e2", "LOGOUT", 5))
    await sincronizar(falsa, fabrica)  # vuelve a leer e1 (mismo instante del cursor) y agrega e2
    assert [f[0] for f in await _filas(fabrica)] == ["sesion.iniciada", "sesion.cerrada"]


async def test_intento_con_usuario_inexistente(fabrica: async_sessionmaker[AsyncSession]) -> None:
    falsa = IdentidadFalsa()
    falsa.eventos = [
        _evento("e1", "LOGIN_ERROR", 5, usuario_id=None, usuario="fantasma", error="user_not_found")
    ]
    await sincronizar(falsa, fabrica)
    assert await _filas(fabrica) == [("sesion.fallida", "fantasma", None, "fallo")]


async def test_sin_nombre_usa_el_de_la_cuenta(fabrica: async_sessionmaker[AsyncSession]) -> None:
    falsa = IdentidadFalsa()
    falsa.usuarios["u-9"] = replace(falsa.agregar("u-9", ["comprador"]), usuario="carla")
    falsa.eventos = [_evento("e1", "LOGOUT", 5, usuario_id="u-9", usuario=None)]
    await sincronizar(falsa, fabrica)
    assert (await _filas(fabrica))[0][1] == "carla"


async def test_el_cursor_avanza(fabrica: async_sessionmaker[AsyncSession]) -> None:
    falsa = IdentidadFalsa()
    falsa.eventos = [_evento("e1", "LOGIN", 30), _evento("e2", "LOGIN", 10)]
    await sincronizar(falsa, fabrica)
    async with fabrica() as sesion:
        hasta = await sesion.scalar(
            text("SELECT hasta FROM cursor_eventos WHERE nombre = 'keycloak'")
        )
    assert hasta == AHORA - timedelta(minutes=10)


async def _esperar_filas(fabrica: async_sessionmaker[AsyncSession], cuantas: int) -> None:
    for _ in range(200):
        if len(await _filas(fabrica)) >= cuantas:
            return
        await asyncio.sleep(0.05)
    pytest.fail(f"No llegaron {cuantas} registros a la bitácora en 10 s")


async def test_el_ciclo_de_vida_copia_los_eventos_y_se_apaga(
    urls_bd: tuple[str, str], fabrica: async_sessionmaker[AsyncSession], claves: ClavesPrueba
) -> None:
    falsa = IdentidadFalsa()
    falsa.eventos = [_evento("e1", "LOGIN", 5)]
    app = crear_app(Configuracion(database_url=urls_bd[1]), claves.validador(), fabrica, falsa)
    async with asyncio.timeout(20), app.router.lifespan_context(app):
        await _esperar_filas(fabrica, 1)
    assert [f[0] for f in await _filas(fabrica)] == ["sesion.iniciada"]


async def test_el_ciclo_sobrevive_a_una_caida_de_la_identidad(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    falsa = IdentidadFalsa()
    falsa.eventos = [_evento("e1", "LOGIN", 5)]
    falsa.caida = True
    tarea = asyncio.create_task(ejecutar_periodicamente(falsa, fabrica, 1))
    try:
        await asyncio.sleep(0.3)  # la primera vuelta falla y se queda esperando para reintentar
        assert not tarea.done()
        falsa.caida = False
        await _esperar_filas(fabrica, 1)
    finally:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
