import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI
from negociacion.config import Configuracion
from negociacion.eventos import aplicar
from negociacion.main import crear_app
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
CLAVE_APLICACION = "clave-aplicacion-prueba"
TABLAS = (
    "evento, linea, palanca, sesion, oferta, mensaje, bitacora, proveedor, servicio, "
    "evento_procesado, outbox"
)
Fabrica = async_sessionmaker[AsyncSession]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]


@pytest.fixture(scope="session")
def urls_bd() -> Iterator[tuple[str, str]]:
    """(URL del dueño, que migra; URL del usuario de la aplicación, con permisos reducidos)."""
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as contenedor:
        # El rol de la aplicación existe antes de migrar, como en infra/postgres/negociacion.sh.
        resultado = contenedor.exec(
            [
                "psql",
                "-U",
                contenedor.username,
                "-d",
                contenedor.dbname,
                "-c",
                f"CREATE ROLE negociacion LOGIN PASSWORD '{CLAVE_APLICACION}'",
            ]
        )
        assert resultado.exit_code == 0, resultado.output
        url_dueno = contenedor.get_connection_url()
        os.environ["DATABASE_URL_MIGRACIONES"] = url_dueno
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        url_app = (
            make_url(url_dueno)
            .set(username="negociacion", password=CLAVE_APLICACION)
            .render_as_string(hide_password=False)
        )
        yield url_dueno, url_app


@pytest.fixture
async def fabrica(urls_bd: tuple[str, str]) -> AsyncIterator[Fabrica]:
    url_dueno, url_app = urls_bd
    motor = create_async_engine(url_app, poolclass=NullPool)
    yield async_sessionmaker(motor, expire_on_commit=False)
    await motor.dispose()
    # La aplicación no puede borrar la bitácora ni los mensajes: limpia el dueño.
    limpieza = create_async_engine(url_dueno, poolclass=NullPool)
    async with limpieza.begin() as conexion:
        await conexion.execute(text(f"TRUNCATE {TABLAS} CASCADE"))
        await conexion.execute(text("ALTER SEQUENCE folio_evento RESTART"))
    await limpieza.dispose()


@pytest.fixture(scope="session")
def claves() -> ClavesPrueba:
    return ClavesPrueba()


@pytest.fixture
def app(urls_bd: tuple[str, str], fabrica: Fabrica, claves: ClavesPrueba) -> FastAPI:
    return crear_app(
        Configuracion(database_url=urls_bd[1], usar_rabbitmq=False), claves.validador(), fabrica
    )


@pytest.fixture
async def cliente(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente


@pytest.fixture
def comprador(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('comprador', sub='comprador-1')}"}


@pytest.fixture
def aprobador(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('aprobador', sub='aprobador-1')}"}


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


@pytest.fixture
def aplicar_evento(fabrica: Fabrica) -> AplicarEvento:
    """Aplica un evento suelto, como si hubiera llegado por la cola."""

    async def _aplicar(tipo: str, payload: dict[str, Any]) -> None:
        async with fabrica() as bd, bd.begin():
            await aplicar(bd, {"event_id": str(uuid.uuid4()), "type": tipo, "payload": payload})

    return _aplicar
