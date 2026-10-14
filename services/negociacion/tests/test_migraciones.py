import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from negociacion import modelos  # noqa: F401
from negociacion.db import Base
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integracion
BITACORA = (
    "INSERT INTO bitacora (id, fecha, actor_tipo, actor_nombre, accion, detalle) "
    "VALUES (gen_random_uuid(), now(), 'sistema', 'Sistema', 'prueba', '{}')"
)


def _diferencias(conexion: Connection) -> list[object]:
    return list(compare_metadata(MigrationContext.configure(conexion), Base.metadata))


async def test_modelos_y_migraciones_coinciden(urls_bd: tuple[str, str]) -> None:
    motor = create_async_engine(urls_bd[0], poolclass=NullPool)
    async with motor.connect() as conexion:
        diferencias = await conexion.run_sync(_diferencias)
    await motor.dispose()
    assert diferencias == []


async def test_la_aplicacion_usa_las_secuencias(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica() as bd:
        assert await bd.scalar(text("SELECT nextval('folio_evento')")) == 1
        assert await bd.scalar(text("SELECT nextval('orden')")) >= 1


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE bitacora SET accion = 'otra'",
        "DELETE FROM bitacora",
        "UPDATE mensaje SET texto = 'otro'",
        "DELETE FROM mensaje",
        "UPDATE oferta SET valida = false",
        "DELETE FROM oferta",
        "DELETE FROM evento",
        "DELETE FROM sesion",
    ],
)
async def test_la_aplicacion_no_reescribe_el_historial(
    fabrica: async_sessionmaker[AsyncSession], sentencia: str
) -> None:
    async with fabrica() as bd:
        await bd.execute(text(BITACORA))
        await bd.commit()
    async with fabrica() as bd:
        with pytest.raises(DBAPIError, match="permission denied"):
            await bd.execute(text(sentencia))
