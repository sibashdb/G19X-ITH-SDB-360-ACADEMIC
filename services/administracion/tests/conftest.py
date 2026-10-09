import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from administracion.config import Configuracion
from administracion.identidad_falsa import IdentidadFalsa
from administracion.main import crear_app
from alembic import command
from alembic.config import Config
from comun.pruebas import ClavesPrueba
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
CLAVE_APLICACION = "clave-aplicacion-prueba"


@pytest.fixture(scope="session")
def urls_bd() -> Iterator[tuple[str, str]]:
    """(URL del dueño, que migra; URL del usuario de la aplicación, con permisos reducidos)."""
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as contenedor:
        # El rol de la aplicación existe antes de migrar, como en infra/postgres/administracion.sh.
        resultado = contenedor.exec(
            [
                "psql",
                "-U",
                contenedor.username,
                "-d",
                contenedor.dbname,
                "-c",
                f"CREATE ROLE administracion LOGIN PASSWORD '{CLAVE_APLICACION}'",
            ]
        )
        assert resultado.exit_code == 0, resultado.output
        url_dueno = contenedor.get_connection_url()
        os.environ["DATABASE_URL_MIGRACIONES"] = url_dueno
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        url_app = (
            make_url(url_dueno)
            .set(username="administracion", password=CLAVE_APLICACION)
            .render_as_string(hide_password=False)
        )
        yield url_dueno, url_app


@pytest.fixture
async def fabrica(
    urls_bd: tuple[str, str],
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url_dueno, url_app = urls_bd
    motor = create_async_engine(url_app, poolclass=NullPool)
    yield async_sessionmaker(motor, expire_on_commit=False)
    await motor.dispose()
    # La aplicación no puede borrar la bitácora: limpia el dueño.
    limpieza = create_async_engine(url_dueno, poolclass=NullPool)
    async with limpieza.begin() as conexion:
        await conexion.execute(text("TRUNCATE actividad, correo_enviado, cursor_eventos"))
    await limpieza.dispose()


@pytest.fixture(scope="session")
def claves() -> ClavesPrueba:
    return ClavesPrueba()


@pytest.fixture
def identidad() -> IdentidadFalsa:
    falsa = IdentidadFalsa()
    falsa.agregar("admin-1", ["admin"], nombre="Andrea", apellidos="Administradora")
    falsa.agregar("comprador-1", ["comprador"], nombre="Carlos", apellidos="Comprador")
    return falsa


@pytest.fixture
async def cliente(
    urls_bd: tuple[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    claves: ClavesPrueba,
    identidad: IdentidadFalsa,
) -> AsyncIterator[httpx.AsyncClient]:
    app = crear_app(
        Configuracion(database_url=urls_bd[1], buzon_url="http://buzon:8025"),
        claves.validador(),
        fabrica,
        identidad,
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente
