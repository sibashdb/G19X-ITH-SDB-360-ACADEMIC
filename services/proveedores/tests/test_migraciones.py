from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from proveedores import modelos  # noqa: F401
from proveedores.db import Base
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integracion

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _diferencias(conexion: Connection) -> list[object]:
    return list(compare_metadata(MigrationContext.configure(conexion), Base.metadata))


async def test_modelos_y_migraciones_coinciden(url_bd: str) -> None:
    motor = create_async_engine(url_bd, poolclass=NullPool)
    async with motor.connect() as conexion:
        diferencias = await conexion.run_sync(_diferencias)
    await motor.dispose()
    assert diferencias == []


async def test_restriccion_unica_de_desempeno_incluye_ambas_columnas(url_bd: str) -> None:
    motor = create_async_engine(url_bd, poolclass=NullPool)
    async with motor.connect() as conexion:
        nombres = await conexion.scalars(
            text("SELECT conname FROM pg_constraint WHERE conname LIKE 'uq_registro_desempeno%'")
        )
        encontrados = list(nombres)
    await motor.dispose()
    assert encontrados == ["uq_registro_desempeno_proveedor_id_periodo"]


def test_migracion_se_revierte_y_se_reaplica(url_bd: str) -> None:
    configuracion = Config(str(ALEMBIC_INI))
    command.downgrade(configuracion, "base")
    command.upgrade(configuracion, "head")
