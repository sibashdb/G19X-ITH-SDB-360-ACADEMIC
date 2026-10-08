import pytest
from administracion import modelos  # noqa: F401
from administracion.db import Base
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integracion

INSERTAR = text(
    "INSERT INTO actividad (id, fecha, actor_nombre, tipo, detalle, resultado, origen, "
    "clave_origen) VALUES (gen_random_uuid(), now(), 'prueba', 'sesion.iniciada', '{}', "
    "'exito', 'keycloak', :clave)"
)


def _diferencias(conexion: Connection) -> list[object]:
    return list(compare_metadata(MigrationContext.configure(conexion), Base.metadata))


async def test_modelos_y_migraciones_coinciden(urls_bd: tuple[str, str]) -> None:
    motor = create_async_engine(urls_bd[0], poolclass=NullPool)
    async with motor.connect() as conexion:
        diferencias = await conexion.run_sync(_diferencias)
    await motor.dispose()
    assert diferencias == []


async def test_la_aplicacion_inserta_y_lee_la_bitacora(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica() as sesion:
        await sesion.execute(INSERTAR, {"clave": "prueba:1"})
        await sesion.commit()
        assert await sesion.scalar(text("SELECT count(*) FROM actividad")) == 1


@pytest.mark.parametrize(
    "sentencia",
    ["UPDATE actividad SET tipo = 'otro'", "DELETE FROM actividad"],
)
async def test_la_aplicacion_no_puede_modificar_ni_borrar_la_bitacora(
    fabrica: async_sessionmaker[AsyncSession], sentencia: str
) -> None:
    async with fabrica() as sesion:
        await sesion.execute(INSERTAR, {"clave": "prueba:2"})
        await sesion.commit()
        with pytest.raises(DBAPIError, match="permission denied"):
            await sesion.execute(text(sentencia))


async def test_la_aplicacion_no_puede_borrar_correos(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica() as sesion:
        with pytest.raises(DBAPIError, match="permission denied"):
            await sesion.execute(text("DELETE FROM correo_enviado"))


async def test_la_aplicacion_actualiza_el_cursor(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica() as sesion:
        await sesion.execute(
            text("INSERT INTO cursor_eventos (nombre, hasta) VALUES ('keycloak', now())")
        )
        await sesion.execute(text("UPDATE cursor_eventos SET hasta = now()"))
        await sesion.commit()
