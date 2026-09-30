import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from comun.pruebas import ClavesPrueba
from proveedores.config import Configuracion
from proveedores.main import crear_app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture(scope="session")
def url_bd() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as contenedor:
        url = contenedor.get_connection_url()
        os.environ["DATABASE_URL"] = url
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        yield url


@pytest.fixture
async def fabrica(url_bd: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    motor = create_async_engine(url_bd, poolclass=NullPool)
    yield async_sessionmaker(motor, expire_on_commit=False)
    async with motor.begin() as conexion:
        await conexion.execute(
            text(
                "TRUNCATE proveedor, servicio_catalogo, contrato, linea_contrato, "
                "registro_desempeno, tipo_cambio, outbox CASCADE"
            )
        )
    await motor.dispose()


@pytest.fixture(scope="session")
def claves() -> ClavesPrueba:
    return ClavesPrueba()


@pytest.fixture
async def cliente(
    url_bd: str, fabrica: async_sessionmaker[AsyncSession], claves: ClavesPrueba
) -> AsyncIterator[httpx.AsyncClient]:
    app = crear_app(Configuracion(database_url=url_bd), claves.validador(), fabrica)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente
