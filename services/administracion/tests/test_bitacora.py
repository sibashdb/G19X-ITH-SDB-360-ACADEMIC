from datetime import UTC, datetime

import pytest
from administracion.bitacora import (
    Actor,
    FiltroActividad,
    Objeto,
    consultar,
    registrar,
    ultimos_accesos,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

ANA = Actor("ana", "ana", "10.0.0.1")
ADMIN = Actor("admin-1", "admin1")


def _f(dia: int, hora: int = 12) -> datetime:
    return datetime(2026, 10, dia, hora, tzinfo=UTC)


async def _sembrar(sesion: AsyncSession) -> None:
    await registrar(
        sesion, "sesion.iniciada", ANA, origen="keycloak", clave_origen="k:1", fecha=_f(1)
    )
    await registrar(
        sesion, "sesion.iniciada", ANA, origen="keycloak", clave_origen="k:2", fecha=_f(5)
    )
    await registrar(
        sesion,
        "usuario.desactivado",
        ADMIN,
        objeto=Objeto("usuario", "ana", "Ana López"),
        fecha=_f(3),
    )
    await registrar(
        sesion,
        "sesion.fallida",
        Actor(None, "fantasma"),
        resultado="fallo",
        origen="keycloak",
        clave_origen="k:3",
        fecha=_f(4),
    )
    await sesion.commit()


async def test_registrar_es_idempotente_por_clave(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica() as sesion:
        for _ in range(2):
            await registrar(sesion, "sesion.iniciada", ANA, origen="keycloak", clave_origen="k:9")
        await sesion.commit()
        total, _ = await consultar(sesion, FiltroActividad(), 0, 10)
    assert total == 1


async def test_consultar_por_persona_incluye_lo_que_hizo_y_lo_que_le_hicieron(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica() as sesion:
        await _sembrar(sesion)
        total, filas = await consultar(sesion, FiltroActividad(persona="ana"), 0, 10)
    assert total == 3
    assert [f.tipo for f in filas] == ["sesion.iniciada", "usuario.desactivado", "sesion.iniciada"]


async def test_consultar_por_grupo_y_rango(fabrica: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica() as sesion:
        await _sembrar(sesion)
        total, filas = await consultar(
            sesion, FiltroActividad(tipo="sesiones", desde=_f(2, 0), hasta=_f(5, 0)), 0, 10
        )
    assert total == 1
    assert filas[0].actor_nombre == "fantasma"
    assert filas[0].actor_id is None


async def test_paginacion_mas_reciente_primero(fabrica: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica() as sesion:
        await _sembrar(sesion)
        total, filas = await consultar(sesion, FiltroActividad(), 1, 2)
    assert total == 4
    assert [f.fecha for f in filas] == [_f(4), _f(3)]


async def test_ultimos_accesos(fabrica: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica() as sesion:
        await _sembrar(sesion)
        accesos = await ultimos_accesos(sesion, ["ana", "admin-1"])
    assert accesos == {"ana": _f(5)}
