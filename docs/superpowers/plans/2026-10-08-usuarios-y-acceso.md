# Usuarios y acceso — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un administrador da de alta, edita, desactiva y reactiva usuarios, les envía un correo para definir su contraseña o les asigna una contraseña temporal, y ve su actividad. Todo pasa desde la plataforma y queda en una bitácora inmutable.

**Architecture:**
- Servicio nuevo `administracion` (FastAPI) con base de datos propia.
  - Bitácora de solo inserción, garantizada con permisos de PostgreSQL.
  - Registro de correos enviados.
  - Cursor de eventos de Keycloak.
- Keycloak queda detrás de un puerto `ProveedorIdentidad`. La implementación real usa la API de administración con una cuenta de servicio de permisos acotados.
- Los correos salen de Keycloak hacia un buzón de desarrollo (Mailpit).
- La SPA agrega el área "Sistema" con Usuarios, Detalle de usuario y Correos.

**Tech Stack:**
- Backend: Python 3.13, FastAPI, SQLAlchemy async + asyncpg, Alembic, httpx, pytest + Testcontainers.
- Identidad y correo: Keycloak 26.5 (API de administración, eventos, SMTP, temas) y Mailpit.
- Web: React 19 + TS, TanStack Query 5, shadcn (radix-nova), Vitest + Testing Library + axe.

**Spec:** `docs/superpowers/specs/2026-10-08-gestion-administracion-design.md`. Este plan cubre el plan 1, "Usuarios y acceso" (sección 10).

## Global Constraints

**Rama y entorno**
- Rama `feat/gestion-administracion`.
- Windows + Git Bash. Comandos de Docker con `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"; export MSYS_NO_PATHCONV=1`.
- Comandos de uv con `export PATH="/c/Users/sebas/AppData/Local/Microsoft/WinGet/Links:$PATH"; export UV_PYTHON="C:/Users/sebas/AppData/Roaming/uv/python/cpython-3.13.15-windows-x86_64-none/python.exe"`.

**Autorización**
- Todos los endpoints de `administracion` exigen el rol `admin`, salvo `/salud/*`.
- Roles asignables: solo `admin`, `comprador` y `aprobador`.
- Reglas de protección:
  - "No puede desactivar su propia cuenta."
  - "No puede quitarse el rol de administrador."
  - "Debe quedar al menos un administrador activo."

**Bitácora y contraseñas**
- Bitácora `actividad`: el usuario de BD de la aplicación (`administracion`) solo tiene SELECT e INSERT. El dueño (`administracion_dueno`) corre las migraciones.
- Contraseña temporal:
  - 16 caracteres con mayúscula, minúscula, dígito y símbolo.
  - La genera el servidor y se devuelve una sola vez.
  - Nunca se guarda en la BD, ni en logs, ni en la bitácora.

**Correos**
- Vigencia del enlace: invitación 72 h (`259200` s); restablecimiento 24 h (`86400` s).
- Mailpit:
  - SMTP `mailpit:1025`, solo en la red interna; interfaz en `127.0.0.1:8025`.
  - Remitente `no-responder@pluri.one.test`, nombre "PluriOne".

**Keycloak**
- Cuenta de servicio del cliente `administracion`: solo `view-users`, `manage-users` y `view-events` de `realm-management`.
- Tiempo límite de 5 s por llamada.
- Eventos `LOGIN`, `LOGIN_ERROR` y `LOGOUT`, guardados 30 días (`2592000` s). `administracion` los lee cada 30 s.

**Interfaz**
- Español de México, de usted; solo tokens de color.
- 0 violaciones de axe; usable de 375 a 1440 px sin scroll horizontal.
- Filtros en la URL.
- Fechas en UTC en la BD; se muestran en `America/Mexico_City`.

**Dependencias nuevas**
- Backend: `httpx` como dependencia de ejecución de `administracion`; ya está en `uv.lock`.
- Web: solo `npx shadcn@4.21.0 add dialog alert-dialog checkbox radio-group label`, que usa el paquete `radix-ui` ya instalado.

**Seguridad de credenciales**
- Nunca escriba contraseñas ni secretos en comandos, archivos versionados o reportes. `infra/.env` no se versiona.
- Las contraseñas de desarrollo están en `infra/keycloak/realm-plataforma.json`; no las repita.

**Calidad**
- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` y `uv run pytest` sin errores.
- En `web/`: `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check "src/**/*.{ts,tsx}"` limpios. La salida de las pruebas no lleva advertencias.

**Commits**
- Conventional Commits en español.
- Mensaje: asunto, una línea en blanco y `Co-Authored-By: <modelo real> <noreply@anthropic.com>` (dos `-m`).
- Verifique con `git log -1 --format=%B`.

## Review Focus

1. **Alta con usuario o correo repetido.** Keycloak responde 409 en ambos casos y la persona debe ver el error junto al campo correcto. Pruebas: Task 3 (`test_crear_usuario_duplicado_distingue_usuario_y_correo`) y Task 5 (`test_alta_duplicada_marca_el_campo`).
2. **La invitación no sale (SMTP caído).** El usuario queda creado, la respuesta dice `correo_enviado: false`, el correo queda `fallido` y la bitácora marca `fallo`. Pruebas: Task 5 (`test_alta_con_correo_caido_crea_la_cuenta_y_lo_avisa`) y Task 9 (aviso con enlace a la ficha).
3. **El último administrador activo.** Solo cuentan los administradores **activos**: uno desactivado no salva al último. Prueba: Task 4 (`test_un_admin_inactivo_no_cuenta_como_respaldo`).
4. **Eventos de Keycloak releídos o sin usuario.**
   - Volver a leer el mismo día no duplica registros.
   - Un `LOGIN_ERROR` de un usuario que no existe (sin `userId`) se registra con el nombre intentado.
   - Pruebas: Task 6 (`test_releer_no_duplica` y `test_intento_con_usuario_inexistente`).
5. **La contraseña temporal reaparece.** Al cerrar el diálogo desaparece del DOM y del estado, y no vuelve al reabrir el alta. Prueba: Task 9 (`la contraseña temporal se muestra una sola vez`).

---

### Task 1: Servicio `administracion`: esqueleto, base de datos y despliegue

**Files:**
- Create:
  - `services/administracion/pyproject.toml`, `services/administracion/Dockerfile`
  - `services/administracion/alembic.ini`
  - `services/administracion/alembic/env.py`, `services/administracion/alembic/script.py.mako`
  - `services/administracion/alembic/versions/0001_esquema_inicial.py`
  - `services/administracion/src/administracion/__init__.py`, `config.py`, `db.py`, `modelos.py`, `main.py`
  - `services/administracion/tests/conftest.py`, `test_migraciones.py`, `test_salud.py`
  - `infra/postgres/administracion.sh`
- Modify:
  - `pyproject.toml` (raíz) y `uv.lock`
  - `infra/docker-compose.yml`, `infra/.env.example`, `infra/nginx/nginx.conf`

**Interfaces:**
- Produces:
  - `administracion.config.Configuracion`, con los campos `database_url`, `database_url_migraciones`, `keycloak_url`, `keycloak_realm`, `keycloak_cliente`, `keycloak_secreto`, `url_app`, `buzon_url` e `intervalo_eventos_s`.
  - `administracion.db.Base` y `obtener_sesion(request) -> AsyncIterator[AsyncSession]`.
  - Modelos `Actividad`, `CorreoEnviado` y `CursorEventos` (columnas abajo).
  - `crear_app(configuracion=None, validador=None, fabrica=None) -> FastAPI`.
  - Fixtures de prueba `urls_bd -> tuple[url_dueno, url_app]`, `fabrica` (usuario de la aplicación), `claves` y `cliente`.

- [ ] **Step 1: Registrar el paquete en el workspace**

`services/administracion/pyproject.toml`:

```toml
[project]
name = "administracion"
version = "0.1.0"
description = "Usuarios, bitácora de actividad, correos y estado del sistema"
requires-python = ">=3.13"
dependencies = [
    "comun",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "httpx>=0.28",
    "tzdata>=2024.1",  # base IANA para ZoneInfo en Windows e imágenes slim
]

[tool.uv.sources]
comun = { workspace = true }

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

En `pyproject.toml` (raíz):
- agregue `"administracion",` al grupo `dev`, después de `"comun",`;
- agregue `administracion = { workspace = true }` en `[tool.uv.sources]`;
- agregue `"administracion"` a `source` en `[tool.coverage.run]`;
- agregue `"administracion"` a `packages` en `[tool.mypy]`.

Cree `services/administracion/src/administracion/__init__.py` vacío.

Run: `uv lock && uv sync` → Expected: `uv.lock` actualizado sin errores.

- [ ] **Step 2: Configuración, base y modelos**

`services/administracion/src/administracion/config.py`:

```python
from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "administracion"
    # Usuario de la aplicación: sin UPDATE ni DELETE sobre la bitácora.
    database_url: str = (
        "postgresql+asyncpg://administracion:administracion@localhost:5432/administracion_db"
    )
    # Dueño del esquema: solo para correr las migraciones.
    database_url_migraciones: str = (
        "postgresql+asyncpg://administracion_dueno:administracion_dueno"
        "@localhost:5432/administracion_db"
    )
    keycloak_url: str = "http://localhost:8080/auth"
    keycloak_realm: str = "plataforma"
    keycloak_cliente: str = "administracion"
    keycloak_secreto: str = ""
    url_app: str = "http://localhost:8080/"
    buzon_url: str = ""
    intervalo_eventos_s: int = 30
```

`services/administracion/src/administracion/db.py`:

```python
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


async def obtener_sesion(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.fabrica() as sesion:
        yield sesion
```

`services/administracion/src/administracion/modelos.py`:

```python
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from administracion.db import Base


def _ahora() -> datetime:
    return datetime.now(UTC)


class Actividad(Base):
    """Bitácora de solo inserción: el usuario de la aplicación no tiene UPDATE ni DELETE."""

    __tablename__ = "actividad"
    __table_args__ = (
        CheckConstraint("resultado IN ('exito', 'fallo')", name="resultado"),
        CheckConstraint("origen IN ('keycloak', 'proveedores', 'administracion')", name="origen"),
        Index("ix_actividad_fecha", "fecha"),
        Index("ix_actividad_actor_id", "actor_id"),
        Index("ix_actividad_objeto_id", "objeto_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    actor_id: Mapped[str | None] = mapped_column(String(64))
    actor_nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(60))
    objeto_tipo: Mapped[str | None] = mapped_column(String(30))
    objeto_id: Mapped[str | None] = mapped_column(String(64))
    objeto_nombre: Mapped[str | None] = mapped_column(String(200))
    detalle: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    resultado: Mapped[str] = mapped_column(String(10), default="exito")
    ip: Mapped[str | None] = mapped_column(String(64))
    origen: Mapped[str] = mapped_column(String(20))
    clave_origen: Mapped[str] = mapped_column(String(200), unique=True)


class CorreoEnviado(Base):
    __tablename__ = "correo_enviado"
    __table_args__ = (
        CheckConstraint("tipo IN ('invitacion', 'restablecimiento')", name="tipo"),
        CheckConstraint("estado IN ('enviado', 'fallido')", name="estado"),
        Index("ix_correo_enviado_fecha", "fecha"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    tipo: Mapped[str] = mapped_column(String(20))
    destinatario: Mapped[str] = mapped_column(String(254))
    usuario_id: Mapped[str] = mapped_column(String(64))
    solicitado_por: Mapped[str] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(10))
    error: Mapped[str | None] = mapped_column(String(500))


class CursorEventos(Base):
    """Hasta qué momento se copiaron a la bitácora los eventos de una fuente."""

    __tablename__ = "cursor_eventos"

    nombre: Mapped[str] = mapped_column(String(30), primary_key=True)
    hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 3: Alembic con el usuario dueño**

Copie `services/proveedores/alembic/script.py.mako` a `services/administracion/alembic/script.py.mako` sin cambios.

`services/administracion/alembic.ini`: copie `services/proveedores/alembic.ini` sin cambios. Su `script_location = %(here)s/alembic` ya es relativo.

`services/administracion/alembic/env.py`:

```python
import asyncio

