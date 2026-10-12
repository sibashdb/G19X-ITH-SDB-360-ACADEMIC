import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from inteligencia import modelos  # noqa: F401
from inteligencia.db import Base
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integracion


def _diferencias(conexion: Connection) -> list[object]:
    return list(compare_metadata(MigrationContext.configure(conexion), Base.metadata))


async def test_modelos_y_migraciones_coinciden(urls_bd: tuple[str, str]) -> None:
    motor = create_async_engine(urls_bd[0], poolclass=NullPool)
    async with motor.connect() as conexion:
        diferencias = await conexion.run_sync(_diferencias)
    await motor.dispose()
    assert diferencias == []


async def test_la_configuracion_inicial_tiene_los_valores_por_defecto(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica() as sesion:
        fila = (
            await sesion.execute(
                text(
                    "SELECT peso_sla, peso_resolucion, peso_incidentes, peso_entregas, "
                    "peso_satisfaccion, umbral_riesgo, inflacion_anual FROM configuracion"
                )
            )
        ).one()
    assert tuple(fila) == (30, 20, 20, 15, 15, 40, 4.5)


async def test_la_aplicacion_escribe_la_copia_local(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica() as sesion:
        await sesion.execute(
            text("INSERT INTO tipo_cambio (periodo, usd_mxn) VALUES ('2026-09-01', 18.25)")
        )
        await sesion.execute(text("UPDATE tipo_cambio SET usd_mxn = 18.30"))
        await sesion.execute(
            text(
                "INSERT INTO evento_procesado (event_id, tipo, procesado_en) "
                "VALUES ('e', 't', now())"
            )
        )
        await sesion.commit()


@pytest.mark.parametrize(
    "sentencia",
    ["DELETE FROM evento_procesado", "DELETE FROM contrato", "DELETE FROM configuracion"],
)
async def test_la_aplicacion_no_puede_borrar(
    fabrica: async_sessionmaker[AsyncSession], sentencia: str
) -> None:
    async with fabrica() as sesion:
        with pytest.raises(DBAPIError, match="permission denied"):
            await sesion.execute(text(sentencia))