from administracion import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from administracion.config import Configuracion
from administracion.db import Base
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
# Migra el dueño del esquema; la aplicación usa otro usuario con menos permisos.
# configparser interpreta "%": se escapa por si la contraseña lo contiene.
config.set_main_option(
    "sqlalchemy.url", Configuracion().database_url_migraciones.replace("%", "%%")
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
```

`services/administracion/alembic/versions/0001_esquema_inicial.py`:

```python
"""Esquema inicial de administracion: bitácora, correos enviados y cursor de eventos.

Revision ID: 0001
Revises:
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "actividad",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("actor_nombre", sa.String(200), nullable=False),
        sa.Column("tipo", sa.String(60), nullable=False),
        sa.Column("objeto_tipo", sa.String(30), nullable=True),
        sa.Column("objeto_id", sa.String(64), nullable=True),
        sa.Column("objeto_nombre", sa.String(200), nullable=True),
        sa.Column("detalle", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resultado", sa.String(10), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("origen", sa.String(20), nullable=False),
        sa.Column("clave_origen", sa.String(200), nullable=False),
        sa.CheckConstraint("resultado IN ('exito', 'fallo')", name=op.f("ck_actividad_resultado")),
        sa.CheckConstraint(
            "origen IN ('keycloak', 'proveedores', 'administracion')",
            name=op.f("ck_actividad_origen"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actividad")),
        sa.UniqueConstraint("clave_origen", name=op.f("uq_actividad_clave_origen")),
    )
    op.create_index("ix_actividad_fecha", "actividad", ["fecha"])
    op.create_index("ix_actividad_actor_id", "actividad", ["actor_id"])
    op.create_index("ix_actividad_objeto_id", "actividad", ["objeto_id"])

    op.create_table(
        "correo_enviado",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("destinatario", sa.String(254), nullable=False),
        sa.Column("usuario_id", sa.String(64), nullable=False),
        sa.Column("solicitado_por", sa.String(200), nullable=False),
        sa.Column("estado", sa.String(10), nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('invitacion', 'restablecimiento')", name=op.f("ck_correo_enviado_tipo")
        ),
        sa.CheckConstraint(
            "estado IN ('enviado', 'fallido')", name=op.f("ck_correo_enviado_estado")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_correo_enviado")),
    )
    op.create_index("ix_correo_enviado_fecha", "correo_enviado", ["fecha"])

    op.create_table(
        "cursor_eventos",
        sa.Column("nombre", sa.String(30), nullable=False),
        sa.Column("hasta", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("nombre", name=op.f("pk_cursor_eventos")),
    )

    # El rol "administracion" (usuario de la aplicación) lo crea infra/postgres/administracion.sh.
    # La bitácora y el registro de correos son de solo inserción para la aplicación.
    op.execute("GRANT SELECT, INSERT ON actividad, correo_enviado TO administracion")
    op.execute("GRANT SELECT, INSERT, UPDATE ON cursor_eventos TO administracion")


def downgrade() -> None:
    op.drop_table("cursor_eventos")
    op.drop_index("ix_correo_enviado_fecha", table_name="correo_enviado")
    op.drop_table("correo_enviado")
    op.drop_index("ix_actividad_objeto_id", table_name="actividad")
    op.drop_index("ix_actividad_actor_id", table_name="actividad")
    op.drop_index("ix_actividad_fecha", table_name="actividad")
    op.drop_table("actividad")
```

- [ ] **Step 4: Aplicación mínima con `/salud`**

`services/administracion/src/administracion/main.py`:

```python
"""Aplicación FastAPI del servicio de administración."""

from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.salud import crear_router_salud
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from administracion.config import Configuracion


def crear_app(
    configuracion: Configuracion | None = None,
    validador: ValidadorJWT | None = None,
    fabrica: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    config = configuracion or Configuracion()
    configurar_logs(config.nombre_servicio, config.log_level)
    sesiones = fabrica or async_sessionmaker(
        create_async_engine(config.database_url, pool_pre_ping=True, hide_parameters=True),
        expire_on_commit=False,
    )
    app = FastAPI(
        title="Servicio de administración", version="0.1.0", root_path=config.root_path
    )
    app.state.fabrica = sesiones
    app.state.config = config
    app.state.validador = validador or validador_desde_jwks(
        config.oidc_issuer, config.oidc_audience, config.oidc_jwks_url
    )
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    async def verificar_postgres() -> None:
        async with sesiones() as sesion:
            await sesion.execute(text("SELECT 1"))

    app.include_router(crear_router_salud({"postgres": verificar_postgres}))
    return app
```

- [ ] **Step 5: Pruebas que fallan (permisos y salud)**

`services/administracion/tests/conftest.py`:

```python
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from administracion.config import Configuracion
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
async def cliente(
    urls_bd: tuple[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    claves: ClavesPrueba,
) -> AsyncIterator[httpx.AsyncClient]:
    app = crear_app(Configuracion(database_url=urls_bd[1]), claves.validador(), fabrica)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente
```

`services/administracion/tests/test_migraciones.py`:

```python
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
```

`services/administracion/tests/test_salud.py`:

```python
import httpx
import pytest

pytestmark = pytest.mark.integracion


async def test_listo_con_postgres(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/salud/listo")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "dependencias": {"postgres": "ok"}}
```

Run: `uv run pytest services/administracion -q`.

Expected: PASS. La migración ya está escrita; el paso existe para confirmar que los permisos funcionan. Compruebe que la prueba de permisos **falla** si quita temporalmente la línea `GRANT SELECT, INSERT ON actividad…` de la migración: debe fallar con `permission denied` en el INSERT. Restaure la línea y anote ambas salidas en el reporte.

- [ ] **Step 6: PostgreSQL, Docker y gateway**

`infra/postgres/administracion.sh`:

```bash
#!/bin/bash
# Base de datos del servicio de administración con dos usuarios: el dueño (corre las migraciones)
# y el de la aplicación (los permisos por tabla los da la migración; sin UPDATE ni DELETE sobre la
# bitácora). Es idempotente. Corre solo en volúmenes nuevos; en un volumen existente:
#   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/20-administracion.sh
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname postgres <<EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'administracion_dueno') THEN
    CREATE ROLE administracion_dueno LOGIN PASSWORD '${ADMINISTRACION_DUENO_DB_PASSWORD}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'administracion') THEN
    CREATE ROLE administracion LOGIN PASSWORD '${ADMINISTRACION_DB_PASSWORD}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE administracion_db OWNER administracion_dueno'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'administracion_db')\gexec
REVOKE CONNECT ON DATABASE administracion_db FROM PUBLIC;
GRANT CONNECT ON DATABASE administracion_db TO administracion;
EOSQL
```

En `infra/docker-compose.yml`:
- En `postgres.environment`, agregue:

  ```yaml
      ADMINISTRACION_DB_PASSWORD: ${ADMINISTRACION_DB_PASSWORD:?Defina ADMINISTRACION_DB_PASSWORD en infra/.env}
      ADMINISTRACION_DUENO_DB_PASSWORD: ${ADMINISTRACION_DUENO_DB_PASSWORD:?Defina ADMINISTRACION_DUENO_DB_PASSWORD en infra/.env}
  ```

  Y en `postgres.volumes`: `- ./postgres/administracion.sh:/docker-entrypoint-initdb.d/20-administracion.sh:ro`.
- Después del servicio `proveedores`, agregue:

  ```yaml
    administracion:
      build:
        context: ..
        dockerfile: services/administracion/Dockerfile
      environment:
        DATABASE_URL: postgresql+asyncpg://administracion:${ADMINISTRACION_DB_PASSWORD}@postgres:5432/administracion_db
        DATABASE_URL_MIGRACIONES: postgresql+asyncpg://administracion_dueno:${ADMINISTRACION_DUENO_DB_PASSWORD}@postgres:5432/administracion_db
        OIDC_ISSUER: http://localhost:8080/auth/realms/plataforma
        OIDC_JWKS_URL: http://keycloak:8080/auth/realms/plataforma/protocol/openid-connect/certs
        ROOT_PATH: /api/administracion
      depends_on:
        postgres:
          condition: service_healthy
      healthcheck:
        test:
          - CMD
          - python
          - -c
          - "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud/listo', timeout=3)"
        interval: 10s
        timeout: 5s
        retries: 12
        start_period: 20s
  ```

- En `gateway.depends_on`, agregue `administracion: { condition: service_healthy }`, con el mismo formato que `proveedores`.

`services/administracion/Dockerfile`: copia de `services/proveedores/Dockerfile` con estos cambios:
- `uv sync --locked --no-dev --package administracion`;
- `CMD ["sh", "-c", "alembic -c services/administracion/alembic.ini upgrade head && exec uvicorn administracion.main:crear_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]`.

Conserve el comentario `ponytail:` sobre migrar al arrancar.

En `infra/nginx/nginx.conf`, después del bloque `location /api/proveedores/ { … }`, agregue:

```nginx
    location /api/administracion/ {
        limit_req zone=api burst=40 nodelay;
        limit_req_status 429;
        proxy_pass http://administracion:8000/;
        # La bitácora registra la IP de quien hace cada cambio.
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Cache-Control "no-store" always;
    }
```

En `infra/.env.example`, agregue al final:

```
ADMINISTRACION_DB_PASSWORD=cambiar-administracion
ADMINISTRACION_DUENO_DB_PASSWORD=cambiar-administracion-dueno
```

Agregue las dos variables a `infra/.env` (no versionado) con valores aleatorios, sin mostrarlos:

```bash
uv run python -c "import pathlib, secrets; p = pathlib.Path('infra/.env'); t = p.read_text(encoding='utf-8'); faltan = [v for v in ('ADMINISTRACION_DB_PASSWORD', 'ADMINISTRACION_DUENO_DB_PASSWORD') if v + '=' not in t]; p.write_text(t.rstrip('\n') + '\n' + ''.join(f'{v}={secrets.token_hex(16)}\n' for v in faltan), encoding='utf-8'); print('agregadas:', faltan)"
```

- [ ] **Step 7: Levantar y verificar contra el stack**

Ejecute primero el bloque de exports de Docker indicado en "Rama y entorno" (Global Constraints). Después:

```bash
docker compose -f infra/docker-compose.yml up -d postgres
docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/20-administracion.sh
docker compose -f infra/docker-compose.yml up -d --build --wait administracion gateway
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/administracion/salud/listo
```

Expected:
- El script imprime `DO` y `REVOKE`/`GRANT`, sin errores. Corrido por segunda vez, tampoco falla.
- El último comando imprime `200`.

Run: `uv run ruff check services/administracion && uv run ruff format --check services/administracion && uv run mypy && uv run pytest services/administracion -q` → Expected: todo en verde.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock services/administracion infra/postgres/administracion.sh infra/docker-compose.yml infra/.env.example infra/nginx/nginx.conf
git commit -m "feat(administracion): servicio con bitácora de solo inserción, base propia y ruta en el gateway" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 2: Keycloak para administración (cliente, eventos, correo y tema) y Mailpit

**Files:**
- Modify:
  - `infra/keycloak/realm-plataforma.json`
  - `infra/keycloak/themes/plataforma/login/messages/messages_es.properties`
  - `infra/docker-compose.yml`, `infra/.env.example`
- Create:
  - `infra/keycloak/themes/plataforma/email/theme.properties`
  - `infra/keycloak/themes/plataforma/email/messages/messages_es.properties`
  - `infra/keycloak/configurar-administracion.sh`

**Interfaces:**
- Consumes: el servicio `administracion` de la Task 1.
- Produces:
  - Cliente confidencial `administracion` con cuenta de servicio (`view-users`, `manage-users`, `view-events`).
  - Eventos `LOGIN`, `LOGIN_ERROR` y `LOGOUT` guardados 30 días.
  - SMTP hacia `mailpit:1025` y tema de correos `plataforma`.
  - Variables de `administracion`: `KEYCLOAK_URL`, `KEYCLOAK_SECRETO`, `URL_APP` y `BUZON_URL`.

- [ ] **Step 1: Realm para instalaciones nuevas**

En `infra/keycloak/realm-plataforma.json`, después de `"refreshTokenMaxReuse": 0,`, agregue:

```json
  "eventsEnabled": true,
  "eventsExpiration": 2592000,
  "eventsListeners": ["jboss-logging"],
  "enabledEventTypes": ["LOGIN", "LOGIN_ERROR", "LOGOUT"],
  "emailTheme": "plataforma",
  "smtpServer": {
    "host": "mailpit",
    "port": "1025",
    "from": "no-responder@pluri.one.test",
    "fromDisplayName": "PluriOne",
    "auth": "false",
    "ssl": "false",
    "starttls": "false"
  },
```

Al final del arreglo `"clients"`, después del cliente `pruebas-humo`, agregue el cliente. Keycloak reemplaza el marcador `${KEYCLOAK_ADMINISTRACION_SECRET}` con la variable de entorno al importar.

```json
    {
      "clientId": "administracion",
      "name": "Servicio de administración",
      "enabled": true,
      "publicClient": false,
      "clientAuthenticatorType": "client-secret",
      "secret": "${KEYCLOAK_ADMINISTRACION_SECRET}",
      "standardFlowEnabled": false,
      "implicitFlowEnabled": false,
      "directAccessGrantsEnabled": false,
      "serviceAccountsEnabled": true
    }
```

Al final del arreglo `"users"`, agregue la cuenta de servicio con permisos acotados:

```json
    {
      "username": "service-account-administracion",
      "enabled": true,
      "serviceAccountClientId": "administracion",
      "clientRoles": {
        "realm-management": ["view-users", "manage-users", "view-events"]
      }
    }
```

- [ ] **Step 2: Tema de correos y textos de "definir contraseña" de usted**

`infra/keycloak/themes/plataforma/email/theme.properties`:

```properties
# Correos del tema "plataforma": de usted y con la marca. Hereda las plantillas de "base".
parent=base
locales=es
```

`infra/keycloak/themes/plataforma/email/messages/messages_es.properties` (ASCII con escapes `\uXXXX`, como el tema de login). Son las llaves que usa `executeActions.ftl` en Keycloak 26.5.7; `{0}` es el enlace y `{4}` la vigencia en texto:

```properties
# Correo para definir la contrase\u00f1a (invitaci\u00f3n y restablecimiento). ASCII con escapes.
executeActionsSubject=Defina su contrase\u00f1a de PluriOne
executeActionsBody=Hola.\n\nPara entrar a PluriOne, defina su contrase\u00f1a con este enlace:\n\n{0}\n\nEl enlace vence en {4}.\n\nSi no esperaba este correo, ign\u00f3relo; su cuenta no cambiar\u00e1.
executeActionsBodyHtml=<p>Hola.</p><p>Para entrar a PluriOne, defina su contrase\u00f1a con este enlace:</p><p><a href="{0}">Definir mi contrase\u00f1a</a></p><p>El enlace vence en {4}.</p><p>Si no esperaba este correo, ign\u00f3relo; su cuenta no cambiar\u00e1.</p>
```

Al final de `infra/keycloak/themes/plataforma/login/messages/messages_es.properties`, agregue estos textos de usted para las páginas a las que lleva el enlace. Los originales de Keycloak mezclan tú y usted.

```properties
# P\u00e1ginas de definir contrase\u00f1a (enlace del correo y contrase\u00f1a temporal), de usted.
updatePasswordTitle=Defina su contrase\u00f1a
updatePasswordMessage=Defina una contrase\u00f1a para activar su cuenta.
requiredAction.UPDATE_PASSWORD=Definir la contrase\u00f1a
proceedWithAction=\u00bb Haga clic aqu\u00ed para continuar
accountUpdatedMessage=Su cuenta se actualiz\u00f3.
accountPasswordUpdatedMessage=Su contrase\u00f1a se actualiz\u00f3.
emailSentMessage=En breve recibir\u00e1 un correo con las instrucciones.
invalidPasswordMinLengthMessage=La contrase\u00f1a debe tener al menos {0} caracteres.
invalidPasswordNotUsernameMessage=La contrase\u00f1a no puede ser igual a su nombre de usuario.
```

- [ ] **Step 3: Script para el realm ya importado**

`infra/keycloak/configurar-administracion.sh`:

```bash
#!/usr/bin/env bash
# Aplica en un realm ya importado lo que necesita el servicio de administración (Keycloak no
# reimporta): eventos de inicio de sesión, SMTP hacia Mailpit, tema de correos y el cliente
# "administracion" con su cuenta de servicio. Es idempotente.
# Uso (desde la raíz del repositorio):
#   docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/configurar-administracion.sh
# La contraseña del administrador y el secreto del cliente se leen del entorno del contenedor y se
# pasan por la entrada estándar, nunca como argumentos.
set -euo pipefail

kcadm=/opt/keycloak/bin/kcadm.sh
config=/tmp/kcadm.config
realm=plataforma

KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" "$kcadm" config credentials --config "$config" \
  --server http://localhost:8080/auth --realm master --user admin

"$kcadm" update events/config --config "$config" -r "$realm" \
  -s eventsEnabled=true -s eventsExpiration=2592000 \
  -s 'enabledEventTypes=["LOGIN","LOGIN_ERROR","LOGOUT"]'
echo "Eventos de inicio de sesión activados (30 días)."

"$kcadm" update "realms/$realm" --config "$config" -s emailTheme=plataforma \
  -s smtpServer.host=mailpit -s smtpServer.port=1025 \
  -s smtpServer.from=no-responder@pluri.one.test -s smtpServer.fromDisplayName=PluriOne \
  -s smtpServer.auth=false -s smtpServer.ssl=false -s smtpServer.starttls=false
echo "Correo hacia Mailpit y tema de correos configurados."

cliente_json() {
  printf '{"clientId":"administracion","name":"Servicio de administración","enabled":true,"publicClient":false,"clientAuthenticatorType":"client-secret","secret":"%s","standardFlowEnabled":false,"implicitFlowEnabled":false,"directAccessGrantsEnabled":false,"serviceAccountsEnabled":true}' \
    "$KEYCLOAK_ADMINISTRACION_SECRET"
}

id=$("$kcadm" get clients --config "$config" -r "$realm" -q clientId=administracion \
  --fields id --format csv --noquotes)
if [ -z "$id" ]; then
  cliente_json | "$kcadm" create clients --config "$config" -r "$realm" -f -
  echo "Cliente administracion creado."
else
  cliente_json | "$kcadm" update "clients/$id" --config "$config" -r "$realm" -f -
  echo "Cliente administracion ya existía; configuración y secreto actualizados."
fi

"$kcadm" add-roles --config "$config" -r "$realm" --uusername service-account-administracion \
  --cclientid realm-management --rolename view-users --rolename manage-users \
  --rolename view-events
echo "Permisos de la cuenta de servicio: view-users, manage-users, view-events."
```

- [ ] **Step 4: Docker Compose (Mailpit y variables)**

En `infra/docker-compose.yml`:
- En `keycloak.environment`, agregue `KEYCLOAK_ADMINISTRACION_SECRET: ${KEYCLOAK_ADMINISTRACION_SECRET:?Defina KEYCLOAK_ADMINISTRACION_SECRET en infra/.env}`.
- En `administracion.environment`, agregue:

  ```yaml
        KEYCLOAK_URL: http://keycloak:8080/auth
        KEYCLOAK_SECRETO: ${KEYCLOAK_ADMINISTRACION_SECRET:?Defina KEYCLOAK_ADMINISTRACION_SECRET en infra/.env}
        URL_APP: http://localhost:8080/
        BUZON_URL: http://localhost:8025
  ```

  Y en `administracion.depends_on`: `keycloak: { condition: service_healthy }`.
- Agregue el servicio, antes de `gateway`:

  ```yaml
    mailpit:
      image: axllent/mailpit:v1.27
      # Buzón de desarrollo: Keycloak le entrega los correos por SMTP (solo red interna, puerto 1025);
      # la interfaz web queda solo en este equipo.
      ports:
        - "127.0.0.1:8025:8025"
      healthcheck:
        test: ["CMD", "/mailpit", "readyz"]
        interval: 10s
        timeout: 5s
        retries: 12
  ```

  Si `docker compose pull mailpit` no encuentra la etiqueta `v1.27`, use la etiqueta `v1.x` más reciente de <https://hub.docker.com/r/axllent/mailpit/tags> y anótelo en el reporte.

En `infra/.env.example`, agregue `KEYCLOAK_ADMINISTRACION_SECRET=cambiar-secreto-administracion`. En `infra/.env` agréguelo sin mostrarlo:

```bash
uv run python -c "import pathlib, secrets; p = pathlib.Path('infra/.env'); t = p.read_text(encoding='utf-8'); v = 'KEYCLOAK_ADMINISTRACION_SECRET'; p.write_text(t if v + '=' in t else t.rstrip('\n') + f'\n{v}={secrets.token_hex(24)}\n', encoding='utf-8'); print('listo')"
```

- [ ] **Step 5: Aplicar y verificar contra el stack**

```bash
docker compose -f infra/docker-compose.yml up -d --wait mailpit keycloak
docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/configurar-administracion.sh
docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/configurar-administracion.sh
docker compose -f infra/docker-compose.yml up -d --wait administracion
```

Expected:
- Ambas corridas del script terminan sin error. La segunda dice "ya existía".
- Keycloak se recrea con la variable nueva y el realm conserva sus usuarios: no se reimporta un realm existente.

Compruebe que la cuenta de servicio obtiene token y puede listar usuarios y eventos, **sin imprimir el secreto**:

```bash
uv run python -c "
import pathlib, httpx
secreto = next(l.split('=', 1)[1].strip() for l in pathlib.Path('infra/.env').read_text(encoding='utf-8').splitlines() if l.startswith('KEYCLOAK_ADMINISTRACION_SECRET='))
base = 'http://localhost:8080/auth'
t = httpx.post(f'{base}/realms/plataforma/protocol/openid-connect/token', data={'grant_type': 'client_credentials', 'client_id': 'administracion', 'client_secret': secreto})
print('token', t.status_code)
h = {'Authorization': 'Bearer ' + t.json()['access_token']}
print('usuarios', httpx.get(f'{base}/admin/realms/plataforma/users', params={'max': 1}, headers=h).status_code)
print('eventos', httpx.get(f'{base}/admin/realms/plataforma/events', params={'max': 1}, headers=h).status_code)
print('clientes (debe ser 403)', httpx.get(f'{base}/admin/realms/plataforma/clients', headers=h).status_code)
"
```

Expected: `token 200`, `usuarios 200`, `eventos 200`, `clientes (debe ser 403) 403`. El último confirma que no es superadministrador.

Compruebe Mailpit: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8025/api/v1/messages` → `200`.

- [ ] **Step 6: Commit**

```bash
git add infra/keycloak/realm-plataforma.json infra/keycloak/themes/plataforma infra/keycloak/configurar-administracion.sh infra/docker-compose.yml infra/.env.example
git commit -m "feat(infra): cliente de administración en Keycloak, eventos de sesión, correo hacia Mailpit y tema de correos" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 3: Puerto de identidad y adaptador de Keycloak

**Files:**
- Create:
  - `services/administracion/src/administracion/identidad.py`
  - `services/administracion/src/administracion/identidad_falsa.py`
  - `services/administracion/src/administracion/keycloak.py`
  - `services/administracion/tests/test_keycloak.py`, `test_identidad_falsa.py`

**Interfaces:**
- Produces (`administracion.identidad`):
  - `ROLES_ASIGNABLES: tuple[str, ...] = ("admin", "comprador", "aprobador")`.
  - `UsuarioIdentidad(id, usuario, nombre, apellidos, correo, activo: bool, roles: frozenset[str], creado_en: datetime)`.
  - `DatosUsuarioNuevo(usuario, nombre, apellidos, correo)`.
  - `EventoSesion(id, tipo, fecha, usuario_id: str | None, usuario: str | None, ip: str | None, error: str | None)`.
  - Excepciones: `IdentidadNoDisponible`, `UsuarioNoEncontrado`, `DatoDuplicado(campo: Literal["usuario", "correo"])` y `CorreoNoEnviado`.
  - `ProveedorIdentidad` (Protocol), con las operaciones `listar_usuarios`, `obtener_usuario`, `crear_usuario -> str` (id), `actualizar_datos`, `fijar_roles`, `fijar_activo`, `enviar_correo_contrasena(usuario_id, vigencia_s)`, `fijar_contrasena_temporal`, `cerrar_sesiones` y `eventos_de_sesion(desde) -> list[EventoSesion]` (orden ascendente por fecha).
- Produces:
  - `administracion.identidad_falsa.IdentidadFalsa`: en memoria. Atributos `usuarios`, `temporales`, `correos: list[tuple[str, int]]`, `sesiones_cerradas`, `eventos`, `caida`, `falla_correo`; método `agregar(usuario, roles, *, activo, nombre, apellidos, correo) -> UsuarioIdentidad`, que usa `id == usuario`.
  - `administracion.keycloak.IdentidadKeycloak(url, realm, cliente, secreto, url_app, transporte=None)` y `cerrar()`.

- [ ] **Step 1: Puerto e implementación falsa**

`services/administracion/src/administracion/identidad.py`:

```python
"""Puerto de identidad: lo que el servicio necesita del proveedor de identidad (hoy Keycloak).

Migrar a Entra ID = escribir otra implementación de ProveedorIdentidad.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from comun.auth import ROLES_INTERNOS

ROLES_ASIGNABLES: tuple[str, ...] = ROLES_INTERNOS


@dataclass(frozen=True)
class UsuarioIdentidad:
    id: str
    usuario: str
    nombre: str
    apellidos: str
    correo: str
    activo: bool
    roles: frozenset[str]
    creado_en: datetime


@dataclass(frozen=True)
class DatosUsuarioNuevo:
    usuario: str
    nombre: str
    apellidos: str
    correo: str


@dataclass(frozen=True)
class EventoSesion:
    id: str
    tipo: str  # LOGIN, LOGIN_ERROR o LOGOUT
    fecha: datetime
    usuario_id: str | None
    usuario: str | None  # nombre de usuario (el intentado, en LOGIN_ERROR)
    ip: str | None
    error: str | None


class IdentidadNoDisponible(Exception):
    """El proveedor de identidad no respondió o respondió con un error inesperado."""


class UsuarioNoEncontrado(Exception):
    """No existe un usuario con ese id."""


class DatoDuplicado(Exception):
    """Ya existe otro usuario con el mismo nombre de usuario o correo."""

    def __init__(self, campo: Literal["usuario", "correo"]) -> None:
        super().__init__(campo)
        self.campo: Literal["usuario", "correo"] = campo


class CorreoNoEnviado(Exception):
    """El proveedor de identidad no pudo entregar el correo al servidor de correo."""


class ProveedorIdentidad(Protocol):
    async def listar_usuarios(self) -> list[UsuarioIdentidad]: ...

    async def obtener_usuario(self, usuario_id: str) -> UsuarioIdentidad: ...

    async def crear_usuario(self, datos: DatosUsuarioNuevo) -> str: ...

    async def actualizar_datos(
        self, usuario_id: str, nombre: str, apellidos: str, correo: str
    ) -> None: ...

    async def fijar_roles(self, usuario_id: str, roles: frozenset[str]) -> None: ...

    async def fijar_activo(self, usuario_id: str, activo: bool) -> None: ...

    async def enviar_correo_contrasena(self, usuario_id: str, vigencia_s: int) -> None: ...

    async def fijar_contrasena_temporal(self, usuario_id: str, contrasena: str) -> None: ...

    async def cerrar_sesiones(self, usuario_id: str) -> None: ...

    async def eventos_de_sesion(self, desde: datetime) -> list[EventoSesion]: ...
```

`services/administracion/src/administracion/identidad_falsa.py`:

```python
"""Proveedor de identidad en memoria para pruebas; permite simular caídas y fallas de correo."""

from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime

from administracion.identidad import (
    CorreoNoEnviado,
    DatoDuplicado,
    DatosUsuarioNuevo,
    EventoSesion,
    IdentidadNoDisponible,
    UsuarioIdentidad,
    UsuarioNoEncontrado,
)


class IdentidadFalsa:
    def __init__(self) -> None:
        self.usuarios: dict[str, UsuarioIdentidad] = {}
        self.temporales: dict[str, str] = {}
        self.correos: list[tuple[str, int]] = []
        self.sesiones_cerradas: list[str] = []
        self.eventos: list[EventoSesion] = []
        self.caida = False
        self.falla_correo = False

    def agregar(
        self,
        usuario: str,
        roles: Iterable[str] = (),
        *,
        activo: bool = True,
        nombre: str = "Nombre",
        apellidos: str = "Apellido",
        correo: str | None = None,
    ) -> UsuarioIdentidad:
        nuevo = UsuarioIdentidad(
            id=usuario,
            usuario=usuario,
            nombre=nombre,
            apellidos=apellidos,
            correo=correo or f"{usuario}@plataforma.example",
            activo=activo,
            roles=frozenset(roles),
            creado_en=datetime(2026, 10, 1, tzinfo=UTC),
        )
        self.usuarios[nuevo.id] = nuevo
        return nuevo

    def _disponible(self) -> None:
        if self.caida:
            raise IdentidadNoDisponible("Proveedor de identidad simulado caído")

    def _buscar(self, usuario_id: str) -> UsuarioIdentidad:
        self._disponible()
        try:
            return self.usuarios[usuario_id]
        except KeyError as exc:
            raise UsuarioNoEncontrado(usuario_id) from exc

    async def listar_usuarios(self) -> list[UsuarioIdentidad]:
        self._disponible()
        return list(self.usuarios.values())

    async def obtener_usuario(self, usuario_id: str) -> UsuarioIdentidad:
        return self._buscar(usuario_id)

    async def crear_usuario(self, datos: DatosUsuarioNuevo) -> str:
        self._disponible()
        if any(u.usuario == datos.usuario for u in self.usuarios.values()):
            raise DatoDuplicado("usuario")
        if any(u.correo == datos.correo for u in self.usuarios.values()):
            raise DatoDuplicado("correo")
        nuevo = UsuarioIdentidad(
            id=f"id-{datos.usuario}",
            usuario=datos.usuario,
            nombre=datos.nombre,
            apellidos=datos.apellidos,
            correo=datos.correo,
            activo=True,
            roles=frozenset(),
            creado_en=datetime.now(UTC),
        )
        self.usuarios[nuevo.id] = nuevo
        return nuevo.id

    async def actualizar_datos(
        self, usuario_id: str, nombre: str, apellidos: str, correo: str
    ) -> None:
        actual = self._buscar(usuario_id)
        if any(u.correo == correo and u.id != usuario_id for u in self.usuarios.values()):
            raise DatoDuplicado("correo")
        self.usuarios[usuario_id] = replace(
            actual, nombre=nombre, apellidos=apellidos, correo=correo
        )

    async def fijar_roles(self, usuario_id: str, roles: frozenset[str]) -> None:
        self.usuarios[usuario_id] = replace(self._buscar(usuario_id), roles=roles)

    async def fijar_activo(self, usuario_id: str, activo: bool) -> None:
        self.usuarios[usuario_id] = replace(self._buscar(usuario_id), activo=activo)

    async def enviar_correo_contrasena(self, usuario_id: str, vigencia_s: int) -> None:
        self._buscar(usuario_id)
        if self.falla_correo:
            raise CorreoNoEnviado("Servidor de correo simulado caído")
        self.correos.append((usuario_id, vigencia_s))

    async def fijar_contrasena_temporal(self, usuario_id: str, contrasena: str) -> None:
        self._buscar(usuario_id)
        self.temporales[usuario_id] = contrasena

    async def cerrar_sesiones(self, usuario_id: str) -> None:
        self._buscar(usuario_id)
        self.sesiones_cerradas.append(usuario_id)

    async def eventos_de_sesion(self, desde: datetime) -> list[EventoSesion]:
        self._disponible()
        return sorted((e for e in self.eventos if e.fecha >= desde), key=lambda e: e.fecha)
```

`services/administracion/tests/test_identidad_falsa.py`:

```python
import pytest
from administracion.identidad import DatoDuplicado, DatosUsuarioNuevo, IdentidadNoDisponible
from administracion.identidad_falsa import IdentidadFalsa


async def test_crear_y_duplicados() -> None:
    falsa = IdentidadFalsa()
    falsa.agregar("ana", ["comprador"], correo="ana@x.mx")
    nuevo = await falsa.crear_usuario(DatosUsuarioNuevo("beto", "Beto", "Ruiz", "beto@x.mx"))
    assert (await falsa.obtener_usuario(nuevo)).usuario == "beto"
    with pytest.raises(DatoDuplicado) as usuario:
        await falsa.crear_usuario(DatosUsuarioNuevo("ana", "A", "B", "otro@x.mx"))
    assert usuario.value.campo == "usuario"
    with pytest.raises(DatoDuplicado) as correo:
        await falsa.crear_usuario(DatosUsuarioNuevo("carla", "C", "D", "ana@x.mx"))
    assert correo.value.campo == "correo"


async def test_caida() -> None:
    falsa = IdentidadFalsa()
    falsa.caida = True
    with pytest.raises(IdentidadNoDisponible):
        await falsa.listar_usuarios()
```

- [ ] **Step 2: Pruebas del adaptador de Keycloak (fallan)**

`services/administracion/tests/test_keycloak.py`:

```python
import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest
from administracion.identidad import (
    CorreoNoEnviado,
    DatoDuplicado,
    DatosUsuarioNuevo,
    IdentidadNoDisponible,
    UsuarioNoEncontrado,
)
from administracion.keycloak import IdentidadKeycloak

BASE = "http://kc/auth"
ADMIN = "/auth/admin/realms/plataforma"
TOKEN = "/auth/realms/plataforma/protocol/openid-connect/token"

Manejador = Callable[[httpx.Request], httpx.Response]


def _keycloak(rutas: dict[tuple[str, str], Manejador]) -> tuple[IdentidadKeycloak, list[httpx.Request]]:
    """Keycloak simulado: responde por (método, ruta) y registra cada petición."""
    peticiones: list[httpx.Request] = []

    def manejar(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        if peticion.url.path == TOKEN:
            return httpx.Response(200, json={"access_token": "t", "expires_in": 300})
        manejador = rutas.get((peticion.method, peticion.url.path))
        return manejador(peticion) if manejador else httpx.Response(404)

    identidad = IdentidadKeycloak(
        BASE, "plataforma", "administracion", "secreto", "http://app/",
        transporte=httpx.MockTransport(manejar),
    )
    return identidad, peticiones


def _usuario(id_: str, usuario: str, *, activo: bool = True) -> dict[str, object]:
    return {
        "id": id_, "username": usuario, "firstName": "Ana", "lastName": "López",
        "email": f"{usuario}@x.mx", "enabled": activo, "createdTimestamp": 1_790_000_000_000,
    }


async def test_el_token_se_reutiliza() -> None:
    identidad, peticiones = _keycloak(
        {("GET", f"{ADMIN}/users/u1"): lambda _: httpx.Response(200, json=_usuario("u1", "ana")),
         ("GET", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(200, json=[])}
    )
    await identidad.obtener_usuario("u1")
    await identidad.obtener_usuario("u1")
    assert sum(p.url.path == TOKEN for p in peticiones) == 1
    assert peticiones[1].headers["Authorization"] == "Bearer t"


async def test_listar_combina_roles_por_rol_y_omite_cuentas_de_servicio() -> None:
    usuarios = [
        _usuario("u1", "ana"),
        _usuario("u2", "beto", activo=False),
        _usuario("s1", "service-account-administracion"),
    ]
    identidad, _ = _keycloak({
        ("GET", f"{ADMIN}/users"): lambda _: httpx.Response(200, json=usuarios),
        ("GET", f"{ADMIN}/roles/admin/users"): lambda _: httpx.Response(200, json=[{"id": "u1"}]),
        ("GET", f"{ADMIN}/roles/comprador/users"): lambda _: httpx.Response(
            200, json=[{"id": "u1"}, {"id": "u2"}]
        ),
        ("GET", f"{ADMIN}/roles/aprobador/users"): lambda _: httpx.Response(200, json=[]),
    })
    lista = {u.usuario: u for u in await identidad.listar_usuarios()}
    assert set(lista) == {"ana", "beto"}
    assert lista["ana"].roles == {"admin", "comprador"}
    assert lista["beto"].roles == {"comprador"}
    assert lista["beto"].activo is False
    assert lista["ana"].creado_en == datetime.fromtimestamp(1_790_000_000, UTC)


async def test_obtener_inexistente() -> None:
    identidad, _ = _keycloak({})
    with pytest.raises(UsuarioNoEncontrado):
        await identidad.obtener_usuario("nadie")


async def test_crear_usuario_devuelve_el_id_de_location() -> None:
    def crear(peticion: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(peticion.content)
        assert cuerpo == {
            "username": "ana", "email": "ana@x.mx", "firstName": "Ana", "lastName": "López",
            "enabled": True, "emailVerified": True,
        }
        return httpx.Response(201, headers={"Location": f"{BASE}/admin/realms/plataforma/users/nuevo-id"})

    identidad, _ = _keycloak({("POST", f"{ADMIN}/users"): crear})
    assert await identidad.crear_usuario(DatosUsuarioNuevo("ana", "Ana", "López", "ana@x.mx")) == "nuevo-id"


@pytest.mark.parametrize(
    ("mensaje", "campo"),
    [("User exists with same username", "usuario"), ("User exists with same email", "correo")],
)
async def test_crear_usuario_duplicado_distingue_usuario_y_correo(mensaje: str, campo: str) -> None:
    identidad, _ = _keycloak(
        {("POST", f"{ADMIN}/users"): lambda _: httpx.Response(409, json={"errorMessage": mensaje})}
    )
    with pytest.raises(DatoDuplicado) as error:
        await identidad.crear_usuario(DatosUsuarioNuevo("ana", "Ana", "López", "ana@x.mx"))
    assert error.value.campo == campo


async def test_fijar_roles_solo_agrega_y_quita_lo_necesario() -> None:
    actuales = [
        {"id": "r-comprador", "name": "comprador"},
        {"id": "r-def", "name": "default-roles-plataforma"},
    ]
    identidad, peticiones = _keycloak({
        ("GET", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(200, json=actuales),
        ("GET", f"{ADMIN}/roles/admin"): lambda _: httpx.Response(200, json={"id": "r-admin", "name": "admin"}),
        ("POST", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(204),
        ("DELETE", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(204),
    })
    await identidad.fijar_roles("u1", frozenset({"admin"}))
    agregados = next(p for p in peticiones if p.method == "POST" and "role-mappings" in p.url.path)
    quitados = next(p for p in peticiones if p.method == "DELETE")
    assert [r["name"] for r in json.loads(agregados.content)] == ["admin"]
    assert [r["name"] for r in json.loads(quitados.content)] == ["comprador"]


async def test_enviar_correo_pide_definir_la_contrasena_con_vigencia_y_regreso() -> None:
    identidad, peticiones = _keycloak(
        {("PUT", f"{ADMIN}/users/u1/execute-actions-email"): lambda _: httpx.Response(204)}
    )
    await identidad.enviar_correo_contrasena("u1", 259200)
    peticion = peticiones[-1]
    assert json.loads(peticion.content) == ["UPDATE_PASSWORD"]
    assert peticion.url.params["lifespan"] == "259200"
    assert peticion.url.params["client_id"] == "web"
    assert peticion.url.params["redirect_uri"] == "http://app/"


async def test_correo_que_no_sale() -> None:
    identidad, _ = _keycloak({
        ("PUT", f"{ADMIN}/users/u1/execute-actions-email"): lambda _: httpx.Response(
            500, json={"errorMessage": "Failed to send execute actions email"}
        )
    })
    with pytest.raises(CorreoNoEnviado):
        await identidad.enviar_correo_contrasena("u1", 86400)


async def test_contrasena_temporal() -> None:
    identidad, peticiones = _keycloak(
        {("PUT", f"{ADMIN}/users/u1/reset-password"): lambda _: httpx.Response(204)}
    )
    await identidad.fijar_contrasena_temporal("u1", "Xy7#abcdefghijkl")
    assert json.loads(peticiones[-1].content) == {
        "type": "password", "value": "Xy7#abcdefghijkl", "temporary": True
    }


async def test_red_caida() -> None:
    def falla(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    identidad = IdentidadKeycloak(
        BASE, "plataforma", "administracion", "s", "http://app/", transporte=httpx.MockTransport(falla)
    )
    with pytest.raises(IdentidadNoDisponible):
        await identidad.listar_usuarios()


async def test_eventos_pagina_traduce_y_filtra_por_fecha() -> None:
    desde = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    ms = int(desde.timestamp() * 1000)
    pagina1 = [
        {"id": f"e{i}", "time": ms + i * 1000, "type": "LOGIN", "userId": "u1",
         "ipAddress": "10.0.0.1", "details": {"username": "ana"}}
        for i in range(200)
    ]
    pagina2 = [
        {"time": ms + 500_000, "type": "LOGIN_ERROR", "userId": None, "sessionId": None,
         "error": "user_not_found", "details": {"username": "fantasma"}},
        {"id": "viejo", "time": ms - 60_000, "type": "LOGOUT", "userId": "u1", "details": {}},
    ]

    def eventos(peticion: httpx.Request) -> httpx.Response:
        assert peticion.url.params.get_list("type") == ["LOGIN", "LOGIN_ERROR", "LOGOUT"]
        assert peticion.url.params["dateFrom"] == "2026-10-08"
        return httpx.Response(200, json=pagina1 if peticion.url.params["first"] == "0" else pagina2)

    identidad, _ = _keycloak({("GET", f"{ADMIN}/events"): eventos})
    lista = await identidad.eventos_de_sesion(desde)
    assert len(lista) == 201  # el evento anterior a "desde" se descarta
    assert lista == sorted(lista, key=lambda e: e.fecha)
    fallido = lista[-1]
    assert fallido.tipo == "LOGIN_ERROR"
    assert fallido.usuario_id is None
    assert fallido.usuario == "fantasma"
    assert fallido.error == "user_not_found"
    assert fallido.id.startswith(str(ms + 500_000))
```

Run: `uv run pytest services/administracion/tests/test_keycloak.py -q` → Expected: FAIL (`ModuleNotFoundError: administracion.keycloak`).

- [ ] **Step 3: Implementar `IdentidadKeycloak`**

`services/administracion/src/administracion/keycloak.py`:

```python
"""Adaptador de identidad para la API de administración de Keycloak.

Usa la cuenta de servicio del cliente "administracion" (client credentials), con permisos de
realm-management limitados a view-users, manage-users y view-events.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from administracion.identidad import (
    ROLES_ASIGNABLES,
    CorreoNoEnviado,
    DatoDuplicado,
    DatosUsuarioNuevo,
    EventoSesion,
    IdentidadNoDisponible,
    UsuarioIdentidad,
    UsuarioNoEncontrado,
)

log = logging.getLogger(__name__)

TIEMPO_LIMITE_S = 5
# ponytail: la lista completa cabe en memoria (hasta 1,000 usuarios); paginar en Keycloak si crece.
MAX_USUARIOS = 1000
TAMANO_PAGINA_EVENTOS = 200
MAX_PAGINAS_EVENTOS = 50
TIPOS_EVENTO = ("LOGIN", "LOGIN_ERROR", "LOGOUT")
PREFIJO_CUENTA_SERVICIO = "service-account-"
MARGEN_TOKEN_S = 30


class IdentidadKeycloak:
    def __init__(
        self,
        url: str,
        realm: str,
        cliente: str,
        secreto: str,
        url_app: str,
        transporte: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url_token = f"{url}/realms/{realm}/protocol/openid-connect/token"
        self._cliente = cliente
        self._secreto = secreto
        self._url_app = url_app
        self._http = httpx.AsyncClient(
            base_url=f"{url}/admin/realms/{realm}", timeout=TIEMPO_LIMITE_S, transport=transporte
        )
        self._token: str | None = None
        self._vence = 0.0

    async def cerrar(self) -> None:
        await self._http.aclose()

    async def _cabeceras(self) -> dict[str, str]:
        if self._token is None or time.monotonic() >= self._vence:
            try:
                respuesta = await self._http.post(
                    self._url_token,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._cliente,
                        "client_secret": self._secreto,
                    },
                )
            except httpx.HTTPError as exc:
                raise IdentidadNoDisponible("Sin conexión con Keycloak") from exc
            if respuesta.status_code != 200:
                raise IdentidadNoDisponible(f"Keycloak rechazó la cuenta de servicio ({respuesta.status_code})")
            datos = respuesta.json()
            self._token = str(datos["access_token"])
            self._vence = time.monotonic() + float(datos.get("expires_in", 60)) - MARGEN_TOKEN_S
        return {"Authorization": f"Bearer {self._token}"}

    async def _pedir(self, metodo: str, ruta: str, **opciones: Any) -> httpx.Response:
        """404 → UsuarioNoEncontrado; red caída o 5xx → IdentidadNoDisponible (salvo 500 tolerado)."""
        tolerar_500 = bool(opciones.pop("tolerar_500", False))
        for intento in range(2):
            try:
                respuesta = await self._http.request(
                    metodo, ruta, headers=await self._cabeceras(), **opciones
                )
            except httpx.HTTPError as exc:
                raise IdentidadNoDisponible("Sin conexión con Keycloak") from exc
            if respuesta.status_code == 401 and intento == 0:
                self._token = None  # token revocado o vencido antes de tiempo: se pide otro
                continue
            break
        if respuesta.status_code == 404:
            raise UsuarioNoEncontrado(ruta)
        if respuesta.status_code >= 500 and not (tolerar_500 and respuesta.status_code == 500):
            raise IdentidadNoDisponible(f"Keycloak respondió {respuesta.status_code}")
        return respuesta

    @staticmethod
    def _exigir_exito(respuesta: httpx.Response) -> None:
        if not respuesta.is_success:
            log.warning("Respuesta inesperada de Keycloak: %s %s", respuesta.status_code, respuesta.url)
            raise IdentidadNoDisponible(f"Keycloak respondió {respuesta.status_code}")

    @staticmethod
    def _a_usuario(datos: dict[str, Any], roles: set[str]) -> UsuarioIdentidad:
        return UsuarioIdentidad(
            id=str(datos["id"]),
            usuario=str(datos["username"]),
            nombre=str(datos.get("firstName") or ""),
            apellidos=str(datos.get("lastName") or ""),
            correo=str(datos.get("email") or ""),
            activo=bool(datos.get("enabled", False)),
            roles=frozenset(roles),
            creado_en=datetime.fromtimestamp(int(datos.get("createdTimestamp", 0)) / 1000, UTC),
        )

    async def listar_usuarios(self) -> list[UsuarioIdentidad]:
        respuesta = await self._pedir(
            "GET", "/users", params={"first": 0, "max": MAX_USUARIOS, "briefRepresentation": "false"}
        )
        self._exigir_exito(respuesta)
        roles: dict[str, set[str]] = {}
        for rol in ROLES_ASIGNABLES:  # tres consultas por rol, no una por usuario
            miembros = await self._pedir(
                "GET", f"/roles/{rol}/users", params={"first": 0, "max": MAX_USUARIOS}
            )
            self._exigir_exito(miembros)
            for miembro in miembros.json():
                roles.setdefault(str(miembro["id"]), set()).add(rol)
        return [
            self._a_usuario(u, roles.get(str(u["id"]), set()))
            for u in respuesta.json()
            if not str(u["username"]).startswith(PREFIJO_CUENTA_SERVICIO)
        ]

    async def _roles_de(self, usuario_id: str) -> list[dict[str, Any]]:
        respuesta = await self._pedir("GET", f"/users/{usuario_id}/role-mappings/realm")
        self._exigir_exito(respuesta)
        return [r for r in respuesta.json() if r.get("name") in ROLES_ASIGNABLES]

    async def obtener_usuario(self, usuario_id: str) -> UsuarioIdentidad:
        respuesta = await self._pedir("GET", f"/users/{usuario_id}")
        self._exigir_exito(respuesta)
        roles = {str(r["name"]) for r in await self._roles_de(usuario_id)}
        return self._a_usuario(respuesta.json(), roles)

    @staticmethod
    def _duplicado(respuesta: httpx.Response) -> DatoDuplicado:
        mensaje = str((respuesta.json() or {}).get("errorMessage", "")).lower()
        return DatoDuplicado("correo" if "email" in mensaje else "usuario")

    async def crear_usuario(self, datos: DatosUsuarioNuevo) -> str:
        respuesta = await self._pedir(
            "POST",
            "/users",
            json={
                "username": datos.usuario,
                "email": datos.correo,
                "firstName": datos.nombre,
                "lastName": datos.apellidos,
                "enabled": True,
                "emailVerified": True,
            },
        )
        if respuesta.status_code == 409:
            raise self._duplicado(respuesta)
        self._exigir_exito(respuesta)
        return respuesta.headers["Location"].rstrip("/").rsplit("/", 1)[-1]

    async def actualizar_datos(
        self, usuario_id: str, nombre: str, apellidos: str, correo: str
    ) -> None:
        respuesta = await self._pedir(
            "PUT",
            f"/users/{usuario_id}",
            json={"firstName": nombre, "lastName": apellidos, "email": correo},
        )
        if respuesta.status_code == 409:
            raise self._duplicado(respuesta)
        self._exigir_exito(respuesta)

    async def fijar_roles(self, usuario_id: str, roles: frozenset[str]) -> None:
        actuales = await self._roles_de(usuario_id)
        nombres_actuales = {str(r["name"]) for r in actuales}
        quitar = [r for r in actuales if r["name"] not in roles]
        agregar: list[dict[str, Any]] = []
        for nombre in sorted(roles - nombres_actuales):
            rol = await self._pedir("GET", f"/roles/{nombre}")
            self._exigir_exito(rol)
            agregar.append(rol.json())
        if agregar:
            self._exigir_exito(
                await self._pedir("POST", f"/users/{usuario_id}/role-mappings/realm", json=agregar)
            )
        if quitar:
            self._exigir_exito(
                await self._pedir("DELETE", f"/users/{usuario_id}/role-mappings/realm", json=quitar)
            )

    async def fijar_activo(self, usuario_id: str, activo: bool) -> None:
        self._exigir_exito(
            await self._pedir("PUT", f"/users/{usuario_id}", json={"enabled": activo})
        )

    async def enviar_correo_contrasena(self, usuario_id: str, vigencia_s: int) -> None:
        respuesta = await self._pedir(
            "PUT",
            f"/users/{usuario_id}/execute-actions-email",
            params={"lifespan": vigencia_s, "client_id": "web", "redirect_uri": self._url_app},
            json=["UPDATE_PASSWORD"],
            tolerar_500=True,
        )
        if respuesta.status_code in (400, 500):  # sin correo o el SMTP no aceptó el mensaje
            log.warning("Keycloak no pudo enviar el correo: %s", respuesta.text[:200])
            raise CorreoNoEnviado(respuesta.text[:200])
        self._exigir_exito(respuesta)

    async def fijar_contrasena_temporal(self, usuario_id: str, contrasena: str) -> None:
        self._exigir_exito(
            await self._pedir(
                "PUT",
                f"/users/{usuario_id}/reset-password",
                json={"type": "password", "value": contrasena, "temporary": True},
            )
        )

    async def cerrar_sesiones(self, usuario_id: str) -> None:
        self._exigir_exito(await self._pedir("POST", f"/users/{usuario_id}/logout"))

    @staticmethod
    def _a_evento(datos: dict[str, Any]) -> EventoSesion:
        detalles = datos.get("details") or {}
        tiempo = int(datos["time"])
        # Keycloak 26 trae "id"; si faltara, la combinación tiempo-tipo-usuario-sesión lo sustituye.
        clave = datos.get("id") or (
            f"{tiempo}-{datos.get('type')}-{datos.get('userId')}-{datos.get('sessionId')}"
        )
        return EventoSesion(
            id=str(clave),
            tipo=str(datos["type"]),
            fecha=datetime.fromtimestamp(tiempo / 1000, UTC),
            usuario_id=datos.get("userId"),
            usuario=detalles.get("username"),
            ip=datos.get("ipAddress"),
            error=datos.get("error"),
        )

    async def eventos_de_sesion(self, desde: datetime) -> list[EventoSesion]:
        eventos: list[EventoSesion] = []
        for pagina in range(MAX_PAGINAS_EVENTOS):
            parametros = [
                *(("type", tipo) for tipo in TIPOS_EVENTO),
                ("dateFrom", desde.astimezone(UTC).date().isoformat()),
                ("first", str(pagina * TAMANO_PAGINA_EVENTOS)),
                ("max", str(TAMANO_PAGINA_EVENTOS)),
            ]
            respuesta = await self._pedir("GET", "/events", params=parametros)
            self._exigir_exito(respuesta)
            lote = respuesta.json()
            eventos += [self._a_evento(e) for e in lote]
            if len(lote) < TAMANO_PAGINA_EVENTOS:
                break
        return sorted((e for e in eventos if e.fecha >= desde), key=lambda e: e.fecha)
```

Run: `uv run pytest services/administracion/tests/test_keycloak.py services/administracion/tests/test_identidad_falsa.py -q` → Expected: PASS.

Run: `uv run ruff check services/administracion && uv run ruff format services/administracion && uv run mypy` → Expected: sin errores. Si ruff pide partir líneas largas de las pruebas, use `ruff format`; no cambie su contenido.

- [ ] **Step 4: Commit**

```bash
git add services/administracion
git commit -m "feat(administracion): puerto de identidad con adaptador de Keycloak y versión en memoria" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 4: Reglas de protección, contraseña temporal y bitácora

**Files:**
- Create:
  - `services/administracion/src/administracion/reglas.py`
  - `services/administracion/src/administracion/bitacora.py`
  - `services/administracion/tests/test_reglas.py`, `test_bitacora.py`

**Interfaces:**
- Consumes: `UsuarioIdentidad` (Task 3), `Actividad` (Task 1).
- Produces:
  - `reglas.ReglaProteccion(Exception)`, con el mensaje para la persona en `str(exc)`.
  - `reglas.generar_contrasena_temporal() -> str`.
  - `reglas.verificar_desactivacion(actor_id, objetivo, usuarios)` y `reglas.verificar_cambio_de_roles(actor_id, objetivo, roles_nuevos, usuarios)`.
  - `bitacora.Actor(id: str | None, nombre: str, ip: str | None = None)` y `bitacora.Objeto(tipo, id, nombre)`.
  - `bitacora.registrar(sesion, tipo, actor, *, objeto=None, detalle=None, resultado="exito", origen="administracion", clave_origen=None, fecha=None) -> None`: idempotente por `clave_origen`; no confirma la transacción.
  - `bitacora.FiltroActividad(persona=None, tipo=None, desde=None, hasta=None)`, con `tipo` ∈ `"sesiones" | "usuarios" | "importaciones" | "catalogo"`.
  - `bitacora.consultar(sesion, filtro, desplazamiento, limite) -> tuple[int, list[Actividad]]` y `bitacora.ultimos_accesos(sesion, ids) -> dict[str, datetime]`.

- [ ] **Step 1: Pruebas de las reglas (fallan)**

`services/administracion/tests/test_reglas.py`:

```python
import string
from datetime import UTC, datetime

import pytest
from administracion.identidad import UsuarioIdentidad
from administracion.reglas import (
    SIMBOLOS,
    ReglaProteccion,
    generar_contrasena_temporal,
    verificar_cambio_de_roles,
    verificar_desactivacion,
)


def _u(id_: str, *roles: str, activo: bool = True) -> UsuarioIdentidad:
    return UsuarioIdentidad(
        id_, id_, "N", "A", f"{id_}@x.mx", activo, frozenset(roles), datetime(2026, 1, 1, tzinfo=UTC)
    )


def test_contrasena_temporal_cumple_la_politica() -> None:
    contrasenas = {generar_contrasena_temporal() for _ in range(50)}
    assert len(contrasenas) == 50
    for c in contrasenas:
        assert len(c) == 16
        assert any(x in string.ascii_uppercase for x in c)
        assert any(x in string.ascii_lowercase for x in c)
        assert any(x in string.digits for x in c)
        assert any(x in SIMBOLOS for x in c)


def test_nadie_se_desactiva_a_si_mismo() -> None:
    yo = _u("yo", "admin")
    with pytest.raises(ReglaProteccion, match="No puede desactivar su propia cuenta."):
        verificar_desactivacion("yo", yo, [yo, _u("otro", "admin")])


def test_se_puede_desactivar_a_otro_admin_si_quedan_mas() -> None:
    otro = _u("otro", "admin")
    verificar_desactivacion("yo", otro, [_u("yo", "admin"), otro])


def test_un_admin_inactivo_no_cuenta_como_respaldo() -> None:
    # Token aún vigente de un admin que ya no lo es: el único admin activo es "ultimo".
    ultimo = _u("ultimo", "admin")
    usuarios = [ultimo, _u("dormido", "admin", activo=False), _u("yo", "comprador")]
    with pytest.raises(ReglaProteccion, match="Debe quedar al menos un administrador activo."):
        verificar_desactivacion("yo", ultimo, usuarios)
    with pytest.raises(ReglaProteccion, match="Debe quedar al menos un administrador activo."):
        verificar_cambio_de_roles("yo", ultimo, frozenset({"comprador"}), usuarios)


def test_nadie_se_quita_el_rol_de_admin() -> None:
    yo = _u("yo", "admin", "comprador")
    with pytest.raises(ReglaProteccion, match="No puede quitarse el rol de administrador."):
        verificar_cambio_de_roles("yo", yo, frozenset({"comprador"}), [yo, _u("otro", "admin")])


def test_cambios_de_roles_permitidos() -> None:
    yo = _u("yo", "admin")
    otro = _u("otro", "admin")
    verificar_cambio_de_roles("yo", yo, frozenset({"admin", "aprobador"}), [yo, otro])
    verificar_cambio_de_roles("yo", otro, frozenset({"comprador"}), [yo, otro])
    verificar_cambio_de_roles("yo", _u("c", "comprador"), frozenset({"aprobador"}), [yo])
```

Run: `uv run pytest services/administracion/tests/test_reglas.py -q` → Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Implementar las reglas**

`services/administracion/src/administracion/reglas.py`:

```python
"""Reglas de la gestión de usuarios, independientes de Keycloak y de la base de datos."""

import secrets
import string

from administracion.identidad import UsuarioIdentidad

LONGITUD_TEMPORAL = 16
SIMBOLOS = "!#$%&*+-=?@_"


class ReglaProteccion(Exception):
    """Cambio prohibido para no dejar la plataforma sin administración; el mensaje es para la persona."""


def generar_contrasena_temporal() -> str:
    """16 caracteres con al menos una mayúscula, una minúscula, un dígito y un símbolo."""
    clases = [string.ascii_uppercase, string.ascii_lowercase, string.digits, SIMBOLOS]
    caracteres = [secrets.choice(clase) for clase in clases]
    todos = "".join(clases)
    caracteres += [secrets.choice(todos) for _ in range(LONGITUD_TEMPORAL - len(clases))]
    secrets.SystemRandom().shuffle(caracteres)
    return "".join(caracteres)


def _admins_activos(usuarios: list[UsuarioIdentidad]) -> set[str]:
    return {u.id for u in usuarios if u.activo and "admin" in u.roles}


def verificar_desactivacion(
    actor_id: str, objetivo: UsuarioIdentidad, usuarios: list[UsuarioIdentidad]
) -> None:
    if objetivo.id == actor_id:
        raise ReglaProteccion("No puede desactivar su propia cuenta.")
    if _admins_activos(usuarios) == {objetivo.id}:
        raise ReglaProteccion("Debe quedar al menos un administrador activo.")


def verificar_cambio_de_roles(
    actor_id: str,
    objetivo: UsuarioIdentidad,
    roles_nuevos: frozenset[str],
    usuarios: list[UsuarioIdentidad],
) -> None:
    if "admin" in roles_nuevos or "admin" not in objetivo.roles:
        return
    if objetivo.id == actor_id:
        raise ReglaProteccion("No puede quitarse el rol de administrador.")
    if _admins_activos(usuarios) == {objetivo.id}:
        raise ReglaProteccion("Debe quedar al menos un administrador activo.")
```

Run: `uv run pytest services/administracion/tests/test_reglas.py -q` → Expected: PASS.

- [ ] **Step 3: Pruebas de la bitácora (fallan)**

`services/administracion/tests/test_bitacora.py`:

```python
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
    await registrar(sesion, "sesion.iniciada", ANA, origen="keycloak", clave_origen="k:1", fecha=_f(1))
    await registrar(sesion, "sesion.iniciada", ANA, origen="keycloak", clave_origen="k:2", fecha=_f(5))
    await registrar(
        sesion, "usuario.desactivado", ADMIN, objeto=Objeto("usuario", "ana", "Ana López"),
        fecha=_f(3),
    )
    await registrar(sesion, "sesion.fallida", Actor(None, "fantasma"), resultado="fallo",
                    origen="keycloak", clave_origen="k:3", fecha=_f(4))
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
```

Run: `uv run pytest services/administracion/tests/test_bitacora.py -q` → Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 4: Implementar la bitácora**

`services/administracion/src/administracion/bitacora.py`:

```python
"""Escritura y consulta de la bitácora de actividad (tabla de solo inserción)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from administracion.modelos import Actividad

GrupoTipo = Literal["sesiones", "usuarios", "importaciones", "catalogo"]
PREFIJOS_GRUPO: dict[str, str] = {
    "sesiones": "sesion.",
    "usuarios": "usuario.",
    "importaciones": "importacion.",
    "catalogo": "servicio.",
}


@dataclass(frozen=True)
class Actor:
    id: str | None
    nombre: str
    ip: str | None = None


@dataclass(frozen=True)
class Objeto:
    tipo: str
    id: str
    nombre: str


@dataclass(frozen=True)
class FiltroActividad:
    persona: str | None = None  # quien actuó o sobre quien se actuó
    tipo: GrupoTipo | None = None
    desde: datetime | None = None
    hasta: datetime | None = None  # exclusivo


async def registrar(
    sesion: AsyncSession,
    tipo: str,
    actor: Actor,
    *,
    objeto: Objeto | None = None,
    detalle: dict[str, Any] | None = None,
    resultado: str = "exito",
    origen: str = "administracion",
    clave_origen: str | None = None,
    fecha: datetime | None = None,
) -> None:
    """Agrega un registro a la transacción en curso; una clave de origen repetida no hace nada."""
    valores: dict[str, Any] = {
        "actor_id": actor.id,
        "actor_nombre": actor.nombre,
        "tipo": tipo,
        "objeto_tipo": objeto.tipo if objeto else None,
        "objeto_id": objeto.id if objeto else None,
        "objeto_nombre": objeto.nombre if objeto else None,
        "detalle": detalle or {},
        "resultado": resultado,
        "ip": actor.ip,
        "origen": origen,
        "clave_origen": clave_origen or f"{origen}:{uuid.uuid4()}",
    }
    if fecha is not None:
        valores["fecha"] = fecha
    await sesion.execute(
        insert(Actividad).values(**valores).on_conflict_do_nothing(index_elements=["clave_origen"])
    )


def _filtrada(filtro: FiltroActividad) -> Select[tuple[Actividad]]:
    consulta = select(Actividad)
    if filtro.persona:
        consulta = consulta.where(
            or_(Actividad.actor_id == filtro.persona, Actividad.objeto_id == filtro.persona)
        )
    if filtro.tipo:
        consulta = consulta.where(Actividad.tipo.startswith(PREFIJOS_GRUPO[filtro.tipo]))
    if filtro.desde:
        consulta = consulta.where(Actividad.fecha >= filtro.desde)
    if filtro.hasta:
        consulta = consulta.where(Actividad.fecha < filtro.hasta)
    return consulta


async def consultar(
    sesion: AsyncSession, filtro: FiltroActividad, desplazamiento: int, limite: int
) -> tuple[int, list[Actividad]]:
    total = await sesion.scalar(select(func.count()).select_from(_filtrada(filtro).subquery()))
    filas = await sesion.scalars(
        _filtrada(filtro)
        .order_by(Actividad.fecha.desc(), Actividad.id)
        .offset(desplazamiento)
        .limit(limite)
    )
    return total or 0, list(filas)


async def ultimos_accesos(sesion: AsyncSession, ids: list[str]) -> dict[str, datetime]:
    if not ids:
        return {}
    filas = await sesion.execute(
        select(Actividad.actor_id, func.max(Actividad.fecha))
        .where(Actividad.tipo == "sesion.iniciada", Actividad.actor_id.in_(ids))
        .group_by(Actividad.actor_id)
    )
    return {actor_id: fecha for actor_id, fecha in filas.tuples() if actor_id is not None}
```

Run: `uv run pytest services/administracion/tests/test_reglas.py services/administracion/tests/test_bitacora.py -q` → Expected: PASS.

Run: `uv run ruff check services/administracion && uv run ruff format services/administracion && uv run mypy` → Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add services/administracion
git commit -m "feat(administracion): reglas de protección, contraseña temporal y bitácora consultable" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 5: API de usuarios y correos

**Files:**
- Create:
  - `services/administracion/src/administracion/api/__init__.py` (vacío)
  - `services/administracion/src/administracion/api/esquemas.py`, `api/rutas.py`
  - `services/administracion/tests/test_usuarios.py`, `test_correos.py`
- Modify: `services/administracion/src/administracion/main.py`, `services/administracion/tests/conftest.py`

**Interfaces:**
- Consumes:
  - Tasks 3 y 4: `ProveedorIdentidad`, excepciones, reglas, `registrar`, `ultimos_accesos`.
  - Task 1: `CorreoEnviado`.
- Produces:
  - Endpoints:
    - `GET /usuarios?busqueda&rol&estado&pagina&tamano` → `{total, elementos: UsuarioSalida[]}`.
    - `POST /usuarios` → 201 `{usuario, correo_enviado: bool | null, contrasena_temporal: str | null}`.
    - `GET /usuarios/{id}` y `PATCH /usuarios/{id}` → `UsuarioSalida`.
    - `POST /usuarios/{id}/desactivar` y `POST /usuarios/{id}/activar` → `UsuarioSalida`.
    - `POST /usuarios/{id}/contrasena` (`{metodo: "correo" | "temporal"}`) → `{contrasena_temporal}`.
    - `POST /usuarios/{id}/cerrar-sesiones` → 204.
    - `GET /correos?pagina&tamano` → `{total, elementos, buzon_url}`.
  - `UsuarioSalida = {id, usuario, nombre, apellidos, correo, roles: string[], activo, creado_en, ultimo_acceso | null}`, con los roles en el orden admin, comprador, aprobador.
  - Errores Problem Details con `codigo`: `identidad_no_disponible` (503), `usuario_no_encontrado` (404), `usuario_duplicado` / `correo_duplicado` (409, con `errores: [{campo, mensaje}]`), `regla_proteccion` (409), `correo_no_enviado` (503), `bitacora_no_registrada` (500) y `sin_correo` (409).
  - Tipos de bitácora: `usuario.creado`, `usuario.actualizado`, `usuario.roles_cambiados`, `usuario.desactivado`, `usuario.activado`, `usuario.correo_contrasena`, `usuario.contrasena_temporal` y `usuario.sesiones_cerradas`.
  - `crear_app(configuracion=None, validador=None, fabrica=None, identidad=None)`.

- [ ] **Step 1: Fixture con identidad en memoria**

En `services/administracion/tests/conftest.py`:
- importe `from administracion.identidad_falsa import IdentidadFalsa`;
- agregue esta fixture;
- cambie `cliente` para recibir `identidad: IdentidadFalsa` y pasarla a `crear_app`, como se muestra:

```python
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
```

- [ ] **Step 2: Pruebas de la API (fallan)**

`services/administracion/tests/test_usuarios.py`:

```python
import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from administracion.bitacora import Actor, registrar
from administracion.identidad_falsa import IdentidadFalsa
from comun.pruebas import ClavesPrueba
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

NUEVO = {
    "usuario": "Ana.Lopez",
    "nombre": "Ana",
    "apellidos": "López",
    "correo": "ana@plataforma.example",
    "roles": ["comprador"],
    "metodo": "invitacion",
}


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


async def _bitacora(fabrica: async_sessionmaker[AsyncSession]) -> list[dict[str, Any]]:
    async with fabrica() as sesion:
        filas = await sesion.execute(
            text("SELECT tipo, objeto_id, detalle, resultado FROM actividad ORDER BY fecha")
        )
        return [dict(f._mapping) for f in filas]


async def test_solo_admin(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    comprador = {"Authorization": f"Bearer {claves.token('comprador')}"}
    assert (await cliente.get("/usuarios", headers=comprador)).status_code == 403
    assert (await cliente.get("/usuarios")).status_code == 401


async def test_lista_filtra_busca_sin_acentos_y_pagina(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    identidad.agregar("lopez", ["aprobador"], nombre="Lucía", apellidos="López", activo=False)
    async with fabrica() as sesion:
        await registrar(sesion, "sesion.iniciada", Actor("lopez", "lopez"),
                        origen="keycloak", clave_origen="k:1",
                        fecha=datetime(2026, 10, 7, tzinfo=UTC))
        await sesion.commit()

    todos = (await cliente.get("/usuarios", headers=admin)).json()
    assert todos["total"] == 3
    busqueda = (await cliente.get("/usuarios", params={"busqueda": "LOPEZ"}, headers=admin)).json()
    assert [u["usuario"] for u in busqueda["elementos"]] == ["lopez"]
    assert busqueda["elementos"][0]["ultimo_acceso"] == "2026-10-07T00:00:00Z"
    assert busqueda["elementos"][0]["activo"] is False
    por_rol = (await cliente.get("/usuarios", params={"rol": "admin"}, headers=admin)).json()
    assert [u["usuario"] for u in por_rol["elementos"]] == ["admin-1"]
    inactivos = (await cliente.get("/usuarios", params={"estado": "inactivos"}, headers=admin)).json()
    assert inactivos["total"] == 1
    pagina = (await cliente.get("/usuarios", params={"tamano": 2, "pagina": 2}, headers=admin)).json()
    assert pagina["total"] == 3
    assert len(pagina["elementos"]) == 1


async def test_alta_por_invitacion(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await cliente.post("/usuarios", json=NUEVO, headers=admin)
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["usuario"]["usuario"] == "ana.lopez"
    assert cuerpo["usuario"]["roles"] == ["comprador"]
    assert cuerpo["correo_enviado"] is True
    assert cuerpo["contrasena_temporal"] is None
    assert identidad.correos == [("id-ana.lopez", 259200)]
    assert [(f["tipo"], f["resultado"]) for f in await _bitacora(fabrica)] == [
        ("usuario.creado", "exito"),
        ("usuario.correo_contrasena", "exito"),
    ]
    correos = (await cliente.get("/correos", headers=admin)).json()
    assert correos["elementos"][0]["tipo"] == "invitacion"
    assert correos["elementos"][0]["estado"] == "enviado"


async def test_alta_con_contrasena_temporal_no_la_guarda(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await cliente.post("/usuarios", json={**NUEVO, "metodo": "temporal"}, headers=admin)
    assert respuesta.status_code == 201
    temporal = respuesta.json()["contrasena_temporal"]
    assert len(temporal) == 16
    assert identidad.temporales["id-ana.lopez"] == temporal
    assert identidad.correos == []
    assert temporal not in json.dumps(await _bitacora(fabrica), default=str)
    async with fabrica() as sesion:
        assert await sesion.scalar(text("SELECT count(*) FROM correo_enviado")) == 0


async def test_alta_duplicada_marca_el_campo(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    respuesta = await cliente.post(
        "/usuarios", json={**NUEVO, "usuario": "comprador-1"}, headers=admin
    )
    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "usuario_duplicado"
    assert cuerpo["errores"] == [
        {"campo": "usuario", "mensaje": "Ya existe un usuario con ese nombre de usuario."}
    ]
    correo = await cliente.post(
        "/usuarios", json={**NUEVO, "correo": "comprador-1@plataforma.example"}, headers=admin
    )
    assert correo.json()["codigo"] == "correo_duplicado"


async def test_alta_con_correo_caido_crea_la_cuenta_y_lo_avisa(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    identidad.falla_correo = True
    respuesta = await cliente.post("/usuarios", json=NUEVO, headers=admin)
    assert respuesta.status_code == 201
    assert respuesta.json()["correo_enviado"] is False
    assert "id-ana.lopez" in identidad.usuarios
    assert (await _bitacora(fabrica))[-1]["resultado"] == "fallo"
    correos = (await cliente.get("/correos", headers=admin)).json()
    assert correos["elementos"][0]["estado"] == "fallido"


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [({"usuario": "ana lopez"}, "body.usuario"), ({"roles": []}, "body.roles"),
     ({"correo": "no-es-correo"}, "body.correo"), ({"roles": ["root"]}, "body.roles.0")],
)
async def test_validacion(
    cliente: httpx.AsyncClient, admin: dict[str, str], cambio: dict[str, Any], campo: str
) -> None:
    respuesta = await cliente.post("/usuarios", json={**NUEVO, **cambio}, headers=admin)
    assert respuesta.status_code == 422
    assert campo in [e["campo"] for e in respuesta.json()["errores"]]


async def test_identidad_caida(
    cliente: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    identidad.caida = True
    respuesta = await cliente.get("/usuarios", headers=admin)
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "identidad_no_disponible"
    assert respuesta.json()["detail"] == (
        "No se pudo conectar con el servicio de identidad. Intente de nuevo en unos minutos."
    )


async def test_editar_datos_y_roles_registra_antes_y_despues(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await cliente.patch(
        "/usuarios/comprador-1",
        json={"apellidos": "Compras", "roles": ["comprador", "aprobador"]},
        headers=admin,
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["roles"] == ["comprador", "aprobador"]
    assert identidad.usuarios["comprador-1"].apellidos == "Compras"
    registros = await _bitacora(fabrica)
    assert [r["tipo"] for r in registros] == ["usuario.actualizado", "usuario.roles_cambiados"]
    assert registros[0]["detalle"] == {"campos": ["apellidos"]}
    assert registros[1]["detalle"] == {
        "antes": ["comprador"], "despues": ["comprador", "aprobador"]
    }


async def test_nadie_se_quita_admin(
    cliente: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    respuesta = await cliente.patch("/usuarios/admin-1", json={"roles": ["comprador"]}, headers=admin)
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "regla_proteccion"
    assert respuesta.json()["detail"] == "No puede quitarse el rol de administrador."
    assert identidad.usuarios["admin-1"].roles == {"admin"}


async def test_desactivar_y_activar(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    propia = await cliente.post("/usuarios/admin-1/desactivar", headers=admin)
    assert propia.json()["detail"] == "No puede desactivar su propia cuenta."
    desactivado = await cliente.post("/usuarios/comprador-1/desactivar", headers=admin)
    assert desactivado.json()["activo"] is False
    assert identidad.sesiones_cerradas == ["comprador-1"]
    activado = await cliente.post("/usuarios/comprador-1/activar", headers=admin)
    assert activado.json()["activo"] is True
    assert [r["tipo"] for r in await _bitacora(fabrica)] == [
        "usuario.desactivado", "usuario.activado"
    ]


async def test_contrasena_por_correo_distingue_invitacion_y_restablecimiento(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    await cliente.post("/usuarios/comprador-1/contrasena", json={"metodo": "correo"}, headers=admin)
    async with fabrica() as sesion:
        await registrar(sesion, "sesion.iniciada", Actor("comprador-1", "comprador-1"),
                        origen="keycloak", clave_origen="k:1")
        await sesion.commit()
    await cliente.post("/usuarios/comprador-1/contrasena", json={"metodo": "correo"}, headers=admin)
    assert identidad.correos == [("comprador-1", 259200), ("comprador-1", 86400)]
    tipos = [c["tipo"] for c in (await cliente.get("/correos", headers=admin)).json()["elementos"]]
    assert tipos == ["restablecimiento", "invitacion"]


async def test_contrasena_temporal_y_correo_caido(
    cliente: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    temporal = await cliente.post(
        "/usuarios/comprador-1/contrasena", json={"metodo": "temporal"}, headers=admin
    )
    assert len(temporal.json()["contrasena_temporal"]) == 16
    identidad.falla_correo = True
    caido = await cliente.post(
        "/usuarios/comprador-1/contrasena", json={"metodo": "correo"}, headers=admin
    )
    assert caido.status_code == 503
    assert caido.json()["codigo"] == "correo_no_enviado"
    correos = (await cliente.get("/correos", headers=admin)).json()
    assert correos["elementos"][0]["estado"] == "fallido"


async def test_cerrar_sesiones(
    cliente: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    respuesta = await cliente.post("/usuarios/comprador-1/cerrar-sesiones", headers=admin)
    assert respuesta.status_code == 204
    assert identidad.sesiones_cerradas == ["comprador-1"]


async def test_usuario_inexistente(cliente: httpx.AsyncClient, admin: dict[str, str]) -> None:
    respuesta = await cliente.get("/usuarios/nadie", headers=admin)
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "usuario_no_encontrado"


async def test_si_la_bitacora_falla_lo_dice(
    cliente: httpx.AsyncClient, admin: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def falla(*_: object, **__: object) -> None:
        raise SQLAlchemyError("sin base")

    monkeypatch.setattr("administracion.api.rutas.registrar", falla)
    respuesta = await cliente.post("/usuarios/comprador-1/cerrar-sesiones", headers=admin)
    assert respuesta.status_code == 500
    assert respuesta.json()["codigo"] == "bitacora_no_registrada"
    assert respuesta.json()["detail"] == "La acción se aplicó, pero no quedó en la bitácora."
```

`services/administracion/tests/test_correos.py`:

```python
import httpx
import pytest
from comun.pruebas import ClavesPrueba

pytestmark = pytest.mark.integracion


async def test_correos_vacio_con_enlace_al_buzon(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await cliente.get(
        "/correos", headers={"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}
    )
    assert respuesta.json() == {"total": 0, "elementos": [], "buzon_url": "http://buzon:8025"}
```

Run: `uv run pytest services/administracion/tests/test_usuarios.py services/administracion/tests/test_correos.py -q` → Expected: FAIL (`crear_app` no acepta `identidad`; no existe `administracion.api`).

- [ ] **Step 3: Esquemas**

`services/administracion/src/administracion/api/esquemas.py`:

```python
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Rol = Literal["admin", "comprador", "aprobador"]
NombreUsuario = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9.-]{3,30}$")
]
Correo = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class UsuarioNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: NombreUsuario
    nombre: Nombre
    apellidos: Nombre
    correo: Correo
    roles: Annotated[list[Rol], Field(min_length=1)]
    metodo: Literal["invitacion", "temporal"]


class CambioUsuario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Nombre | None = None
    apellidos: Nombre | None = None
    correo: Correo | None = None
    roles: Annotated[list[Rol], Field(min_length=1)] | None = None


class MetodoContrasena(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metodo: Literal["correo", "temporal"]


class UsuarioSalida(BaseModel):
    id: str
    usuario: str
    nombre: str
    apellidos: str
    correo: str
    roles: list[str]
    activo: bool
    creado_en: datetime
    ultimo_acceso: datetime | None


class PaginaUsuarios(BaseModel):
    total: int
    elementos: list[UsuarioSalida]


class ResultadoAlta(BaseModel):
    usuario: UsuarioSalida
    correo_enviado: bool | None
    contrasena_temporal: str | None


class ResultadoContrasena(BaseModel):
    contrasena_temporal: str | None


class CorreoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: datetime
    tipo: str
    destinatario: str
    solicitado_por: str
    estado: str
    error: str | None


class PaginaCorreos(BaseModel):
    total: int
    elementos: list[CorreoSalida]
    buzon_url: str | None


class ActividadSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: datetime
    actor_id: str | None
    actor_nombre: str
    tipo: str
    objeto_tipo: str | None
    objeto_id: str | None
    objeto_nombre: str | None
    detalle: dict[str, Any]
    resultado: str
    ip: str | None


class PaginaActividad(BaseModel):
    total: int
    elementos: list[ActividadSalida]
```

Pydantic serializa `uuid.UUID` como texto y las fechas UTC con sufijo `Z` (por ejemplo `2026-10-07T00:00:00Z`), que es lo que esperan las pruebas.

- [ ] **Step 4: Rutas**

`services/administracion/src/administracion/api/rutas.py`:

```python
"""API de gestión de usuarios y correos (solo administración)."""

import logging
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Literal

from comun.auth import Usuario, requiere_rol
from comun.errores import ErrorDominio
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from administracion.api import esquemas
from administracion.bitacora import Actor, Objeto, registrar, ultimos_accesos
from administracion.db import obtener_sesion
from administracion.identidad import (
    ROLES_ASIGNABLES,
    CorreoNoEnviado,
    DatoDuplicado,
    DatosUsuarioNuevo,
    IdentidadNoDisponible,
    ProveedorIdentidad,
    UsuarioIdentidad,
    UsuarioNoEncontrado,
)
from administracion.modelos import CorreoEnviado
from administracion.reglas import (
    ReglaProteccion,
    generar_contrasena_temporal,
    verificar_cambio_de_roles,
    verificar_desactivacion,
)

log = logging.getLogger(__name__)
router = APIRouter()

VIGENCIA_INVITACION_S = 72 * 3600
VIGENCIA_RESTABLECIMIENTO_S = 24 * 3600

Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]
Admin = Annotated[Usuario, Depends(requiere_rol("admin"))]


def _identidad(request: Request) -> ProveedorIdentidad:
    proveedor: ProveedorIdentidad = request.app.state.identidad
    return proveedor


Identidad = Annotated[ProveedorIdentidad, Depends(_identidad)]

MENSAJES_DUPLICADO = {
    "usuario": "Ya existe un usuario con ese nombre de usuario.",
    "correo": "Ya existe un usuario con ese correo.",
}


@contextmanager
def _traducir_errores() -> Iterator[None]:
    """Convierte los errores de identidad y de las reglas en respuestas para la persona."""
    try:
        yield
    except IdentidadNoDisponible as exc:
        log.warning("Servicio de identidad no disponible: %s", exc)
        raise ErrorDominio(
            503,
            "Servicio no disponible",
            "No se pudo conectar con el servicio de identidad. Intente de nuevo en unos minutos.",
            {"codigo": "identidad_no_disponible"},
        ) from exc
    except UsuarioNoEncontrado as exc:
        raise ErrorDominio(
            404, "No encontrado", "El usuario no existe.", {"codigo": "usuario_no_encontrado"}
        ) from exc
    except DatoDuplicado as exc:
        mensaje = MENSAJES_DUPLICADO[exc.campo]
        raise ErrorDominio(
            409,
            "Conflicto",
            mensaje,
            {"codigo": f"{exc.campo}_duplicado", "errores": [{"campo": exc.campo, "mensaje": mensaje}]},
        ) from exc
    except ReglaProteccion as exc:
        raise ErrorDominio(409, "Conflicto", str(exc), {"codigo": "regla_proteccion"}) from exc


def _sin_bitacora(exc: SQLAlchemyError) -> ErrorDominio:
    log.error("La acción se aplicó, pero no quedó en la bitácora", exc_info=exc)
    return ErrorDominio(
        500,
        "Error interno",
        "La acción se aplicó, pero no quedó en la bitácora.",
        {"codigo": "bitacora_no_registrada"},
    )


def _actor(usuario: Usuario, request: Request) -> Actor:
    return Actor(usuario.id, usuario.nombre, request.client.host if request.client else None)


def _nombre_completo(u: UsuarioIdentidad) -> str:
    return f"{u.nombre} {u.apellidos}".strip() or u.usuario


def _objeto(u: UsuarioIdentidad) -> Objeto:
    return Objeto("usuario", u.id, _nombre_completo(u))


def _roles_ordenados(roles: frozenset[str]) -> list[str]:
    return [r for r in ROLES_ASIGNABLES if r in roles]


def _salida(u: UsuarioIdentidad, ultimo_acceso: datetime | None) -> esquemas.UsuarioSalida:
    return esquemas.UsuarioSalida(
        id=u.id,
        usuario=u.usuario,
        nombre=u.nombre,
        apellidos=u.apellidos,
        correo=u.correo,
        roles=_roles_ordenados(u.roles),
        activo=u.activo,
        creado_en=u.creado_en,
        ultimo_acceso=ultimo_acceso,
    )


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para que "lopez" encuentre "López"."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


async def _enviar_correo(
    identidad: ProveedorIdentidad,
    sesion: AsyncSession,
    usuario: UsuarioIdentidad,
    tipo: Literal["invitacion", "restablecimiento"],
    actor: Actor,
) -> bool:
    """Pide el correo y deja su registro en la transacción; devuelve si salió."""
    vigencia = VIGENCIA_INVITACION_S if tipo == "invitacion" else VIGENCIA_RESTABLECIMIENTO_S
    error: str | None = None
    try:
        await identidad.enviar_correo_contrasena(usuario.id, vigencia)
    except CorreoNoEnviado:
        log.warning("No se pudo enviar el correo de %s a %s", tipo, usuario.id)
        error = "No se pudo entregar el correo al servidor de correo."
    sesion.add(
        CorreoEnviado(
            tipo=tipo,
            destinatario=usuario.correo,
            usuario_id=usuario.id,
            solicitado_por=actor.nombre,
            estado="fallido" if error else "enviado",
            error=error,
        )
    )
    return error is None


@router.get("/usuarios", tags=["usuarios"])
async def listar_usuarios(
    sesion: Sesion,
    identidad: Identidad,
    _: Admin,
    busqueda: Annotated[str | None, Query(max_length=100)] = None,
    rol: esquemas.Rol | None = None,
    estado: Literal["activos", "inactivos"] | None = None,
    pagina: Annotated[int, Query(ge=1, le=1000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
) -> esquemas.PaginaUsuarios:
    with _traducir_errores():
        usuarios = await identidad.listar_usuarios()
    texto = _normalizar((busqueda or "").strip())
    filtrados = sorted(
        (
            u
            for u in usuarios
            if (not texto or texto in _normalizar(f"{u.usuario} {u.nombre} {u.apellidos} {u.correo}"))
            and (rol is None or rol in u.roles)
            and (estado is None or u.activo == (estado == "activos"))
        ),
        key=lambda u: (_normalizar(u.nombre), _normalizar(u.apellidos), u.usuario),
    )
    visibles = filtrados[(pagina - 1) * tamano : pagina * tamano]
    accesos = await ultimos_accesos(sesion, [u.id for u in visibles])
    return esquemas.PaginaUsuarios(
        total=len(filtrados), elementos=[_salida(u, accesos.get(u.id)) for u in visibles]
    )


@router.post("/usuarios", status_code=201, tags=["usuarios"])
async def crear_usuario(
    datos: esquemas.UsuarioNuevo,
    request: Request,
    sesion: Sesion,
    identidad: Identidad,
    admin: Admin,
) -> esquemas.ResultadoAlta:
    actor = _actor(admin, request)
    temporal: str | None = None
    correo_enviado: bool | None = None
    with _traducir_errores():
        usuario_id = await identidad.crear_usuario(
            DatosUsuarioNuevo(datos.usuario, datos.nombre, datos.apellidos, datos.correo)
        )
        await identidad.fijar_roles(usuario_id, frozenset(datos.roles))
        nuevo = await identidad.obtener_usuario(usuario_id)
        if datos.metodo == "temporal":
            temporal = generar_contrasena_temporal()
            await identidad.fijar_contrasena_temporal(usuario_id, temporal)
        else:
            correo_enviado = await _enviar_correo(identidad, sesion, nuevo, "invitacion", actor)
    try:
        await registrar(
            sesion, "usuario.creado", actor, objeto=_objeto(nuevo),
            detalle={"roles": _roles_ordenados(nuevo.roles)},
        )
        if temporal is not None:
            await registrar(sesion, "usuario.contrasena_temporal", actor, objeto=_objeto(nuevo))
        else:
            await registrar(
                sesion, "usuario.correo_contrasena", actor, objeto=_objeto(nuevo),
                detalle={"tipo": "invitacion"}, resultado="exito" if correo_enviado else "fallo",
            )
        await sesion.commit()
    except SQLAlchemyError as exc:
        raise _sin_bitacora(exc) from exc
    return esquemas.ResultadoAlta(
        usuario=_salida(nuevo, None), correo_enviado=correo_enviado, contrasena_temporal=temporal
    )


@router.get("/usuarios/{usuario_id}", tags=["usuarios"])
async def obtener_usuario(
    usuario_id: str, sesion: Sesion, identidad: Identidad, _: Admin
) -> esquemas.UsuarioSalida:
    with _traducir_errores():
        usuario = await identidad.obtener_usuario(usuario_id)
    accesos = await ultimos_accesos(sesion, [usuario.id])
    return _salida(usuario, accesos.get(usuario.id))


@router.patch("/usuarios/{usuario_id}", tags=["usuarios"])
async def editar_usuario(
    usuario_id: str,
    datos: esquemas.CambioUsuario,
    request: Request,
    sesion: Sesion,
    identidad: Identidad,
    admin: Admin,
) -> esquemas.UsuarioSalida:
    actor = _actor(admin, request)
    with _traducir_errores():
        objetivo = await identidad.obtener_usuario(usuario_id)
        nuevos = {"nombre": datos.nombre, "apellidos": datos.apellidos, "correo": datos.correo}
        campos = sorted(k for k, v in nuevos.items() if v is not None and v != getattr(objetivo, k))
        roles_nuevos = frozenset(datos.roles) if datos.roles is not None else objetivo.roles
        if roles_nuevos != objetivo.roles:
            verificar_cambio_de_roles(
                admin.id, objetivo, roles_nuevos, await identidad.listar_usuarios()
            )
        if campos:
            await identidad.actualizar_datos(
                usuario_id,
                datos.nombre or objetivo.nombre,
                datos.apellidos or objetivo.apellidos,
                datos.correo or objetivo.correo,
            )
        if roles_nuevos != objetivo.roles:
            await identidad.fijar_roles(usuario_id, roles_nuevos)
        actualizado = await identidad.obtener_usuario(usuario_id)
    try:
        if campos:
            await registrar(
                sesion, "usuario.actualizado", actor, objeto=_objeto(actualizado),
                detalle={"campos": campos},
            )
        if roles_nuevos != objetivo.roles:
            await registrar(
                sesion, "usuario.roles_cambiados", actor, objeto=_objeto(actualizado),
                detalle={
                    "antes": _roles_ordenados(objetivo.roles),
                    "despues": _roles_ordenados(roles_nuevos),
                },
            )
        await sesion.commit()
    except SQLAlchemyError as exc:
        raise _sin_bitacora(exc) from exc
    accesos = await ultimos_accesos(sesion, [usuario_id])
    return _salida(actualizado, accesos.get(usuario_id))


async def _cambiar_activo(
    usuario_id: str,
    activo: bool,
    request: Request,
    sesion: AsyncSession,
    identidad: ProveedorIdentidad,
    admin: Usuario,
) -> esquemas.UsuarioSalida:
    actor = _actor(admin, request)
    with _traducir_errores():
        objetivo = await identidad.obtener_usuario(usuario_id)
        if not activo:
            verificar_desactivacion(admin.id, objetivo, await identidad.listar_usuarios())
        cambia = objetivo.activo != activo
        if cambia:
            await identidad.fijar_activo(usuario_id, activo)
            if not activo:
                await identidad.cerrar_sesiones(usuario_id)  # que salga de inmediato
        actualizado = await identidad.obtener_usuario(usuario_id)
    if cambia:
        try:
            tipo = "usuario.activado" if activo else "usuario.desactivado"
            await registrar(sesion, tipo, actor, objeto=_objeto(actualizado))
            await sesion.commit()
        except SQLAlchemyError as exc:
            raise _sin_bitacora(exc) from exc
    accesos = await ultimos_accesos(sesion, [usuario_id])
    return _salida(actualizado, accesos.get(usuario_id))


@router.post("/usuarios/{usuario_id}/desactivar", tags=["usuarios"])
async def desactivar_usuario(
    usuario_id: str, request: Request, sesion: Sesion, identidad: Identidad, admin: Admin
) -> esquemas.UsuarioSalida:
    return await _cambiar_activo(usuario_id, False, request, sesion, identidad, admin)


@router.post("/usuarios/{usuario_id}/activar", tags=["usuarios"])
async def activar_usuario(
    usuario_id: str, request: Request, sesion: Sesion, identidad: Identidad, admin: Admin
) -> esquemas.UsuarioSalida:
    return await _cambiar_activo(usuario_id, True, request, sesion, identidad, admin)


@router.post("/usuarios/{usuario_id}/contrasena", tags=["usuarios"])
async def contrasena_usuario(
    usuario_id: str,
    datos: esquemas.MetodoContrasena,
    request: Request,
    sesion: Sesion,
    identidad: Identidad,
    admin: Admin,
) -> esquemas.ResultadoContrasena:
    actor = _actor(admin, request)
    temporal: str | None = None
    enviado = True
    tipo: Literal["invitacion", "restablecimiento"] = "invitacion"
    with _traducir_errores():
        objetivo = await identidad.obtener_usuario(usuario_id)
        if datos.metodo == "temporal":
            temporal = generar_contrasena_temporal()
            await identidad.fijar_contrasena_temporal(usuario_id, temporal)
        else:
            if not objetivo.correo:
                raise ErrorDominio(
                    409,
                    "Conflicto",
                    "El usuario no tiene correo; agregue uno o asígnele una contraseña temporal.",
                    {"codigo": "sin_correo"},
                )
            if await ultimos_accesos(sesion, [usuario_id]):
                tipo = "restablecimiento"
            enviado = await _enviar_correo(identidad, sesion, objetivo, tipo, actor)
    try:
        if temporal is not None:
            await registrar(sesion, "usuario.contrasena_temporal", actor, objeto=_objeto(objetivo))
        else:
            await registrar(
                sesion, "usuario.correo_contrasena", actor, objeto=_objeto(objetivo),
                detalle={"tipo": tipo}, resultado="exito" if enviado else "fallo",
            )
        await sesion.commit()
    except SQLAlchemyError as exc:
        raise _sin_bitacora(exc) from exc
    if not enviado:
        raise ErrorDominio(
            503,
            "Servicio no disponible",
            "No se pudo enviar el correo. Intente de nuevo en unos minutos o asigne una "
            "contraseña temporal.",
            {"codigo": "correo_no_enviado"},
        )
    return esquemas.ResultadoContrasena(contrasena_temporal=temporal)


@router.post("/usuarios/{usuario_id}/cerrar-sesiones", status_code=204, tags=["usuarios"])
async def cerrar_sesiones(
    usuario_id: str, request: Request, sesion: Sesion, identidad: Identidad, admin: Admin
) -> Response:
    actor = _actor(admin, request)
    with _traducir_errores():
        objetivo = await identidad.obtener_usuario(usuario_id)
        await identidad.cerrar_sesiones(usuario_id)
    try:
        await registrar(sesion, "usuario.sesiones_cerradas", actor, objeto=_objeto(objetivo))
        await sesion.commit()
    except SQLAlchemyError as exc:
        raise _sin_bitacora(exc) from exc
    return Response(status_code=204)


@router.get("/correos", tags=["correos"])
async def listar_correos(
    request: Request,
    sesion: Sesion,
    _: Admin,
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
) -> esquemas.PaginaCorreos:
    total = await sesion.scalar(select(func.count()).select_from(CorreoEnviado)) or 0
    filas = await sesion.scalars(
        select(CorreoEnviado)
        .order_by(CorreoEnviado.fecha.desc(), CorreoEnviado.id)
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return esquemas.PaginaCorreos(
        total=total,
        elementos=[esquemas.CorreoSalida.model_validate(f) for f in filas],
        buzon_url=request.app.state.config.buzon_url or None,
    )
```

- [ ] **Step 5: Conectar el router y la identidad en `main.py`**

Reemplace `services/administracion/src/administracion/main.py` por:

```python
"""Aplicación FastAPI del servicio de administración."""

from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.salud import crear_router_salud
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from administracion.api.rutas import router
from administracion.config import Configuracion
from administracion.identidad import ProveedorIdentidad
from administracion.keycloak import IdentidadKeycloak


def crear_app(
    configuracion: Configuracion | None = None,
    validador: ValidadorJWT | None = None,
    fabrica: async_sessionmaker[AsyncSession] | None = None,
    identidad: ProveedorIdentidad | None = None,
) -> FastAPI:
    config = configuracion or Configuracion()
    configurar_logs(config.nombre_servicio, config.log_level)
    sesiones = fabrica or async_sessionmaker(
        create_async_engine(config.database_url, pool_pre_ping=True, hide_parameters=True),
        expire_on_commit=False,
    )
    proveedor = identidad or IdentidadKeycloak(
        config.keycloak_url,
        config.keycloak_realm,
        config.keycloak_cliente,
        config.keycloak_secreto,
        config.url_app,
    )
    app = FastAPI(
        title="Servicio de administración", version="0.1.0", root_path=config.root_path
    )
    app.state.fabrica = sesiones
    app.state.config = config
    app.state.identidad = proveedor
    app.state.validador = validador or validador_desde_jwks(
        config.oidc_issuer, config.oidc_audience, config.oidc_jwks_url
    )
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    async def verificar_postgres() -> None:
        async with sesiones() as sesion:
            await sesion.execute(text("SELECT 1"))

    app.include_router(crear_router_salud({"postgres": verificar_postgres}))
    app.include_router(router)
    return app
```

Run: `uv run pytest services/administracion -q` → Expected: PASS.

Run: `uv run ruff check services/administracion && uv run ruff format services/administracion && uv run mypy` → Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add services/administracion
git commit -m "feat(administracion): API de usuarios con alta por invitación o contraseña temporal, reglas de protección y registro de correos" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 6: Inicios de sesión en la bitácora y consulta de actividad

**Files:**
- Create: `services/administracion/src/administracion/sesiones.py`, `services/administracion/tests/test_sesiones.py`, `test_actividad.py`
- Modify: `services/administracion/src/administracion/api/rutas.py`, `services/administracion/src/administracion/main.py`

**Interfaces:**
- Consumes:
  - `ProveedorIdentidad.eventos_de_sesion` y `listar_usuarios` (Task 3).
  - `registrar`, `consultar` y `FiltroActividad` (Task 4).
  - `CursorEventos` (Task 1).
- Produces:
  - `sesiones.sincronizar(identidad, fabrica) -> int` y `sesiones.ejecutar_periodicamente(identidad, fabrica, intervalo_s)`.
  - Tipos de bitácora: `sesion.iniciada`, `sesion.fallida` (con `detalle.error`, el código de Keycloak) y `sesion.cerrada`.
  - `GET /actividad?persona&tipo&desde&hasta&pagina&tamano` → `{total, elementos: ActividadSalida[]}`:
    - `desde` y `hasta` son fechas `AAAA-MM-DD` del día en `America/Mexico_City`; `hasta` es inclusivo.
    - `tipo` ∈ `sesiones | usuarios | importaciones | catalogo`.
    - `persona` incluye lo que la persona hizo y lo que le hicieron.

- [ ] **Step 1: Pruebas de la sincronización (fallan)**

`services/administracion/tests/test_sesiones.py`:

```python
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from administracion.identidad import EventoSesion
from administracion.identidad_falsa import IdentidadFalsa
from administracion.sesiones import sincronizar
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
        hasta = await sesion.scalar(text("SELECT hasta FROM cursor_eventos WHERE nombre = 'keycloak'"))
    assert hasta == AHORA - timedelta(minutes=10)
```

Run: `uv run pytest services/administracion/tests/test_sesiones.py -q` → Expected: FAIL (`ModuleNotFoundError: administracion.sesiones`).

- [ ] **Step 2: Implementar la sincronización**

`services/administracion/src/administracion/sesiones.py`:

```python
"""Copia a la bitácora los eventos de inicio de sesión que Keycloak guarda 30 días."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from administracion.bitacora import Actor, registrar
from administracion.identidad import IdentidadNoDisponible, ProveedorIdentidad
from administracion.modelos import CursorEventos

log = logging.getLogger(__name__)

TIPOS = {"LOGIN": "sesion.iniciada", "LOGIN_ERROR": "sesion.fallida", "LOGOUT": "sesion.cerrada"}
CURSOR = "keycloak"
RETENCION_KEYCLOAK = timedelta(days=30)


async def sincronizar(
    identidad: ProveedorIdentidad, fabrica: async_sessionmaker[AsyncSession]
) -> int:
    """Lee los eventos desde el cursor y los inserta (idempotente). Devuelve cuántos leyó."""
    async with fabrica() as sesion:
        cursor = await sesion.get(CursorEventos, CURSOR)
        desde = cursor.hasta if cursor else datetime.now(UTC) - RETENCION_KEYCLOAK
        eventos = [e for e in await identidad.eventos_de_sesion(desde) if e.tipo in TIPOS]
        nombres: dict[str, str] = {}
        if any(e.usuario is None and e.usuario_id for e in eventos):
            nombres = {u.id: u.usuario for u in await identidad.listar_usuarios()}
        for evento in eventos:
            nombre = evento.usuario or nombres.get(evento.usuario_id or "") or "Usuario desconocido"
            await registrar(
                sesion,
                TIPOS[evento.tipo],
                Actor(evento.usuario_id, nombre, evento.ip),
                detalle={"error": evento.error} if evento.error else {},
                resultado="fallo" if evento.tipo == "LOGIN_ERROR" else "exito",
                origen="keycloak",
                clave_origen=f"keycloak:{evento.id}",
                fecha=evento.fecha,
            )
        if eventos:
            ultimo = max(e.fecha for e in eventos)
            if cursor:
                cursor.hasta = ultimo
            else:
                sesion.add(CursorEventos(nombre=CURSOR, hasta=ultimo))
        await sesion.commit()
        return len(eventos)


async def ejecutar_periodicamente(
    identidad: ProveedorIdentidad, fabrica: async_sessionmaker[AsyncSession], intervalo_s: int
) -> None:
    while True:
        try:
            await sincronizar(identidad, fabrica)
        except IdentidadNoDisponible:
            log.warning("No se pudieron leer los eventos de Keycloak; se reintentará")
        except Exception:
            log.exception("Error al copiar los eventos de inicio de sesión; se reintentará")
        await asyncio.sleep(intervalo_s)
```

Run: `uv run pytest services/administracion/tests/test_sesiones.py -q` → Expected: PASS.

- [ ] **Step 3: Pruebas de `GET /actividad` (fallan)**

`services/administracion/tests/test_actividad.py`:

```python
from datetime import UTC, datetime

import httpx
import pytest
from administracion.bitacora import Actor, Objeto, registrar
from comun.pruebas import ClavesPrueba
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


@pytest.fixture
async def sembrada(fabrica: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica() as sesion:
        # 05:30 UTC del 8 de octubre = 23:30 del 7 de octubre en la Ciudad de México.
        await registrar(sesion, "sesion.iniciada", Actor("ana", "ana"), origen="keycloak",
                        clave_origen="k:1", fecha=datetime(2026, 10, 8, 5, 30, tzinfo=UTC))
        await registrar(sesion, "usuario.desactivado", Actor("admin-1", "admin1"),
                        objeto=Objeto("usuario", "ana", "Ana López"),
                        fecha=datetime(2026, 10, 8, 18, 0, tzinfo=UTC))
        await sesion.commit()


@pytest.mark.usefixtures("sembrada")
async def test_filtros_y_dia_en_hora_de_mexico(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    del7 = (await cliente.get(
        "/actividad", params={"desde": "2026-10-07", "hasta": "2026-10-07"}, headers=admin
    )).json()
    assert [e["tipo"] for e in del7["elementos"]] == ["sesion.iniciada"]
    persona = (await cliente.get("/actividad", params={"persona": "ana"}, headers=admin)).json()
    assert persona["total"] == 2
    usuarios = (await cliente.get("/actividad", params={"tipo": "usuarios"}, headers=admin)).json()
    assert [e["objeto_nombre"] for e in usuarios["elementos"]] == ["Ana López"]


async def test_rango_invertido(cliente: httpx.AsyncClient, admin: dict[str, str]) -> None:
    respuesta = await cliente.get(
        "/actividad", params={"desde": "2026-10-08", "hasta": "2026-10-01"}, headers=admin
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        {"campo": "hasta", "mensaje": "Debe ser igual o posterior a la fecha inicial"}
    ]


async def test_solo_admin(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    comprador = {"Authorization": f"Bearer {claves.token('comprador')}"}
    assert (await cliente.get("/actividad", headers=comprador)).status_code == 403
```

Run: `uv run pytest services/administracion/tests/test_actividad.py -q` → Expected: FAIL (404).

- [ ] **Step 4: Endpoint de actividad y lectura periódica**

Al final de `services/administracion/src/administracion/api/rutas.py`, agregue:
- los imports `from datetime import date, time, timedelta` y `from zoneinfo import ZoneInfo`, más `consultar`, `FiltroActividad` y `GrupoTipo` desde `administracion.bitacora`;
- este código:

```python
ZONA = ZoneInfo("America/Mexico_City")


def _inicio_del_dia(dia: date) -> datetime:
    return datetime.combine(dia, time.min, tzinfo=ZONA)


@router.get("/actividad", tags=["actividad"])
async def listar_actividad(
    sesion: Sesion,
    _: Admin,
    persona: Annotated[str | None, Query(max_length=64)] = None,
    tipo: GrupoTipo | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
) -> esquemas.PaginaActividad:
    if desde and hasta and hasta < desde:
        raise ErrorDominio(
            422,
            "Solicitud inválida",
            "Revise los campos indicados.",
            {"errores": [{"campo": "hasta", "mensaje": "Debe ser igual o posterior a la fecha inicial"}]},
        )
    filtro = FiltroActividad(
        persona=persona,
        tipo=tipo,
        desde=_inicio_del_dia(desde) if desde else None,
        hasta=_inicio_del_dia(hasta + timedelta(days=1)) if hasta else None,
    )
    total, filas = await consultar(sesion, filtro, (pagina - 1) * tamano, tamano)
    return esquemas.PaginaActividad(
        total=total, elementos=[esquemas.ActividadSalida.model_validate(f) for f in filas]
    )
```

En `services/administracion/src/administracion/main.py`, agregue el ciclo de vida que lee los eventos cada `intervalo_eventos_s` y cierra el cliente HTTP al apagar:
- imports `asyncio`, `contextlib`, `from collections.abc import AsyncIterator`, `from contextlib import asynccontextmanager` y `from administracion.sesiones import ejecutar_periodicamente`;
- dentro de `crear_app`, antes de `app = FastAPI(...)`:

```python
    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        tarea = asyncio.create_task(
            ejecutar_periodicamente(proveedor, sesiones, config.intervalo_eventos_s)
        )
        yield
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
        if isinstance(proveedor, IdentidadKeycloak):
            await proveedor.cerrar()
```

- y pase `lifespan=ciclo_de_vida` a `FastAPI(...)`.

Las pruebas con `httpx.ASGITransport` no ejecutan el ciclo de vida. Por eso no hace falta apagarlo en ellas.

Run: `uv run pytest services/administracion -q` → Expected: PASS.

Run: `uv run ruff check services/administracion && uv run ruff format services/administracion && uv run mypy && uv run pytest services/administracion --cov=administracion --cov-report=term-missing -q` → Expected: sin errores y cobertura de `reglas.py`, `bitacora.py` y `sesiones.py` ≥ 80 %. Pegue las líneas de cobertura en el reporte.

- [ ] **Step 5: Commit**

```bash
git add services/administracion
git commit -m "feat(administracion): inicios de sesión de Keycloak en la bitácora y consulta de actividad por persona, tipo y fechas" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 7: Prueba de humo y README

**Files:**
- Modify: `infra/smoke_test.py`, `README.md`

**Interfaces:**
- Consumes: todo el backend (Tasks 1–6) desplegado con Docker Compose.

- [ ] **Step 1: Ampliar la prueba de humo**

En `infra/smoke_test.py`:
- agregue `import time` y la constante `BUZON = "http://localhost:8025"`;
- agregue estas funciones antes de `main()`:

```python
def token_de(cliente: httpx.Client, usuario: str) -> dict[str, str]:
    respuesta = cliente.post(
        "/auth/realms/plataforma/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "pruebas-humo",
            "username": usuario,
            "password": contrasena_de_desarrollo(usuario),
        },
    )
    verificar(respuesta.status_code == 200, f"{usuario} no obtuvo token: {respuesta.text}")
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


def verificar_administracion(cliente: httpx.Client) -> None:
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")
    api = "/api/administracion"
    verificar(cliente.get(f"{api}/usuarios", headers=comprador).status_code == 403,
              "un comprador no debe gestionar usuarios")
    lista = cliente.get(f"{api}/usuarios", headers=admin)
    verificar(lista.status_code == 200, f"listar usuarios falló: {lista.text}")

    # Usuario de humo reutilizable: se crea la primera vez y después se reactiva.
    datos = {"usuario": "humo.prueba", "nombre": "Humo", "apellidos": "Prueba",
             "correo": "humo.prueba@plataforma.example", "roles": ["comprador"],
             "metodo": "invitacion"}
    alta = cliente.post(f"{api}/usuarios", json=datos, headers=admin)
    if alta.status_code == 201:
        usuario_id = alta.json()["usuario"]["id"]
        verificar(alta.json()["correo_enviado"] is True, "la invitación no se envió")
    else:
        verificar(alta.json().get("codigo") == "usuario_duplicado", f"alta falló: {alta.text}")
        [existente] = cliente.get(f"{api}/usuarios", params={"busqueda": "humo.prueba"},
                                  headers=admin).json()["elementos"]
        usuario_id = existente["id"]
        cliente.post(f"{api}/usuarios/{usuario_id}/activar", headers=admin)
        correo = cliente.post(f"{api}/usuarios/{usuario_id}/contrasena",
                              json={"metodo": "correo"}, headers=admin)
        verificar(correo.status_code == 200, f"el correo no se envió: {correo.text}")

    mensajes = httpx.get(f"{BUZON}/api/v1/search",
                         params={"query": "to:humo.prueba@plataforma.example"}, timeout=10)
    asuntos = [m["Subject"] for m in mensajes.json().get("messages", [])]
    verificar("Defina su contraseña de PluriOne" in asuntos,
              f"el correo no llegó a Mailpit con el asunto esperado: {asuntos}")

    baja = cliente.post(f"{api}/usuarios/{usuario_id}/desactivar", headers=admin)
    verificar(baja.status_code == 200 and baja.json()["activo"] is False,
              f"desactivar falló: {baja.text}")
    tipos = [e["tipo"] for e in cliente.get(f"{api}/actividad", params={"persona": usuario_id},
                                            headers=admin).json()["elementos"]]
    verificar("usuario.desactivado" in tipos and "usuario.correo_contrasena" in tipos,
              f"la bitácora no registró las acciones: {tipos}")

    # Los inicios de sesión llegan a la bitácora en menos de un minuto (lectura cada 30 s).
    limite = time.monotonic() + 75
    while time.monotonic() < limite:
        sesiones = cliente.get(f"{api}/actividad", params={"tipo": "sesiones"},
                               headers=admin).json()["elementos"]
        if any(e["actor_nombre"] == "admin1" for e in sesiones):
            return
        time.sleep(5)
    raise SystemExit("FALLA: los inicios de sesión no llegaron a la bitácora en 75 s")
```

- y dentro de `main()`, antes del `print("OK: …")`, llame `verificar_administracion(cliente)`. Cambie el mensaje final a:

```python
    print(
        f"OK: SPA, Keycloak, proveedores y administración responden "
        f"({lista.json()['total']} proveedores)."
    )
```

Run:

```bash
docker compose -f infra/docker-compose.yml up -d --build --wait
uv run python infra/smoke_test.py
uv run python infra/smoke_test.py
```

Expected: las dos corridas imprimen `OK: …`. La segunda reutiliza `humo.prueba`.

- [ ] **Step 2: README**

En `README.md`, sin borrar nada de lo que ya existe:
- En la tabla o lista de servicios, agregue `administracion` (usuarios, bitácora y correos, en `/api/administracion/`) y Mailpit (buzón de desarrollo en <http://localhost:8025>; solo en este equipo).
- En la sección de `.env`, agregue `ADMINISTRACION_DB_PASSWORD`, `ADMINISTRACION_DUENO_DB_PASSWORD` y `KEYCLOAK_ADMINISTRACION_SECRET`, con una línea sobre qué es cada una.
- Agregue la sección "Activar la administración en un entorno ya creado" con los dos comandos, en este orden:

  ```bash
  docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/20-administracion.sh
  docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/configurar-administracion.sh
  ```

  Diga que ambos son idempotentes. Diga que el primero crea la base y sus dos usuarios, y que el segundo configura en Keycloak el cliente, los eventos, el correo y el tema.
- Agregue una línea: la prueba de humo deja un usuario `humo.prueba` desactivado. Lo reutiliza en cada corrida.

- [ ] **Step 3: Commit**

```bash
git add infra/smoke_test.py README.md
git commit -m "test(infra): prueba de humo de la administración de usuarios con correo en Mailpit y bitácora" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 8: Web — base de administración (tipos, API, menú "Sistema" y componentes)

**Files:**
- Create (con la CLI de shadcn):
  - `web/src/components/ui/dialog.tsx`, `alert-dialog.tsx`, `checkbox.tsx`, `radio-group.tsx`, `label.tsx`
- Create:
  - `web/src/fechas.ts`, `web/src/fechas.test.ts`
  - `web/src/usuarios.ts`, `web/src/usuarios.test.ts`
- Modify:
  - `web/src/api.ts`, `web/src/api.test.ts`
  - `web/src/auth.ts`, `web/src/tipos.ts`
  - `web/src/componentes/navegacion.ts`, `web/src/componentes/navegacion.test.ts`

**Interfaces:**
- Produces:
  - `api.ts`:
    - `ErrorFila.fila` pasa a ser opcional.
    - `ErrorApi.codigo: string | null`, tomado del campo `codigo` de Problem Details.
    - `enviarJson(metodo: "POST" | "PATCH", datos?: unknown): RequestInit`.
    - `erroresPorCampo(error: unknown): Record<string, string>`, que quita el prefijo `body.`.
    - `pedir` devuelve `undefined` en un 204.
  - `auth.ts`: `ROLES: readonly Rol[]` (exportado) y `DESCRIPCIONES_ROL: Record<Rol, string>`.
  - `tipos.ts`: `UsuarioAdmin`, `PaginaUsuarios`, `MetodoAlta`, `ResultadoAlta`, `ResultadoContrasena`, `RegistroActividad`, `PaginaActividad`, `CorreoEnviado` y `PaginaCorreos`.
  - `fechas.ts`: `formatoFechaHora(iso)` y `haceCuanto(iso, ahora?)`.
  - `usuarios.ts`: `nombreCompleto(u)` y `sugerirUsuario(correo)`.
  - `navegacion.ts`: la sección "Sistema" (Usuarios, Correos, Importación, Configuración) reemplaza a "Datos", y `migasDe` usa la ruta más larga que coincida.

- [ ] **Step 1: Componentes de shadcn**

Run: `(cd web && npx shadcn@4.21.0 add dialog alert-dialog checkbox radio-group label)` → Expected:
- Se crean los cinco archivos.
- `package.json` no cambia, porque `radix-ui` ya está instalado. Si cambiara, deténgase y repórtelo.

- [ ] **Step 2: Pruebas (fallan)**

`web/src/fechas.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { formatoFechaHora, haceCuanto } from "@/fechas"

const AHORA = new Date("2026-10-08T18:00:00Z")

describe("haceCuanto", () => {
  it.each([
    ["2026-10-08T17:59:30Z", "hace un momento"],
    ["2026-10-08T17:45:00Z", "hace 15 minutos"],
    ["2026-10-08T16:00:00Z", "hace 2 horas"],
    ["2026-10-07T18:00:00Z", "ayer"],
    ["2026-09-08T18:00:00Z", "hace 1 mes"],
  ])("%s → %s", (iso, esperado) => {
    expect(haceCuanto(iso, AHORA)).toBe(esperado)
  })
})

describe("formatoFechaHora", () => {
  it("muestra la hora de la Ciudad de México", () => {
    // 05:30 UTC = 23:30 del día anterior en la Ciudad de México.
    expect(formatoFechaHora("2026-10-08T05:30:00Z")).toMatch(/7 oct 2026.*11:30/)
  })
})
```

`web/src/usuarios.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { nombreCompleto, sugerirUsuario } from "@/usuarios"

describe("sugerirUsuario", () => {
  it.each([
    ["Ana.López@Empresa.mx", "ana.lopez"],
    ["juan_perez+compras@x.mx", "juanperezcompras"],
    ["", ""],
    ["a".repeat(40) + "@x.mx", "a".repeat(30)],
  ])("%s → %s", (correo, esperado) => {
    expect(sugerirUsuario(correo)).toBe(esperado)
  })
})

describe("nombreCompleto", () => {
  it("usa el usuario si no hay nombre", () => {
    expect(nombreCompleto({ nombre: "", apellidos: "", usuario: "ana" })).toBe(
      "ana"
    )
    expect(
      nombreCompleto({ nombre: "Ana", apellidos: "López", usuario: "ana" })
    ).toBe("Ana López")
  })
})
```

En `web/src/api.test.ts` agregue (importe `enviarJson`, `erroresPorCampo` y `ErrorApi` si faltan; use el `simularApi`/`respuestaJson` que ya usa el archivo, o `vi.stubGlobal("fetch", …)` como en sus otras pruebas):

```ts
describe("administración", () => {
  it("expone el código del problema y los errores por campo sin el prefijo body.", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            title: "Conflicto",
            detail: "Ya existe un usuario con ese nombre de usuario.",
            codigo: "usuario_duplicado",
            errores: [{ campo: "body.correo", mensaje: "Formato inválido" }],
          }),
          { status: 409, headers: { "Content-Type": "application/problem+json" } }
        )
      )
    )
    const error = await pedir("/administracion/usuarios", "t").catch((e) => e)
    expect(error).toBeInstanceOf(ErrorApi)
    expect(error.codigo).toBe("usuario_duplicado")
    expect(erroresPorCampo(error)).toEqual({ correo: "Formato inválido" })
    vi.unstubAllGlobals()
  })

  it("un 204 no intenta leer JSON", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })))
    await expect(
      pedir("/administracion/usuarios/x/cerrar-sesiones", "t", enviarJson("POST"))
    ).resolves.toBeUndefined()
    vi.unstubAllGlobals()
  })

  it("enviarJson arma el cuerpo y la cabecera", () => {
    const init = enviarJson("PATCH", { roles: ["admin"] })
    expect(init.method).toBe("PATCH")
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json")
    expect(init.body).toBe('{"roles":["admin"]}')
  })
})
```

En `web/src/componentes/navegacion.test.ts`:
- en "muestra todo al admin, agrupado por sección", cambie el arreglo esperado a `["Resumen", "Proveedores", "Inteligencia", "Sistema"]`;
- en "descarta las secciones que quedan vacías", cambie `"Datos"` por `"Sistema"`;
- en "descripciones del menú", agregue `Usuarios: "Quién entra y con qué rol"` y `Correos: "Invitaciones y restablecimientos enviados"` al objeto esperado;
- agregue estos casos a `migasDe`:

```ts
    ["/sistema/usuarios", [{ titulo: "Sistema" }, { titulo: "Usuarios" }]],
    [
      "/sistema/usuarios/abc",
      [
        { titulo: "Sistema" },
        { titulo: "Usuarios", ruta: "/sistema/usuarios" },
        { titulo: "Detalle" },
      ],
    ],
    ["/importacion", [{ titulo: "Sistema" }, { titulo: "Importación" }]],
    ["/sistema", [{ titulo: "Página no encontrada" }]],
```

Run: `(cd web && npx vitest run src/fechas.test.ts src/usuarios.test.ts src/api.test.ts src/componentes/navegacion.test.ts)` → Expected: FAIL.

- [ ] **Step 3: Implementar**

`web/src/fechas.ts`:

```ts
const ZONA = "America/Mexico_City"

/** Fecha y hora en la Ciudad de México (p. ej. "7 oct 2026, 11:30 p.m."). */
export function formatoFechaHora(iso: string): string {
  return new Date(iso).toLocaleString("es-MX", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: ZONA,
  })
}

const UNIDADES: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
]

/** Tiempo relativo en español ("hace 2 horas", "ayer"). */
export function haceCuanto(iso: string, ahora: Date = new Date()): string {
  const segundos = Math.round((new Date(iso).getTime() - ahora.getTime()) / 1000)
  const formato = new Intl.RelativeTimeFormat("es-MX", { numeric: "auto" })
  for (const [unidad, tamano] of UNIDADES) {
    if (Math.abs(segundos) >= tamano)
      return formato.format(Math.trunc(segundos / tamano), unidad)
  }
  return "hace un momento"
}
```

`web/src/usuarios.ts`:

```ts
/** "Ana López", o el nombre de usuario si la cuenta no tiene nombre. */
export function nombreCompleto(u: {
  nombre: string
  apellidos: string
  usuario: string
}): string {
  return `${u.nombre} ${u.apellidos}`.trim() || u.usuario
}

/** Usuario sugerido a partir del correo: minúsculas, sin acentos, solo letras, números, punto y guion. */
export function sugerirUsuario(correo: string): string {
  return (correo.split("@")[0] ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9.-]/g, "")
    .slice(0, 30)
}
```

En `web/src/api.ts`:
- Cambie `export type ErrorFila = { fila: number; campo: string; mensaje: string }` por `export type ErrorFila = { fila?: number; campo: string; mensaje: string }`.
- Agregue a `ErrorApi` el campo `readonly codigo: string | null`, como quinto parámetro del constructor con valor por defecto `null`.
- En `pedir`:
  - al tipo leído del cuerpo agregue `codigo?: string` y pase `problema.codigo ?? null` al construir el `ErrorApi`;
  - antes de `return (await respuesta.json()) as T`, agregue `if (respuesta.status === 204) return undefined as T`.
- Al final del archivo, agregue:

```ts
/** Opciones de fetch para enviar JSON. */
export function enviarJson(
  metodo: "POST" | "PATCH",
  datos?: unknown
): RequestInit {
  return {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: datos === undefined ? undefined : JSON.stringify(datos),
  }
}

/** Mensajes de error por campo ("body.correo" → "correo") para mostrarlos junto a cada campo. */
export function erroresPorCampo(error: unknown): Record<string, string> {
  if (!(error instanceof ErrorApi)) return {}
  return Object.fromEntries(
    error.errores.map((e) => [e.campo.replace(/^body\./, ""), e.mensaje])
  )
}
```

En `web/src/auth.ts`, cambie `const ROLES` por `export const ROLES` y agregue debajo de `NOMBRES_ROL`:

```ts
export const DESCRIPCIONES_ROL: Record<Rol, string> = {
  admin: "Gestiona usuarios, catálogos e importaciones.",
  comprador: "Crea y supervisa las negociaciones.",
  aprobador: "Aprueba adjudicaciones y cierres.",
}
```

Al final de `web/src/tipos.ts`, agregue (importe `type Rol` desde `@/auth`):

```ts
export type UsuarioAdmin = {
  id: string
  usuario: string
  nombre: string
  apellidos: string
  correo: string
  roles: Rol[]
  activo: boolean
  creado_en: string
  ultimo_acceso: string | null
}
export type PaginaUsuarios = { total: number; elementos: UsuarioAdmin[] }
export type MetodoAlta = "invitacion" | "temporal"
export type ResultadoAlta = {
  usuario: UsuarioAdmin
  correo_enviado: boolean | null
  contrasena_temporal: string | null
}
export type ResultadoContrasena = { contrasena_temporal: string | null }
export type RegistroActividad = {
  id: string
  fecha: string
  actor_id: string | null
  actor_nombre: string
  tipo: string
  objeto_tipo: string | null
  objeto_id: string | null
  objeto_nombre: string | null
  detalle: Record<string, unknown>
  resultado: "exito" | "fallo"
  ip: string | null
}
export type PaginaActividad = { total: number; elementos: RegistroActividad[] }
export type CorreoEnviado = {
  id: string
  fecha: string
  tipo: "invitacion" | "restablecimiento"
  destinatario: string
  solicitado_por: string
  estado: "enviado" | "fallido"
  error: string | null
}
export type PaginaCorreos = {
  total: number
  elementos: CorreoEnviado[]
  buzon_url: string | null
}
```

En `web/src/componentes/navegacion.ts`:
- Importe `Mail` y `UsersRound` de `lucide-react`.
- Reemplace la sección `"Datos"` por esta, en el mismo lugar:

```ts
  {
    titulo: "Sistema",
    elementos: [
      {
        titulo: "Usuarios",
        ruta: "/sistema/usuarios",
        descripcion: "Quién entra y con qué rol",
        icono: UsersRound,
        soloAdmin: true,
      },
      {
        titulo: "Correos",
        ruta: "/sistema/correos",
        descripcion: "Invitaciones y restablecimientos enviados",
        icono: Mail,
        soloAdmin: true,
      },
      {
        titulo: "Importación",
        ruta: "/importacion",
        descripcion: "Cargar datos del ERP",
        icono: FileUp,
        soloAdmin: true,
      },
      {
        titulo: "Configuración",
        ruta: "/configuracion",
        descripcion: "Ajustes de puntuación y precios",
        icono: Settings,
        soloAdmin: true,
      },
    ],
  },
```

- Reemplace `migasDe` por esta versión, que usa la ruta del menú más larga que coincida:

```ts
/** Migas de pan: sección › página › detalle (la sección se omite si se llama igual que la página). */
export function migasDe(pathname: string): Miga[] {
  const ruta = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname
  let mejor: { seccion: SeccionNavegacion; elemento: ElementoNavegacion } | null =
    null
  for (const seccion of NAVEGACION) {
    for (const elemento of seccion.elementos) {
      const coincide = estaActiva(elemento.ruta, ruta)
      if (coincide && (!mejor || elemento.ruta.length > mejor.elemento.ruta.length))
        mejor = { seccion, elemento }
    }
  }
  if (!mejor) return [{ titulo: "Página no encontrada" }]
  const { seccion, elemento } = mejor
  const migas: Miga[] =
    seccion.titulo === elemento.titulo ? [] : [{ titulo: seccion.titulo }]
  if (ruta !== elemento.ruta) {
    return [
      ...migas,
      { titulo: elemento.titulo, ruta: elemento.ruta },
      { titulo: "Detalle" },
    ]
  }
  return [...migas, { titulo: elemento.titulo }]
}
```

Run: `(cd web && npx vitest run src/fechas.test.ts src/usuarios.test.ts src/api.test.ts src/componentes/navegacion.test.ts src/componentes/Layout.test.tsx)` → Expected: PASS.

Si `formatoFechaHora` usa otra forma para "p.m." en el ICU de Node, la expresión `/7 oct 2026.*11:30/` igual pasa: valida el día y la hora, no el sufijo. No la cambie.

Run: `(cd web && npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}")` → Expected: todo en verde.

- [ ] **Step 4: Commit**

```bash
git add web
git commit -m "feat(web): área Sistema en el menú, migas por ruta más larga y base para la administración de usuarios" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 9: Web — Usuarios (lista y alta)

**Files:**
- Create:
  - `web/src/componentes/Filtro.tsx`, `Paginacion.tsx`, `CamposRoles.tsx`, `DialogoContrasenaTemporal.tsx`, `FormularioAltaUsuario.tsx`
  - `web/src/paginas/Usuarios.tsx`, `web/src/paginas/Usuarios.test.tsx`
- Modify: `web/src/paginas/Proveedores.tsx` (usar `Filtro` y `Paginacion`), `web/src/rutas.tsx`

**Interfaces:**
- Consumes: Task 8 (`pedir`, `enviarJson`, `erroresPorCampo`, `ROLES`, `NOMBRES_ROL`, `DESCRIPCIONES_ROL`, tipos, `haceCuanto`, `formatoFechaHora`, `nombreCompleto`, `sugerirUsuario`) y componentes existentes (`EncabezadoPagina`, `Estados`, `EtiquetaEstado`, `Iniciales`, `RequiereRol`).
- Produces:
  - `Filtro({ activo, onClick, children })`, movido tal cual desde `Proveedores.tsx`.
  - `Paginacion({ pagina, total, porPagina, nombre, alCambiar })`. `nombre` es el plural ("proveedores", "usuarios", "correos").
  - `CamposRoles({ valor: Rol[], alCambiar(roles: Rol[]), error?: string })`.
  - `DialogoContrasenaTemporal({ datos: { nombre: string; contrasena: string } | null, alCerrar() })`.
  - `FormularioAltaUsuario({ abierto, alCambiarAbierto(abierto), alTerminar(resultado: ResultadoAlta) })`.
  - Página `Usuarios` en la ruta `/sistema/usuarios`.

- [ ] **Step 1: Extraer `Filtro` y `Paginacion` (refactor sin cambio de conducta)**

`web/src/componentes/Filtro.tsx`: mueva la función `Filtro` de `web/src/paginas/Proveedores.tsx` sin cambios y expórtela con sus imports (`Button`, `ReactNode`).

`web/src/componentes/Paginacion.tsx`:

```tsx
import { ArrowLeft, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"

/** "Mostrando 1–25 de 60 …" con Anterior/Siguiente. */
export function Paginacion({
  pagina,
  total,
  porPagina,
  nombre,
  alCambiar,
}: {
  pagina: number
  total: number
  porPagina: number
  nombre: string
  alCambiar: (pagina: number) => void
}) {
  const paginas = Math.max(1, Math.ceil(total / porPagina))
  const desde = (pagina - 1) * porPagina + 1
  const hasta = Math.min(pagina * porPagina, total)
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
      <span aria-live="polite">
        Mostrando {desde.toLocaleString("es-MX")}–{hasta.toLocaleString("es-MX")}{" "}
        de {total.toLocaleString("es-MX")} {nombre}
      </span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={pagina <= 1}
          onClick={() => alCambiar(pagina - 1)}
        >
          <ArrowLeft aria-hidden />
          Anterior
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={pagina >= paginas}
          onClick={() => alCambiar(pagina + 1)}
        >
          Siguiente
          <ArrowRight aria-hidden />
        </Button>
      </div>
    </div>
  )
}
```

En `web/src/paginas/Proveedores.tsx`:
- importe `Filtro` desde `@/componentes/Filtro` y borre la definición local;
- reemplace el bloque de paginación (el `div` con "Mostrando …" y los dos botones) por:

```tsx
<Paginacion
  pagina={pagina}
  total={total}
  porPagina={POR_PAGINA}
  nombre="proveedores"
  alCambiar={(p) => actualizar({ pagina: String(p) })}
/>
```

- quite los imports que queden sin uso (`ArrowLeft`, `ArrowRight` y las variables `paginas`, `desde`, `hasta`).

Run: `(cd web && npx vitest run src/paginas/Proveedores.test.tsx)` → Expected: PASS sin cambios en las pruebas.

- [ ] **Step 2: Pruebas de la página (fallan)**

`web/src/paginas/Usuarios.test.tsx`:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Usuarios } from "@/paginas/Usuarios"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"
import type { UsuarioAdmin } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ANA: UsuarioAdmin = {
  id: "u-ana",
  usuario: "ana.lopez",
  nombre: "Ana",
  apellidos: "López",
  correo: "ana@plataforma.example",
  roles: ["comprador"],
  activo: true,
  creado_en: "2026-10-01T00:00:00Z",
  ultimo_acceso: null,
}
const LISTA = { total: 1, elementos: [ANA] }

function api(
  alta: () => Response | Promise<Response> = () =>
    respuestaJson(
      { usuario: ANA, correo_enviado: true, contrasena_temporal: null },
      201
    )
) {
  return simularApi((url) => {
    if (url.startsWith("/api/administracion/usuarios?"))
      return respuestaJson(LISTA)
    if (url === "/api/administracion/usuarios") return alta()
    return new Response("", { status: 404 })
  })
}

async function llenarAlta(metodo: "invitacion" | "temporal" = "invitacion") {
  await userEvent.click(screen.getByRole("button", { name: "Nuevo usuario" }))
  const panel = await screen.findByRole("dialog", { name: "Nuevo usuario" })
  await userEvent.type(within(panel).getByLabelText("Nombre"), "Ana")
  await userEvent.type(within(panel).getByLabelText("Apellidos"), "López")
  await userEvent.type(
    within(panel).getByLabelText("Correo"),
    "Ana.López@plataforma.example"
  )
  await userEvent.click(within(panel).getByLabelText("Compras"))
  if (metodo === "temporal")
    await userEvent.click(within(panel).getByLabelText("Contraseña temporal"))
  return panel
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Usuarios", () => {
  it("lista con roles, estado y último acceso", async () => {
    api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    const fila = (await screen.findByRole("link", { name: "Ana López" })).closest(
      "tr"
    )!
    expect(within(fila).getByText("Compras")).toBeInTheDocument()
    expect(within(fila).getByText("Activo")).toBeInTheDocument()
    expect(within(fila).getByText("Nunca")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Ana López" })).toHaveAttribute(
      "href",
      "/sistema/usuarios/u-ana"
    )
  })

  it("los filtros viajan en la URL y en la consulta", async () => {
    const fetch = api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    await userEvent.click(
      within(screen.getByRole("group", { name: "Filtrar por rol" })).getByRole(
        "button",
        { name: "Aprobación" }
      )
    )
    expect(ubicacionActual()).toBe("/sistema/usuarios?rol=aprobador")
    await waitFor(() =>
      expect(urlDeLlamada(fetch).searchParams.get("rol")).toBe("aprobador")
    )
  })

  it("alta por invitación: envía los datos y avisa", async () => {
    const fetch = api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta()
    expect(within(panel).getByLabelText("Usuario")).toHaveValue("ana.lopez")
    await userEvent.click(within(panel).getByRole("button", { name: "Dar de alta" }))
    expect(
      await screen.findByText(/Se envió la invitación a ana@plataforma.example/)
    ).toBeInTheDocument()
    const llamada = fetch.mock.calls.find(
      ([url]) => url === "/api/administracion/usuarios"
    )!
    expect(JSON.parse(String((llamada[1] as RequestInit).body))).toEqual({
      usuario: "ana.lopez",
      nombre: "Ana",
      apellidos: "López",
      correo: "Ana.López@plataforma.example",
      roles: ["comprador"],
      metodo: "invitacion",
    })
  })

  it("la contraseña temporal se muestra una sola vez", async () => {
    api(() =>
      respuestaJson(
        { usuario: ANA, correo_enviado: null, contrasena_temporal: "Xy7#abcdefghijkl" },
        201
      )
    )
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta("temporal")
    await userEvent.click(within(panel).getByRole("button", { name: "Dar de alta" }))
    const dialogo = await screen.findByRole("dialog", {
      name: "Contraseña temporal de Ana López",
    })
    expect(within(dialogo).getByText("Xy7#abcdefghijkl")).toBeInTheDocument()
    expect(within(dialogo).getByText(/No se volverá a mostrar/)).toBeInTheDocument()
    await userEvent.click(within(dialogo).getByRole("button", { name: "Listo" }))
    expect(screen.queryByText("Xy7#abcdefghijkl")).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Nuevo usuario" }))
    expect(screen.queryByText("Xy7#abcdefghijkl")).not.toBeInTheDocument()
  })

  it("muestra el duplicado junto al campo", async () => {
    api(() =>
      respuestaJson(
        {
          title: "Conflicto",
          detail: "Ya existe un usuario con ese nombre de usuario.",
          codigo: "usuario_duplicado",
          errores: [
            {
              campo: "usuario",
              mensaje: "Ya existe un usuario con ese nombre de usuario.",
            },
          ],
        },
        409
      )
    )
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta()
    await userEvent.click(within(panel).getByRole("button", { name: "Dar de alta" }))
    const campo = within(panel).getByLabelText("Usuario")
    expect(campo).toHaveAttribute("aria-invalid", "true")
    expect(campo).toHaveAccessibleDescription(
      /Ya existe un usuario con ese nombre de usuario./
    )
  })

  it("si la invitación no sale, lo dice y lleva a la ficha", async () => {
    api(() =>
      respuestaJson(
        { usuario: ANA, correo_enviado: false, contrasena_temporal: null },
        201
      )
    )
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta()
    await userEvent.click(within(panel).getByRole("button", { name: "Dar de alta" }))
    expect(
      await screen.findByText(
        "Se creó la cuenta, pero no se pudo enviar la invitación."
      )
    ).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Abrir la ficha de Ana López" })).toHaveAttribute(
      "href",
      "/sistema/usuarios/u-ana"
    )
  })

  it("con el servicio de identidad caído, ofrece reintentar", async () => {
    simularApi(() =>
      respuestaJson(
        {
          title: "Servicio no disponible",
          detail:
            "No se pudo conectar con el servicio de identidad. Intente de nuevo en unos minutos.",
          codigo: "identidad_no_disponible",
        },
        503
      )
    )
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    expect(
      await screen.findByText(/No se pudo conectar con el servicio de identidad/)
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Reintentar/ })).toBeInTheDocument()
  })

  it("solo para administración", async () => {
    sesionDePrueba.roles = ["comprador"]
    api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad (lista y alta abierta)", async () => {
    api()
    const { container } = renderizarPagina(<Usuarios />, {
      ruta: "/sistema/usuarios",
    })
    await screen.findByRole("link", { name: "Ana López" })
    await esperarSinViolaciones(container)
    await userEvent.click(screen.getByRole("button", { name: "Nuevo usuario" }))
    await screen.findByRole("dialog", { name: "Nuevo usuario" })
    await esperarSinViolaciones(document.body)
  })
})
```

Run: `(cd web && npx vitest run src/paginas/Usuarios.test.tsx)` → Expected: FAIL (no existe `@/paginas/Usuarios`).

- [ ] **Step 3: Componentes del alta**

`web/src/componentes/CamposRoles.tsx`:

```tsx
import { useId } from "react"
import { DESCRIPCIONES_ROL, NOMBRES_ROL, ROLES, type Rol } from "@/auth"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"

/** Casillas de roles, cada una con una línea de qué puede hacer. */
export function CamposRoles({
  valor,
  alCambiar,
  error,
}: {
  valor: Rol[]
  alCambiar: (roles: Rol[]) => void
  error?: string
}) {
  const id = useId()
  function cambiar(rol: Rol, marcado: boolean) {
    const siguientes = marcado ? [...valor, rol] : valor.filter((r) => r !== rol)
    alCambiar(ROLES.filter((r) => siguientes.includes(r)))
  }
  return (
    <fieldset
      className="space-y-3"
      aria-describedby={error ? `${id}-error` : undefined}
    >
      <legend className="mb-2 text-sm font-medium">Roles</legend>
      {ROLES.map((rol) => (
        <div key={rol} className="flex items-start gap-2">
          <Checkbox
            id={`${id}-${rol}`}
            checked={valor.includes(rol)}
            onCheckedChange={(marcado) => cambiar(rol, marcado === true)}
            aria-describedby={`${id}-${rol}-descripcion`}
          />
          <div className="grid gap-0.5">
            <Label htmlFor={`${id}-${rol}`}>{NOMBRES_ROL[rol]}</Label>
            <p
              id={`${id}-${rol}-descripcion`}
              className="text-xs text-muted-foreground"
            >
              {DESCRIPCIONES_ROL[rol]}
            </p>
          </div>
        </div>
      ))}
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </fieldset>
  )
}
```

`web/src/componentes/DialogoContrasenaTemporal.tsx`:

```tsx
import { Check, Copy } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

/** Muestra la contraseña temporal una sola vez; al cerrar, el padre la descarta. */
export function DialogoContrasenaTemporal({
  datos,
  alCerrar,
}: {
  datos: { nombre: string; contrasena: string } | null
  alCerrar: () => void
}) {
  const [copia, setCopia] = useState<"lista" | "copiada" | "fallo">("lista")
  async function copiar() {
    try {
      await navigator.clipboard.writeText(datos?.contrasena ?? "")
      setCopia("copiada")
    } catch {
      setCopia("fallo")
    }
  }
  return (
    <Dialog
      open={datos !== null}
      onOpenChange={(abierto) => {
        if (!abierto) {
          setCopia("lista")
          alCerrar()
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Contraseña temporal de {datos?.nombre}</DialogTitle>
          <DialogDescription>
            No se volverá a mostrar. Entréguela a la persona por un medio
            seguro; deberá cambiarla al entrar.
          </DialogDescription>
        </DialogHeader>
        <p className="rounded-md border bg-muted px-3 py-2 text-center font-mono text-lg tracking-wider break-all select-all">
          {datos?.contrasena}
        </p>
        <p aria-live="polite" className="text-sm text-muted-foreground">
          {copia === "copiada" && "Contraseña copiada."}
          {copia === "fallo" && "No se pudo copiar; selecciónela y cópiela a mano."}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => void copiar()}>
            {copia === "copiada" ? <Check aria-hidden /> : <Copy aria-hidden />}
            Copiar
          </Button>
          <DialogClose asChild>
            <Button>Listo</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

`web/src/componentes/FormularioAltaUsuario.tsx`:

```tsx
import { useMutation } from "@tanstack/react-query"
import { CircleAlert } from "lucide-react"
import { useId, useState, type FormEvent } from "react"
import { enviarJson, erroresPorCampo, ErrorApi, pedir } from "@/api"
import { useToken, type Rol } from "@/auth"
import { CamposRoles } from "@/componentes/CamposRoles"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { MetodoAlta, ResultadoAlta } from "@/tipos"
import { sugerirUsuario } from "@/usuarios"

const CAMPOS = ["nombre", "apellidos", "correo", "usuario"] as const
const ETIQUETAS: Record<(typeof CAMPOS)[number], string> = {
  nombre: "Nombre",
  apellidos: "Apellidos",
  correo: "Correo",
  usuario: "Usuario",
}
const AYUDA_USUARIO =
  "Entre 3 y 30 caracteres: minúsculas, números, punto o guion."

export function FormularioAltaUsuario({
  abierto,
  alCambiarAbierto,
  alTerminar,
}: {
  abierto: boolean
  alCambiarAbierto: (abierto: boolean) => void
  alTerminar: (resultado: ResultadoAlta) => void
}) {
  const token = useToken()
  const id = useId()
  const [valores, setValores] = useState({
    nombre: "",
    apellidos: "",
    correo: "",
    usuario: "",
  })
  const [usuarioEditado, setUsuarioEditado] = useState(false)
  const [roles, setRoles] = useState<Rol[]>([])
  const [metodo, setMetodo] = useState<MetodoAlta>("invitacion")
  const mutacion = useMutation({
    mutationFn: (datos: object) =>
      pedir<ResultadoAlta>(
        "/administracion/usuarios",
        token,
        enviarJson("POST", datos)
      ),
    onSuccess: (resultado) => {
      reiniciar()
      alCambiarAbierto(false)
      alTerminar(resultado)
    },
  })
  const errores = erroresPorCampo(mutacion.error)
  const errorGeneral =
    mutacion.error && Object.keys(errores).length === 0 ? mutacion.error : null

  function reiniciar() {
    setValores({ nombre: "", apellidos: "", correo: "", usuario: "" })
    setUsuarioEditado(false)
    setRoles([])
    setMetodo("invitacion")
    mutacion.reset()
  }

  function cambiar(campo: (typeof CAMPOS)[number], valor: string) {
    setValores((previos) => ({
      ...previos,
      [campo]: valor,
      // El usuario se sugiere del correo hasta que la persona lo escribe a mano.
      ...(campo === "correo" && !usuarioEditado
        ? { usuario: sugerirUsuario(valor) }
        : {}),
    }))
    if (campo === "usuario") setUsuarioEditado(true)
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    mutacion.mutate({ ...valores, roles, metodo })
  }

  return (
    <Sheet
      open={abierto}
      onOpenChange={(siguiente) => {
        if (!siguiente) reiniciar()
        alCambiarAbierto(siguiente)
      }}
    >
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Nuevo usuario</SheetTitle>
          <SheetDescription>
            La persona entrará con su usuario y la contraseña que defina.
          </SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={enviar} className="space-y-5 px-4 pb-4">
          {errorGeneral && (
            <Alert variant="destructive">
              <CircleAlert aria-hidden />
              <AlertTitle>
                {errorGeneral instanceof ErrorApi
                  ? errorGeneral.titulo
                  : "No se pudo dar de alta"}
              </AlertTitle>
              <AlertDescription>{errorGeneral.message}</AlertDescription>
            </Alert>
          )}
          {CAMPOS.map((campo) => {
            const error = errores[campo]
            const ayuda = campo === "usuario" ? AYUDA_USUARIO : null
            const descritoPor =
              [ayuda && `${id}-${campo}-ayuda`, error && `${id}-${campo}-error`]
                .filter(Boolean)
                .join(" ") || undefined
            return (
              <div key={campo} className="grid gap-1.5">
                <Label htmlFor={`${id}-${campo}`}>{ETIQUETAS[campo]}</Label>
                <Input
                  id={`${id}-${campo}`}
                  value={valores[campo]}
                  onChange={(e) => cambiar(campo, e.target.value)}
                  type={campo === "correo" ? "email" : "text"}
                  autoComplete="off"
                  aria-invalid={error ? true : undefined}
                  aria-describedby={descritoPor}
                />
                {ayuda && (
                  <p
                    id={`${id}-${campo}-ayuda`}
                    className="text-xs text-muted-foreground"
                  >
                    {ayuda}
                  </p>
                )}
                {error && (
                  <p id={`${id}-${campo}-error`} className="text-sm text-destructive">
                    {error}
                  </p>
                )}
              </div>
            )
          })}
          <CamposRoles valor={roles} alCambiar={setRoles} error={errores.roles} />
          <div className="space-y-2">
            <p id={`${id}-metodo`} className="text-sm font-medium">
              ¿Cómo obtendrá su contraseña?
            </p>
            <RadioGroup
              aria-labelledby={`${id}-metodo`}
              value={metodo}
              onValueChange={(v) => setMetodo(v as MetodoAlta)}
              className="gap-3"
            >
              <div className="flex items-start gap-2">
                <RadioGroupItem
                  value="invitacion"
                  id={`${id}-invitacion`}
                  aria-describedby={`${id}-invitacion-descripcion`}
                />
                <div className="grid gap-0.5">
                  <Label htmlFor={`${id}-invitacion`}>
                    Invitación por correo (recomendada)
                  </Label>
                  <p
                    id={`${id}-invitacion-descripcion`}
                    className="text-xs text-muted-foreground"
                  >
                    Recibe un enlace para definir su propia contraseña; vence en 72
                    horas.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <RadioGroupItem
                  value="temporal"
                  id={`${id}-temporal`}
                  aria-describedby={`${id}-temporal-descripcion`}
                />
                <div className="grid gap-0.5">
                  <Label htmlFor={`${id}-temporal`}>Contraseña temporal</Label>
                  <p
                    id={`${id}-temporal-descripcion`}
                    className="text-xs text-muted-foreground"
                  >
                    Usted la verá una sola vez y se la entrega; deberá cambiarla al
                    entrar.
                  </p>
                </div>
              </div>
            </RadioGroup>
          </div>
          <SheetFooter className="px-0">
            <Button type="submit" disabled={mutacion.isPending}>
              {mutacion.isPending ? "Dando de alta…" : "Dar de alta"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
```

La etiqueta del campo "Usuario" debe coincidir exactamente con `getByLabelText("Usuario")` de la prueba. Revise que ninguna otra etiqueta del panel contenga "Usuario" como texto completo.

- [ ] **Step 4: Página Usuarios y ruta**

`web/src/paginas/Usuarios.tsx`:

```tsx
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { CircleAlert, MailCheck, Search, UserPlus, X } from "lucide-react"
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { NOMBRES_ROL, ROLES, useToken } from "@/auth"
import { DialogoContrasenaTemporal } from "@/componentes/DialogoContrasenaTemporal"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Filtro } from "@/componentes/Filtro"
import { FormularioAltaUsuario } from "@/componentes/FormularioAltaUsuario"
import { Iniciales } from "@/componentes/Iniciales"
import { Paginacion } from "@/componentes/Paginacion"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora, haceCuanto } from "@/fechas"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import type { PaginaUsuarios, ResultadoAlta } from "@/tipos"
import { nombreCompleto } from "@/usuarios"

const POR_PAGINA = 25
const ESTADOS = ["activos", "inactivos"] as const

export function Usuarios() {
  return (
    <RequiereRol rol="admin">
      <ContenidoUsuarios />
    </RequiereRol>
  )
}

function ContenidoUsuarios() {
  const token = useToken()
  const cliente = useQueryClient()
  const [parametros, actualizar] = useParametros()
  const q = (parametros.get("q") ?? "").trim().slice(0, 100)
  const rol = unoDe(parametros.get("rol"), ROLES)
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const pagina = enteroPositivo(parametros.get("pagina"), 1, 1000)
  const hayFiltros = Boolean(q || rol || estado)
  const [altaAbierta, setAltaAbierta] = useState(false)
  const [aviso, setAviso] = useState<ReactNode>(null)
  const [temporal, setTemporal] = useState<{
    nombre: string
    contrasena: string
  } | null>(null)

  const campoBusqueda = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const campo = campoBusqueda.current
    if (campo && campo.value.trim() !== q) campo.value = q
  }, [q])

  const consulta = useQuery({
    queryKey: ["usuarios", { q, rol, estado, pagina }],
    queryFn: () => {
      const busqueda = new URLSearchParams({
        pagina: String(pagina),
        tamano: String(POR_PAGINA),
      })
      if (q) busqueda.set("busqueda", q)
      if (rol) busqueda.set("rol", rol)
      if (estado) busqueda.set("estado", estado)
      return pedir<PaginaUsuarios>(`/administracion/usuarios?${busqueda}`, token)
    },
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })

  function alTerminarAlta(resultado: ResultadoAlta) {
    void cliente.invalidateQueries({ queryKey: ["usuarios"] })
    const nombre = nombreCompleto(resultado.usuario)
    if (resultado.contrasena_temporal) {
      setAviso(null)
      setTemporal({ nombre, contrasena: resultado.contrasena_temporal })
    } else if (resultado.correo_enviado) {
      setAviso(
        <Alert>
          <MailCheck aria-hidden />
          <AlertTitle>Usuario dado de alta</AlertTitle>
          <AlertDescription>
            Se envió la invitación a {resultado.usuario.correo}. La persona definirá
            su contraseña con el enlace, que vence en 72 horas.
          </AlertDescription>
        </Alert>
      )
    } else {
      setAviso(
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>Se creó la cuenta, pero no se pudo enviar la invitación.</AlertTitle>
          <AlertDescription>
            <p>Desde su ficha puede reintentar el envío o asignar una contraseña temporal.</p>
            <Link
              to={`/sistema/usuarios/${encodeURIComponent(resultado.usuario.id)}`}
              className="font-medium underline"
            >
              Abrir la ficha de {nombre}
            </Link>
          </AlertDescription>
        </Alert>
      )
    }
  }

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = String(new FormData(evento.currentTarget).get("q") ?? "").trim()
    actualizar({ q: texto || null, pagina: null })
  }
  const limpiar = () =>
    actualizar({ q: null, rol: null, estado: null, pagina: null })

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError)
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    const { total, elementos } = consulta.data
    if (elementos.length === 0) {
      return (
        <EstadoVacio
          titulo="Sin resultados"
          descripcion={
            hayFiltros
              ? "Ningún usuario coincide con la búsqueda o los filtros."
              : "Aún no hay usuarios."
          }
          accion={
            hayFiltros && (
              <Button variant="ghost" onClick={limpiar}>
                <X aria-hidden />
                Limpiar filtros
              </Button>
            )
          }
        />
      )
    }
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Persona</TableHead>
              <TableHead>Usuario</TableHead>
              <TableHead>Roles</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Último acceso</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Iniciales nombre={nombreCompleto(u)} />
                    <div>
                      <Link
                        to={`/sistema/usuarios/${encodeURIComponent(u.id)}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {nombreCompleto(u)}
                      </Link>
                      <div className="text-xs text-muted-foreground">{u.correo}</div>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs">{u.usuario}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {u.roles.map((r) => (
                      <Badge key={r} variant="secondary">
                        {NOMBRES_ROL[r]}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <EtiquetaEstado activo={u.activo} />
                </TableCell>
                <TableCell>
                  {u.ultimo_acceso ? (
                    <time
                      dateTime={u.ultimo_acceso}
                      title={formatoFechaHora(u.ultimo_acceso)}
                    >
                      {haceCuanto(u.ultimo_acceso)}
                    </time>
                  ) : (
                    <span className="text-muted-foreground">Nunca</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="usuarios"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Usuarios"
        descripcion="Quién puede entrar a la plataforma y con qué rol. Las cuentas se desactivan, no se borran: su historial se conserva."
        acciones={
          <Button onClick={() => setAltaAbierta(true)}>
            <UserPlus aria-hidden />
            Nuevo usuario
          </Button>
        }
      />
      <div aria-live="polite">{aviso}</div>
      <Card>
        <CardContent className="space-y-4">
          <form role="search" onSubmit={buscar} className="flex flex-wrap items-center gap-2">
            <label htmlFor="busqueda-usuarios" className="sr-only">
              Buscar por nombre, usuario o correo
            </label>
            <div className="relative w-full max-w-sm">
              <Search
                aria-hidden
                className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                id="busqueda-usuarios"
                name="q"
                ref={campoBusqueda}
                defaultValue={q}
                placeholder="Nombre, usuario o correo"
                maxLength={100}
                className="pl-8"
              />
            </div>
            <Button type="submit">Buscar</Button>
          </form>
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label="Filtrar por rol" className="flex flex-wrap gap-2">
              <Filtro activo={!rol} onClick={() => actualizar({ rol: null, pagina: null })}>
                Todos los roles
              </Filtro>
              {ROLES.map((r) => (
                <Filtro
                  key={r}
                  activo={rol === r}
                  onClick={() => actualizar({ rol: r, pagina: null })}
                >
                  {NOMBRES_ROL[r]}
                </Filtro>
              ))}
            </div>
            <div
              role="group"
              aria-label="Filtrar por estado"
              className="flex flex-wrap gap-2 md:ml-auto"
            >
              <Filtro
                activo={!estado}
                onClick={() => actualizar({ estado: null, pagina: null })}
              >
                Todos
              </Filtro>
              <Filtro
                activo={estado === "activos"}
                onClick={() => actualizar({ estado: "activos", pagina: null })}
              >
                Activos
              </Filtro>
              <Filtro
                activo={estado === "inactivos"}
                onClick={() => actualizar({ estado: "inactivos", pagina: null })}
              >
                Inactivos
              </Filtro>
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
      <FormularioAltaUsuario
        abierto={altaAbierta}
        alCambiarAbierto={setAltaAbierta}
        alTerminar={alTerminarAlta}
      />
      <DialogoContrasenaTemporal datos={temporal} alCerrar={() => setTemporal(null)} />
    </section>
  )
}
```

`EncabezadoPagina` puede no aceptar `acciones`. Revíselo:
- Si no lo acepta, agregue una prop opcional `acciones?: ReactNode`, que se pinta a la derecha del título (`flex flex-wrap items-start justify-between gap-4`), sin cambiar el resto.
- Agregue en su prueba existente un caso que pinte la acción.

En `web/src/rutas.tsx`, agregue `import { Usuarios } from "@/paginas/Usuarios"` y la ruta `{ path: "sistema/usuarios", Component: Usuarios },` antes de `"*"`.

Run: `(cd web && npx vitest run src/paginas/Usuarios.test.tsx src/paginas/Proveedores.test.tsx)` → Expected: PASS.

Run: `(cd web && npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}")` → Expected: todo en verde y sin advertencias.

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat(web): página de usuarios con búsqueda, filtros y alta por invitación o contraseña temporal" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 10: Web — Detalle de usuario, Correos y textos de la bitácora

**Files:**
- Create:
  - `web/src/actividad.ts`, `web/src/actividad.test.ts`
  - `web/src/componentes/ConfirmarAccion.tsx`
  - `web/src/paginas/UsuarioDetalle.tsx`, `web/src/paginas/UsuarioDetalle.test.tsx`
  - `web/src/paginas/Correos.tsx`, `web/src/paginas/Correos.test.tsx`
- Modify: `web/src/rutas.tsx`

**Interfaces:**
- Consumes:
  - Tasks 8 y 9: `CamposRoles`, `DialogoContrasenaTemporal`, `Paginacion`, `enviarJson`, `erroresPorCampo`, `ErrorApi.codigo`, `haceCuanto`, `formatoFechaHora` y `nombreCompleto`.
  - API de las Tasks 5 y 6.
- Produces:
  - `actividad.ts`: `TIPOS_ACTIVIDAD` y `describirActividad(registro: RegistroActividad): string`.
    - Para importaciones usa `objeto_nombre` (la entidad legible, p. ej. "proveedores") con `detalle.registros` y `detalle.errores`.
    - Para el catálogo usa `objeto_nombre` (el código del servicio).
    - El plan 2 debe emitir esos campos.
  - `ConfirmarAccion({ titulo, descripcion, textoConfirmar, alConfirmar, children })`, donde `children` es el botón que abre la confirmación.
  - Páginas `UsuarioDetalle` (`/sistema/usuarios/:id`) y `Correos` (`/sistema/correos`).

- [ ] **Step 1: Pruebas (fallan)**

`web/src/actividad.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { describirActividad, TIPOS_ACTIVIDAD } from "@/actividad"
import type { RegistroActividad } from "@/tipos"

const base: RegistroActividad = {
  id: "1",
  fecha: "2026-10-08T00:00:00Z",
  actor_id: "admin-1",
  actor_nombre: "admin1",
  tipo: "",
  objeto_tipo: "usuario",
  objeto_id: "u-ana",
  objeto_nombre: "Ana López",
  detalle: {},
  resultado: "exito",
  ip: null,
}

describe("describirActividad", () => {
  it("todo tipo tiene texto propio", () => {
    for (const tipo of TIPOS_ACTIVIDAD) {
      expect(describirActividad({ ...base, tipo })).not.toBe(tipo)
    }
  })

  it.each([
    ["sesion.iniciada", {}, "Inició sesión"],
    [
      "sesion.fallida",
      { error: "invalid_user_credentials" },
      "Intento fallido de inicio de sesión: contraseña incorrecta",
    ],
    [
      "sesion.fallida",
      { error: "user_temporarily_disabled" },
      "Intento fallido de inicio de sesión: cuenta bloqueada temporalmente",
    ],
    ["usuario.creado", {}, "Dio de alta a Ana López"],
    [
      "usuario.roles_cambiados",
      { antes: ["comprador"], despues: ["comprador", "aprobador"] },
      "Cambió los roles de Ana López: Compras → Compras, Aprobación",
    ],
    [
      "usuario.correo_contrasena",
      {},
      "Envió a Ana López un correo para definir su contraseña",
    ],
  ])("%s", (tipo, detalle, esperado) => {
    expect(describirActividad({ ...base, tipo, detalle })).toBe(esperado)
  })

  it("un tipo desconocido se muestra tal cual", () => {
    expect(describirActividad({ ...base, tipo: "otro.tipo" })).toBe("otro.tipo")
  })
})
```

`web/src/paginas/UsuarioDetalle.test.tsx`:

```tsx
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { UsuarioDetalle } from "@/paginas/UsuarioDetalle"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"
import type { UsuarioAdmin } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ANA: UsuarioAdmin = {
  id: "u-ana",
  usuario: "ana.lopez",
  nombre: "Ana",
  apellidos: "López",
  correo: "ana@plataforma.example",
  roles: ["comprador"],
  activo: true,
  creado_en: "2026-10-01T00:00:00Z",
  ultimo_acceso: "2026-10-07T18:00:00Z",
}
const RUTA = "/api/administracion/usuarios/u-ana"
const ACTIVIDAD = {
  total: 1,
  elementos: [
    {
      id: "a1",
      fecha: "2026-10-07T18:00:00Z",
      actor_id: "u-ana",
      actor_nombre: "ana.lopez",
      tipo: "sesion.iniciada",
      objeto_tipo: null,
      objeto_id: null,
      objeto_nombre: null,
      detalle: {},
      resultado: "exito",
      ip: "10.0.0.7",
    },
  ],
}

function api(cambios: Record<string, () => Response | Promise<Response>> = {}) {
  return simularApi((url) => {
    const respuesta = Object.entries(cambios).find(([clave]) => url === clave)
    if (respuesta) return respuesta[1]()
    if (url === RUTA) return respuestaJson(ANA)
    if (url.startsWith("/api/administracion/actividad?")) return respuestaJson(ACTIVIDAD)
    return new Response("", { status: 404 })
  })
}

function renderizar() {
  return renderizarPagina(<UsuarioDetalle />, {
    ruta: "/sistema/usuarios/u-ana",
    patron: "/sistema/usuarios/:id",
  })
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("UsuarioDetalle", () => {
  it("muestra datos, roles, estado y actividad reciente", async () => {
    api()
    renderizar()
    expect(
      await screen.findByRole("heading", { level: 1, name: "Ana López" })
    ).toBeInTheDocument()
    expect(screen.getByLabelText("Compras")).toBeChecked()
    expect(screen.getByText("Activo")).toBeInTheDocument()
    expect(screen.getByText("Inició sesión")).toBeInTheDocument()
  })

  it("guarda solo lo que cambió", async () => {
    // La API simulada responde por URL (sin método): GET y PATCH devuelven el mismo usuario.
    const fetch = api()
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await userEvent.click(screen.getByLabelText("Aprobación"))
    await userEvent.click(screen.getByRole("button", { name: "Guardar cambios" }))
    expect(await screen.findByText("Cambios guardados.")).toBeInTheDocument()
    const patch = fetch.mock.calls.find(
      ([, init]) => (init as RequestInit | undefined)?.method === "PATCH"
    )!
    expect(JSON.parse(String((patch[1] as RequestInit).body))).toEqual({
      roles: ["comprador", "aprobador"],
    })
  })

  it("explica una regla de protección", async () => {
    api({
      [`${RUTA}/desactivar`]: () =>
        respuestaJson(
          {
            title: "Conflicto",
            detail: "No puede desactivar su propia cuenta.",
            codigo: "regla_proteccion",
          },
          409
        ),
    })
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await userEvent.click(screen.getByRole("button", { name: "Desactivar" }))
    const confirmacion = await screen.findByRole("alertdialog")
    expect(
      within(confirmacion).getByText(/No podrá iniciar sesión/)
    ).toBeInTheDocument()
    await userEvent.click(
      within(confirmacion).getByRole("button", { name: "Desactivar la cuenta" })
    )
    expect(
      await screen.findByText("No puede desactivar su propia cuenta.")
    ).toBeInTheDocument()
  })

  it("asigna una contraseña temporal tras confirmar y la muestra una vez", async () => {
    api({
      [`${RUTA}/contrasena`]: () =>
        respuestaJson({ contrasena_temporal: "Ab1#cdefghijklmn" }),
    })
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await userEvent.click(
      screen.getByRole("button", { name: "Asignar contraseña temporal" })
    )
    await userEvent.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Asignar",
      })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Contraseña temporal de Ana López",
    })
    expect(within(dialogo).getByText("Ab1#cdefghijklmn")).toBeInTheDocument()
  })

  it("si el correo no sale, ofrece la contraseña temporal", async () => {
    api({
      [`${RUTA}/contrasena`]: () =>
        respuestaJson(
          {
            title: "Servicio no disponible",
            detail:
              "No se pudo enviar el correo. Intente de nuevo en unos minutos o asigne una contraseña temporal.",
            codigo: "correo_no_enviado",
          },
          503
        ),
    })
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await userEvent.click(
      screen.getByRole("button", { name: "Enviar correo para definir contraseña" })
    )
    expect(
      await screen.findByText(/No se pudo enviar el correo/)
    ).toBeInTheDocument()
  })

  it("usuario inexistente", async () => {
    api({
      [RUTA]: () =>
        respuestaJson(
          { title: "No encontrado", detail: "El usuario no existe.", codigo: "usuario_no_encontrado" },
          404
        ),
    })
    renderizar()
    expect(await screen.findByText("Este usuario no existe")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Volver a Usuarios" })).toHaveAttribute(
      "href",
      "/sistema/usuarios"
    )
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await screen.findByText("Inició sesión")
    await esperarSinViolaciones(container)
  })
})
```

`web/src/paginas/Correos.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Correos } from "@/paginas/Correos"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const CORREOS = {
  total: 2,
  buzon_url: "http://localhost:8025",
  elementos: [
    {
      id: "c2",
      fecha: "2026-10-08T18:00:00Z",
      tipo: "restablecimiento",
      destinatario: "ana@plataforma.example",
      solicitado_por: "admin1",
      estado: "fallido",
      error: "No se pudo entregar el correo al servidor de correo.",
    },
    {
      id: "c1",
      fecha: "2026-10-07T18:00:00Z",
      tipo: "invitacion",
      destinatario: "ana@plataforma.example",
      solicitado_por: "admin1",
      estado: "enviado",
      error: null,
    },
  ],
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Correos", () => {
  it("lista los correos con su estado y enlaza al buzón", async () => {
    simularApi(() => respuestaJson(CORREOS))
    const { container } = renderizarPagina(<Correos />, { ruta: "/sistema/correos" })
    expect(await screen.findByText("Invitación")).toBeInTheDocument()
    expect(screen.getByText("Restablecimiento")).toBeInTheDocument()
    expect(screen.getByText("No se envió")).toBeInTheDocument()
    expect(screen.getByText("Enviado")).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /Abrir buzón de desarrollo/ })
    ).toHaveAttribute("href", "http://localhost:8025")
    await esperarSinViolaciones(container)
  })

  it("estado vacío sin buzón", async () => {
    simularApi(() => respuestaJson({ total: 0, elementos: [], buzon_url: null }))
    renderizarPagina(<Correos />, { ruta: "/sistema/correos" })
    expect(
      await screen.findByText("Aún no se han enviado correos")
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("link", { name: /Abrir buzón de desarrollo/ })
    ).not.toBeInTheDocument()
  })
})
```

Run: `(cd web && npx vitest run src/actividad.test.ts src/paginas/UsuarioDetalle.test.tsx src/paginas/Correos.test.tsx)` → Expected: FAIL.

- [ ] **Step 2: Textos de la bitácora**

`web/src/actividad.ts`:

```ts
import { NOMBRES_ROL, type Rol } from "@/auth"
import type { RegistroActividad } from "@/tipos"

export const TIPOS_ACTIVIDAD = [
  "sesion.iniciada",
  "sesion.fallida",
  "sesion.cerrada",
  "usuario.creado",
  "usuario.actualizado",
  "usuario.roles_cambiados",
  "usuario.desactivado",
  "usuario.activado",
  "usuario.correo_contrasena",
  "usuario.contrasena_temporal",
  "usuario.sesiones_cerradas",
  "importacion.completada",
  "importacion.rechazada",
  "servicio.creado",
  "servicio.actualizado",
  "servicio.desactivado",
  "servicio.activado",
] as const
type TipoActividad = (typeof TIPOS_ACTIVIDAD)[number]

const ERRORES_SESION: Record<string, string> = {
  invalid_user_credentials: "contraseña incorrecta",
  user_not_found: "usuario inexistente",
  user_disabled: "cuenta desactivada",
  user_temporarily_disabled: "cuenta bloqueada temporalmente",
}

function roles(valor: unknown): string {
  return Array.isArray(valor)
    ? valor.map((r) => NOMBRES_ROL[r as Rol] ?? String(r)).join(", ")
    : ""
}

const TEXTOS: Record<TipoActividad, (a: RegistroActividad) => string> = {
  "sesion.iniciada": () => "Inició sesión",
  "sesion.fallida": (a) => {
    const motivo = ERRORES_SESION[String(a.detalle.error ?? "")]
    return motivo
      ? `Intento fallido de inicio de sesión: ${motivo}`
      : "Intento fallido de inicio de sesión"
  },
  "sesion.cerrada": () => "Cerró sesión",
  "usuario.creado": (a) => `Dio de alta a ${a.objeto_nombre}`,
  "usuario.actualizado": (a) => `Editó los datos de ${a.objeto_nombre}`,
  "usuario.roles_cambiados": (a) =>
    `Cambió los roles de ${a.objeto_nombre}: ${roles(a.detalle.antes)} → ${roles(a.detalle.despues)}`,
  "usuario.desactivado": (a) => `Desactivó a ${a.objeto_nombre}`,
  "usuario.activado": (a) => `Activó a ${a.objeto_nombre}`,
  "usuario.correo_contrasena": (a) =>
    `Envió a ${a.objeto_nombre} un correo para definir su contraseña`,
  "usuario.contrasena_temporal": (a) =>
    `Asignó una contraseña temporal a ${a.objeto_nombre}`,
  "usuario.sesiones_cerradas": (a) => `Cerró las sesiones de ${a.objeto_nombre}`,
  "importacion.completada": (a) =>
    `Importó ${Number(a.detalle.registros ?? 0).toLocaleString("es-MX")} ${a.objeto_nombre}`,
  "importacion.rechazada": (a) =>
    `Intentó importar ${a.objeto_nombre}; el archivo tenía ${Number(a.detalle.errores ?? 0).toLocaleString("es-MX")} errores`,
  "servicio.creado": (a) => `Dio de alta el servicio ${a.objeto_nombre}`,
  "servicio.actualizado": (a) => `Editó el servicio ${a.objeto_nombre}`,
  "servicio.desactivado": (a) => `Desactivó el servicio ${a.objeto_nombre}`,
  "servicio.activado": (a) => `Activó el servicio ${a.objeto_nombre}`,
}

/** La acción en lenguaje llano; un tipo desconocido se muestra tal cual. */
export function describirActividad(registro: RegistroActividad): string {
  const texto = TEXTOS[registro.tipo as TipoActividad]
  return texto ? texto(registro) : registro.tipo
}
```

- [ ] **Step 3: Confirmación reutilizable**

`web/src/componentes/ConfirmarAccion.tsx`:

```tsx
import type { ReactNode } from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

/** Pide confirmar una acción con consecuencias; `children` es el botón que la abre. */
export function ConfirmarAccion({
  titulo,
  descripcion,
  textoConfirmar,
  alConfirmar,
  children,
}: {
  titulo: string
  descripcion: string
  textoConfirmar: string
  alConfirmar: () => void
  children: ReactNode
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{children}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{titulo}</AlertDialogTitle>
          <AlertDialogDescription>{descripcion}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <AlertDialogAction onClick={alConfirmar}>{textoConfirmar}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
```

- [ ] **Step 4: Detalle de usuario**

`web/src/paginas/UsuarioDetalle.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft,
  CircleAlert,
  CircleCheck,
  KeyRound,
  LogOut,
  Mail,
  UserCheck,
  UserX,
} from "lucide-react"
import { useId, useState, type FormEvent, type ReactNode } from "react"
import { Link, useParams } from "react-router"
import { describirActividad } from "@/actividad"
import { enviarJson, erroresPorCampo, ErrorApi, pedir } from "@/api"
import { NOMBRES_ROL, useToken, type Rol } from "@/auth"
import { CamposRoles } from "@/componentes/CamposRoles"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { DialogoContrasenaTemporal } from "@/componentes/DialogoContrasenaTemporal"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Iniciales } from "@/componentes/Iniciales"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { formatoFechaHora, haceCuanto } from "@/fechas"
import type {
  PaginaActividad,
  ResultadoContrasena,
  UsuarioAdmin,
} from "@/tipos"
import { nombreCompleto } from "@/usuarios"

type Mensaje = { tipo: "exito" | "error"; texto: string } | null

export function UsuarioDetalle() {
  return (
    <RequiereRol rol="admin">
      <ContenidoDetalle />
    </RequiereRol>
  )
}

function ContenidoDetalle() {
  const { id = "" } = useParams()
  const token = useToken()
  const ruta = `/administracion/usuarios/${encodeURIComponent(id)}`
  const consulta = useQuery({
    queryKey: ["usuario", id],
    queryFn: () => pedir<UsuarioAdmin>(ruta, token),
    enabled: Boolean(token && id),
  })

  if (consulta.isPending) return <EstadoCarga />
  if (consulta.isError) {
    if (consulta.error instanceof ErrorApi && consulta.error.estado === 404) {
      return (
        <EstadoVacio
          titulo="Este usuario no existe"
          descripcion="Puede que el enlace sea incorrecto."
          accion={
            <Button asChild variant="outline">
              <Link to="/sistema/usuarios">Volver a Usuarios</Link>
            </Button>
          }
        />
      )
    }
    return (
      <EstadoError error={consulta.error} alReintentar={() => void consulta.refetch()} />
    )
  }
  return <Ficha usuario={consulta.data} ruta={ruta} />
}

function Ficha({ usuario, ruta }: { usuario: UsuarioAdmin; ruta: string }) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const nombre = nombreCompleto(usuario)
  const [datos, setDatos] = useState({
    nombre: usuario.nombre,
    apellidos: usuario.apellidos,
    correo: usuario.correo,
  })
  const [roles, setRoles] = useState<Rol[]>(usuario.roles)
  const [mensaje, setMensaje] = useState<Mensaje>(null)
  const [temporal, setTemporal] = useState<string | null>(null)
  // El formulario parte de los datos cargados; tras guardar ya coincide con lo que guardó el servidor.

  function actualizarCache(siguiente: UsuarioAdmin) {
    cliente.setQueryData(["usuario", usuario.id], siguiente)
    void cliente.invalidateQueries({ queryKey: ["usuarios"] })
    void cliente.invalidateQueries({ queryKey: ["actividad", usuario.id] })
  }
  function falla(error: Error) {
    setMensaje({ tipo: "error", texto: error.message })
  }

  const guardar = useMutation({
    mutationFn: (cambios: object) =>
      pedir<UsuarioAdmin>(ruta, token, enviarJson("PATCH", cambios)),
    onSuccess: (siguiente) => {
      actualizarCache(siguiente)
      setMensaje({ tipo: "exito", texto: "Cambios guardados." })
    },
    onError: (error) => {
      if (Object.keys(erroresPorCampo(error)).length === 0) falla(error)
    },
  })
  const errores = erroresPorCampo(guardar.error)

  const accion = useMutation({
    mutationFn: ({ sufijo, cuerpo }: { sufijo: string; cuerpo?: object }) =>
      pedir<UsuarioAdmin | ResultadoContrasena | undefined>(
        `${ruta}/${sufijo}`,
        token,
        enviarJson("POST", cuerpo)
      ),
    onError: falla,
  })

  function enviarCambios(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setMensaje(null)
    const cambios: Record<string, unknown> = {}
    for (const campo of ["nombre", "apellidos", "correo"] as const) {
      if (datos[campo].trim() !== usuario[campo]) cambios[campo] = datos[campo].trim()
    }
    if (roles.join() !== usuario.roles.join()) cambios.roles = roles
    if (Object.keys(cambios).length === 0) {
      setMensaje({ tipo: "exito", texto: "No hay cambios que guardar." })
      return
    }
    guardar.mutate(cambios)
  }

  function ejecutar(sufijo: string, exito: string, cuerpo?: object) {
    setMensaje(null)
    accion.mutate(
      { sufijo, cuerpo },
      {
        onSuccess: (resultado) => {
          if (resultado && "contrasena_temporal" in resultado) {
            if (resultado.contrasena_temporal) setTemporal(resultado.contrasena_temporal)
            else setMensaje({ tipo: "exito", texto: exito })
          } else {
            if (resultado) actualizarCache(resultado)
            setMensaje({ tipo: "exito", texto: exito })
          }
          void cliente.invalidateQueries({ queryKey: ["actividad", usuario.id] })
        },
      }
    )
  }

  return (
    <section className="space-y-6">
      <Link
        to="/sistema/usuarios"
        className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
      >
        <ArrowLeft aria-hidden className="size-4" />
        Usuarios
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <Iniciales nombre={nombre} tamano="lg" />
        <div className="min-w-0 space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{nombre}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono">{usuario.usuario}</span>
            <EtiquetaEstado activo={usuario.activo} />
            {usuario.roles.map((r) => (
              <Badge key={r} variant="secondary">
                {NOMBRES_ROL[r]}
              </Badge>
            ))}
            <span>
              Último acceso:{" "}
              {usuario.ultimo_acceso ? (
                <time
                  dateTime={usuario.ultimo_acceso}
                  title={formatoFechaHora(usuario.ultimo_acceso)}
                >
                  {haceCuanto(usuario.ultimo_acceso)}
                </time>
              ) : (
                "nunca"
              )}
            </span>
          </div>
        </div>
      </div>

      <div aria-live="polite">
        {mensaje && (
          <Alert variant={mensaje.tipo === "error" ? "destructive" : "default"}>
            {mensaje.tipo === "error" ? (
              <CircleAlert aria-hidden />
            ) : (
              <CircleCheck aria-hidden />
            )}
            <AlertTitle>
              {mensaje.tipo === "error" ? "No se aplicó el cambio" : "Listo"}
            </AlertTitle>
            <AlertDescription>{mensaje.texto}</AlertDescription>
          </Alert>
        )}
      </div>

      <Seccion titulo="Datos y roles">
        <form noValidate onSubmit={enviarCambios} className="max-w-lg space-y-4">
          {(["nombre", "apellidos", "correo"] as const).map((campo) => (
            <div key={campo} className="grid gap-1.5">
              <Label htmlFor={`${id}-${campo}`}>
                {{ nombre: "Nombre", apellidos: "Apellidos", correo: "Correo" }[campo]}
              </Label>
              <Input
                id={`${id}-${campo}`}
                type={campo === "correo" ? "email" : "text"}
                value={datos[campo]}
                onChange={(e) => setDatos((d) => ({ ...d, [campo]: e.target.value }))}
                aria-invalid={errores[campo] ? true : undefined}
                aria-describedby={errores[campo] ? `${id}-${campo}-error` : undefined}
              />
              {errores[campo] && (
                <p id={`${id}-${campo}-error`} className="text-sm text-destructive">
                  {errores[campo]}
                </p>
              )}
            </div>
          ))}
          <CamposRoles valor={roles} alCambiar={setRoles} error={errores.roles} />
          <Button type="submit" disabled={guardar.isPending}>
            {guardar.isPending ? "Guardando…" : "Guardar cambios"}
          </Button>
        </form>
      </Seccion>

      <Seccion
        titulo="Acceso"
        descripcion="Contraseña, sesiones abiertas y estado de la cuenta."
      >
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={accion.isPending}
            onClick={() =>
              ejecutar("contrasena", `Se envió el correo a ${usuario.correo}.`, {
                metodo: "correo",
              })
            }
          >
            <Mail aria-hidden />
            Enviar correo para definir contraseña
          </Button>
          <ConfirmarAccion
            titulo="¿Asignar una contraseña temporal?"
            descripcion="La contraseña actual dejará de funcionar. Verá la nueva una sola vez y la persona deberá cambiarla al entrar."
            textoConfirmar="Asignar"
            alConfirmar={() => ejecutar("contrasena", "", { metodo: "temporal" })}
          >
            <Button variant="outline" disabled={accion.isPending}>
              <KeyRound aria-hidden />
              Asignar contraseña temporal
            </Button>
          </ConfirmarAccion>
          <ConfirmarAccion
            titulo="¿Cerrar sus sesiones?"
            descripcion="Se cerrarán todas sus sesiones abiertas; tendrá que volver a iniciar sesión."
            textoConfirmar="Cerrar sesiones"
            alConfirmar={() => ejecutar("cerrar-sesiones", "Se cerraron sus sesiones.")}
          >
            <Button variant="outline" disabled={accion.isPending}>
              <LogOut aria-hidden />
              Cerrar sesiones
            </Button>
          </ConfirmarAccion>
          {usuario.activo ? (
            <ConfirmarAccion
              titulo="¿Desactivar la cuenta?"
              descripcion="No podrá iniciar sesión y se cerrarán sus sesiones abiertas. Su historial se conserva y puede reactivarla cuando quiera."
              textoConfirmar="Desactivar la cuenta"
              alConfirmar={() => ejecutar("desactivar", "La cuenta quedó desactivada.")}
            >
              <Button variant="outline" disabled={accion.isPending}>
                <UserX aria-hidden />
                Desactivar
              </Button>
            </ConfirmarAccion>
          ) : (
            <Button
              variant="outline"
              disabled={accion.isPending}
              onClick={() => ejecutar("activar", "La cuenta quedó activa.")}
            >
              <UserCheck aria-hidden />
              Activar
            </Button>
          )}
        </div>
      </Seccion>

      <ActividadReciente usuarioId={usuario.id} />
      <DialogoContrasenaTemporal
        datos={temporal ? { nombre, contrasena: temporal } : null}
        alCerrar={() => setTemporal(null)}
      />
    </section>
  )
}

function ActividadReciente({ usuarioId }: { usuarioId: string }) {
  const token = useToken()
  const consulta = useQuery({
    queryKey: ["actividad", usuarioId],
    queryFn: () =>
      pedir<PaginaActividad>(
        `/administracion/actividad?${new URLSearchParams({ persona: usuarioId, tamano: "20" })}`,
        token
      ),
    enabled: Boolean(token),
  })
  let contenido: ReactNode
  if (consulta.isPending) contenido = <EstadoCarga filas={3} />
  else if (consulta.isError)
    contenido = (
      <EstadoError error={consulta.error} alReintentar={() => void consulta.refetch()} />
    )
  else if (consulta.data.elementos.length === 0)
    contenido = (
      <p className="text-sm text-muted-foreground">Aún no hay actividad registrada.</p>
    )
  else
    contenido = (
      <ul className="divide-y">
        {consulta.data.elementos.map((a) => (
          <li key={a.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-sm">
            <time dateTime={a.fecha} className="w-44 shrink-0 text-muted-foreground">
              {formatoFechaHora(a.fecha)}
            </time>
            <span className="min-w-0 flex-1">
              {a.actor_id !== usuarioId && (
                <span className="font-medium">{a.actor_nombre}: </span>
              )}
              {describirActividad(a)}
            </span>
            {a.resultado === "fallo" && <Badge variant="destructive">Falló</Badge>}
          </li>
        ))}
      </ul>
    )
  return (
    <Seccion
      titulo="Actividad reciente"
      descripcion="Lo que hizo esta persona y lo que se hizo con su cuenta (últimos 20 registros)."
    >
      {contenido}
    </Seccion>
  )
}
```

Primero confirme que `Seccion` acepta `descripcion` y `children`, y que `Badge` tiene la variante `destructive`. Ambos existen en el código actual.

- [ ] **Step 5: Correos y rutas**

`web/src/paginas/Correos.tsx`:

```tsx
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { CircleAlert, CircleCheck, ExternalLink, Mail } from "lucide-react"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Paginacion } from "@/componentes/Paginacion"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora } from "@/fechas"
import { enteroPositivo, useParametros } from "@/parametros"
import type { PaginaCorreos } from "@/tipos"

const POR_PAGINA = 25
const TIPOS = { invitacion: "Invitación", restablecimiento: "Restablecimiento" }

export function Correos() {
  return (
    <RequiereRol rol="admin">
      <ContenidoCorreos />
    </RequiereRol>
  )
}

function ContenidoCorreos() {
  const token = useToken()
  const [parametros, actualizar] = useParametros()
  const pagina = enteroPositivo(parametros.get("pagina"), 1, 10_000)
  const consulta = useQuery({
    queryKey: ["correos", pagina],
    queryFn: () =>
      pedir<PaginaCorreos>(
        `/administracion/correos?${new URLSearchParams({ pagina: String(pagina), tamano: String(POR_PAGINA) })}`,
        token
      ),
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError)
      return (
        <EstadoError error={consulta.error} alReintentar={() => void consulta.refetch()} />
      )
    const { total, elementos } = consulta.data
    if (elementos.length === 0)
      return (
        <EstadoVacio
          icono={Mail}
          titulo="Aún no se han enviado correos"
          descripcion="Las invitaciones y los correos para restablecer la contraseña aparecerán aquí."
        />
      )
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Destinatario</TableHead>
              <TableHead>Lo pidió</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((c) => (
              <TableRow key={c.id}>
                <TableCell>
                  <time dateTime={c.fecha}>{formatoFechaHora(c.fecha)}</time>
                </TableCell>
                <TableCell>{TIPOS[c.tipo]}</TableCell>
                <TableCell>{c.destinatario}</TableCell>
                <TableCell>{c.solicitado_por}</TableCell>
                <TableCell>
                  {c.estado === "enviado" ? (
                    <Badge variant="success">
                      <CircleCheck aria-hidden />
                      Enviado
                    </Badge>
                  ) : (
                    <Badge variant="destructive" title={c.error ?? undefined}>
                      <CircleAlert aria-hidden />
                      No se envió
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="correos"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  const buzon = consulta.data?.buzon_url
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Correos del sistema"
        descripcion="Invitaciones y correos para restablecer la contraseña que envió la plataforma, y si salieron bien."
        acciones={
          buzon && (
            <Button asChild variant="outline">
              <a href={buzon} target="_blank" rel="noreferrer">
                Abrir buzón de desarrollo
                <ExternalLink aria-hidden />
              </a>
            </Button>
          )
        }
      />
      <Card>
        <CardContent>{contenido()}</CardContent>
      </Card>
    </section>
  )
}
```

En `web/src/rutas.tsx`, importe `UsuarioDetalle` y `Correos`, y agregue antes de `"*"`:

```tsx
      { path: "sistema/usuarios/:id", Component: UsuarioDetalle },
      { path: "sistema/correos", Component: Correos },
```

Run: `(cd web && npx vitest run src/actividad.test.ts src/paginas/UsuarioDetalle.test.tsx src/paginas/Correos.test.tsx)` → Expected: PASS.

Run: `(cd web && npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}")` → Expected: todo en verde y sin advertencias.

- [ ] **Step 6: Commit**

```bash
git add web
git commit -m "feat(web): ficha de usuario con acceso y actividad reciente, y página de correos del sistema" -m "Co-Authored-By: <modelo real> <noreply@anthropic.com>"
```

---

### Task 11: Verificación en el stack real

La hace el **controlador**, porque necesita el panel de navegador. Las correcciones se despachan a un implementador y pasan por revisión. Esta tarea no crea documento de QA; la revisión completa en navegador con su documento es del plan 2.

**Files:**
- Modify: los archivos que requieran correcciones, cada una con su prueba cuando se pueda comprobar en jsdom o pytest.

- [ ] **Step 1: Stack y prueba de humo**

```bash
docker compose -f infra/docker-compose.yml up -d --build --wait
uv run python infra/smoke_test.py
```

Expected: `OK: …`.

- [ ] **Step 2: Flujos en el navegador (controlador)**

En `http://localhost:8080`, con `admin1`:
1. **Menú.** En "Sistema" aparecen Usuarios, Correos, Importación y Configuración; "Datos" ya no está.
2. **Alta por invitación.** Dé de alta a una persona de prueba con invitación. Abra Mailpit (<http://localhost:8025>) y confirme el asunto "Defina su contraseña de PluriOne", con el texto de usted y el enlace.
3. **Definir la contraseña.**
   - Abra el enlace en una ventana sin sesión. La página "Defina su contraseña" debe tener los textos de usted.
   - Defina una contraseña de prueba **generada para esta verificación**. No la repita en el chat; anótela solo donde indiquen las reglas del proyecto para valores de prueba.
   - Confirme que la persona entra y no ve el área "Sistema".
4. **Contraseña temporal.** Dé de alta otra persona con contraseña temporal.
   - El diálogo la muestra una vez y "Copiar" funciona.
   - Al entrar con ella, Keycloak pide cambiarla.
5. **Desactivar.** Desactive a esa persona. Su siguiente intento de entrar falla, y la bitácora de su ficha muestra "Intento fallido de inicio de sesión: cuenta desactivada" en menos de un minuto.
6. **Protección.** Intente quitarse a sí mismo el rol de administrador: aparece "No puede quitarse el rol de administrador."
7. **Accesibilidad.** Corra axe con contraste (en Vite, como en la revisión anterior) sobre Usuarios, el alta abierta, la ficha y Correos, a 375 y 1440 px y en claro y oscuro: 0 violaciones y sin scroll horizontal.

Anote los hallazgos en un archivo de trabajo del controlador.

- [ ] **Step 3: Corregir (implementador)**

Corrija cada hallazgo con su prueba cuando aplique, en un commit `fix(…)` por hallazgo. El controlador vuelve a verificar en el navegador.
