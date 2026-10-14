# N1a — Servicio de negociación: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el servicio `negociacion`. Un comprador crea una negociación con límites basados en el precio justo e invita a proveedores. Un agente determinista negocia por el portal dentro de esos límites, y el comprador supervisa y puede intervenir. Bots medidos por simulación prueban que nunca cierra fuera de límites.

**Architecture:**
- `negociacion` es un microservicio FastAPI más, con la plantilla de `inteligencia`: base propia con dos usuarios, outbox, consumidor común y copias locales por eventos.
- El motor (`dominio/`) es puro y se prueba con Hypothesis. La capa de servicio (`turnos.py`, `publicacion.py`) lo envuelve en transacciones con `FOR UPDATE`.
- El portal autentica con un token de invitación del que solo se guarda el hash.
- `administracion` registra en Actividad y Correos los eventos que publica `negociacion`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 async + asyncpg, Alembic, aio-pika (RabbitMQ), httpx, `smtplib` de la biblioteca estándar, pytest + Hypothesis + Testcontainers, React/Vitest (solo `actividad.ts`, Actividad y Correos).

**Spec:** `docs/superpowers/specs/2026-10-13-negociacion-determinista-design.md` (§2 N1a, §3–§9, §11–§16). El PRD padre es `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md`.

## Global Constraints

- **Dependencias:** sin dependencias de terceros nuevas. El servicio usa las mismas de `inteligencia` más `httpx`, que ya está en el workspace. El correo se manda con `smtplib` y `email.message.EmailMessage`.
- **Dinero:** `NUMERIC(14,4)` en la base y `Decimal` en Python; nunca `float` para valores guardados. La utilidad se calcula en `float` y se guarda en `NUMERIC(6,4)`.
- **Precisión de los términos:**
  - precio y cuota: 0.01;
  - plazo en meses y plazo de pago: enteros;
  - SLA: 0.01;
  - tope: 0.1.
- **Rangos de los términos:**
  - precio > 0 (hasta 10,000,000);
  - plazo de 1 a 60 meses;
  - plazo de pago de 0 a 180 días;
  - SLA de 0 a 100;
  - tope de 0 a 100;
  - cuota de 0 a 10,000,000.
- **Textos:** en español y en «usted». Los errores van en Problem Details con `comun.errores.ErrorDominio` (o `HTTPException`); los de validación por campo van en `{"codigo": …, "errores": [{"campo": …, "mensaje": …}]}`.
- **Eventos:** se publican solo con `registrar_evento(bd, Outbox, "<tipo literal>", payload)`. El tipo va como literal en la llamada, porque `libs/comun/tests/test_topologia.py` lo busca con una expresión regular.
- **Seguridad:**
  - El token de invitación nunca se guarda (solo su SHA-256), nunca se registra en logs y nunca viaja en un evento.
  - Ninguna respuesta del portal ni ningún mensaje del agente contiene ideales, límites, pesos, utilidades ni la referencia de precios.
- **Permisos:** `comprador` opera todos los eventos; `aprobador` y `admin` solo consultan. El portal no acepta JWT; acepta solo `Authorization: Invitacion <token>`.
- **Herramientas:** ruff con líneas de 100, `mypy --strict`, pytest con `asyncio_mode = auto` y la marca `integracion` en las pruebas que usan Docker. Antes de cada commit, `uv run ruff format .`, `uv run ruff check .` y `uv run mypy` deben quedar sin errores. El formateador no parte cadenas largas: si E501 lo pide, pártalas a mano.
- **Cómo correr comandos:** desde la raíz del repositorio, con `uv run …`. En Windows con Git Bash se usan los mismos comandos.
- **Commits:** mensajes en español con prefijo convencional (`feat(negociacion): …`). Todos terminan con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **No se versionan:** `infra/.env`, `datos/`, `web/node_modules`, `web/dist`, `.superpowers/`. Nunca se escriben contraseñas en comandos, archivos versionados ni reportes.
- **Planes viejos:** no se editan los planes ni las bitácoras anteriores.

## Review Focus

1. **Publicar dos veces a la vez** (doble clic): una publicación responde 200 y la otra 409. Se crea un solo juego de sesiones y se manda un solo correo por proveedor. Prueba en la Tarea 8.
2. **Oferta con forma equivocada** (una línea de otro evento, una palanca que falta o sobra, más decimales de los permitidos, un precio de 0): 422 con el campo y un mensaje en español, nunca 500. Pruebas en las Tareas 3 y 9.
3. **Fecha límite sin zona horaria** (`2026-10-20T18:00:00`): 422 con un mensaje en español que pida la zona horaria, no el texto en inglés de Pydantic. Prueba en la Tarea 6.
4. **`inteligencia` responde 500, cuerpo que no es JSON, o se cae:** 503 «No se pudo consultar la referencia de precios» y no queda ningún evento a medias. Prueba en la Tarea 6.
5. **El proveedor aún no llega a la copia local** (se importó hace segundos): 422 `proveedor_no_disponible` con un mensaje claro, no 500 ni un evento sin destinatario. Prueba en la Tarea 6.

---

### Task 1: Topología: cola de negociación y eventos nuevos

**Files:**
- Modify: `libs/comun/src/comun/topologia.py`
- Modify: `infra/rabbitmq/definitions.json` (se regenera)
- Test: `libs/comun/tests/test_topologia.py`

**Interfaces:**
- Produces: `COLA_NEGOCIACION = Cola("negociacion.eventos", ("proveedor.*", "servicio.*"))`. `COLA_ADMINISTRACION` agrega la clave `"negociacion.*"`. `TIPOS_EVENTO` agrega `"negociacion.publicada"`, `"negociacion.cancelada"` y `"negociacion.invitacion_enviada"`.

- [ ] **Step 1: Write the failing test**

En `libs/comun/tests/test_topologia.py`:
1. Agregue `COLA_NEGOCIACION` a la importación de `comun.topologia`.
2. Reemplace la prueba `test_las_claves_comparan_palabra_por_palabra` completa por:

```python
def test_las_claves_comparan_palabra_por_palabra() -> None:
    assert coincide("servicio.*", "servicio.actualizado")
    assert not coincide("servicio.*", "contrato.registrado")
    assert not coincide("servicio.*", "servicio.actualizado.extra")
    assert colas_de("servicio.actualizado") == [
        COLA_INTELIGENCIA.nombre,
        COLA_ADMINISTRACION.nombre,
        COLA_NEGOCIACION.nombre,
    ]
    assert colas_de("importacion.completada") == [COLA_ADMINISTRACION.nombre]
    assert colas_de("modelo.entrenado") == [COLA_ADMINISTRACION.nombre]


def test_negociacion_recibe_proveedores_y_catalogo_y_publica_a_administracion() -> None:
    assert colas_de("proveedor.actualizado") == [COLA_INTELIGENCIA.nombre, COLA_NEGOCIACION.nombre]
    assert colas_de("contrato.registrado") == [COLA_INTELIGENCIA.nombre]
    for tipo in (
        "negociacion.publicada",
        "negociacion.cancelada",
        "negociacion.invitacion_enviada",
    ):
        assert tipo in TIPOS_EVENTO
        assert colas_de(tipo) == [COLA_ADMINISTRACION.nombre]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest libs/comun/tests/test_topologia.py -q -m "not integracion"`
Expected: FAIL. La importación de `COLA_NEGOCIACION` da `ImportError`.

- [ ] **Step 3: Write minimal implementation**

En `libs/comun/src/comun/topologia.py`, reemplace las definiciones de `COLA_ADMINISTRACION`, `COLAS` y `TIPOS_EVENTO` por:

```python
COLA_ADMINISTRACION = Cola(
    "administracion.actividad",
    ("importacion.*", "servicio.*", "configuracion.*", "modelo.*", "negociacion.*"),
)
# Copias locales de negociacion: el contacto del proveedor y el catálogo de servicios.
COLA_NEGOCIACION = Cola("negociacion.eventos", ("proveedor.*", "servicio.*"))
COLAS = (COLA_INTELIGENCIA, COLA_ADMINISTRACION, COLA_NEGOCIACION)

TIPOS_EVENTO = frozenset(
    {
        "proveedor.actualizado",
        "servicio.actualizado",
        "contrato.registrado",
        "desempeno.registrado",
        "tipo_cambio.registrado",
        "importacion.completada",
        "importacion.rechazada",
        "configuracion.actualizada",
        "modelo.entrenado",
        "negociacion.publicada",
        "negociacion.cancelada",
        "negociacion.invitacion_enviada",
    }
)
```

Regenere el archivo de definiciones. El comando lo escribe con fin de línea LF y una línea final vacía, como está hoy:

```bash
uv run python -c "import json, pathlib; from comun.topologia import definiciones; pathlib.Path('infra/rabbitmq/definitions.json').write_text(json.dumps(definiciones(), indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest libs/comun/tests/test_topologia.py -q`
Expected: PASS. Incluye `test_el_archivo_coincide_con_el_modulo` y la prueba de integración con RabbitMQ, que acepta la cola nueva.

- [ ] **Step 5: Commit**

```bash
git add libs/comun/src/comun/topologia.py libs/comun/tests/test_topologia.py infra/rabbitmq/definitions.json
git commit -m "feat(comun): cola de negociación y eventos de negociación en la topología" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Servicio `negociacion`: esqueleto, modelo de datos y copias locales

**Files:**
- Create: `services/negociacion/pyproject.toml`
- Create: `services/negociacion/Dockerfile`
- Create: `services/negociacion/alembic.ini`
- Create: `services/negociacion/alembic/env.py`
- Create: `services/negociacion/alembic/script.py.mako` (copia exacta de `services/inteligencia/alembic/script.py.mako`)
- Create: `services/negociacion/alembic/versions/0001_esquema_inicial.py`
- Create: `services/negociacion/src/negociacion/__init__.py` (vacío)
- Create: `services/negociacion/src/negociacion/config.py`
- Create: `services/negociacion/src/negociacion/db.py`
- Create: `services/negociacion/src/negociacion/modelos.py`
- Create: `services/negociacion/src/negociacion/eventos.py`
- Create: `services/negociacion/src/negociacion/main.py`
- Create: `services/negociacion/tests/conftest.py`
- Test: `services/negociacion/tests/test_migraciones.py`, `services/negociacion/tests/test_salud.py`, `services/negociacion/tests/test_eventos.py`
- Modify: `pyproject.toml` (raíz) y `uv.lock`

**Interfaces:**
- Consumes: `COLA_NEGOCIACION` (Task 1). De `libs/comun`: `ConfiguracionBase`, `ColumnasOutbox`, `RelayOutbox`, `ConsumidorEventos`, `EventoInvalido`, `crear_router_salud`, `registrar_manejadores`, `configurar_logs`, `middleware_correlacion`, `ValidadorJWT`, `validador_desde_jwks`.
- Produces:
  - **Modelos de `negociacion.modelos`:** `Evento`, `Linea`, `Palanca`, `SesionNegociacion` (tabla `sesion`), `Oferta`, `Mensaje`, `Bitacora`, `Proveedor`, `Servicio`, `EventoProcesado`, `Outbox`.
  - **Constantes de `negociacion.modelos`:** `FINALES`, `ESTADOS_SESION`, `ESTADOS_EVENTO`, `CLAVES_PALANCA`.
  - **Copia local:** `negociacion.eventos.aplicar(bd, sobre) -> bool` y `atendedor(fabrica) -> Atender`.
  - **Aplicación:** `negociacion.main.crear_app(configuracion=None, validador=None, fabrica=None) -> FastAPI`.
  - **Fixtures de `conftest.py`:** `urls_bd`, `fabrica`, `claves`, `app`, `cliente`, `comprador`, `aprobador`, `admin`, `aplicar_evento`.
  - **Secuencias:** `folio_evento` (folios) y `orden` (orden de mensajes y ofertas).

- [ ] **Step 1: Write the failing tests**

`services/negociacion/tests/conftest.py`:

```python
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
```

`services/negociacion/tests/test_migraciones.py`:

```python
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
```

`services/negociacion/tests/test_salud.py`:

```python
import httpx
import pytest

pytestmark = pytest.mark.integracion


async def test_listo_con_postgres(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/salud/listo")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "dependencias": {"postgres": "ok"}}
```

`services/negociacion/tests/test_eventos.py`:

```python
import asyncio
import json
import uuid
from collections.abc import Iterator
from typing import Any

import aio_pika
import pytest
from comun.consumidor import ConsumidorEventos, EventoInvalido
from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import COLA_NEGOCIACION
from negociacion.eventos import aplicar, atendedor
from negociacion.modelos import EventoProcesado, Proveedor, Servicio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.rabbitmq import RabbitMqContainer

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]

PROVEEDOR = {
    "id": "00000000-0000-4000-8000-000000000001",
    "rfc": "NNO010101AB1",
    "nombre": "Nube Norte S.A. de C.V.",
    "tamano": "mediana",
    "categorias": ["nube"],
    "contacto_nombre": "Lucía Pérez",
    "contacto_email": "lucia@nubenorte.example",
    "activo": True,
}
SERVICIO = {
    "id": "00000000-0000-4000-8000-000000000101",
    "codigo": "NUBE-VM-STD",
    "nombre": "Máquina virtual estándar",
    "categoria": "nube",
    "unidad": "vcpu_mes",
    "moneda": "MXN",
    "activo": True,
}


def _sobre(tipo: str, payload: Any, event_id: str | None = None) -> dict[str, Any]:
    return {"event_id": event_id or str(uuid.uuid4()), "type": tipo, "payload": payload}


async def _contar(fabrica: Fabrica, modelo: type[Any]) -> int:
    async with fabrica() as bd:
        return int(await bd.scalar(select(func.count()).select_from(modelo)) or 0)


async def test_cada_evento_actualiza_la_copia(fabrica: Fabrica) -> None:
    async with fabrica() as bd, bd.begin():
        assert await aplicar(bd, _sobre("proveedor.actualizado", PROVEEDOR))
        assert await aplicar(bd, _sobre("servicio.actualizado", SERVICIO))
        assert await aplicar(
            bd, _sobre("proveedor.actualizado", PROVEEDOR | {"contacto_email": "nuevo@x.example"})
        )
    async with fabrica() as bd:
        proveedor = await bd.get(Proveedor, uuid.UUID(PROVEEDOR["id"]))
        servicio = await bd.scalar(select(Servicio).where(Servicio.codigo == "NUBE-VM-STD"))
    assert proveedor is not None
    assert proveedor.contacto_email == "nuevo@x.example"
    assert proveedor.categorias == ["nube"]
    assert servicio is not None
    assert (servicio.moneda, servicio.unidad) == ("MXN", "vcpu_mes")


async def test_un_evento_repetido_no_se_aplica_dos_veces(fabrica: Fabrica) -> None:
    async with fabrica() as bd, bd.begin():
        assert await aplicar(bd, _sobre("proveedor.actualizado", PROVEEDOR, "e-1"))
        assert not await aplicar(
            bd, _sobre("proveedor.actualizado", PROVEEDOR | {"nombre": "Otro"}, "e-1")
        )
    async with fabrica() as bd:
        proveedor = await bd.get(Proveedor, uuid.UUID(PROVEEDOR["id"]))
    assert proveedor is not None and proveedor.nombre == "Nube Norte S.A. de C.V."


async def test_un_tipo_que_no_le_importa_solo_se_anota(fabrica: Fabrica) -> None:
    async with fabrica() as bd, bd.begin():
        assert await aplicar(bd, _sobre("contrato.registrado", {"id": "x"}))
    assert await _contar(fabrica, EventoProcesado) == 1


async def test_un_evento_mal_formado_es_invalido_y_no_deja_rastro(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    with pytest.raises(EventoInvalido):
        await atender(_sobre("proveedor.actualizado", {"id": PROVEEDOR["id"]}))
    with pytest.raises(ValueError):
        await atender(_sobre("servicio.actualizado", SERVICIO | {"id": "no-es-uuid"}))
    assert await _contar(fabrica, EventoProcesado) == 0


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


async def test_consume_los_eventos_de_su_cola(fabrica: Fabrica, url_rabbitmq: str) -> None:
    consumidor = ConsumidorEventos(url_rabbitmq, COLA_NEGOCIACION, atendedor(fabrica))
    tarea = asyncio.create_task(consumidor.ejecutar())
    try:
        for _ in range(200):
            if consumidor.conectado():
                break
            await asyncio.sleep(0.05)
        conexion = await aio_pika.connect_robust(url_rabbitmq)
        async with conexion:
            canal = await conexion.channel()
            exchange = await canal.declare_exchange(
                EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
            )
            for tipo, payload in (
                ("proveedor.actualizado", PROVEEDOR),
                ("servicio.actualizado", SERVICIO),
            ):
                await exchange.publish(
                    aio_pika.Message(json.dumps(_sobre(tipo, payload)).encode()),
                    routing_key=tipo,
                )
        for _ in range(200):
            if await _contar(fabrica, Servicio) and await _contar(fabrica, Proveedor):
                break
            await asyncio.sleep(0.05)
        assert await _contar(fabrica, Proveedor) == 1
        assert await _contar(fabrica, Servicio) == 1
    finally:
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea
        await consumidor.cerrar()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest services/negociacion -q`
Expected: FAIL. La colección da `ModuleNotFoundError: No module named 'negociacion'`.

- [ ] **Step 3: Write the package, the models, the migration and the app**

`services/negociacion/pyproject.toml`:

```toml
[project]
name = "negociacion"
version = "0.1.0"
description = "Eventos de negociación, sesiones con proveedores, motor de concesiones y portal"
requires-python = ">=3.13"
dependencies = [
    "comun",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "aio-pika>=9.5",
    "httpx>=0.28",
    "tzdata>=2024.1",  # base IANA para ZoneInfo en Windows e imágenes slim
]

[tool.uv.sources]
comun = { workspace = true }

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

`services/negociacion/Dockerfile`:

```dockerfile
# Contexto de construcción: la raíz del repositorio (ver infra/docker-compose.yml).
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app
# --locked valida uv.lock contra todos los miembros del workspace, así que se copia el repo
# completo (lo pesado queda fuera por .dockerignore).
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package negociacion

ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 servicio
USER servicio
EXPOSE 8000

# ponytail: migra al arrancar; con varias réplicas, mover a un job de migración previo al despliegue.
CMD ["sh", "-c", "alembic -c services/negociacion/alembic.ini upgrade head && exec env -u DATABASE_URL_MIGRACIONES uvicorn negociacion.main:crear_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
```

`services/negociacion/alembic.ini`:

```ini
[alembic]
script_location = %(here)s/alembic
```

`services/negociacion/alembic/env.py` es el de `inteligencia`, cambiando solo las tres importaciones:

```python
import asyncio

from alembic import context
from negociacion import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from negociacion.config import Configuracion
from negociacion.db import Base
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

Copie la plantilla de revisiones:

```bash
cp services/inteligencia/alembic/script.py.mako services/negociacion/alembic/script.py.mako
```

`services/negociacion/src/negociacion/config.py`:

```python
from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "negociacion"
    # Usuario de la aplicación: nunca cambia ni borra la bitácora, los mensajes ni las ofertas.
    database_url: str = (
        "postgresql+asyncpg://negociacion:negociacion@localhost:5432/negociacion_db"
    )
    # Dueño del esquema: solo para correr las migraciones.
    database_url_migraciones: str = (
        "postgresql+asyncpg://negociacion_dueno:negociacion_dueno@localhost:5432/negociacion_db"
    )
    # Las pruebas lo apagan: no hay RabbitMQ en ellas.
    usar_rabbitmq: bool = True
```

`services/negociacion/src/negociacion/db.py`:

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

`services/negociacion/src/negociacion/modelos.py`:

```python
"""Tablas de negociacion: eventos, sesiones, mensajes, ofertas, bitácora y copias locales.

Los estados se guardan en minúsculas (`borrador`, `acuerdo_tentativo`…). Los mensajes y las
ofertas se ordenan por `secuencia` (de la secuencia `orden`): dos registros del mismo turno
comparten la hora, pero nunca la secuencia.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from comun.outbox import ColumnasOutbox
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from negociacion.db import Base

DINERO = Numeric(14, 4)
UTILIDAD = Numeric(6, 4)
SIGUIENTE_ORDEN = text("nextval('orden')")

ESTADOS_EVENTO = ("borrador", "abierto", "en_evaluacion", "cancelado")
ESTADOS_SESION = (
    "invitada",
    "activa",
    "acuerdo_tentativo",
    "sin_acuerdo",
    "expirada",
    "escalada",
)
FINALES = ("acuerdo_tentativo", "sin_acuerdo", "expirada")
CLAVES_PALANCA = (
    "precio",
    "plazo_meses",
    "plazo_pago_dias",
    "sla_disponibilidad",
    "tope_aumento_pct",
    "cuota_implementacion",
)


def _ahora() -> datetime:
    return datetime.now(UTC)


def _en(columna: str, valores: tuple[str, ...]) -> str:
    return f"{columna} IN ({', '.join(repr(v) for v in valores)})"


class Evento(Base):
    __tablename__ = "evento"
    __table_args__ = (
        CheckConstraint(_en("tipo", ("compra", "renovacion")), name="tipo"),
        CheckConstraint(_en("estado", ESTADOS_EVENTO), name="estado"),
        CheckConstraint(_en("estilo", ("firme", "balanceado", "flexible")), name="estilo"),
        CheckConstraint("rondas_max BETWEEN 2 AND 12", name="rondas"),
        CheckConstraint("plazo_meses BETWEEN 1 AND 60", name="plazo"),
        Index("ix_evento_estado", "estado"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    folio: Mapped[str] = mapped_column(String(20), unique=True)
    tipo: Mapped[str] = mapped_column(String(12))
    titulo: Mapped[str] = mapped_column(String(120))
    moneda: Mapped[str] = mapped_column(String(3))
    plazo_meses: Mapped[int]
    estado: Mapped[str] = mapped_column(String(15), default="borrador")
    fecha_limite: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rondas_max: Mapped[int] = mapped_column(default=6)
    estilo: Mapped[str] = mapped_column(String(10), default="balanceado")
    contrato_origen_id: Mapped[uuid.UUID | None]
    proveedor_vigente_id: Mapped[uuid.UUID | None]
    # Los proveedores elegidos en el borrador; las sesiones se crean al publicar.
    invitados: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    # La fecha de la foto y, en renovación, los términos vigentes del contrato.
    foto: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(500))
    creado_por_id: Mapped[str] = mapped_column(String(64))
    creado_por_nombre: Mapped[str] = mapped_column(String(200))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)


class Linea(Base):
    __tablename__ = "linea"
    __table_args__ = (
        UniqueConstraint("evento_id", "orden"),
        CheckConstraint("cantidad > 0", name="cantidad"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evento.id"))
    orden: Mapped[int]
    codigo_servicio: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(200))
    unidad: Mapped[str] = mapped_column(String(20))
    cantidad: Mapped[Decimal] = mapped_column(DINERO)
    precio_vigente: Mapped[Decimal | None] = mapped_column(DINERO)
    ideal: Mapped[Decimal | None] = mapped_column(DINERO)
    limite: Mapped[Decimal | None] = mapped_column(DINERO)
    # La parte de la foto de esta línea: P25/P50/P75 de inteligencia o None si no hay referencia.
    referencia: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Palanca(Base):
    """Una fila por palanca activa; la del precio no lleva ideal ni límite (van por línea)."""

    __tablename__ = "palanca"
    __table_args__ = (
        CheckConstraint(_en("clave", CLAVES_PALANCA), name="clave"),
        CheckConstraint("peso BETWEEN 0 AND 100", name="peso"),
    )

    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evento.id"), primary_key=True)
    clave: Mapped[str] = mapped_column(String(30), primary_key=True)
    peso: Mapped[int]
    ideal: Mapped[Decimal | None] = mapped_column(DINERO)
    limite: Mapped[Decimal | None] = mapped_column(DINERO)


class SesionNegociacion(Base):
    """La negociación con un proveedor; su token de invitación solo se guarda como SHA-256."""

    __tablename__ = "sesion"
    __table_args__ = (
        UniqueConstraint("evento_id", "proveedor_id"),
        CheckConstraint(_en("estado", ESTADOS_SESION), name="estado"),
        CheckConstraint(_en("modo", ("agente", "comprador")), name="modo"),
        CheckConstraint(
            _en("correo_estado", ("pendiente", "enviado", "fallido")), name="correo_estado"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evento.id"))
    proveedor_id: Mapped[uuid.UUID]
    proveedor_nombre: Mapped[str] = mapped_column(String(200))
    destinatario: Mapped[str] = mapped_column(String(254))
    estado: Mapped[str] = mapped_column(String(20), default="invitada")
    modo: Mapped[str] = mapped_column(String(10), default="agente")
    ronda: Mapped[int] = mapped_column(default=0)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    correo_estado: Mapped[str] = mapped_column(String(10), default="pendiente")
    correo_error: Mapped[str | None] = mapped_column(String(500))
    correo_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fuera_de_limites: Mapped[bool] = mapped_column(default=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Oferta(Base):
    """Solo inserción: una oferta del proveedor, una contraoferta del agente o del comprador."""

    __tablename__ = "oferta"
    __table_args__ = (
        CheckConstraint(_en("autor", ("proveedor", "agente", "comprador")), name="autor"),
        CheckConstraint(_en("origen", ("formulario", "texto")), name="origen"),
        Index("ix_oferta_sesion_id_secuencia", "sesion_id", "secuencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sesion.id"))
    secuencia: Mapped[int] = mapped_column(BigInteger, server_default=SIGUIENTE_ORDEN)
    autor: Mapped[str] = mapped_column(String(10))
    ronda: Mapped[int]
    # {"precios": {id de línea: "30.80"}, "palancas": {clave: "45"}}
    valores: Mapped[dict[str, Any]] = mapped_column(JSONB)
    utilidad: Mapped[Decimal] = mapped_column(UTILIDAD)
    valida: Mapped[bool]
    origen: Mapped[str] = mapped_column(String(12), default="formulario")
    fuera_de_limites_confirmada: Mapped[bool] = mapped_column(default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Mensaje(Base):
    """Solo inserción. Una clave de idempotencia repetida en la misma sesión choca."""

    __tablename__ = "mensaje"
    __table_args__ = (
        UniqueConstraint("sesion_id", "clave_idempotencia"),
        CheckConstraint(
            _en("autor", ("proveedor", "agente", "comprador", "sistema")), name="autor"
        ),
        Index("ix_mensaje_sesion_id_secuencia", "sesion_id", "secuencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sesion.id"))
    secuencia: Mapped[int] = mapped_column(BigInteger, server_default=SIGUIENTE_ORDEN)
    autor: Mapped[str] = mapped_column(String(10))
    texto: Mapped[str] = mapped_column(Text)
    ronda: Mapped[int]
    oferta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("oferta.id"))
    clave_idempotencia: Mapped[str | None] = mapped_column(String(64))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Bitacora(Base):
    """Solo inserción: el usuario de la aplicación no tiene UPDATE ni DELETE (spec §12)."""

    __tablename__ = "bitacora"
    __table_args__ = (
        CheckConstraint(
            _en("actor_tipo", ("comprador", "proveedor", "agente", "sistema")), name="actor_tipo"
        ),
        Index("ix_bitacora_evento_id", "evento_id"),
        Index("ix_bitacora_sesion_id", "sesion_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    actor_tipo: Mapped[str] = mapped_column(String(10))
    actor_id: Mapped[str | None] = mapped_column(String(64))
    actor_nombre: Mapped[str] = mapped_column(String(200))
    accion: Mapped[str] = mapped_column(String(60))
    evento_id: Mapped[uuid.UUID | None]
    sesion_id: Mapped[uuid.UUID | None]
    detalle: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Proveedor(Base):
    """Copia local, alimentada por proveedor.actualizado."""

    __tablename__ = "proveedor"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    categorias: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    contacto_nombre: Mapped[str] = mapped_column(String(120))
    contacto_email: Mapped[str] = mapped_column(String(254))
    activo: Mapped[bool]
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Servicio(Base):
    """Copia local del catálogo, alimentada por servicio.actualizado."""

    __tablename__ = "servicio"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(20))
    unidad: Mapped[str] = mapped_column(String(20))
    moneda: Mapped[str] = mapped_column(String(3))
    activo: Mapped[bool]


class EventoProcesado(Base):
    """Idempotencia: un evento repetido choca con su event_id y no se aplica dos veces."""

    __tablename__ = "evento_procesado"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100))
    procesado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Outbox(ColumnasOutbox, Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_pendientes", "ocurrido_en", postgresql_where=text("publicado_en IS NULL")),
    )
```

`services/negociacion/alembic/versions/0001_esquema_inicial.py`:

```python
"""Esquema inicial de negociacion: eventos, sesiones, historial, bitácora, copias y outbox.

Revision ID: 0001
Revises:
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDEN = sa.text("nextval('orden')")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE folio_evento")
    op.execute("CREATE SEQUENCE orden")
    op.create_table(
        "proveedor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("categorias", postgresql.ARRAY(sa.String(20)), nullable=False),
        sa.Column("contacto_nombre", sa.String(120), nullable=False),
        sa.Column("contacto_email", sa.String(254), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proveedor")),
    )
    op.create_table(
        "servicio",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_servicio")),
        sa.UniqueConstraint("codigo", name=op.f("uq_servicio_codigo")),
    )
    op.create_table(
        "evento",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("folio", sa.String(20), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("titulo", sa.String(120), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("plazo_meses", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("fecha_limite", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rondas_max", sa.Integer(), nullable=False),
        sa.Column("estilo", sa.String(10), nullable=False),
        sa.Column("contrato_origen_id", sa.Uuid(), nullable=True),
        sa.Column("proveedor_vigente_id", sa.Uuid(), nullable=True),
        sa.Column("invitados", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("foto", postgresql.JSONB(), nullable=False),
        sa.Column("motivo_cancelacion", sa.String(500), nullable=True),
        sa.Column("creado_por_id", sa.String(64), nullable=False),
        sa.Column("creado_por_nombre", sa.String(200), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cerrado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("tipo IN ('compra', 'renovacion')", name=op.f("ck_evento_tipo")),
        sa.CheckConstraint(
            "estado IN ('borrador', 'abierto', 'en_evaluacion', 'cancelado')",
            name=op.f("ck_evento_estado"),
        ),
        sa.CheckConstraint(
            "estilo IN ('firme', 'balanceado', 'flexible')", name=op.f("ck_evento_estilo")
        ),
        sa.CheckConstraint("rondas_max BETWEEN 2 AND 12", name=op.f("ck_evento_rondas")),
        sa.CheckConstraint("plazo_meses BETWEEN 1 AND 60", name=op.f("ck_evento_plazo")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evento")),
        sa.UniqueConstraint("folio", name=op.f("uq_evento_folio")),
    )
    op.create_index("ix_evento_estado", "evento", ["estado"])
    op.create_table(
        "linea",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evento_id", sa.Uuid(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("codigo_servicio", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=False),
        sa.Column("precio_vigente", sa.Numeric(14, 4), nullable=True),
        sa.Column("ideal", sa.Numeric(14, 4), nullable=True),
        sa.Column("limite", sa.Numeric(14, 4), nullable=True),
        sa.Column("referencia", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint("cantidad > 0", name=op.f("ck_linea_cantidad")),
        sa.ForeignKeyConstraint(
            ["evento_id"], ["evento.id"], name=op.f("fk_linea_evento_id_evento")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_linea")),
        sa.UniqueConstraint("evento_id", "orden", name=op.f("uq_linea_evento_id_orden")),
    )
    op.create_table(
        "palanca",
        sa.Column("evento_id", sa.Uuid(), nullable=False),
        sa.Column("clave", sa.String(30), nullable=False),
        sa.Column("peso", sa.Integer(), nullable=False),
        sa.Column("ideal", sa.Numeric(14, 4), nullable=True),
        sa.Column("limite", sa.Numeric(14, 4), nullable=True),
        sa.CheckConstraint(
            "clave IN ('precio', 'plazo_meses', 'plazo_pago_dias', 'sla_disponibilidad', "
            "'tope_aumento_pct', 'cuota_implementacion')",
            name=op.f("ck_palanca_clave"),
        ),
        sa.CheckConstraint("peso BETWEEN 0 AND 100", name=op.f("ck_palanca_peso")),
        sa.ForeignKeyConstraint(
            ["evento_id"], ["evento.id"], name=op.f("fk_palanca_evento_id_evento")
        ),
        sa.PrimaryKeyConstraint("evento_id", "clave", name=op.f("pk_palanca")),
    )
    op.create_table(
        "sesion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evento_id", sa.Uuid(), nullable=False),
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("proveedor_nombre", sa.String(200), nullable=False),
        sa.Column("destinatario", sa.String(254), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("modo", sa.String(10), nullable=False),
        sa.Column("ronda", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("correo_estado", sa.String(10), nullable=False),
        sa.Column("correo_error", sa.String(500), nullable=True),
        sa.Column("correo_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fuera_de_limites", sa.Boolean(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "estado IN ('invitada', 'activa', 'acuerdo_tentativo', 'sin_acuerdo', 'expirada', "
            "'escalada')",
            name=op.f("ck_sesion_estado"),
        ),
        sa.CheckConstraint("modo IN ('agente', 'comprador')", name=op.f("ck_sesion_modo")),
        sa.CheckConstraint(
            "correo_estado IN ('pendiente', 'enviado', 'fallido')",
            name=op.f("ck_sesion_correo_estado"),
        ),
        sa.ForeignKeyConstraint(
            ["evento_id"], ["evento.id"], name=op.f("fk_sesion_evento_id_evento")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sesion")),
        sa.UniqueConstraint(
            "evento_id", "proveedor_id", name=op.f("uq_sesion_evento_id_proveedor_id")
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sesion_token_hash")),
    )
    op.create_table(
        "oferta",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sesion_id", sa.Uuid(), nullable=False),
        sa.Column("secuencia", sa.BigInteger(), server_default=ORDEN, nullable=False),
        sa.Column("autor", sa.String(10), nullable=False),
        sa.Column("ronda", sa.Integer(), nullable=False),
        sa.Column("valores", postgresql.JSONB(), nullable=False),
        sa.Column("utilidad", sa.Numeric(6, 4), nullable=False),
        sa.Column("valida", sa.Boolean(), nullable=False),
        sa.Column("origen", sa.String(12), nullable=False),
        sa.Column("fuera_de_limites_confirmada", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "autor IN ('proveedor', 'agente', 'comprador')", name=op.f("ck_oferta_autor")
        ),
        sa.CheckConstraint("origen IN ('formulario', 'texto')", name=op.f("ck_oferta_origen")),
        sa.ForeignKeyConstraint(
            ["sesion_id"], ["sesion.id"], name=op.f("fk_oferta_sesion_id_sesion")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oferta")),
    )
    op.create_index("ix_oferta_sesion_id_secuencia", "oferta", ["sesion_id", "secuencia"])
    op.create_table(
        "mensaje",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sesion_id", sa.Uuid(), nullable=False),
        sa.Column("secuencia", sa.BigInteger(), server_default=ORDEN, nullable=False),
        sa.Column("autor", sa.String(10), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("ronda", sa.Integer(), nullable=False),
        sa.Column("oferta_id", sa.Uuid(), nullable=True),
        sa.Column("clave_idempotencia", sa.String(64), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "autor IN ('proveedor', 'agente', 'comprador', 'sistema')",
            name=op.f("ck_mensaje_autor"),
        ),
        sa.ForeignKeyConstraint(
            ["sesion_id"], ["sesion.id"], name=op.f("fk_mensaje_sesion_id_sesion")
        ),
        sa.ForeignKeyConstraint(
            ["oferta_id"], ["oferta.id"], name=op.f("fk_mensaje_oferta_id_oferta")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mensaje")),
        sa.UniqueConstraint(
            "sesion_id",
            "clave_idempotencia",
            name=op.f("uq_mensaje_sesion_id_clave_idempotencia"),
        ),
    )
    op.create_index("ix_mensaje_sesion_id_secuencia", "mensaje", ["sesion_id", "secuencia"])
    op.create_table(
        "bitacora",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_tipo", sa.String(10), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("actor_nombre", sa.String(200), nullable=False),
        sa.Column("accion", sa.String(60), nullable=False),
        sa.Column("evento_id", sa.Uuid(), nullable=True),
        sa.Column("sesion_id", sa.Uuid(), nullable=True),
        sa.Column("detalle", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "actor_tipo IN ('comprador', 'proveedor', 'agente', 'sistema')",
            name=op.f("ck_bitacora_actor_tipo"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bitacora")),
    )
    op.create_index("ix_bitacora_evento_id", "bitacora", ["evento_id"])
    op.create_index("ix_bitacora_sesion_id", "bitacora", ["sesion_id"])
    op.create_table(
        "evento_procesado",
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_evento_procesado")),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("ocurrido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
    )
    op.create_index(
        "ix_outbox_pendientes",
        "outbox",
        ["ocurrido_en"],
        postgresql_where=sa.text("publicado_en IS NULL"),
    )

    # El rol "negociacion" (usuario de la aplicación) lo crea infra/postgres/negociacion.sh.
    # El historial (bitácora, mensajes y ofertas) es de solo inserción; el borrador reemplaza sus
    # líneas y palancas, y por eso solo ahí hay DELETE.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON evento, sesion, proveedor, servicio, outbox "
        "TO negociacion"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON linea, palanca TO negociacion")
    op.execute("GRANT SELECT, INSERT ON mensaje, oferta, bitacora, evento_procesado TO negociacion")
    op.execute("GRANT USAGE ON SEQUENCE folio_evento, orden TO negociacion")


def downgrade() -> None:
    op.drop_index("ix_outbox_pendientes", table_name="outbox")
    op.drop_table("outbox")
    op.drop_table("evento_procesado")
    op.drop_index("ix_bitacora_sesion_id", table_name="bitacora")
    op.drop_index("ix_bitacora_evento_id", table_name="bitacora")
    op.drop_table("bitacora")
    op.drop_index("ix_mensaje_sesion_id_secuencia", table_name="mensaje")
    op.drop_table("mensaje")
    op.drop_index("ix_oferta_sesion_id_secuencia", table_name="oferta")
    op.drop_table("oferta")
    op.drop_table("sesion")
    op.drop_table("palanca")
    op.drop_table("linea")
    op.drop_index("ix_evento_estado", table_name="evento")
    op.drop_table("evento")
    op.drop_table("servicio")
    op.drop_table("proveedor")
    op.execute("DROP SEQUENCE orden")
    op.execute("DROP SEQUENCE folio_evento")
```

`services/negociacion/src/negociacion/eventos.py`:

```python
"""Copias locales de proveedores y del catálogo, alimentadas por sus eventos.

Igual que en inteligencia: cada evento se aplica en una transacción que también registra su
event_id, así que uno repetido no se aplica dos veces.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from comun.consumidor import Atender, EventoInvalido
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from negociacion.modelos import EventoProcesado, Proveedor, Servicio


def _uuid(valor: Any) -> uuid.UUID:
    return uuid.UUID(str(valor))


async def _proveedor(bd: AsyncSession, p: dict[str, Any]) -> None:
    consulta = insert(Proveedor).values(
        id=_uuid(p["id"]),
        nombre=str(p["nombre"]),
        categorias=[str(c) for c in p["categorias"]],
        contacto_nombre=str(p["contacto_nombre"]),
        contacto_email=str(p["contacto_email"]),
        activo=bool(p["activo"]),
    )
    columnas = ("nombre", "categorias", "contacto_nombre", "contacto_email", "activo")
    await bd.execute(
        consulta.on_conflict_do_update(
            index_elements=[Proveedor.id],
            set_={c: consulta.excluded[c] for c in columnas}
            | {"actualizado_en": consulta.excluded.actualizado_en},
        )
    )


async def _servicio(bd: AsyncSession, p: dict[str, Any]) -> None:
    """La copia de la importación y la edición del catálogo traen los mismos datos del servicio."""
    consulta = insert(Servicio).values(
        id=_uuid(p["id"]),
        codigo=str(p["codigo"]),
        nombre=str(p["nombre"]),
        categoria=str(p["categoria"]),
        unidad=str(p["unidad"]),
        moneda=str(p["moneda"]),
        activo=bool(p["activo"]),
    )
    columnas = ("codigo", "nombre", "categoria", "unidad", "moneda", "activo")
    await bd.execute(
        consulta.on_conflict_do_update(
            index_elements=[Servicio.id], set_={c: consulta.excluded[c] for c in columnas}
        )
    )


APLICADORES: dict[str, Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]] = {
    "proveedor.actualizado": _proveedor,
    "servicio.actualizado": _servicio,
}


async def aplicar(bd: AsyncSession, sobre: dict[str, Any]) -> bool:
    """Aplica el evento en la transacción en curso; False si ese event_id ya se había aplicado."""
    tipo = str(sobre["type"])
    nuevo = await bd.scalar(
        insert(EventoProcesado)
        .values(event_id=str(sobre["event_id"]), tipo=tipo)
        .on_conflict_do_nothing(index_elements=[EventoProcesado.event_id])
        .returning(EventoProcesado.event_id)
    )
    if nuevo is None:
        return False
    aplicador = APLICADORES.get(tipo)
    if aplicador is not None:
        await aplicador(bd, sobre["payload"])
    return True


def atendedor(fabrica: async_sessionmaker[AsyncSession]) -> Atender:
    """La función que el consumidor común llama con cada sobre de evento."""

    async def atender(sobre: dict[str, Any]) -> None:
        try:
            async with fabrica() as bd, bd.begin():
                await aplicar(bd, sobre)
        # Un ValueError (UUID inválido) ya lo trata el consumidor como evento inválido.
        except (KeyError, TypeError, AttributeError) as exc:
            raise EventoInvalido(repr(exc)) from exc

    return atender
```

`services/negociacion/src/negociacion/main.py`:

```python
"""Aplicación FastAPI del servicio de negociación."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.consumidor import ConsumidorEventos
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.outbox import RelayOutbox
from comun.salud import crear_router_salud
from comun.topologia import COLA_NEGOCIACION
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from negociacion.config import Configuracion
from negociacion.eventos import atendedor
from negociacion.modelos import Outbox


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
    relay = RelayOutbox(sesiones, Outbox, config.rabbitmq_url)
    consumidor = ConsumidorEventos(config.rabbitmq_url, COLA_NEGOCIACION, atendedor(sesiones))

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        tareas: list[asyncio.Task[None]] = []
        if config.usar_rabbitmq:
            await relay.conectar()
            tareas.append(asyncio.create_task(relay.ejecutar()))
            tareas.append(asyncio.create_task(consumidor.ejecutar()))
        yield
        for tarea in tareas:
            tarea.cancel()
        for tarea in tareas:
            with contextlib.suppress(asyncio.CancelledError):
                await tarea
        if config.usar_rabbitmq:
            await consumidor.cerrar()
            await relay.cerrar()

    app = FastAPI(
        title="Servicio de negociación",
        version="0.1.0",
        root_path=config.root_path,
        lifespan=ciclo_de_vida,
    )
    app.state.fabrica = sesiones
    app.state.config = config
    app.state.validador = validador or validador_desde_jwks(
        config.oidc_issuer, config.oidc_audience, config.oidc_jwks_url
    )
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    async def verificar_postgres() -> None:
        async with sesiones() as bd:
            await bd.execute(text("SELECT 1"))

    app.include_router(crear_router_salud({"postgres": verificar_postgres}))
    return app
```

En el `pyproject.toml` de la raíz:
1. Agregue `"negociacion",` al grupo `dev` (después de `"inteligencia",`).
2. Agregue `negociacion = { workspace = true }` en `[tool.uv.sources]`.
3. Agregue `"negociacion"` a `source` de `[tool.coverage.run]` y a `packages` de `[tool.mypy]`.

Después actualice el lock y el entorno:

```bash
uv lock
uv sync --all-packages
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest services/negociacion -q`
Expected: PASS (todas, con Docker).

Run: `uv run ruff format --check . && uv run ruff check . && uv run mypy`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add services/negociacion pyproject.toml uv.lock
git commit -m "feat(negociacion): esqueleto del servicio, modelo de datos y copias locales" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 3: Dominio: términos, utilidad y precisión

**Files:**
- Create: `services/negociacion/src/negociacion/dominio/__init__.py` (vacío)
- Create: `services/negociacion/src/negociacion/dominio/terminos.py`
- Test: `services/negociacion/tests/test_terminos.py`

**Interfaces:**
- Consumes: `negociacion.modelos.CLAVES_PALANCA` (Task 2), solo en la prueba.
- Produces (`negociacion.dominio.terminos`):
  - **Constantes:** `CLAVES`, `PALANCAS` (las que no son precio), `PRECISION: dict[str, Decimal]`, `RANGOS: dict[str, tuple[Decimal, Decimal]]`.
  - **Tipos:** `Rango(ideal, limite)` con `.menos_es_mejor`, `.utilidad(v) -> float`, `.valido(v) -> bool` y `.acotar(v) -> Decimal`; `Linea(id: str, nombre: str, cantidad: Decimal, rango: Rango, referencia: Decimal | None = None)`; `Palanca(clave: str, peso: int, rango: Rango)`; `Terminos(peso_precio: int, lineas: tuple[Linea, ...], palancas: tuple[Palanca, ...] = ())`; `Valores(precios: Mapping[str, Decimal], palancas: Mapping[str, Decimal])` con `.a_json()` y `Valores.de_json(d)`.
  - **Funciones:** `redondear(clave, valor, modo=ROUND_HALF_UP) -> Decimal`, `problema_de_valor(clave, valor) -> str | None`, `transformar(terminos, valores, f)`, `combinar(terminos, a, b, f)`, `ideales(terminos) -> Valores`, `fuera_de_limite(terminos, valores) -> list[str]`, `es_valida(terminos, valores) -> bool`, `utilidades(terminos, valores) -> dict[str, float]` y `utilidad(terminos, valores) -> float`.

- [ ] **Step 1: Write the failing test**

`services/negociacion/tests/test_terminos.py`:

```python
from decimal import Decimal as D

import pytest
from hypothesis import given
from hypothesis import strategies as st
from negociacion.dominio.terminos import (
    CLAVES,
    Linea,
    Palanca,
    Rango,
    Terminos,
    Valores,
    es_valida,
    fuera_de_limite,
    problema_de_valor,
    redondear,
    utilidad,
    utilidades,
)
from negociacion.modelos import CLAVES_PALANCA

TERMINOS = Terminos(
    peso_precio=70,
    lineas=(
        Linea("a", "Licencias", D(100), Rango(D(10), D(20))),
        Linea("b", "Soporte", D(10), Rango(D(100), D(200))),
    ),
    palancas=(Palanca("plazo_pago_dias", 30, Rango(D(60), D(30))),),
)


def test_las_claves_coinciden_con_la_tabla() -> None:
    assert set(CLAVES) == set(CLAVES_PALANCA)


def test_la_utilidad_va_del_limite_al_ideal_en_ambas_direcciones() -> None:
    precio = Rango(D(30), D(35))  # menos es mejor
    assert precio.menos_es_mejor
    assert precio.utilidad(D(30)) == 1.0
    assert precio.utilidad(D(35)) == 0.0
    assert precio.utilidad(D("32.5")) == pytest.approx(0.5)
    assert precio.utilidad(D(28)) == 1.0  # mejor que el ideal
    assert precio.utilidad(D(40)) == 0.0
    assert precio.valido(D(35)) and not precio.valido(D("35.01"))
    assert precio.acotar(D(40)) == D(35) and precio.acotar(D(31)) == D(31)
    pago = Rango(D(60), D(30))  # más días es mejor para el comprador
    assert not pago.menos_es_mejor
    assert pago.utilidad(D(45)) == pytest.approx(0.5)
    assert pago.valido(D(30)) and not pago.valido(D(29))


def test_un_rango_sin_direccion_es_invalido() -> None:
    with pytest.raises(ValueError, match="distintos"):
        Rango(D(30), D("30.00"))


def test_el_precio_pondera_cada_linea_por_cantidad_por_limite() -> None:
    # Pesos de las líneas: a = 100 × 20 = 2,000 y b = 10 × 200 = 2,000: mitad y mitad.
    valores = Valores({"a": D(10), "b": D(200)}, {"plazo_pago_dias": D(60)})
    assert utilidades(TERMINOS, valores) == {"a": 1.0, "b": 0.0, "plazo_pago_dias": 1.0}
    assert utilidad(TERMINOS, valores) == pytest.approx(0.7 * 0.5 + 0.3 * 1.0)


def test_una_oferta_con_un_valor_mas_alla_del_limite_es_invalida() -> None:
    buena = Valores({"a": D(20), "b": D(200)}, {"plazo_pago_dias": D(30)})
    assert es_valida(TERMINOS, buena)
    cara = Valores({"a": D("20.01"), "b": D(200)}, {"plazo_pago_dias": D(29)})
    assert not es_valida(TERMINOS, cara)
    assert fuera_de_limite(TERMINOS, cara) == ["a", "plazo_pago_dias"]


@pytest.mark.parametrize(
    ("clave", "valor", "esperado"),
    [
        ("precio", D("30.125"), D("30.13")),
        ("plazo_meses", D("12.5"), D(13)),
        ("plazo_pago_dias", D("29.4"), D(29)),
        ("sla_disponibilidad", D("99.954"), D("99.95")),
        ("tope_aumento_pct", D("5.25"), D("5.3")),
        ("cuota_implementacion", D("0.005"), D("0.01")),
    ],
)
def test_redondea_a_la_precision_de_cada_termino(clave: str, valor: D, esperado: D) -> None:
    assert redondear(clave, valor) == esperado


@pytest.mark.parametrize(
    ("clave", "valor", "mensaje"),
    [
        ("precio", D(0), "Debe ser mayor que 0."),
        ("precio", D("30.123"), "Use como máximo 2 decimales."),
        ("precio", D("0.001"), "Use como máximo 2 decimales."),
        ("precio", D(20_000_000), "Debe ser como máximo 10,000,000."),
        ("plazo_meses", D(61), "Debe estar entre 1 y 60."),
        ("plazo_meses", D("12.5"), "Use un número entero."),
        ("plazo_pago_dias", D(-1), "Debe estar entre 0 y 180."),
        ("sla_disponibilidad", D("100.5"), "Debe estar entre 0 y 100."),
        ("tope_aumento_pct", D("5.25"), "Use como máximo 1 decimal."),
        ("cuota_implementacion", D(-1), "No puede ser negativo."),
        ("precio", D("30.10"), None),
        ("plazo_meses", D("12.0"), None),
        ("cuota_implementacion", D(0), None),
    ],
)
def test_problema_de_valor(clave: str, valor: D, mensaje: str | None) -> None:
    assert problema_de_valor(clave, valor) == mensaje


def test_valores_ida_y_vuelta_en_json() -> None:
    valores = Valores({"a": D("30.80")}, {"plazo_meses": D(12)})
    assert valores.a_json() == {"precios": {"a": "30.80"}, "palancas": {"plazo_meses": "12"}}
    assert Valores.de_json(valores.a_json()) == valores


@given(st.integers(1, 10**6), st.integers(1, 10**6), st.integers(0, 2 * 10**6))
def test_la_utilidad_siempre_esta_entre_0_y_1(ideal: int, limite: int, valor: int) -> None:
    if ideal == limite:
        return
    rango = Rango(D(ideal) / 100, D(limite) / 100)
    assert 0.0 <= rango.utilidad(D(valor) / 100) <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest services/negociacion/tests/test_terminos.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'negociacion.dominio'`.

- [ ] **Step 3: Write minimal implementation**

`services/negociacion/src/negociacion/dominio/terminos.py`:

```python
"""Términos de una oferta, su utilidad para el comprador y su precisión (spec §6.1 y §6.4).

Cada término (el precio de una línea o una palanca) va del ideal del comprador, que vale 1, a su
límite, que vale 0. La dirección sale de esos dos valores: si el ideal es menor que el límite,
menos es mejor. Un valor más allá del límite hace inválida la oferta completa.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

CLAVES = (
    "precio",
    "plazo_meses",
    "plazo_pago_dias",
    "sla_disponibilidad",
    "tope_aumento_pct",
    "cuota_implementacion",
)
PALANCAS = CLAVES[1:]  # las que no son el precio

CENTAVO = Decimal("0.01")
PRECISION: dict[str, Decimal] = {
    "precio": CENTAVO,
    "plazo_meses": Decimal(1),
    "plazo_pago_dias": Decimal(1),
    "sla_disponibilidad": CENTAVO,
    "tope_aumento_pct": Decimal("0.1"),
    "cuota_implementacion": CENTAVO,
}
MENSAJE_PRECISION: dict[str, str] = {
    "precio": "Use como máximo 2 decimales.",
    "plazo_meses": "Use un número entero.",
    "plazo_pago_dias": "Use un número entero.",
    "sla_disponibilidad": "Use como máximo 2 decimales.",
    "tope_aumento_pct": "Use como máximo 1 decimal.",
    "cuota_implementacion": "Use como máximo 2 decimales.",
}
MAXIMO_MONTO = Decimal(10_000_000)
# El precio además debe ser mayor que 0 (lo revisa problema_de_valor).
RANGOS: dict[str, tuple[Decimal, Decimal]] = {
    "precio": (Decimal(0), MAXIMO_MONTO),
    "plazo_meses": (Decimal(1), Decimal(60)),
    "plazo_pago_dias": (Decimal(0), Decimal(180)),
    "sla_disponibilidad": (Decimal(0), Decimal(100)),
    "tope_aumento_pct": (Decimal(0), Decimal(100)),
    "cuota_implementacion": (Decimal(0), MAXIMO_MONTO),
}


def redondear(clave: str, valor: Decimal, modo: str = ROUND_HALF_UP) -> Decimal:
    return valor.quantize(PRECISION[clave], rounding=modo)


def problema_de_valor(clave: str, valor: Decimal) -> str | None:
    """Por qué no se acepta un valor para ese término (rango o precisión); None si se acepta."""
    minimo, maximo = RANGOS[clave]
    if clave == "precio" and valor <= 0:
        return "Debe ser mayor que 0."
    if clave == "cuota_implementacion" and valor < 0:
        return "No puede ser negativo."
    if valor > maximo and maximo == MAXIMO_MONTO:
        return f"Debe ser como máximo {maximo:,}."
    if not minimo <= valor <= maximo:
        return f"Debe estar entre {minimo} y {maximo}."
    if valor != redondear(clave, valor):
        return MENSAJE_PRECISION[clave]
    return None


@dataclass(frozen=True)
class Rango:
    ideal: Decimal
    limite: Decimal

    def __post_init__(self) -> None:
        if self.ideal == self.limite:
            raise ValueError("El ideal y el límite deben ser distintos")

    @property
    def menos_es_mejor(self) -> bool:
        return self.ideal < self.limite

    def utilidad(self, valor: Decimal) -> float:
        return min(1.0, max(0.0, float((self.limite - valor) / (self.limite - self.ideal))))

    def valido(self, valor: Decimal) -> bool:
        return valor <= self.limite if self.menos_es_mejor else valor >= self.limite

    def acotar(self, valor: Decimal) -> Decimal:
        """El valor, llevado al límite si lo cruzaba."""
        return valor if self.valido(valor) else self.limite


@dataclass(frozen=True)
class Linea:
    id: str
    nombre: str
    cantidad: Decimal
    rango: Rango
    referencia: Decimal | None = None  # P50 de la foto; sin referencia, la cordura usa el límite


@dataclass(frozen=True)
class Palanca:
    clave: str
    peso: int
    rango: Rango


@dataclass(frozen=True)
class Terminos:
    peso_precio: int
    lineas: tuple[Linea, ...]
    palancas: tuple[Palanca, ...] = ()


@dataclass(frozen=True)
class Valores:
    """Los términos de una oferta: precio unitario por línea (por id) y valor por palanca."""

    precios: Mapping[str, Decimal]
    palancas: Mapping[str, Decimal]

    def a_json(self) -> dict[str, dict[str, str]]:
        return {
            "precios": {linea: str(valor) for linea, valor in self.precios.items()},
            "palancas": {clave: str(valor) for clave, valor in self.palancas.items()},
        }

    @classmethod
    def de_json(cls, datos: Mapping[str, Any]) -> "Valores":
        return cls(
            precios={str(k): Decimal(str(v)) for k, v in datos["precios"].items()},
            palancas={str(k): Decimal(str(v)) for k, v in datos["palancas"].items()},
        )


def transformar(
    terminos: Terminos, valores: Valores, f: Callable[[str, Rango, Decimal], Decimal]
) -> Valores:
    """Aplica f(clave, rango, valor) a cada término."""
    return Valores(
        precios={
            linea.id: f("precio", linea.rango, valores.precios[linea.id])
            for linea in terminos.lineas
        },
        palancas={
            p.clave: f(p.clave, p.rango, valores.palancas[p.clave]) for p in terminos.palancas
        },
    )


def combinar(
    terminos: Terminos,
    a: Valores,
    b: Valores,
    f: Callable[[str, Rango, Decimal, Decimal], Decimal],
) -> Valores:
    """Aplica f(clave, rango, valor de a, valor de b) a cada término."""
    return Valores(
        precios={
            linea.id: f("precio", linea.rango, a.precios[linea.id], b.precios[linea.id])
            for linea in terminos.lineas
        },
        palancas={
            p.clave: f(p.clave, p.rango, a.palancas[p.clave], b.palancas[p.clave])
            for p in terminos.palancas
        },
    )


def ideales(terminos: Terminos) -> Valores:
    return Valores(
        {linea.id: linea.rango.ideal for linea in terminos.lineas},
        {p.clave: p.rango.ideal for p in terminos.palancas},
    )


def fuera_de_limite(terminos: Terminos, valores: Valores) -> list[str]:
    """Las líneas (por id) y las palancas (por clave) que cruzan su límite."""
    return [
        linea.id for linea in terminos.lineas if not linea.rango.valido(valores.precios[linea.id])
    ] + [p.clave for p in terminos.palancas if not p.rango.valido(valores.palancas[p.clave])]


def es_valida(terminos: Terminos, valores: Valores) -> bool:
    return not fuera_de_limite(terminos, valores)


def utilidades(terminos: Terminos, valores: Valores) -> dict[str, float]:
    """La utilidad de cada término: por id de línea y por clave de palanca."""
    return {
        linea.id: linea.rango.utilidad(valores.precios[linea.id]) for linea in terminos.lineas
    } | {p.clave: p.rango.utilidad(valores.palancas[p.clave]) for p in terminos.palancas}


def utilidad(terminos: Terminos, valores: Valores) -> float:
    """U = Σ wᵢ·uᵢ; el precio reparte su peso entre las líneas según cantidad × límite."""
    u = utilidades(terminos, valores)
    total = sum(linea.cantidad * linea.rango.limite for linea in terminos.lineas)
    u_precio = sum(
        float(linea.cantidad * linea.rango.limite / total) * u[linea.id]
        for linea in terminos.lineas
    )
    return (
        terminos.peso_precio * u_precio + sum(p.peso * u[p.clave] for p in terminos.palancas)
    ) / 100
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest services/negociacion/tests/test_terminos.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/negociacion/src/negociacion/dominio services/negociacion/tests/test_terminos.py
git commit -m "feat(negociacion): términos de la oferta, utilidad y precisión" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Dominio: motor de concesiones

**Files:**
- Create: `services/negociacion/src/negociacion/dominio/motor.py`
- Test: `services/negociacion/tests/test_motor.py`

**Interfaces:**
- Consumes: todo `negociacion.dominio.terminos` (Task 3).
- Produces (`negociacion.dominio.motor`):
  - **Constantes:** `VERSION_MOTOR = 1`, `BETA = {"firme": 0.3, "balanceado": 0.6, "flexible": 1.0}`, `CORDURA`.
  - **Estado:** `Estado(ronda: int, rondas: int, beta: float, anterior: Valores | None = None, hay_mejor_oferta: bool = False)`.
  - **Decisión:** `Decision(accion, contraoferta: Valores | None, dudosas: tuple[str, ...], ultima_ronda: bool, traza: dict[str, Any])`, con `accion` en `"aceptar" | "contraofertar" | "pedir_aclaracion" | "cerrar_sin_acuerdo"`.
  - **Funciones:** `u_objetivo(t, rondas, beta) -> float`, `curva(clave, rango, u_obj) -> Decimal`, `dudosas(terminos, oferta) -> tuple[str, ...]`, `contraoferta(terminos, oferta, estado) -> tuple[Valores, dict[str, Any]]` y `decidir(terminos, estado, oferta, confirmar_valores=False) -> Decision`.
  - **Claves de la traza:** `version_motor`, `t`, `T`, `beta`, `u`, `utilidad_oferta`, `valida`, `hay_mejor_oferta`, `accion`. Con contraoferta calculada, además `u_objetivo`, `objetivo`, `tramo` (`"acotada" | "acotada_a_propia" | "propia_a_ideal"`), `paso`, `de_curva`, `redondeo` (`"ninguno" | "cercano" | "hacia_proveedor"`), `utilidad_contraoferta`. En `contraofertar`, también `contraoferta` (JSON). En `pedir_aclaracion`, `dudosas`.

- [ ] **Step 1: Write the failing test**

`services/negociacion/tests/test_motor.py`:

```python
from decimal import Decimal as D

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from negociacion.dominio.motor import BETA, Estado, contraoferta, curva, decidir, u_objetivo
from negociacion.dominio.terminos import (
    PALANCAS,
    PRECISION,
    RANGOS,
    Linea,
    Palanca,
    Rango,
    Terminos,
    Valores,
    es_valida,
    redondear,
    utilidad,
)

# El ejemplo del PRD §3.3: una línea, ideal 30, límite 35, T = 6, β = 0.6.
PRD = Terminos(peso_precio=100, lineas=(Linea("l", "Licencia", D(10), Rango(D(30), D(35))),))


def _oferta(precio: str) -> Valores:
    return Valores({"l": D(precio)}, {})


def test_el_ejemplo_del_prd() -> None:
    anterior: Valores | None = None
    obtenidas: dict[int, D] = {}
    for t in range(1, 7):
        propuesta, _ = contraoferta(PRD, _oferta("40.00"), Estado(t, 6, 0.6, anterior))
        obtenidas[t] = propuesta.precios["l"]
        anterior = propuesta
    assert [obtenidas[t] for t in (2, 4, 5, 6)] == [D("30.80"), D("32.54"), D("33.69"), D("35.00")]


def test_u_objetivo_baja_de_1_a_0() -> None:
    assert u_objetivo(0, 6, 0.6) == 1.0
    assert u_objetivo(6, 6, 0.6) == 0.0
    assert u_objetivo(9, 6, 0.6) == 0.0  # más allá de T se trata como T
    assert u_objetivo(2, 6, 0.6) == pytest.approx(0.8398, abs=1e-4)


def test_con_una_oferta_fuera_de_limite_no_contesta_con_el_limite() -> None:
    propuesta, traza = contraoferta(PRD, _oferta("40.00"), Estado(1, 6, 0.6))
    assert D(30) < propuesta.precios["l"] < D(35)
    assert traza["de_curva"] == ["l"]


def test_acepta_una_oferta_valida_mejor_que_su_contraoferta() -> None:
    decision = decidir(PRD, Estado(4, 6, 0.6), _oferta("32.00"))
    assert decision.accion == "aceptar"
    assert decision.contraoferta is None


def test_contraoferta_una_oferta_valida_pero_cara() -> None:
    decision = decidir(PRD, Estado(1, 6, 0.6), _oferta("34.00"))
    assert decision.accion == "contraofertar"
    assert decision.contraoferta is not None
    assert decision.contraoferta.precios["l"] < D("34.00")


def test_acepta_cuando_el_proveedor_reenvia_la_propuesta_anterior() -> None:
    propuesta, _ = contraoferta(PRD, _oferta("40.00"), Estado(2, 6, 0.6))
    assert decidir(PRD, Estado(3, 6, 0.6, anterior=propuesta), propuesta).accion == "aceptar"


def test_en_la_ultima_ronda_acepta_lo_valido_y_cierra_lo_demas() -> None:
    assert decidir(PRD, Estado(6, 6, 0.6), _oferta("35.00")).accion == "aceptar"
    assert decidir(PRD, Estado(6, 6, 0.6), _oferta("35.01")).accion == "cerrar_sin_acuerdo"


def test_avisa_cuando_la_siguiente_es_la_ultima_ronda() -> None:
    assert decidir(PRD, Estado(5, 6, 0.6), _oferta("40.00")).ultima_ronda
    assert not decidir(PRD, Estado(4, 6, 0.6), _oferta("40.00")).ultima_ronda


def test_pide_aclaracion_ante_un_precio_fuera_de_lo_usual() -> None:
    con_referencia = Terminos(
        100, (Linea("l", "Licencia", D(10), Rango(D(30), D(35)), referencia=D(33)),)
    )
    decision = decidir(con_referencia, Estado(1, 6, 0.6), _oferta("3300.00"))
    assert decision.accion == "pedir_aclaracion"
    assert decision.dudosas == ("l",)
    confirmada = decidir(con_referencia, Estado(1, 6, 0.6), _oferta("3300.00"), True)
    assert confirmada.accion == "contraofertar"
    # Sin referencia, la cordura se mide contra el límite (0.1 × 35 = 3.50).
    assert decidir(PRD, Estado(1, 6, 0.6), _oferta("3.40")).accion == "pedir_aclaracion"


def test_una_palanca_fuera_de_limite_usa_la_curva_propia() -> None:
    terminos = Terminos(80, PRD.lineas, (Palanca("plazo_pago_dias", 20, Rango(D(60), D(30))),))
    oferta = Valores({"l": D("31.00")}, {"plazo_pago_dias": D(15)})
    propuesta, traza = contraoferta(terminos, oferta, Estado(1, 6, 0.6))
    assert D(30) < propuesta.palancas["plazo_pago_dias"] <= D(60)
    assert traza["de_curva"] == ["plazo_pago_dias"]


def test_la_curva_llega_al_limite_solo_en_la_ultima_ronda() -> None:
    rango = Rango(D(30), D(35))
    assert curva("precio", rango, u_objetivo(5, 6, 0.6)) < D(35)
    assert curva("precio", rango, u_objetivo(6, 6, 0.6)) == D(35)


def test_la_traza_explica_la_decision() -> None:
    traza = decidir(PRD, Estado(2, 6, 0.6), _oferta("40.00")).traza
    assert traza["accion"] == "contraofertar"
    assert {
        "version_motor",
        "t",
        "T",
        "beta",
        "u",
        "utilidad_oferta",
        "valida",
        "hay_mejor_oferta",
        "u_objetivo",
        "objetivo",
        "tramo",
        "paso",
        "de_curva",
        "redondeo",
        "utilidad_contraoferta",
        "contraoferta",
    } <= set(traza)


# Propiedades (spec §6.7) sobre configuraciones y ofertas al azar, en la precisión de cada término.
def _en_rejilla(clave: str) -> st.SearchStrategy[D]:
    paso = PRECISION[clave]
    minimo, maximo = RANGOS[clave]
    if clave in ("precio", "cuota_implementacion"):
        minimo, maximo = (paso if clave == "precio" else minimo), D(100_000)
    return st.integers(int(minimo / paso), int(maximo / paso)).map(lambda n: D(n) * paso)


@st.composite
def _rango(draw: st.DrawFn, clave: str) -> Rango:
    ideal = draw(_en_rejilla(clave))
    limite = draw(_en_rejilla(clave).filter(lambda valor: valor != ideal))
    return Rango(ideal, limite)


@st.composite
def _escenario(draw: st.DrawFn) -> tuple[Terminos, int, float, list[Valores]]:
    lineas = tuple(
        Linea(f"l{i}", f"Línea {i}", D(draw(st.integers(1, 500))), draw(_rango("precio")))
        for i in range(draw(st.integers(1, 3)))
    )
    claves = draw(st.lists(st.sampled_from(PALANCAS), unique=True, max_size=3))
    palancas = tuple(Palanca(c, draw(st.integers(1, 30)), draw(_rango(c))) for c in claves)
    terminos = Terminos(100 - sum(p.peso for p in palancas), lineas, palancas)
    rondas = draw(st.integers(2, 12))
    beta = draw(st.sampled_from(sorted(BETA.values())))
    ofertas = [
        Valores(
            {linea.id: draw(_en_rejilla("precio")) for linea in lineas},
            {p.clave: draw(_en_rejilla(p.clave)) for p in palancas},
        )
        for _ in range(rondas)
    ]
    return terminos, rondas, beta, ofertas


@settings(max_examples=200, deadline=None)
@given(_escenario())
def test_propiedades_del_motor(escenario: tuple[Terminos, int, float, list[Valores]]) -> None:
    terminos, rondas, beta, ofertas = escenario
    anterior: Valores | None = None
    for t, oferta in enumerate(ofertas, start=1):
        decision = decidir(terminos, Estado(t, rondas, beta, anterior), oferta, True)
        if decision.accion == "aceptar":
            assert es_valida(terminos, oferta)  # nunca acepta una oferta inválida
            assert utilidad(terminos, oferta) >= decision.traza["utilidad_contraoferta"]
            return
        if decision.accion == "cerrar_sin_acuerdo":
            assert t >= rondas  # solo cierra en la ronda T
            assert not es_valida(terminos, oferta)
            return
        assert decision.accion == "contraofertar"
        assert t < rondas  # en la ronda T nunca contraoferta
        propuesta = decision.contraoferta
        assert propuesta is not None
        assert es_valida(terminos, propuesta)  # nunca fuera de los límites
        assert not (es_valida(terminos, oferta) and utilidad(terminos, oferta) >= utilidad(terminos, propuesta))
        for linea in terminos.lineas:  # todo valor en su precisión
            assert propuesta.precios[linea.id] == redondear("precio", propuesta.precios[linea.id])
        for p in terminos.palancas:
            assert propuesta.palancas[p.clave] == redondear(p.clave, propuesta.palancas[p.clave])
        if anterior is not None and decision.traza["tramo"] != "acotada":
            # No retrocede, salvo cuando la oferta acotada ya supera el objetivo (spec §6.7).
            assert utilidad(terminos, propuesta) <= utilidad(terminos, anterior) + 1e-9
        anterior = propuesta
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest services/negociacion/tests/test_motor.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'negociacion.dominio.motor'`.

- [ ] **Step 3: Write minimal implementation**

`services/negociacion/src/negociacion/dominio/motor.py`:

```python
"""Motor de concesiones (spec §6): decide cómo responde el agente a una oferta del proveedor.

Es puro: no lee la base ni la red. La capa de servicio arma los términos y el estado, llama a
`decidir` y guarda la decisión con su traza en la bitácora.
"""

from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any, Literal

from negociacion.dominio.terminos import (
    Rango,
    Terminos,
    Valores,
    combinar,
    es_valida,
    fuera_de_limite,
    ideales,
    redondear,
    transformar,
    utilidad,
    utilidades,
)

VERSION_MOTOR = 1  # sube con cada cambio de comportamiento; queda en cada traza
BETA = {"firme": 0.3, "balanceado": 0.6, "flexible": 1.0}
ITERACIONES = 60  # bisección sobre un camino de largo 2: sobra para centavos
TOLERANCIA = 1e-9  # ruido de punto flotante al comparar utilidades
CORDURA = (Decimal("0.1"), Decimal(10))  # spec §6.3: fuera de 0.1× a 10× se pide aclaración

Accion = Literal["aceptar", "contraofertar", "pedir_aclaracion", "cerrar_sin_acuerdo"]


@dataclass(frozen=True)
class Estado:
    ronda: int  # t: el número de esta oferta del proveedor, desde 1
    rondas: int  # T: las rondas máximas del evento
    beta: float
    anterior: Valores | None = None  # la última contraoferta de la sesión, del agente o del comprador
    hay_mejor_oferta: bool = False


@dataclass(frozen=True)
class Decision:
    accion: Accion
    contraoferta: Valores | None = None
    dudosas: tuple[str, ...] = ()  # líneas con un precio fuera de lo usual
    ultima_ronda: bool = False  # la siguiente oferta del proveedor será la última
    traza: dict[str, Any] = field(default_factory=dict)


def u_objetivo(t: int, rondas: int, beta: float) -> float:
    """U_obj(t) = 1 − (t/T)^(1/β); más allá de T vale lo mismo que en T."""
    return 1.0 - (min(t, rondas) / rondas) ** (1.0 / beta)


def curva(clave: str, rango: Rango, u_obj: float) -> Decimal:
    """Lo que el agente pide por su cuenta en un término: llega al límite solo con U_obj = 0."""
    valor = rango.ideal + Decimal(repr(1.0 - u_obj)) * (rango.limite - rango.ideal)
    return redondear(clave, valor)


def dudosas(terminos: Terminos, oferta: Valores) -> tuple[str, ...]:
    """Las líneas con un precio fuera de 0.1× a 10× de su referencia (o de su límite, sin ella)."""
    minimo, maximo = CORDURA
    fuera: list[str] = []
    for linea in terminos.lineas:
        base = linea.referencia if linea.referencia is not None else linea.rango.limite
        if not base * minimo <= oferta.precios[linea.id] <= base * maximo:
            fuera.append(linea.id)
    return tuple(fuera)


def _interpolar(terminos: Terminos, a: Valores, b: Valores, fraccion: float) -> Valores:
    f = Decimal(repr(fraccion))
    return combinar(terminos, a, b, lambda _c, _r, x, y: x + f * (y - x))


def contraoferta(
    terminos: Terminos, oferta: Valores, estado: Estado
) -> tuple[Valores, dict[str, Any]]:
    """La contraoferta de la ronda (spec §6.4) y su parte de la traza.

    El camino va de la oferta acotada a los límites (s′), a la oferta con la curva propia del
    agente en lo que cruzaba un límite (s̃), y de ahí al ideal (I). La utilidad no baja a lo
    largo del camino, así que la bisección encuentra el punto con U = objetivo.
    """
    u_obj = u_objetivo(estado.ronda, estado.rondas, estado.beta)
    u_anterior = None if estado.anterior is None else utilidad(terminos, estado.anterior)
    objetivo = u_obj if u_anterior is None else min(u_obj, u_anterior)
    acotada = transformar(terminos, oferta, lambda _c, r, v: r.acotar(v))
    propia = transformar(
        terminos, oferta, lambda c, r, v: v if r.valido(v) else curva(c, r, u_obj)
    )
    ideal = ideales(terminos)

    def punto(paso: float) -> Valores:
        if paso <= 1:
            return _interpolar(terminos, acotada, propia, paso)
        return _interpolar(terminos, propia, ideal, paso - 1)

    if utilidad(terminos, acotada) >= objetivo:
        paso, resultado = 0.0, acotada
    else:
        bajo, alto = 0.0, 2.0
        for _ in range(ITERACIONES):
            medio = (bajo + alto) / 2
            if utilidad(terminos, punto(medio)) >= objetivo:
                alto = medio
            else:
                bajo = medio
        paso, resultado = alto, punto(alto)

    redondeo = "ninguno"  # s′ ya está en la precisión de cada término
    if paso > 0:
        sin_redondear = resultado
        redondeo = "cercano"
        resultado = transformar(terminos, sin_redondear, lambda c, _r, v: redondear(c, v))
        if u_anterior is not None and utilidad(terminos, resultado) > u_anterior + TOLERANCIA:
            # Redondear hacia la oferta del proveedor concede menos de un centavo y nunca
            # retrocede; los extremos del camino ya están en la precisión, así que no cruza límites.
            redondeo = "hacia_proveedor"
            resultado = transformar(
                terminos,
                sin_redondear,
                lambda c, r, v: redondear(c, v, ROUND_CEILING if r.menos_es_mejor else ROUND_FLOOR),
            )
    if paso == 0:
        tramo = "acotada"
    elif paso <= 1:
        tramo = "acotada_a_propia"
    else:
        tramo = "propia_a_ideal"
    traza: dict[str, Any] = {
        "u_objetivo": u_obj,
        "objetivo": objetivo,
        "tramo": tramo,
        "paso": paso,
        "de_curva": fuera_de_limite(terminos, oferta),
        "redondeo": redondeo,
        "utilidad_contraoferta": utilidad(terminos, resultado),
    }
    return resultado, traza


def decidir(
    terminos: Terminos, estado: Estado, oferta: Valores, confirmar_valores: bool = False
) -> Decision:
    """La respuesta del agente a la oferta `estado.ronda` del proveedor (spec §6.3)."""
    u_oferta = utilidad(terminos, oferta)
    valida = es_valida(terminos, oferta)
    base: dict[str, Any] = {
        "version_motor": VERSION_MOTOR,
        "t": estado.ronda,
        "T": estado.rondas,
        "beta": estado.beta,
        "u": utilidades(terminos, oferta),
        "utilidad_oferta": u_oferta,
        "valida": valida,
        "hay_mejor_oferta": estado.hay_mejor_oferta,
    }
    raras = () if confirmar_valores else dudosas(terminos, oferta)
    if raras:
        return Decision(
            "pedir_aclaracion",
            dudosas=raras,
            traza=base | {"accion": "pedir_aclaracion", "dudosas": list(raras)},
        )
    propuesta, parte = contraoferta(terminos, oferta, estado)
    traza = base | parte
    if valida and u_oferta >= utilidad(terminos, propuesta):
        return Decision("aceptar", traza=traza | {"accion": "aceptar"})
    if estado.ronda >= estado.rondas:
        return Decision("cerrar_sin_acuerdo", traza=traza | {"accion": "cerrar_sin_acuerdo"})
    return Decision(
        "contraofertar",
        contraoferta=propuesta,
        ultima_ronda=estado.ronda + 1 == estado.rondas,
        traza=traza | {"accion": "contraofertar", "contraoferta": propuesta.a_json()},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest services/negociacion/tests/test_motor.py -q`
Expected: PASS. Si `test_el_ejemplo_del_prd` falla por un centavo, revise que el redondeo sea al más cercano (`ROUND_HALF_UP`). La regla «hacia el proveedor» solo se usa cuando el redondeo al más cercano dejaría la utilidad por encima de la contraoferta anterior.

Run: `uv run pytest services/negociacion/tests/test_motor.py services/negociacion/tests/test_terminos.py --cov=negociacion.dominio --cov-report=term-missing -q`
Expected: cobertura de `negociacion/dominio` ≥ 80 % (spec §1).

- [ ] **Step 5: Commit**

```bash
git add services/negociacion/src/negociacion/dominio/motor.py services/negociacion/tests/test_motor.py
git commit -m "feat(negociacion): motor de concesiones con pruebas de propiedades" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Dominio: valores sugeridos y reglas para publicar

**Files:**
- Create: `services/negociacion/src/negociacion/dominio/configuracion.py`
- Test: `services/negociacion/tests/test_configuracion.py`

**Interfaces:**
- Consumes: `redondear` y `problema_de_valor` de `negociacion.dominio.terminos` (Task 3).
- Produces (`negociacion.dominio.configuracion`):
  - **Tipos:** `Banda(p25, p50, p75)`, `Problema(campo: str, mensaje: str)`, `LineaRevision(nombre, ideal, limite, precio_vigente=None, p75=None)`, `PalancaRevision(clave, peso, ideal=None, limite=None)`, `Revision(tipo, fecha_limite, lineas, palancas, invitados: int, tope_pct=None)`.
  - **Funciones:** `sugerir_precio(tipo, banda, vigente, tope_pct) -> tuple[Decimal | None, Decimal | None]`, `techo_renovacion(vigente, tope_pct) -> Decimal`, `errores(revision, ahora) -> list[Problema]` y `avisos(revision) -> list[Problema]`.
  - **Nombres de campo de los problemas:** `fecha_limite`, `proveedores`, `lineas.<i>.ideal`, `lineas.<i>.limite`, `palancas.<clave>.ideal`, `palancas.<clave>.limite`, `palancas.<clave>.peso` y `palancas`.

- [ ] **Step 1: Write the failing test**

`services/negociacion/tests/test_configuracion.py`:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest
from negociacion.dominio.configuracion import (
    Banda,
    LineaRevision,
    PalancaRevision,
    Problema,
    Revision,
    avisos,
    errores,
    sugerir_precio,
)

AHORA = datetime(2026, 10, 13, 15, tzinfo=UTC)
BANDA = Banda(D("28.1234"), D("31.5049"), D("36.0000"))


@pytest.mark.parametrize(
    ("tipo", "banda", "vigente", "tope", "esperado"),
    [
        ("compra", BANDA, None, None, (D("28.12"), D("31.50"))),
        ("compra", None, None, None, (None, None)),
        # Renovación: ideal = min(P25, vigente × 0.95); límite = min(P50, vigente × (1 + tope)).
        ("renovacion", BANDA, D("32.0000"), D("5.00"), (D("28.12"), D("31.50"))),
        ("renovacion", BANDA, D("25.0000"), None, (D("23.75"), D("25.00"))),
        ("renovacion", None, D("40.0000"), D("10.00"), (D("38.00"), D("44.00"))),
        # El techo se redondea hacia abajo para que la sugerencia nunca lo supere.
        ("renovacion", None, D("33.3333"), D("5.00"), (D("31.67"), D("34.99"))),
    ],
)
def test_sugiere_ideal_y_limite(
    tipo: str,
    banda: Banda | None,
    vigente: D | None,
    tope: D | None,
    esperado: tuple[D | None, D | None],
) -> None:
    assert sugerir_precio(tipo, banda, vigente, tope) == esperado


def _revision(**cambios: object) -> Revision:
    datos: dict[str, object] = {
        "tipo": "compra",
        "fecha_limite": AHORA + timedelta(days=7),
        "lineas": (LineaRevision("Licencias", D("28.00"), D("31.50"), p75=D("36.00")),),
        "palancas": (PalancaRevision("precio", 100),),
        "invitados": 2,
    }
    return Revision(**(datos | cambios))  # type: ignore[arg-type]


def test_una_configuracion_completa_no_tiene_errores() -> None:
    assert errores(_revision(), AHORA) == []
    assert avisos(_revision()) == []


@pytest.mark.parametrize(
    "fecha", [AHORA + timedelta(minutes=30), AHORA + timedelta(days=61), AHORA - timedelta(days=1)]
)
def test_la_fecha_limite_va_de_1_hora_a_60_dias(fecha: datetime) -> None:
    assert errores(_revision(fecha_limite=fecha), AHORA) == [
        Problema("fecha_limite", "La fecha límite debe estar entre 1 hora y 60 días a partir de ahora.")
    ]


def test_cada_linea_necesita_ideal_y_limite_distintos_y_en_centavos() -> None:
    lineas = (
        LineaRevision("Sin valores", None, None),
        LineaRevision("Iguales", D("30.00"), D("30.00")),
        LineaRevision("Milésimos", D("28.00"), D("31.505")),
    )
    assert errores(_revision(lineas=lineas, invitados=0), AHORA) == [
        Problema("proveedores", "Invite al menos a un proveedor."),
        Problema("lineas.0.ideal", "Indique el precio ideal."),
        Problema("lineas.0.limite", "Indique el precio límite."),
        Problema("lineas.1.limite", "El ideal y el límite deben ser distintos."),
        Problema("lineas.2.limite", "Use como máximo 2 decimales."),
    ]


def test_en_renovacion_el_limite_no_supera_el_vigente_mas_el_tope() -> None:
    lineas = (LineaRevision("Licencias", D("30.00"), D("33.61"), precio_vigente=D("32.0000")),)
    assert errores(_revision(tipo="renovacion", lineas=lineas, tope_pct=D("5.00")), AHORA) == [
        Problema(
            "lineas.0.limite",
            "En una renovación, el límite no puede superar $33.60 "
            "(el precio vigente más el tope de aumento).",
        )
    ]


def test_las_palancas_necesitan_valores_y_los_pesos_suman_100() -> None:
    palancas = (
        PalancaRevision("precio", 70),
        PalancaRevision("plazo_pago_dias", 30, None, D(30)),
        PalancaRevision("sla_disponibilidad", 0, D("99.9"), D("101")),
    )
    assert errores(_revision(palancas=palancas), AHORA) == [
        Problema("palancas.plazo_pago_dias.ideal", "Indique el valor ideal."),
        Problema("palancas.sla_disponibilidad.peso", "Cada palanca activa necesita un peso de al menos 1."),
        Problema("palancas.sla_disponibilidad.limite", "Debe estar entre 0 y 100."),
    ]
    sin_cien = (PalancaRevision("precio", 80), PalancaRevision("plazo_meses", 10, D(12), D(36)))
    assert errores(_revision(palancas=sin_cien), AHORA) == [
        Problema("palancas", "Los pesos deben sumar 100; ahora suman 90.")
    ]


def test_avisa_si_el_limite_queda_sobre_p75() -> None:
    lineas = (LineaRevision("Licencias", D("28.00"), D("37.00"), p75=D("36.00")),)
    assert avisos(_revision(lineas=lineas)) == [
        Problema(
            "lineas.0.limite",
            "El límite queda por encima del P75 del mercado ($36.00): pagaría más que en tres de "
            "cada cuatro contratos.",
        )
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest services/negociacion/tests/test_configuracion.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'negociacion.dominio.configuracion'`.

- [ ] **Step 3: Write minimal implementation**

`services/negociacion/src/negociacion/dominio/configuracion.py`:

```python
"""Valores sugeridos y reglas para publicar un evento (spec §5.2 y §5.3)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, Decimal

from negociacion.dominio.terminos import problema_de_valor, redondear

DESCUENTO_RENOVACION = Decimal("0.95")  # en renovación, el ideal pide al menos 5 % menos que hoy
VENTANA_FECHA_LIMITE = (timedelta(hours=1), timedelta(days=60))


@dataclass(frozen=True)
class Banda:
    p25: Decimal
    p50: Decimal
    p75: Decimal


@dataclass(frozen=True)
class Problema:
    campo: str
    mensaje: str


@dataclass(frozen=True)
class LineaRevision:
    nombre: str
    ideal: Decimal | None
    limite: Decimal | None
    precio_vigente: Decimal | None = None
    p75: Decimal | None = None


@dataclass(frozen=True)
class PalancaRevision:
    clave: str
    peso: int
    ideal: Decimal | None = None
    limite: Decimal | None = None


@dataclass(frozen=True)
class Revision:
    tipo: str
    fecha_limite: datetime
    lineas: tuple[LineaRevision, ...]
    palancas: tuple[PalancaRevision, ...]  # las activas, incluido el precio (sin ideal ni límite)
    invitados: int
    tope_pct: Decimal | None = None  # del contrato, en renovación


def techo_renovacion(vigente: Decimal, tope_pct: Decimal | None) -> Decimal:
    """El precio vigente más el tope de aumento; un contrato sin tope no admite aumento."""
    return vigente * (1 + (tope_pct or Decimal(0)) / 100)


def sugerir_precio(
    tipo: str, banda: Banda | None, vigente: Decimal | None, tope_pct: Decimal | None
) -> tuple[Decimal | None, Decimal | None]:
    """(ideal, límite) sugeridos para el precio de una línea; (None, None) sin datos."""
    if tipo == "renovacion" and vigente is not None:
        ideal = vigente * DESCUENTO_RENOVACION
        techo = techo_renovacion(vigente, tope_pct)
        if banda is not None:
            ideal, techo = min(banda.p25, ideal), min(banda.p50, techo)
        # El límite se redondea hacia abajo para no pasar nunca del techo de la renovación.
        return redondear("precio", ideal), redondear("precio", techo, ROUND_FLOOR)
    if banda is None:
        return None, None
    return redondear("precio", banda.p25), redondear("precio", banda.p50)


def _rango(
    campo: str, clave: str, ideal: Decimal | None, limite: Decimal | None, que: str
) -> list[Problema]:
    problemas: list[Problema] = []
    if ideal is None:
        problemas.append(Problema(f"{campo}.ideal", f"Indique {que} ideal."))
    if limite is None:
        problemas.append(Problema(f"{campo}.limite", f"Indique {que} límite."))
    for nombre, valor in (("ideal", ideal), ("limite", limite)):
        mensaje = None if valor is None else problema_de_valor(clave, valor)
        if mensaje is not None:
            problemas.append(Problema(f"{campo}.{nombre}", mensaje))
    if ideal is not None and limite is not None and ideal == limite:
        problemas.append(Problema(f"{campo}.limite", "El ideal y el límite deben ser distintos."))
    return problemas


def errores(revision: Revision, ahora: datetime) -> list[Problema]:
    """Lo que impide publicar; vacío si se puede."""
    problemas: list[Problema] = []
    minimo, maximo = VENTANA_FECHA_LIMITE
    if not ahora + minimo <= revision.fecha_limite <= ahora + maximo:
        problemas.append(
            Problema(
                "fecha_limite",
                "La fecha límite debe estar entre 1 hora y 60 días a partir de ahora.",
            )
        )
    if revision.invitados == 0:
        problemas.append(Problema("proveedores", "Invite al menos a un proveedor."))
    for i, linea in enumerate(revision.lineas):
        problemas += _rango(f"lineas.{i}", "precio", linea.ideal, linea.limite, "el precio")
        if (
            revision.tipo == "renovacion"
            and linea.precio_vigente is not None
            and linea.limite is not None
        ):
            techo = techo_renovacion(linea.precio_vigente, revision.tope_pct)
            if linea.limite > techo:
                problemas.append(
                    Problema(
                        f"lineas.{i}.limite",
                        "En una renovación, el límite no puede superar "
                        f"${redondear('precio', techo, ROUND_FLOOR):,.2f} "
                        "(el precio vigente más el tope de aumento).",
                    )
                )
    pesos = 0
    for palanca in revision.palancas:
        pesos += palanca.peso
        campo = f"palancas.{palanca.clave}"
        if palanca.peso < 1:
            problemas.append(
                Problema(f"{campo}.peso", "Cada palanca activa necesita un peso de al menos 1.")
            )
        if palanca.clave != "precio":
            problemas += _rango(campo, palanca.clave, palanca.ideal, palanca.limite, "el valor")
    if pesos != 100:
        problemas.append(Problema("palancas", f"Los pesos deben sumar 100; ahora suman {pesos}."))
    return problemas


def avisos(revision: Revision) -> list[Problema]:
    """Lo que conviene revisar pero no impide publicar."""
    return [
        Problema(
            f"lineas.{i}.limite",
            f"El límite queda por encima del P75 del mercado (${linea.p75:,.2f}): pagaría más que "
            "en tres de cada cuatro contratos.",
        )
        for i, linea in enumerate(revision.lineas)
        if linea.p75 is not None and linea.limite is not None and linea.limite > linea.p75
    ]
```

En `test_cada_linea_necesita…`, el orden esperado pone `proveedores` antes que las líneas porque `errores` revisa primero la fecha y los invitados.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest services/negociacion/tests/test_configuracion.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/negociacion/src/negociacion/dominio/configuracion.py services/negociacion/tests/test_configuracion.py
git commit -m "feat(negociacion): valores sugeridos y reglas para publicar una negociación" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: API: crear y consultar negociaciones

**Files:**
- Create: `services/negociacion/src/negociacion/errores.py`
- Create: `services/negociacion/src/negociacion/bitacora.py`
- Create: `services/negociacion/src/negociacion/textos.py`
- Create: `services/negociacion/src/negociacion/integraciones.py`
- Create: `services/negociacion/src/negociacion/consultas.py`
- Create: `services/negociacion/src/negociacion/api/__init__.py` (vacío)
- Create: `services/negociacion/src/negociacion/api/dependencias.py`
- Create: `services/negociacion/src/negociacion/api/esquemas.py`
- Create: `services/negociacion/src/negociacion/api/eventos.py`
- Modify: `services/negociacion/src/negociacion/config.py`, `services/negociacion/src/negociacion/main.py`
- Modify: `services/negociacion/tests/conftest.py` (se reemplaza completo)
- Modify: `libs/comun/src/comun/mensajes.py`
- Test: `services/negociacion/tests/test_api_eventos.py`, `services/negociacion/tests/test_api_permisos.py`, `libs/comun/tests/test_mensajes.py`

**Interfaces:**
- Consumes:
  - `sugerir_precio`, `Banda`, `Revision`, `LineaRevision`, `PalancaRevision`, `errores` y `avisos` (Task 5).
  - `CLAVES` (Task 3).
  - Los modelos de la Task 2.
- Produces:
  - **`negociacion.errores`:** `invalido(campo, mensaje, codigo)`, `invalidos(lista, codigo)`, `no_existe(detalle)`, `conflicto(detalle, codigo)` y `no_disponible()`. Todas devuelven `ErrorDominio`.
  - **`negociacion.bitacora`:**
    - `Actor(tipo, id, nombre)` con `.para_evento() -> {"id", "nombre"}`;
    - las constantes `AGENTE` y `SISTEMA`;
    - `de_usuario(usuario) -> Actor`;
    - `registrar(bd, accion, actor, *, evento_id=None, sesion_id=None, detalle=None, fecha=None)`.
  - **`negociacion.textos`:** `PALANCAS` y `nombre_y_unidad(clave, moneda) -> tuple[str, str]`.
  - **`negociacion.integraciones`:** `Integraciones(http, inteligencia_url, proveedores_url)` con `await .referencia(token, codigo, cantidad, plazo) -> dict | None` y `await .contrato(token, proveedor_id, contrato_id) -> ContratoVigente`. `ContratoVigente` expone `.plazo_meses`, `.terminos() -> dict` y `.lineas: tuple[LineaVigente, ...]`.
  - **`negociacion.consultas`:** `decimal_o_nada`, `banda_de`, `evento_o_404(bd, id, bloquear=False)`, `lineas_de`, `palancas_de`, `revision_de`, `evento_salida(bd, id, ahora) -> EventoSalida`, `servicios_activos(bd, codigos)` y `proveedores_invitables(bd, ids, campos=None)`.
  - **`negociacion.api.dependencias`:** `Bd`, `Lector`, `Comprador`, `TokenUsuario`, `Reloj` e `Integ`.
  - **Rutas:** `POST /eventos` (201) y `GET /eventos/{evento_id}`.
  - **`crear_app`:** agrega `transporte: httpx.AsyncBaseTransport | None = None` y `reloj: Callable[[], datetime] | None = None`, y guarda en `app.state` `reloj` e `integraciones`.
  - **Fixtures de `conftest.py`:** `AHORA`, `FECHA_LIMITE`, `externos` (`Externos`), `reloj` (`Reloj`), `catalogo`, `ids`, `cuerpo_compra(**cambios) -> dict` y `nueva_compra(**cambios) -> dict`.

- [ ] **Step 1: Write the failing tests**

En `libs/comun/tests/test_mensajes.py`, agregue al final:

```python
def test_traduce_los_errores_de_fecha_y_hora() -> None:
    zona = traducir_error(
        {"type": "timezone_aware", "loc": ("body", "fecha_limite"), "msg": "x", "input": "x"}
    )
    assert zona == "Incluya la zona horaria, por ejemplo 2026-10-20T18:00:00-06:00"
    formato = traducir_error(
        {"type": "datetime_from_date_parsing", "loc": ("body",), "msg": "x", "input": "x"}
    )
    assert formato == "Fecha y hora inválidas; use el formato 2026-10-20T18:00:00-06:00"
```

(Si el archivo no importa `traducir_error`, agregue `from comun.mensajes import traducir_error`.)

Reemplace `services/negociacion/tests/conftest.py` completo por:

```python
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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
AHORA = datetime(2026, 10, 13, 15, tzinfo=UTC)
FECHA_LIMITE = AHORA + timedelta(days=7)
Fabrica = async_sessionmaker[AsyncSession]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
Cuerpo = Callable[..., dict[str, Any]]
Compra = Callable[..., Awaitable[dict[str, Any]]]


def _id(numero: int) -> str:
    return f"00000000-0000-4000-8000-{numero:012d}"


IDS = {"nube_norte": _id(1), "datos_sur": _id(2), "inactivo": _id(3), "contrato": _id(901)}
SERVICIOS = [
    {
        "id": _id(101),
        "codigo": "SAAS-CRM-PRO",
        "nombre": "CRM profesional",
        "categoria": "licencia_saas",
        "unidad": "usuario_mes",
        "moneda": "USD",
        "activo": True,
    },
    {
        "id": _id(102),
        "codigo": "SAAS-CRM-BAS",
        "nombre": "CRM básico",
        "categoria": "licencia_saas",
        "unidad": "usuario_mes",
        "moneda": "USD",
        "activo": True,
    },
    {
        "id": _id(103),
        "codigo": "NUBE-VM-STD",
        "nombre": "Máquina virtual estándar",
        "categoria": "nube",
        "unidad": "vcpu_mes",
        "moneda": "MXN",
        "activo": True,
    },
    {
        "id": _id(104),
        "codigo": "SOP-VIEJO",
        "nombre": "Soporte descontinuado",
        "categoria": "soporte",
        "unidad": "ticket",
        "moneda": "MXN",
        "activo": False,
    },
]
PROVEEDORES = [
    {
        "id": IDS["nube_norte"],
        "rfc": "NNO010101AB1",
        "nombre": "Nube Norte S.A. de C.V.",
        "tamano": "mediana",
        "categorias": ["licencia_saas", "nube"],
        "contacto_nombre": "Lucía Pérez",
        "contacto_email": "lucia@nubenorte.example",
        "activo": True,
    },
    {
        "id": IDS["datos_sur"],
        "rfc": "DSU020202CD2",
        "nombre": "Datos del Sur S.A.",
        "tamano": "pequena",
        "categorias": ["licencia_saas"],
        "contacto_nombre": "Marco Ruiz",
        "contacto_email": "ventas@datossur.example",
        "activo": True,
    },
    {
        "id": IDS["inactivo"],
        "rfc": "INA030303EF3",
        "nombre": "Inactivo S.A.",
        "tamano": "micro",
        "categorias": ["soporte"],
        "contacto_nombre": "Nadie",
        "contacto_email": "nadie@inactivo.example",
        "activo": False,
    },
]
REFERENCIAS = {
    "SAAS-CRM-PRO": {
        "p25": "28.0000",
        "p50": "31.5000",
        "p75": "36.0000",
        "metodo": "linea_base",
        "version": None,
        "confianza": "normal",
        "observaciones": 57,
    },
    "SAAS-CRM-BAS": {
        "p25": "12.0000",
        "p50": "14.0000",
        "p75": "17.0000",
        "metodo": "modelo",
        "version": 2,
        "confianza": "baja",
        "observaciones": 9,
    },
}
CONTRATO = {
    "id": IDS["contrato"],
    "folio": "C-000901",
    "tipo": "nuevo",
    "fecha_inicio": "2025-11-01",
    "fecha_fin": "2026-10-31",
    "moneda": "USD",
    "plazo_pago_dias": 30,
    "sla_disponibilidad": "99.50",
    "tope_aumento_pct": "5.00",
    "cuota_implementacion": "0",
    "lineas": [
        {
            "codigo_servicio": "SAAS-CRM-PRO",
            "nombre_servicio": "CRM profesional",
            "unidad": "usuario_mes",
            "cantidad": "120.0000",
            "precio_unitario": "32.0000",
        }
    ],
}


@dataclass
class Externos:
    """Lo que responden inteligencia (host intel) y proveedores (host prov) en las pruebas."""

    referencias: dict[str, dict[str, Any]] = field(default_factory=lambda: dict(REFERENCIAS))
    contratos: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {IDS["nube_norte"]: [CONTRATO]}
    )
    caido: str | None = None  # host que no responde
    estado_intel: int | None = None  # fuerza esta respuesta de inteligencia
    cuerpo_intel: bytes = b""
    peticiones: list[httpx.Request] = field(default_factory=list)

    async def manejar(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        if peticion.url.host == self.caido:
            raise httpx.ConnectError("sin red", request=peticion)
        partes = peticion.url.path.strip("/").split("/")
        if peticion.url.host == "intel":
            if self.estado_intel is not None:
                return httpx.Response(self.estado_intel, content=self.cuerpo_intel)
            banda = self.referencias.get(partes[2])
            if banda is None:
                return httpx.Response(404, json={"codigo": "sin_observaciones"})
            return httpx.Response(200, json={"codigo": partes[2], **banda})
        if peticion.url.host == "prov":
            contratos = self.contratos.get(partes[1])
            if contratos is None:
                return httpx.Response(404, json={"title": "No encontrado"})
            return httpx.Response(200, json=contratos)
        return httpx.Response(500)


@dataclass
class Reloj:
    momento: datetime = AHORA

    def __call__(self) -> datetime:
        return self.momento


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
def externos() -> Externos:
    return Externos()


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def app(
    urls_bd: tuple[str, str],
    fabrica: Fabrica,
    claves: ClavesPrueba,
    externos: Externos,
    reloj: Reloj,
) -> FastAPI:
    return crear_app(
        Configuracion(
            database_url=urls_bd[1],
            usar_rabbitmq=False,
            inteligencia_url="http://intel",
            proveedores_url="http://prov",
        ),
        claves.validador(),
        fabrica,
        transporte=httpx.MockTransport(externos.manejar),
        reloj=reloj,
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


@pytest.fixture
def ids() -> dict[str, str]:
    return dict(IDS)


@pytest.fixture
async def catalogo(aplicar_evento: AplicarEvento) -> None:
    """Las copias locales de servicios y proveedores, como si hubieran llegado por eventos."""
    for servicio in SERVICIOS:
        await aplicar_evento("servicio.actualizado", servicio)
    for proveedor in PROVEEDORES:
        await aplicar_evento("proveedor.actualizado", proveedor)


@pytest.fixture
def cuerpo_compra(catalogo: None) -> Cuerpo:
    """El cuerpo de una compra lista para publicar; los cambios reemplazan sus campos."""

    def _cuerpo(**cambios: Any) -> dict[str, Any]:
        return {
            "tipo": "compra",
            "titulo": "Licencias de CRM 2027",
            "fecha_limite": FECHA_LIMITE.isoformat(),
            "lineas": [{"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "100"}],
            "proveedores": [IDS["nube_norte"], IDS["datos_sur"]],
        } | cambios

    return _cuerpo


@pytest.fixture
def nueva_compra(
    cliente: httpx.AsyncClient, comprador: dict[str, str], cuerpo_compra: Cuerpo
) -> Compra:
    """Crea una compra por la API y devuelve su respuesta."""

    async def _crear(**cambios: Any) -> dict[str, Any]:
        respuesta = await cliente.post("/eventos", json=cuerpo_compra(**cambios), headers=comprador)
        assert respuesta.status_code == 201, respuesta.text
        return dict(respuesta.json())

    return _crear
```

`services/negociacion/tests/test_api_eventos.py`:

```python
import uuid
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
from negociacion.modelos import Bitacora, Evento
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]
FECHA_LIMITE = "2026-10-20T15:00:00+00:00"


def _renovacion(ids: dict[str, str]) -> dict[str, Any]:
    return {
        "tipo": "renovacion",
        "titulo": "Renovación del CRM",
        "fecha_limite": FECHA_LIMITE,
        "proveedor_id": ids["nube_norte"],
        "contrato_id": ids["contrato"],
    }


async def test_crea_una_compra_con_los_valores_sugeridos(
    nueva_compra: Any, externos: Any, comprador: dict[str, str]
) -> None:
    evento = await nueva_compra(
        lineas=[
            {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "100"},
            {"codigo_servicio": "SAAS-CRM-BAS", "cantidad": "40"},
        ]
    )
    assert evento["folio"] == "NEG-2026-0001"
    assert (evento["estado"], evento["moneda"], evento["version"]) == ("borrador", "USD", 1)
    pro, bas = evento["lineas"]
    assert (D(pro["ideal"]), D(pro["limite"])) == (D("28.00"), D("31.50"))
    assert D(pro["referencia"]["p50"]) == D("31.5")
    assert (D(bas["ideal"]), D(bas["limite"])) == (D("12.00"), D("14.00"))
    assert [p["clave"] for p in evento["palancas"]] == [
        "precio",
        "plazo_meses",
        "plazo_pago_dias",
        "sla_disponibilidad",
        "tope_aumento_pct",
        "cuota_implementacion",
    ]
    precio = evento["palancas"][0]
    assert (precio["activa"], precio["peso"], precio["unidad"]) == (True, 100, "USD")
    assert not any(p["activa"] for p in evento["palancas"][1:])
    assert [i["nombre"] for i in evento["invitados"]] == [
        "Nube Norte S.A. de C.V.",
        "Datos del Sur S.A.",
    ]
    assert evento["errores"] == [] and evento["avisos"] == []
    # inteligencia recibió el token del comprador y el plazo del evento.
    primera = externos.peticiones[0]
    assert primera.headers["authorization"] == comprador["Authorization"]
    assert primera.url.path == "/precios/servicios/SAAS-CRM-PRO/referencia"
    assert (primera.url.params["cantidad"], primera.url.params["plazo"]) == ("100", "12")


async def test_una_linea_sin_referencia_queda_sin_sugerencia(nueva_compra: Any) -> None:
    evento = await nueva_compra(lineas=[{"codigo_servicio": "NUBE-VM-STD", "cantidad": "64"}])
    [linea] = evento["lineas"]
    assert linea["referencia"] is None
    assert (linea["ideal"], linea["limite"]) == (None, None)
    assert evento["moneda"] == "MXN"
    assert {e["campo"] for e in evento["errores"]} == {"lineas.0.ideal", "lineas.0.limite"}


async def test_crea_una_renovacion_desde_el_contrato_vigente(
    cliente: httpx.AsyncClient, comprador: dict[str, str], catalogo: None, ids: dict[str, str]
) -> None:
    respuesta = await cliente.post("/eventos", json=_renovacion(ids), headers=comprador)
    assert respuesta.status_code == 201, respuesta.text
    evento = respuesta.json()
    assert (evento["tipo"], evento["moneda"], evento["plazo_meses"]) == ("renovacion", "USD", 12)
    assert evento["contrato_origen_id"] == ids["contrato"]
    assert evento["proveedor_vigente_id"] == ids["nube_norte"]
    [linea] = evento["lineas"]
    assert D(linea["precio_vigente"]) == D(32)
    # ideal = min(P25 28, 32 × 0.95); límite = min(P50 31.50, 32 × 1.05).
    assert (D(linea["ideal"]), D(linea["limite"])) == (D("28.00"), D("31.50"))
    vigentes = {p["clave"]: p["vigente"] for p in evento["palancas"]}
    assert D(vigentes["plazo_pago_dias"]) == 30
    assert D(vigentes["tope_aumento_pct"]) == 5
    assert D(vigentes["plazo_meses"]) == 12
    assert [i["id"] for i in evento["invitados"]] == [ids["nube_norte"]]


async def test_una_renovacion_exige_un_contrato_vigente_del_proveedor(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    catalogo: None,
    ids: dict[str, str],
    externos: Any,
) -> None:
    contrato = externos.contratos[ids["nube_norte"]][0]
    externos.contratos[ids["nube_norte"]] = [contrato | {"fecha_fin": "2026-09-30"}]
    vencido = await cliente.post("/eventos", json=_renovacion(ids), headers=comprador)
    assert vencido.status_code == 422
    assert vencido.json()["codigo"] == "contrato_no_vigente"
    externos.contratos[ids["nube_norte"]] = []
    ajeno = await cliente.post("/eventos", json=_renovacion(ids), headers=comprador)
    assert ajeno.status_code == 422
    assert ajeno.json()["codigo"] == "contrato_inexistente"


@pytest.mark.parametrize("falla", ["caida", "error", "basura"])
async def test_si_inteligencia_falla_responde_503_sin_crear_nada(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    cuerpo_compra: Any,
    externos: Any,
    fabrica: Fabrica,
    falla: str,
) -> None:
    if falla == "caida":
        externos.caido = "intel"
    elif falla == "error":
        externos.estado_intel = 500
    else:
        externos.estado_intel, externos.cuerpo_intel = 200, b"<html>no es JSON</html>"
    respuesta = await cliente.post("/eventos", json=cuerpo_compra(), headers=comprador)
    assert respuesta.status_code == 503
    assert respuesta.json()["detail"] == (
        "No se pudo consultar la referencia de precios; intente de nuevo."
    )
    async with fabrica() as bd:
        assert await bd.scalar(select(func.count()).select_from(Evento)) == 0


async def test_valida_servicios_proveedores_y_moneda(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    cuerpo_compra: Any,
    ids: dict[str, str],
) -> None:
    sin_copia = "00000000-0000-4000-8000-000000000999"  # recién importado: aún no llega la copia
    casos = [
        (
            cuerpo_compra(lineas=[{"codigo_servicio": "NO-EXISTE", "cantidad": "1"}]),
            "lineas.0.codigo_servicio",
            "servicio_no_disponible",
        ),
        (
            cuerpo_compra(lineas=[{"codigo_servicio": "SOP-VIEJO", "cantidad": "1"}]),
            "lineas.0.codigo_servicio",
            "servicio_no_disponible",
        ),
        (
            cuerpo_compra(proveedores=[ids["nube_norte"], ids["inactivo"]]),
            "proveedores.1",
            "proveedor_no_disponible",
        ),
        (cuerpo_compra(proveedores=[sin_copia]), "proveedores.0", "proveedor_no_disponible"),
        (
            cuerpo_compra(
                lineas=[
                    {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "1"},
                    {"codigo_servicio": "NUBE-VM-STD", "cantidad": "1"},
                ]
            ),
            "lineas",
            "monedas_distintas",
        ),
    ]
    for cuerpo, campo, codigo in casos:
        respuesta = await cliente.post("/eventos", json=cuerpo, headers=comprador)
        assert respuesta.status_code == 422, respuesta.text
        assert respuesta.json()["codigo"] == codigo
        assert respuesta.json()["errores"][0]["campo"] == campo


async def test_la_fecha_limite_debe_traer_zona_horaria(
    cliente: httpx.AsyncClient, comprador: dict[str, str], cuerpo_compra: Any
) -> None:
    respuesta = await cliente.post(
        "/eventos", json=cuerpo_compra(fecha_limite="2026-10-20T18:00:00"), headers=comprador
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        {
            "campo": "body.fecha_limite",
            "mensaje": "Incluya la zona horaria, por ejemplo 2026-10-20T18:00:00-06:00",
        }
    ]


async def test_una_compra_necesita_lineas_y_proveedores_sin_repetir(
    cliente: httpx.AsyncClient, comprador: dict[str, str], cuerpo_compra: Any, ids: dict[str, str]
) -> None:
    sin_lineas = await cliente.post("/eventos", json=cuerpo_compra(lineas=[]), headers=comprador)
    assert sin_lineas.json()["errores"][0]["mensaje"] == "Una compra necesita al menos una línea."
    repetido = await cliente.post(
        "/eventos", json=cuerpo_compra(proveedores=[ids["nube_norte"]] * 2), headers=comprador
    )
    assert repetido.json()["errores"][0]["mensaje"] == "Un proveedor aparece dos veces."


async def test_los_folios_son_consecutivos(nueva_compra: Any) -> None:
    assert (await nueva_compra())["folio"] == "NEG-2026-0001"
    assert (await nueva_compra())["folio"] == "NEG-2026-0002"


async def test_el_aprobador_consulta_pero_no_crea(
    cliente: httpx.AsyncClient, aprobador: dict[str, str], cuerpo_compra: Any, nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    creado = await cliente.post("/eventos", json=cuerpo_compra(), headers=aprobador)
    assert creado.status_code == 403
    respuesta = await cliente.get(f"/eventos/{evento['id']}", headers=aprobador)
    assert respuesta.status_code == 200
    assert respuesta.json()["folio"] == evento["folio"]


async def test_una_negociacion_inexistente_da_404(
    cliente: httpx.AsyncClient, comprador: dict[str, str]
) -> None:
    respuesta = await cliente.get(f"/eventos/{uuid.uuid4()}", headers=comprador)
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "La negociación no existe."


async def test_la_bitacora_registra_quien_creo_la_negociacion(
    nueva_compra: Any, fabrica: Fabrica
) -> None:
    evento = await nueva_compra()
    async with fabrica() as bd:
        fila = await bd.scalar(
            select(Bitacora).where(Bitacora.evento_id == uuid.UUID(evento["id"]))
        )
    assert fila is not None
    assert (fila.accion, fila.actor_tipo, fila.actor_id) == (
        "evento.creado",
        "comprador",
        "comprador-1",
    )
```

`services/negociacion/tests/test_api_permisos.py`:

```python
import re

import httpx
import pytest
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI

pytestmark = pytest.mark.integracion
UUID = "00000000-0000-4000-8000-000000000000"
# Las tareas que agregan rutas del comprador las suman aquí.
ESPERADAS = {("POST", "/eventos"), ("GET", "/eventos/{evento_id}")}


async def test_las_rutas_del_comprador_exigen_su_rol(
    app: FastAPI, cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    externo = {"Authorization": f"Bearer {claves.token('proveedor')}"}
    aprobador = {"Authorization": f"Bearer {claves.token('aprobador')}"}
    # app.routes no aplana los routers incluidos: se recorre el esquema OpenAPI.
    rutas = [
        (metodo.upper(), ruta)
        for ruta, metodos in app.openapi()["paths"].items()
        if not ruta.startswith(("/salud", "/portal"))
        for metodo in metodos
    ]
    assert ESPERADAS <= set(rutas)
    for metodo, plantilla in rutas:
        ruta = re.sub(r"\{[^}]+\}", UUID, plantilla)
        sin_token = await cliente.request(metodo, ruta)
        assert sin_token.status_code == 401, (metodo, plantilla)
        de_externo = await cliente.request(metodo, ruta, headers=externo)
        assert de_externo.status_code == 403, (metodo, plantilla)
        if metodo != "GET":  # aprobador y admin solo consultan
            de_aprobador = await cliente.request(metodo, ruta, headers=aprobador)
            assert de_aprobador.status_code == 403, (metodo, plantilla)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest libs/comun/tests/test_mensajes.py services/negociacion/tests/test_api_eventos.py services/negociacion/tests/test_api_permisos.py -q`
Expected: FAIL. La traducción no existe todavía y `crear_app()` no acepta `transporte`.

- [ ] **Step 3: Write the implementation**

En `libs/comun/src/comun/mensajes.py`, agregue al diccionario `MENSAJES`:

```python
    "timezone_aware": "Incluya la zona horaria, por ejemplo 2026-10-20T18:00:00-06:00",
    "datetime_parsing": "Fecha y hora inválidas; use el formato 2026-10-20T18:00:00-06:00",
    "datetime_from_date_parsing": (
        "Fecha y hora inválidas; use el formato 2026-10-20T18:00:00-06:00"
    ),
    "datetime_type": "Fecha y hora inválidas; use el formato 2026-10-20T18:00:00-06:00",
```

`services/negociacion/src/negociacion/errores.py`:

```python
"""Errores de negocio con el formato común de Problem Details (comun.errores)."""

from comun.errores import ErrorDominio

REVISE = "Revise los campos indicados."


def invalidos(errores: list[dict[str, str]], codigo: str) -> ErrorDominio:
    return ErrorDominio(422, "Solicitud inválida", REVISE, {"codigo": codigo, "errores": errores})


def invalido(campo: str, mensaje: str, codigo: str) -> ErrorDominio:
    return invalidos([{"campo": campo, "mensaje": mensaje}], codigo)


def no_existe(detalle: str) -> ErrorDominio:
    return ErrorDominio(404, "No encontrado", detalle)


def conflicto(detalle: str, codigo: str) -> ErrorDominio:
    return ErrorDominio(409, "Conflicto", detalle, {"codigo": codigo})


def no_disponible() -> ErrorDominio:
    return ErrorDominio(
        503,
        "Servicio no disponible",
        "No se pudo consultar la referencia de precios; intente de nuevo.",
        {"codigo": "dependencia_no_disponible"},
    )
```

`services/negociacion/src/negociacion/bitacora.py`:

```python
"""Bitácora de auditoría de solo inserción (spec §12): quién hizo qué en cada evento y sesión."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from comun.auth import Usuario
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion.modelos import Bitacora

MAX_NOMBRE = 200


@dataclass(frozen=True)
class Actor:
    tipo: str  # comprador, proveedor, agente o sistema
    id: str | None
    nombre: str

    def para_evento(self) -> dict[str, str | None]:
        """El actor como lo esperan los consumidores de eventos (administracion)."""
        return {"id": self.id, "nombre": self.nombre}


AGENTE = Actor("agente", None, "Agente")
SISTEMA = Actor("sistema", None, "Sistema")


def de_usuario(usuario: Usuario) -> Actor:
    return Actor("comprador", usuario.id, usuario.nombre)


def registrar(
    bd: AsyncSession,
    accion: str,
    actor: Actor,
    *,
    evento_id: uuid.UUID | None = None,
    sesion_id: uuid.UUID | None = None,
    detalle: dict[str, Any] | None = None,
    fecha: datetime | None = None,
) -> None:
    """Agrega el registro a la transacción en curso."""
    fila = Bitacora(
        actor_tipo=actor.tipo,
        actor_id=actor.id,
        actor_nombre=actor.nombre[:MAX_NOMBRE],
        accion=accion,
        evento_id=evento_id,
        sesion_id=sesion_id,
        detalle=detalle or {},
    )
    if fecha is not None:
        fila.fecha = fecha
    bd.add(fila)
```

`services/negociacion/src/negociacion/textos.py`:

```python
"""Textos del servicio: los nombres de las palancas (y, desde la Task 9, los mensajes del agente)."""

PALANCAS: dict[str, tuple[str, str | None]] = {
    "precio": ("Precio unitario", None),
    "plazo_meses": ("Plazo del contrato", "meses"),
    "plazo_pago_dias": ("Plazo de pago", "días"),
    "sla_disponibilidad": ("Disponibilidad garantizada (SLA)", "%"),
    "tope_aumento_pct": ("Tope de aumento anual", "%"),
    "cuota_implementacion": ("Cuota de implementación", None),
}


def nombre_y_unidad(clave: str, moneda: str) -> tuple[str, str]:
    """El nombre de la palanca y su unidad; los montos se miden en la moneda del evento."""
    nombre, unidad = PALANCAS[clave]
    return nombre, unidad or moneda
```

`services/negociacion/src/negociacion/integraciones.py`:

```python
"""Consultas a inteligencia y a proveedores con el token del comprador (spec D5).

Solo se usan al crear o editar un borrador; los turnos nunca llaman a otros servicios, así que una
negociación se reproduce aunque cambie el benchmark.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from negociacion.errores import invalido, no_disponible

log = logging.getLogger(__name__)
TIEMPO_ESPERA_S = 5.0
CAMPOS_REFERENCIA = ("p25", "p50", "p75", "metodo", "version", "confianza", "observaciones")


@dataclass(frozen=True)
class LineaVigente:
    codigo_servicio: str
    nombre: str
    unidad: str
    cantidad: Decimal
    precio_unitario: Decimal


@dataclass(frozen=True)
class ContratoVigente:
    id: uuid.UUID
    folio: str
    moneda: str
    fecha_inicio: date
    fecha_fin: date
    plazo_pago_dias: int
    sla_disponibilidad: Decimal | None
    tope_aumento_pct: Decimal | None
    cuota_implementacion: Decimal
    lineas: tuple[LineaVigente, ...]

    @property
    def plazo_meses(self) -> int:
        """Meses de calendario del contrato (del 2025-11-01 al 2026-10-31 son 12), de 1 a 60."""
        meses = (
            (self.fecha_fin.year - self.fecha_inicio.year) * 12
            + self.fecha_fin.month
            - self.fecha_inicio.month
            + 1
        )
        return min(60, max(1, meses))

    def terminos(self) -> dict[str, Any]:
        """Lo que se guarda en la foto del evento: los términos vigentes, como texto."""
        return {
            "folio": self.folio,
            "fecha_inicio": self.fecha_inicio.isoformat(),
            "fecha_fin": self.fecha_fin.isoformat(),
            "plazo_meses": self.plazo_meses,
            "plazo_pago_dias": self.plazo_pago_dias,
            "sla_disponibilidad": _texto(self.sla_disponibilidad),
            "tope_aumento_pct": _texto(self.tope_aumento_pct),
            "cuota_implementacion": str(self.cuota_implementacion),
        }


def _texto(valor: Decimal | None) -> str | None:
    return None if valor is None else str(valor)


def _decimal(valor: Any) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def _contrato(datos: dict[str, Any]) -> ContratoVigente:
    return ContratoVigente(
        id=uuid.UUID(str(datos["id"])),
        folio=str(datos["folio"]),
        moneda=str(datos["moneda"]),
        fecha_inicio=date.fromisoformat(str(datos["fecha_inicio"])),
        fecha_fin=date.fromisoformat(str(datos["fecha_fin"])),
        plazo_pago_dias=int(datos["plazo_pago_dias"]),
        sla_disponibilidad=_decimal(datos["sla_disponibilidad"]),
        tope_aumento_pct=_decimal(datos["tope_aumento_pct"]),
        cuota_implementacion=Decimal(str(datos["cuota_implementacion"])),
        lineas=tuple(
            LineaVigente(
                codigo_servicio=str(linea["codigo_servicio"]),
                nombre=str(linea["nombre_servicio"]),
                unidad=str(linea["unidad"]),
                cantidad=Decimal(str(linea["cantidad"])),
                precio_unitario=Decimal(str(linea["precio_unitario"])),
            )
            for linea in datos["lineas"]
        ),
    )


class Integraciones:
    def __init__(self, http: httpx.AsyncClient, inteligencia_url: str, proveedores_url: str) -> None:
        self._http = http
        self._inteligencia = inteligencia_url.rstrip("/")
        self._proveedores = proveedores_url.rstrip("/")

    async def _get(
        self, url: str, token: str, params: dict[str, str] | None = None
    ) -> httpx.Response:
        try:
            return await self._http.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIEMPO_ESPERA_S,
            )
        except httpx.HTTPError as exc:
            log.warning("No respondió %s: %r", url, exc)
            raise no_disponible() from exc

    async def referencia(
        self, token: str, codigo: str, cantidad: Decimal, plazo: int
    ) -> dict[str, Any] | None:
        """P25/P50/P75 y su origen para esa cantidad y plazo; None si no hay referencia."""
        respuesta = await self._get(
            f"{self._inteligencia}/precios/servicios/{codigo}/referencia",
            token,
            {"cantidad": str(cantidad), "plazo": str(plazo)},
        )
        if respuesta.status_code == 404:  # sin contratos recientes (o aún no llega a su copia)
            return None
        if respuesta.status_code != 200:
            raise no_disponible()
        try:
            datos = respuesta.json()
            return {campo: datos[campo] for campo in CAMPOS_REFERENCIA}
        except (ValueError, KeyError, TypeError) as exc:
            raise no_disponible() from exc

    async def contrato(
        self, token: str, proveedor_id: uuid.UUID, contrato_id: uuid.UUID
    ) -> ContratoVigente:
        respuesta = await self._get(f"{self._proveedores}/proveedores/{proveedor_id}/contratos", token)
        if respuesta.status_code == 404:
            raise invalido("proveedor_id", "El proveedor no existe.", "proveedor_inexistente")
        if respuesta.status_code != 200:
            raise no_disponible()
        try:
            for datos in respuesta.json():
                if str(datos["id"]) == str(contrato_id):
                    return _contrato(datos)
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            raise no_disponible() from exc
        raise invalido("contrato_id", "El contrato no es de ese proveedor.", "contrato_inexistente")
```

`services/negociacion/src/negociacion/api/esquemas.py`:

```python
"""Formas de entrada y salida de la API; los montos viajan como texto decimal."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, model_validator

Codigo = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{3,30}$")]
Titulo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Cantidad = Annotated[Decimal, Field(gt=0, le=10_000_000, decimal_places=4)]
Estilo = Literal["firme", "balanceado", "flexible"]
TipoEvento = Literal["compra", "renovacion"]
EstadoEvento = Literal["borrador", "abierto", "en_evaluacion", "cancelado"]


class LineaNueva(BaseModel):
    codigo_servicio: Codigo
    cantidad: Cantidad


class EventoNuevo(BaseModel):
    tipo: TipoEvento
    titulo: Titulo
    fecha_limite: AwareDatetime
    rondas_max: int = Field(6, ge=2, le=12)
    estilo: Estilo = "balanceado"
    plazo_meses: int = Field(12, ge=1, le=60)  # en renovación sale del contrato
    lineas: list[LineaNueva] = Field(default_factory=list, max_length=20)
    proveedores: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    proveedor_id: uuid.UUID | None = None
    contrato_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _por_tipo(self) -> Self:
        if self.tipo == "compra":
            if not self.lineas:
                raise ValueError("Una compra necesita al menos una línea.")
            if not self.proveedores:
                raise ValueError("Invite al menos a un proveedor.")
            if len(set(self.proveedores)) != len(self.proveedores):
                raise ValueError("Un proveedor aparece dos veces.")
        elif self.proveedor_id is None or self.contrato_id is None:
            raise ValueError("Una renovación necesita el proveedor y el contrato.")
        return self


class Banda(BaseModel):
    p25: Decimal
    p50: Decimal
    p75: Decimal
    metodo: str
    confianza: str
    observaciones: int


class LineaSalida(BaseModel):
    id: uuid.UUID
    orden: int
    codigo_servicio: str
    nombre: str
    unidad: str
    cantidad: Decimal
    precio_vigente: Decimal | None
    ideal: Decimal | None
    limite: Decimal | None
    referencia: Banda | None


class PalancaSalida(BaseModel):
    clave: str
    nombre: str
    unidad: str
    activa: bool
    peso: int
    ideal: Decimal | None
    limite: Decimal | None
    vigente: Decimal | None  # el valor del contrato, en renovación


class Invitado(BaseModel):
    id: uuid.UUID
    nombre: str


class ProblemaSalida(BaseModel):
    campo: str
    mensaje: str


class SesionResumen(BaseModel):
    id: uuid.UUID
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    estado: str
    modo: str
    ronda: int
    utilidad: float | None  # de la última oferta del proveedor, de 0 a 1
    correo_estado: str
    correo_error: str | None
    fuera_de_limites: bool
    actualizado_en: datetime


class EventoSalida(BaseModel):
    id: uuid.UUID
    folio: str
    tipo: str
    titulo: str
    moneda: str
    plazo_meses: int
    estado: str
    fecha_limite: datetime
    rondas_max: int
    estilo: str
    contrato_origen_id: uuid.UUID | None
    proveedor_vigente_id: uuid.UUID | None
    invitados: list[Invitado]
    lineas: list[LineaSalida]
    palancas: list[PalancaSalida]
    referencia_fecha: datetime | None
    creado_por_nombre: str
    creado_en: datetime
    publicado_en: datetime | None
    cerrado_en: datetime | None
    motivo_cancelacion: str | None
    version: int
    errores: list[ProblemaSalida]  # lo que impide publicar (solo en borrador)
    avisos: list[ProblemaSalida]
    sesiones: list[SesionResumen]
```

`services/negociacion/src/negociacion/consultas.py`:

```python
"""Lecturas que arman las respuestas de la API (y, desde la Task 9, los términos del motor)."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion.api import esquemas
from negociacion.dominio.configuracion import (
    Banda,
    LineaRevision,
    PalancaRevision,
    Revision,
    avisos,
    errores,
)
from negociacion.dominio.terminos import CLAVES
from negociacion.errores import invalido, no_existe
from negociacion.modelos import Evento, Linea, Oferta, Palanca, Proveedor, Servicio, SesionNegociacion
from negociacion.textos import nombre_y_unidad

PROVEEDOR_NO_DISPONIBLE = (
    "El proveedor no está disponible para invitar: no existe, está inactivo o no tiene correo "
    "de contacto."
)


def decimal_o_nada(valor: Any) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def banda_de(referencia: dict[str, Any] | None) -> Banda | None:
    if referencia is None:
        return None
    return Banda(
        Decimal(str(referencia["p25"])),
        Decimal(str(referencia["p50"])),
        Decimal(str(referencia["p75"])),
    )


async def evento_o_404(bd: AsyncSession, evento_id: uuid.UUID, bloquear: bool = False) -> Evento:
    # populate_existing: un UPDATE masivo (cerrar_eventos_terminados) no refresca los objetos
    # que la sesión ya tenía cargados.
    evento = await bd.get(Evento, evento_id, with_for_update=bloquear, populate_existing=True)
    if evento is None:
        raise no_existe("La negociación no existe.")
    return evento


async def lineas_de(bd: AsyncSession, evento_id: uuid.UUID) -> list[Linea]:
    consulta = select(Linea).where(Linea.evento_id == evento_id).order_by(Linea.orden)
    return list((await bd.scalars(consulta)).all())


async def palancas_de(bd: AsyncSession, evento_id: uuid.UUID) -> dict[str, Palanca]:
    filas = await bd.scalars(select(Palanca).where(Palanca.evento_id == evento_id))
    return {p.clave: p for p in sorted(filas, key=lambda p: CLAVES.index(p.clave))}


async def servicios_activos(bd: AsyncSession, codigos: Sequence[str]) -> dict[str, Servicio]:
    consulta = select(Servicio).where(Servicio.codigo.in_(codigos), Servicio.activo.is_(True))
    filas = {s.codigo: s for s in await bd.scalars(consulta)}
    for i, codigo in enumerate(codigos):
        if codigo not in filas:
            raise invalido(
                f"lineas.{i}.codigo_servicio",
                f"El servicio {codigo} no existe o está inactivo.",
                "servicio_no_disponible",
            )
    return filas


async def proveedores_invitables(
    bd: AsyncSession, ids: Sequence[uuid.UUID], campos: Sequence[str] | None = None
) -> list[Proveedor]:
    """Los proveedores en el orden dado; cada uno activo y con correo de contacto en la copia."""
    filas = {p.id: p for p in await bd.scalars(select(Proveedor).where(Proveedor.id.in_(ids)))}
    for i, proveedor_id in enumerate(ids):
        proveedor = filas.get(proveedor_id)
        if proveedor is None or not proveedor.activo or not proveedor.contacto_email:
            campo = campos[i] if campos is not None else f"proveedores.{i}"
            raise invalido(campo, PROVEEDOR_NO_DISPONIBLE, "proveedor_no_disponible")
    return [filas[i] for i in ids]


def revision_de(evento: Evento, lineas: list[Linea], palancas: dict[str, Palanca]) -> Revision:
    contrato = evento.foto.get("contrato") or {}
    return Revision(
        tipo=evento.tipo,
        fecha_limite=evento.fecha_limite,
        lineas=tuple(
            LineaRevision(
                linea.nombre,
                linea.ideal,
                linea.limite,
                linea.precio_vigente,
                None if (banda := banda_de(linea.referencia)) is None else banda.p75,
            )
            for linea in lineas
        ),
        palancas=tuple(
            PalancaRevision(p.clave, p.peso, p.ideal, p.limite) for p in palancas.values()
        ),
        invitados=len(evento.invitados),
        tope_pct=decimal_o_nada(contrato.get("tope_aumento_pct")),
    )


async def _utilidades(bd: AsyncSession, sesiones: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    """La utilidad de la última oferta del proveedor en cada sesión."""
    if not sesiones:
        return {}
    filas = await bd.execute(
        select(Oferta.sesion_id, Oferta.utilidad)
        .where(Oferta.sesion_id.in_(sesiones), Oferta.autor == "proveedor")
        .distinct(Oferta.sesion_id)
        .order_by(Oferta.sesion_id, Oferta.secuencia.desc())
    )
    return {sesion_id: float(u) for sesion_id, u in filas.tuples()}


def _palanca(
    clave: str, fila: Palanca | None, moneda: str, vigente: Any
) -> esquemas.PalancaSalida:
    nombre, unidad = nombre_y_unidad(clave, moneda)
    return esquemas.PalancaSalida(
        clave=clave,
        nombre=nombre,
        unidad=unidad,
        activa=fila is not None,
        peso=0 if fila is None else fila.peso,
        ideal=None if fila is None else fila.ideal,
        limite=None if fila is None else fila.limite,
        vigente=decimal_o_nada(vigente),
    )


async def evento_salida(
    bd: AsyncSession, evento_id: uuid.UUID, ahora: datetime
) -> esquemas.EventoSalida:
    evento = await evento_o_404(bd, evento_id)
    lineas = await lineas_de(bd, evento.id)
    palancas = await palancas_de(bd, evento.id)
    nombres = dict(
        (
            await bd.execute(
                select(Proveedor.id, Proveedor.nombre).where(Proveedor.id.in_(evento.invitados))
            )
        )
        .tuples()
        .all()
    )
    sesiones = list(
        (
            await bd.scalars(
                select(SesionNegociacion)
                .where(SesionNegociacion.evento_id == evento.id)
                .order_by(SesionNegociacion.proveedor_nombre)
            )
        ).all()
    )
    utilidades = await _utilidades(bd, [s.id for s in sesiones])
    revision = revision_de(evento, lineas, palancas)
    vigentes = evento.foto.get("contrato") or {}
    borrador = evento.estado == "borrador"
    fecha_foto = evento.foto.get("fecha")
    return esquemas.EventoSalida(
        id=evento.id,
        folio=evento.folio,
        tipo=evento.tipo,
        titulo=evento.titulo,
        moneda=evento.moneda,
        plazo_meses=evento.plazo_meses,
        estado=evento.estado,
        fecha_limite=evento.fecha_limite,
        rondas_max=evento.rondas_max,
        estilo=evento.estilo,
        contrato_origen_id=evento.contrato_origen_id,
        proveedor_vigente_id=evento.proveedor_vigente_id,
        invitados=[
            esquemas.Invitado(id=i, nombre=nombres.get(i, "Proveedor sin datos"))
            for i in evento.invitados
        ],
        lineas=[
            esquemas.LineaSalida(
                id=linea.id,
                orden=linea.orden,
                codigo_servicio=linea.codigo_servicio,
                nombre=linea.nombre,
                unidad=linea.unidad,
                cantidad=linea.cantidad,
                precio_vigente=linea.precio_vigente,
                ideal=linea.ideal,
                limite=linea.limite,
                referencia=None
                if linea.referencia is None
                else esquemas.Banda.model_validate(linea.referencia),
            )
            for linea in lineas
        ],
        palancas=[
            _palanca(clave, palancas.get(clave), evento.moneda, vigentes.get(clave))
            for clave in CLAVES
        ],
        referencia_fecha=None if fecha_foto is None else datetime.fromisoformat(fecha_foto),
        creado_por_nombre=evento.creado_por_nombre,
        creado_en=evento.creado_en,
        publicado_en=evento.publicado_en,
        cerrado_en=evento.cerrado_en,
        motivo_cancelacion=evento.motivo_cancelacion,
        version=evento.version,
        errores=[
            esquemas.ProblemaSalida(campo=p.campo, mensaje=p.mensaje)
            for p in errores(revision, ahora)
        ]
        if borrador
        else [],
        avisos=[
            esquemas.ProblemaSalida(campo=p.campo, mensaje=p.mensaje) for p in avisos(revision)
        ]
        if borrador
        else [],
        sesiones=[
            esquemas.SesionResumen(
                id=s.id,
                proveedor_id=s.proveedor_id,
                proveedor_nombre=s.proveedor_nombre,
                estado=s.estado,
                modo=s.modo,
                ronda=s.ronda,
                utilidad=utilidades.get(s.id),
                correo_estado=s.correo_estado,
                correo_error=s.correo_error,
                fuera_de_limites=s.fuera_de_limites,
                actualizado_en=s.actualizado_en,
            )
            for s in sesiones
        ],
    )
```

`services/negociacion/src/negociacion/api/dependencias.py`:

```python
"""Base de datos, roles, reloj y dependencias externas para las rutas."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from comun.auth import ROLES_INTERNOS, Usuario, requiere_rol
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion.db import obtener_sesion
from negociacion.integraciones import Integraciones

_bearer = HTTPBearer(auto_error=False)


def _token(credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> str:
    """El token del comprador, para consultar a los otros servicios en su nombre (spec D5).

    Las rutas que lo usan también exigen el rol, que es lo que valida el token.
    """
    return "" if credenciales is None else credenciales.credentials


def _reloj(request: Request) -> Callable[[], datetime]:
    reloj: Callable[[], datetime] = request.app.state.reloj
    return reloj


def _integraciones(request: Request) -> Integraciones:
    integraciones: Integraciones = request.app.state.integraciones
    return integraciones


Bd = Annotated[AsyncSession, Depends(obtener_sesion)]
Lector = Annotated[Usuario, Depends(requiere_rol(*ROLES_INTERNOS))]
Comprador = Annotated[Usuario, Depends(requiere_rol("comprador"))]
TokenUsuario = Annotated[str, Depends(_token)]
Reloj = Annotated[Callable[[], datetime], Depends(_reloj)]
Integ = Annotated[Integraciones, Depends(_integraciones)]
```

`services/negociacion/src/negociacion/api/eventos.py`:

```python
"""Rutas del comprador para crear, consultar, editar, publicar y cancelar negociaciones."""

import uuid
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import text

from negociacion import consultas
from negociacion.api import esquemas
from negociacion.api.dependencias import Bd, Comprador, Integ, Lector, Reloj, TokenUsuario
from negociacion.bitacora import de_usuario, registrar
from negociacion.dominio.configuracion import sugerir_precio
from negociacion.errores import invalido
from negociacion.integraciones import ContratoVigente
from negociacion.modelos import Evento, Linea, Palanca

router = APIRouter(tags=["eventos"])
# (código, nombre, unidad, cantidad, precio vigente) de cada línea nueva.
LineaPorCrear = tuple[str, str, str, Decimal, Decimal | None]


@router.post("/eventos", status_code=201)
async def crear_evento(
    datos: esquemas.EventoNuevo,
    token: TokenUsuario,
    usuario: Comprador,
    bd: Bd,
    integraciones: Integ,
    reloj: Reloj,
) -> esquemas.EventoSalida:
    momento = reloj()
    contrato: ContratoVigente | None = None
    if datos.tipo == "compra":
        async with bd.begin():
            servicios = await consultas.servicios_activos(
                bd, [linea.codigo_servicio for linea in datos.lineas]
            )
            await consultas.proveedores_invitables(bd, datos.proveedores)
        monedas = {s.moneda for s in servicios.values()}
        if len(monedas) > 1:
            raise invalido(
                "lineas", "Todas las líneas deben estar en la misma moneda.", "monedas_distintas"
            )
        moneda, plazo, invitados = monedas.pop(), datos.plazo_meses, list(datos.proveedores)
        nuevas: list[LineaPorCrear] = [
            (
                linea.codigo_servicio,
                servicios[linea.codigo_servicio].nombre,
                servicios[linea.codigo_servicio].unidad,
                linea.cantidad,
                None,
            )
            for linea in datos.lineas
        ]
    else:
        if datos.proveedor_id is None or datos.contrato_id is None:  # lo exige EventoNuevo
            raise RuntimeError("Renovación sin proveedor o contrato")
        contrato = await integraciones.contrato(token, datos.proveedor_id, datos.contrato_id)
        if not contrato.fecha_inicio <= momento.date() <= contrato.fecha_fin:
            raise invalido("contrato_id", "El contrato no está vigente.", "contrato_no_vigente")
        async with bd.begin():
            await consultas.proveedores_invitables(bd, [datos.proveedor_id], ["proveedor_id"])
        moneda, plazo, invitados = contrato.moneda, contrato.plazo_meses, [datos.proveedor_id]
        nuevas = [
            (
                linea.codigo_servicio,
                linea.nombre,
                linea.unidad,
                linea.cantidad,
                linea.precio_unitario,
            )
            for linea in contrato.lineas
        ]
    # ponytail: una consulta por línea, en serie (≤ 20 líneas en la red interna); con muchas
    # más, lanzarlas en paralelo con asyncio.TaskGroup.
    referencias = [
        await integraciones.referencia(token, codigo, cantidad, plazo)
        for codigo, _, _, cantidad, _ in nuevas
    ]
    async with bd.begin():
        numero = int(await bd.scalar(text("SELECT nextval('folio_evento')")) or 0)
        evento = Evento(
            folio=f"NEG-{momento.year}-{numero:04d}",
            tipo=datos.tipo,
            titulo=datos.titulo,
            moneda=moneda,
            plazo_meses=plazo,
            fecha_limite=datos.fecha_limite,
            rondas_max=datos.rondas_max,
            estilo=datos.estilo,
            contrato_origen_id=None if contrato is None else contrato.id,
            proveedor_vigente_id=None if contrato is None else datos.proveedor_id,
            invitados=invitados,
            foto={
                "fecha": momento.isoformat(),
                "contrato": None if contrato is None else contrato.terminos(),
            },
            creado_por_id=usuario.id,
            creado_por_nombre=usuario.nombre,
            creado_en=momento,
        )
        bd.add(evento)
        await bd.flush()
        tope = None if contrato is None else contrato.tope_aumento_pct
        for orden, ((codigo, nombre, unidad, cantidad, vigente), referencia) in enumerate(
            zip(nuevas, referencias, strict=True)
        ):
            ideal, limite = sugerir_precio(
                datos.tipo, consultas.banda_de(referencia), vigente, tope
            )
            bd.add(
                Linea(
                    evento_id=evento.id,
                    orden=orden,
                    codigo_servicio=codigo,
                    nombre=nombre,
                    unidad=unidad,
                    cantidad=cantidad,
                    precio_vigente=vigente,
                    ideal=ideal,
                    limite=limite,
                    referencia=referencia,
                )
            )
        bd.add(Palanca(evento_id=evento.id, clave="precio", peso=100))
        registrar(
            bd,
            "evento.creado",
            de_usuario(usuario),
            evento_id=evento.id,
            detalle={"folio": evento.folio, "tipo": evento.tipo},
            fecha=momento,
        )
    return await consultas.evento_salida(bd, evento.id, momento)


@router.get("/eventos/{evento_id}")
async def ver_evento(
    evento_id: uuid.UUID, _: Lector, bd: Bd, reloj: Reloj
) -> esquemas.EventoSalida:
    return await consultas.evento_salida(bd, evento_id, reloj())
```

En `config.py`, agregue a `Configuracion`:

```python
    # Servicios que se consultan al crear o editar un borrador, con el token del comprador.
    inteligencia_url: str = "http://localhost:8000"
    proveedores_url: str = "http://localhost:8000"
```

En `main.py`:
1. Agregue las importaciones:

```python
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import httpx

from negociacion.api import eventos
from negociacion.integraciones import Integraciones
```

2. Cambie la firma por:

```python
def crear_app(
    configuracion: Configuracion | None = None,
    validador: ValidadorJWT | None = None,
    fabrica: async_sessionmaker[AsyncSession] | None = None,
    transporte: httpx.AsyncBaseTransport | None = None,
    reloj: Callable[[], datetime] | None = None,
) -> FastAPI:
```

3. Después de crear `consumidor`, agregue `http = httpx.AsyncClient(transport=transporte)`.
4. En `ciclo_de_vida`, después de esperar a que terminen las tareas, agregue `await http.aclose()`.
5. Después de `app.state.config = config`, agregue:

```python
    app.state.reloj = reloj or (lambda: datetime.now(UTC))
    app.state.integraciones = Integraciones(
        http, config.inteligencia_url, config.proveedores_url
    )
```

6. Después de incluir el router de salud, agregue `app.include_router(eventos.router)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest libs/comun/tests/test_mensajes.py services/negociacion -q`
Expected: PASS.

Run: `uv run ruff format . && uv run ruff check . && uv run mypy`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add libs/comun services/negociacion
git commit -m "feat(negociacion): crear y consultar negociaciones con la foto del precio justo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: API: editar el borrador y listar negociaciones

**Files:**
- Modify: `services/negociacion/src/negociacion/api/esquemas.py`
- Modify: `services/negociacion/src/negociacion/api/eventos.py`
- Test: `services/negociacion/tests/test_api_edicion.py`
- Modify: `services/negociacion/tests/test_api_permisos.py` (ESPERADAS)

**Interfaces:**
- Consumes: `consultas.*`, `sugerir_precio` y los fixtures de la Task 6.
- Produces:
  - `PATCH /eventos/{evento_id}` con `EventoCambios`. Responde `EventoSalida`; 409 con `codigo` `version_desactualizada` o `no_editable`.
  - `GET /eventos?estado=&tipo=&pagina=&tamano=` responde `PaginaEventos{total, elementos: [EventoResumen]}`.
  - **Esquemas:** `LineaCambio`, `PalancaEntrada`, `EventoCambios`, `EventoResumen`, `PaginaEventos` y el tipo `ClavePalanca`.

- [ ] **Step 1: Write the failing test**

En `test_api_permisos.py`, cambie `ESPERADAS` por:

```python
ESPERADAS = {
    ("POST", "/eventos"),
    ("GET", "/eventos"),
    ("GET", "/eventos/{evento_id}"),
    ("PATCH", "/eventos/{evento_id}"),
}
```

`services/negociacion/tests/test_api_edicion.py`:

```python
import uuid
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
from negociacion.modelos import Evento, SesionNegociacion
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]


async def _editar(
    cliente: httpx.AsyncClient, comprador: dict[str, str], evento: dict[str, Any], **cambios: Any
) -> httpx.Response:
    return await cliente.patch(f"/eventos/{evento['id']}", json=cambios, headers=comprador)


async def test_edita_el_borrador_y_sube_la_version(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    respuesta = await _editar(
        cliente, comprador, evento, version=1, titulo="CRM 2027", rondas_max=4, estilo="firme"
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["titulo"], cuerpo["rondas_max"], cuerpo["estilo"]) == ("CRM 2027", 4, "firme")
    assert cuerpo["version"] == 2


async def test_una_version_vieja_da_409(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    assert (await _editar(cliente, comprador, evento, version=1, titulo="A")).status_code == 200
    vieja = await _editar(cliente, comprador, evento, version=1, titulo="B")
    assert vieja.status_code == 409
    assert vieja.json()["codigo"] == "version_desactualizada"


async def test_solo_se_edita_un_borrador(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, fabrica: Fabrica
) -> None:
    evento = await nueva_compra()
    async with fabrica() as bd:
        await bd.execute(update(Evento).values(estado="abierto"))
        await bd.commit()
    respuesta = await _editar(cliente, comprador, evento, version=1, titulo="Otro")
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "no_editable"


async def test_reemplazar_lineas_solo_consulta_las_nuevas(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, externos: Any
) -> None:
    evento = await nueva_compra()
    antes = len(externos.peticiones)
    lineas = [
        {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "100", "ideal": "27.50", "limite": "31"},
        {"codigo_servicio": "SAAS-CRM-BAS", "cantidad": "40"},
    ]
    respuesta = await _editar(cliente, comprador, evento, version=1, lineas=lineas)
    assert respuesta.status_code == 200, respuesta.text
    pro, bas = respuesta.json()["lineas"]
    assert (D(pro["ideal"]), D(pro["limite"])) == (D("27.50"), D(31))
    assert D(pro["referencia"]["p50"]) == D("31.5")  # la foto de la línea que no cambió se queda
    assert (D(bas["ideal"]), D(bas["limite"])) == (D(12), D(14))  # sugeridos para la nueva
    assert [p.url.path for p in externos.peticiones[antes:]] == [
        "/precios/servicios/SAAS-CRM-BAS/referencia"
    ]


async def test_cambiar_el_plazo_vuelve_a_consultar_las_referencias(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, externos: Any
) -> None:
    evento = await nueva_compra()
    antes = len(externos.peticiones)
    respuesta = await _editar(cliente, comprador, evento, version=1, plazo_meses=24)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["plazo_meses"] == 24
    assert [p.url.params["plazo"] for p in externos.peticiones[antes:]] == ["24"]
    assert D(respuesta.json()["lineas"][0]["ideal"]) == D(28)  # lo que fijó el comprador se queda


async def test_las_lineas_no_mezclan_monedas(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    lineas = [
        {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "100"},
        {"codigo_servicio": "NUBE-VM-STD", "cantidad": "8"},
    ]
    respuesta = await _editar(cliente, comprador, evento, version=1, lineas=lineas)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "monedas_distintas"


async def test_activa_palancas_y_avisa_lo_que_falta(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    palancas = [
        {"clave": "precio", "peso": 70},
        {"clave": "plazo_pago_dias", "peso": 20, "ideal": "60", "limite": "30"},
    ]
    respuesta = await _editar(cliente, comprador, evento, version=1, palancas=palancas)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    activas = {p["clave"]: p for p in cuerpo["palancas"] if p["activa"]}
    assert set(activas) == {"precio", "plazo_pago_dias"}
    assert (activas["plazo_pago_dias"]["unidad"], D(activas["plazo_pago_dias"]["ideal"])) == (
        "días",
        D(60),
    )
    assert cuerpo["errores"] == [
        {"campo": "palancas", "mensaje": "Los pesos deben sumar 100; ahora suman 90."}
    ]


async def test_el_precio_siempre_es_una_palanca_activa(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    palancas = [{"clave": "plazo_meses", "peso": 100, "ideal": "12", "limite": "36"}]
    respuesta = await _editar(cliente, comprador, evento, version=1, palancas=palancas)
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"][0]["mensaje"] == "El precio siempre es una palanca activa."


async def test_en_renovacion_solo_cambian_el_ideal_y_el_limite(
    cliente: httpx.AsyncClient, comprador: dict[str, str], catalogo: None, ids: dict[str, str]
) -> None:
    creada = await cliente.post(
        "/eventos",
        json={
            "tipo": "renovacion",
            "titulo": "Renovación del CRM",
            "fecha_limite": "2026-10-20T15:00:00+00:00",
            "proveedor_id": ids["nube_norte"],
            "contrato_id": ids["contrato"],
        },
        headers=comprador,
    )
    evento = creada.json()
    misma = [{"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "120", "ideal": "29", "limite": "32"}]
    respuesta = await _editar(cliente, comprador, evento, version=1, lineas=misma)
    assert respuesta.status_code == 200, respuesta.text
    assert D(respuesta.json()["lineas"][0]["limite"]) == D(32)
    otra = [{"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "150", "ideal": "29", "limite": "32"}]
    for cambios in ({"lineas": otra}, {"plazo_meses": 24}, {"proveedores": [ids["datos_sur"]]}):
        rechazo = await _editar(cliente, comprador, evento, version=2, **cambios)
        assert rechazo.status_code == 422, cambios
        assert rechazo.json()["codigo"] == "no_editable"


async def test_lista_con_filtros_paginas_y_conteos(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    nueva_compra: Any,
    fabrica: Fabrica,
    ids: dict[str, str],
) -> None:
    await nueva_compra()
    segunda = await nueva_compra(titulo="Otra compra")
    evento_id = uuid.UUID(segunda["id"])
    async with fabrica() as bd:
        await bd.execute(update(Evento).where(Evento.id == evento_id).values(estado="abierto"))
        for proveedor, estado in (
            (ids["nube_norte"], "acuerdo_tentativo"),
            (ids["datos_sur"], "escalada"),
        ):
            bd.add(
                SesionNegociacion(
                    evento_id=evento_id,
                    proveedor_id=uuid.UUID(proveedor),
                    proveedor_nombre="Proveedor",
                    destinatario="ventas@proveedor.example",
                    estado=estado,
                )
            )
        await bd.commit()
    pagina = (await cliente.get("/eventos", headers=aprobador)).json()
    assert pagina["total"] == 2
    assert [e["folio"] for e in pagina["elementos"]] == ["NEG-2026-0002", "NEG-2026-0001"]
    primero = pagina["elementos"][0]
    assert (primero["sesiones"], primero["acuerdos"], primero["escaladas"]) == (2, 1, 1)
    assert primero["invitados"] == 2
    abiertos = (await cliente.get("/eventos", params={"estado": "abierto"}, headers=comprador)).json()
    assert [e["folio"] for e in abiertos["elementos"]] == ["NEG-2026-0002"]
    otra_pagina = (
        await cliente.get("/eventos", params={"tamano": 1, "pagina": 2}, headers=comprador)
    ).json()
    assert [e["folio"] for e in otra_pagina["elementos"]] == ["NEG-2026-0001"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest services/negociacion/tests/test_api_edicion.py services/negociacion/tests/test_api_permisos.py -q`
Expected: FAIL. `PATCH /eventos/{id}` responde 405 y `GET /eventos` también.

- [ ] **Step 3: Write the implementation**

Al final de `api/esquemas.py`:

```python
ClavePalanca = Literal[
    "precio",
    "plazo_meses",
    "plazo_pago_dias",
    "sla_disponibilidad",
    "tope_aumento_pct",
    "cuota_implementacion",
]
# Ideal y límite de un término; el rango y la precisión de cada uno se revisan al publicar.
Monto = Annotated[Decimal, Field(ge=0, le=10_000_000, decimal_places=4)]


class LineaCambio(BaseModel):
    codigo_servicio: Codigo
    cantidad: Cantidad
    ideal: Monto | None = None
    limite: Monto | None = None


class PalancaEntrada(BaseModel):
    clave: ClavePalanca
    peso: int = Field(ge=0, le=100)
    ideal: Monto | None = None  # el precio no lleva: va por línea
    limite: Monto | None = None


class EventoCambios(BaseModel):
    version: int
    titulo: Titulo | None = None
    fecha_limite: AwareDatetime | None = None
    rondas_max: int | None = Field(None, ge=2, le=12)
    estilo: Estilo | None = None
    plazo_meses: int | None = Field(None, ge=1, le=60)
    lineas: list[LineaCambio] | None = Field(None, min_length=1, max_length=20)
    proveedores: list[uuid.UUID] | None = Field(None, min_length=1, max_length=10)
    palancas: list[PalancaEntrada] | None = None

    @model_validator(mode="after")
    def _listas(self) -> Self:
        if self.palancas is not None:
            claves = [p.clave for p in self.palancas]
            if len(set(claves)) != len(claves):
                raise ValueError("Una palanca aparece dos veces.")
            if "precio" not in claves:
                raise ValueError("El precio siempre es una palanca activa.")
        if self.proveedores is not None and len(set(self.proveedores)) != len(self.proveedores):
            raise ValueError("Un proveedor aparece dos veces.")
        return self


class EventoResumen(BaseModel):
    id: uuid.UUID
    folio: str
    tipo: str
    titulo: str
    estado: str
    fecha_limite: datetime
    invitados: int
    sesiones: int
    acuerdos: int
    escaladas: int
    creado_por_nombre: str
    creado_en: datetime


class PaginaEventos(BaseModel):
    total: int
    elementos: list[EventoResumen]
```

En `api/eventos.py`:
1. Agregue estas importaciones:

```python
from typing import Annotated

from fastapi import Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion.integraciones import Integraciones
from negociacion.errores import conflicto
from negociacion.modelos import SesionNegociacion
```

2. Agregue estas rutas y funciones:

```python
@router.get("/eventos")
async def listar_eventos(
    _: Lector,
    bd: Bd,
    estado: esquemas.EstadoEvento | None = None,
    tipo: esquemas.TipoEvento | None = None,
    pagina: Annotated[int, Query(ge=1, le=1000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
) -> esquemas.PaginaEventos:
    filtros = []
    if estado is not None:
        filtros.append(Evento.estado == estado)
    if tipo is not None:
        filtros.append(Evento.tipo == tipo)
    total = await bd.scalar(select(func.count()).select_from(Evento).where(*filtros))
    conteos = (
        select(
            SesionNegociacion.evento_id,
            func.count().label("sesiones"),
            func.count().filter(SesionNegociacion.estado == "acuerdo_tentativo").label("acuerdos"),
            func.count().filter(SesionNegociacion.estado == "escalada").label("escaladas"),
        )
        .group_by(SesionNegociacion.evento_id)
        .subquery()
    )
    filas = await bd.execute(
        select(Evento, conteos.c.sesiones, conteos.c.acuerdos, conteos.c.escaladas)
        .outerjoin(conteos, conteos.c.evento_id == Evento.id)
        .where(*filtros)
        .order_by(Evento.creado_en.desc(), Evento.folio.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return esquemas.PaginaEventos(
        total=total or 0,
        elementos=[
            esquemas.EventoResumen(
                id=evento.id,
                folio=evento.folio,
                tipo=evento.tipo,
                titulo=evento.titulo,
                estado=evento.estado,
                fecha_limite=evento.fecha_limite,
                invitados=len(evento.invitados),
                sesiones=sesiones or 0,
                acuerdos=acuerdos or 0,
                escaladas=escaladas or 0,
                creado_por_nombre=evento.creado_por_nombre,
                creado_en=evento.creado_en,
            )
            for evento, sesiones, acuerdos, escaladas in filas.tuples()
        ],
    )


NO_EDITABLE_RENOVACION = (
    "En una renovación, las líneas salen del contrato; solo puede cambiar el ideal y el límite."
)


def _ajustar_renovacion(lineas: list[Linea], cambios: list[esquemas.LineaCambio]) -> None:
    actuales = [(linea.codigo_servicio, linea.cantidad) for linea in lineas]
    if actuales != [(c.codigo_servicio, c.cantidad) for c in cambios]:
        raise invalido("lineas", NO_EDITABLE_RENOVACION, "no_editable")
    for linea, cambio in zip(lineas, cambios, strict=True):
        linea.ideal, linea.limite = cambio.ideal, cambio.limite


async def _reemplazar_lineas(
    bd: AsyncSession,
    evento: Evento,
    cambios: list[esquemas.LineaCambio],
    token: str,
    integraciones: Integraciones,
    plazo_cambio: bool,
) -> None:
    """Las líneas de una compra se reemplazan; las que no cambian conservan su foto."""
    servicios = await consultas.servicios_activos(bd, [c.codigo_servicio for c in cambios])
    monedas = {s.moneda for s in servicios.values()}
    if len(monedas) > 1:
        raise invalido(
            "lineas", "Todas las líneas deben estar en la misma moneda.", "monedas_distintas"
        )
    evento.moneda = monedas.pop()
    previas = {(p.codigo_servicio, p.cantidad): p for p in await consultas.lineas_de(bd, evento.id)}
    nuevas: list[Linea] = []
    for orden, cambio in enumerate(cambios):
        previa = previas.get((cambio.codigo_servicio, cambio.cantidad))
        if previa is None or plazo_cambio:
            referencia = await integraciones.referencia(
                token, cambio.codigo_servicio, cambio.cantidad, evento.plazo_meses
            )
        else:
            referencia = previa.referencia
        if cambio.ideal is not None or cambio.limite is not None:
            ideal, limite = cambio.ideal, cambio.limite
        elif previa is not None:
            ideal, limite = previa.ideal, previa.limite
        else:
            ideal, limite = sugerir_precio("compra", consultas.banda_de(referencia), None, None)
        servicio = servicios[cambio.codigo_servicio]
        nuevas.append(
            Linea(
                evento_id=evento.id,
                orden=orden,
                codigo_servicio=servicio.codigo,
                nombre=servicio.nombre,
                unidad=servicio.unidad,
                cantidad=cambio.cantidad,
                ideal=ideal,
                limite=limite,
                referencia=referencia,
            )
        )
    await bd.execute(delete(Linea).where(Linea.evento_id == evento.id))
    bd.add_all(nuevas)


@router.patch("/eventos/{evento_id}")
async def editar_evento(
    evento_id: uuid.UUID,
    datos: esquemas.EventoCambios,
    token: TokenUsuario,
    usuario: Comprador,
    bd: Bd,
    integraciones: Integ,
    reloj: Reloj,
) -> esquemas.EventoSalida:
    momento = reloj()
    # ponytail: la consulta a inteligencia corre con el evento bloqueado (≤ 5 s por línea); basta
    # para borradores que edita una persona a la vez.
    async with bd.begin():
        evento = await consultas.evento_o_404(bd, evento_id, bloquear=True)
        if evento.estado != "borrador":
            raise conflicto("Solo se puede editar una negociación en borrador.", "no_editable")
        if evento.version != datos.version:
            raise conflicto(
                "Otra persona cambió esta negociación; recárguela para ver sus cambios.",
                "version_desactualizada",
            )
        renovacion = evento.tipo == "renovacion"
        cambios: list[str] = []
        for campo in ("titulo", "fecha_limite", "rondas_max", "estilo"):
            valor = getattr(datos, campo)
            if valor is not None and valor != getattr(evento, campo):
                setattr(evento, campo, valor)
                cambios.append(campo)
        if datos.plazo_meses is not None and datos.plazo_meses != evento.plazo_meses:
            if renovacion:
                raise invalido(
                    "plazo_meses", "El plazo de una renovación sale del contrato.", "no_editable"
                )
            evento.plazo_meses = datos.plazo_meses
            cambios.append("plazo_meses")
        if datos.proveedores is not None:
            if renovacion:
                raise invalido(
                    "proveedores",
                    "En una renovación solo participa el proveedor del contrato.",
                    "no_editable",
                )
            await consultas.proveedores_invitables(bd, datos.proveedores)
            if datos.proveedores != evento.invitados:
                evento.invitados = list(datos.proveedores)
                cambios.append("proveedores")
        if datos.lineas is not None:
            if renovacion:
                _ajustar_renovacion(await consultas.lineas_de(bd, evento.id), datos.lineas)
            else:
                await _reemplazar_lineas(
                    bd, evento, datos.lineas, token, integraciones, "plazo_meses" in cambios
                )
            cambios.append("lineas")
        elif "plazo_meses" in cambios:
            for linea in await consultas.lineas_de(bd, evento.id):
                linea.referencia = await integraciones.referencia(
                    token, linea.codigo_servicio, linea.cantidad, evento.plazo_meses
                )
        if datos.palancas is not None:
            await bd.execute(delete(Palanca).where(Palanca.evento_id == evento.id))
            bd.add_all(
                Palanca(
                    evento_id=evento.id,
                    clave=p.clave,
                    peso=p.peso,
                    ideal=None if p.clave == "precio" else p.ideal,
                    limite=None if p.clave == "precio" else p.limite,
                )
                for p in datos.palancas
            )
            cambios.append("palancas")
        if cambios:
            evento.version += 1
            registrar(
                bd,
                "evento.editado",
                de_usuario(usuario),
                evento_id=evento.id,
                detalle={"campos": cambios},
                fecha=momento,
            )
    return await consultas.evento_salida(bd, evento.id, momento)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest services/negociacion -q`
Expected: PASS.

Run: `uv run ruff format . && uv run ruff check . && uv run mypy`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add services/negociacion
git commit -m "feat(negociacion): editar el borrador con bloqueo optimista y listar negociaciones" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Publicar, cancelar y reenviar invitaciones

**Files:**
- Create: `services/negociacion/src/negociacion/tokens.py`
- Create: `services/negociacion/src/negociacion/correo.py`
- Create: `services/negociacion/src/negociacion/publicacion.py`
- Create: `services/negociacion/src/negociacion/api/sesiones.py`
- Modify: `services/negociacion/src/negociacion/config.py`, `services/negociacion/src/negociacion/main.py`, `services/negociacion/src/negociacion/api/esquemas.py`, `services/negociacion/src/negociacion/api/dependencias.py`, `services/negociacion/src/negociacion/api/eventos.py`, `services/negociacion/src/negociacion/textos.py`
- Modify: `services/negociacion/tests/conftest.py` (fixtures `buzon` y `publicar`), `services/negociacion/tests/test_api_permisos.py`
- Test: `services/negociacion/tests/test_api_publicacion.py`, `services/negociacion/tests/test_correo.py`

**Interfaces:**
- Consumes: `consultas.*`, `errores` (Task 5), `bitacora.registrar` y `Actor`.
- Produces:
  - **`negociacion.tokens`:** `nuevo_token() -> tuple[str, str]` (token y hash) y `hash_de(token) -> str` (SHA-256 en hexadecimal).
  - **`negociacion.correo`:** `EnviarCorreo = Callable[[EmailMessage], Awaitable[None]]`, `invitacion(...) -> EmailMessage`, `enviador_smtp(host, puerto) -> EnviarCorreo` y `NO_ENTREGADO`.
  - **`negociacion.publicacion`:** `enlace(url_publica, token)`, `preparar_publicacion`, `enviar_invitaciones`, `registrar_envios`, `cancelar` y `preparar_reenvio`.
  - **Rutas:**
    - `POST /eventos/{id}/publicar` responde `Publicacion{evento, enlaces: [EnlaceSalida]}`;
    - `POST /eventos/{id}/cancelar` recibe `{motivo}` y responde `EventoSalida`;
    - `POST /sesiones/{id}/invitacion` responde `EnlaceSalida`.
  - **`crear_app`:** agrega `enviar_correo: EnviarCorreo | None = None`.
  - **Eventos al outbox:** `negociacion.publicada`, `negociacion.cancelada` y `negociacion.invitacion_enviada`, con los payloads de la spec §9.2.
  - **Fixtures:** `buzon` (`Buzon` con `.enviados` y `.falla`) y `publicar(**cambios) -> (evento, enlaces)`.

- [ ] **Step 1: Write the failing tests**

En `test_api_permisos.py`, agregue a `ESPERADAS`:

```python
    ("POST", "/eventos/{evento_id}/publicar"),
    ("POST", "/eventos/{evento_id}/cancelar"),
    ("POST", "/sesiones/{sesion_id}/invitacion"),
```

En `conftest.py`:
1. Agregue `from email.message import EmailMessage`.
2. Agregue la clase y los fixtures:

```python
Publicar = Callable[..., Awaitable[tuple[dict[str, Any], list[dict[str, Any]]]]]


@dataclass
class Buzon:
    """Recoge los correos en lugar de mandarlos; con `falla`, simula un SMTP caído."""

    enviados: list[EmailMessage] = field(default_factory=list)
    falla: bool = False

    async def enviar(self, mensaje: EmailMessage) -> None:
        if self.falla:
            raise OSError("sin servidor de correo")
        self.enviados.append(mensaje)


@pytest.fixture
def buzon() -> Buzon:
    return Buzon()


@pytest.fixture
def publicar(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Compra
) -> Publicar:
    """Crea una compra (con los cambios dados), la publica y devuelve (evento, enlaces)."""

    async def _publicar(**cambios: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        evento = await nueva_compra(**cambios)
        respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()["evento"], respuesta.json()["enlaces"]

    return _publicar
```

3. En el fixture `app`, agregue el parámetro `buzon: Buzon` y pase `enviar_correo=buzon.enviar` a `crear_app`.

`services/negociacion/tests/test_correo.py`:

```python
from datetime import UTC, datetime

from negociacion.correo import invitacion
from negociacion.publicacion import enlace


def test_la_invitacion_lleva_el_enlace_y_la_fecha_limite_en_hora_de_mexico() -> None:
    url = enlace("http://localhost:8080/", "abc123")
    assert url == "http://localhost:8080/portal#t=abc123"
    mensaje = invitacion(
        remitente="compras@plataforma.example",
        destinatario="lucia@nubenorte.example",
        contacto="Lucía Pérez",
        titulo="Licencias de CRM 2027",
        folio="NEG-2026-0001",
        fecha_limite=datetime(2026, 10, 20, 15, tzinfo=UTC),
        enlace=url,
    )
    assert mensaje["Subject"] == "Invitación a negociar: Licencias de CRM 2027 (NEG-2026-0001)"
    assert mensaje["To"] == "lucia@nubenorte.example"
    cuerpo = mensaje.get_content()
    assert "Estimado(a) Lucía Pérez:" in cuerpo
    assert url in cuerpo
    assert "20/10/2026 a las 09:00" in cuerpo  # 15:00 UTC son las 09:00 en la Ciudad de México
    assert "El enlace es personal" in cuerpo
```

`services/negociacion/tests/test_api_publicacion.py`:

```python
import asyncio
import hashlib
import json
import uuid
from typing import Any

import httpx
import pytest
from negociacion.modelos import Mensaje, Outbox, SesionNegociacion
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _token(enlace: str) -> str:
    return enlace.split("#t=")[1]


async def _outbox(fabrica: Fabrica) -> list[Outbox]:
    async with fabrica() as bd:
        return list((await bd.scalars(select(Outbox).order_by(Outbox.ocurrido_en))).all())


async def test_publica_crea_sesiones_manda_correos_y_eventos(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    nueva_compra: Any,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    evento = await nueva_compra()
    respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["evento"]["estado"] == "abierto"
    assert [s["estado"] for s in cuerpo["evento"]["sesiones"]] == ["invitada", "invitada"]
    enlaces = cuerpo["enlaces"]
    assert [e["proveedor_nombre"] for e in enlaces] == [
        "Nube Norte S.A. de C.V.",
        "Datos del Sur S.A.",
    ]
    assert all(e["enlace"].startswith("http://localhost:8080/portal#t=") for e in enlaces)
    assert {e["correo_estado"] for e in enlaces} == {"enviado"}
    tokens = [_token(e["enlace"]) for e in enlaces]
    assert [m["To"] for m in buzon.enviados] == [
        "lucia@nubenorte.example",
        "ventas@datossur.example",
    ]
    assert buzon.enviados[0]["Subject"] == (
        f"Invitación a negociar: Licencias de CRM 2027 ({evento['folio']})"
    )
    assert enlaces[0]["enlace"] in buzon.enviados[0].get_content()
    async with fabrica() as bd:
        hashes = set((await bd.scalars(select(SesionNegociacion.token_hash))).all())
    assert hashes == {_hash(t) for t in tokens}  # la base solo guarda el hash
    eventos = await _outbox(fabrica)
    assert sorted(e.tipo for e in eventos) == [
        "negociacion.invitacion_enviada",
        "negociacion.invitacion_enviada",
        "negociacion.publicada",
    ]
    assert not any(t in json.dumps(e.payload) for e in eventos for t in tokens)
    publicada = next(e for e in eventos if e.tipo == "negociacion.publicada")
    assert publicada.payload == {
        "folio": evento["folio"],
        "titulo": "Licencias de CRM 2027",
        "tipo": "compra",
        "proveedores": 2,
        "actor": {"id": "comprador-1", "nombre": "comprador-1"},
    }
    invitacion = next(
        e
        for e in eventos
        if e.tipo == "negociacion.invitacion_enviada"
        and e.payload["proveedor"] == "Nube Norte S.A. de C.V."
    )
    assert invitacion.payload | {"actor": None} == {
        "folio": evento["folio"],
        "titulo": "Licencias de CRM 2027",
        "proveedor": "Nube Norte S.A. de C.V.",
        "destinatario": "lucia@nubenorte.example",
        "estado": "enviado",
        "error": None,
        "reenvio": False,
        "actor": None,
    }


async def test_no_publica_un_borrador_incompleto(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, buzon: Any
) -> None:
    evento = await nueva_compra(lineas=[{"codigo_servicio": "NUBE-VM-STD", "cantidad": "64"}])
    respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "evento_incompleto"
    assert {e["campo"] for e in respuesta.json()["errores"]} == {"lineas.0.ideal", "lineas.0.limite"}
    assert buzon.enviados == []


async def test_publicar_dos_veces_a_la_vez_crea_un_solo_juego_de_sesiones(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    nueva_compra: Any,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    evento = await nueva_compra()
    ruta = f"/eventos/{evento['id']}/publicar"
    primera, segunda = await asyncio.gather(
        cliente.post(ruta, headers=comprador), cliente.post(ruta, headers=comprador)
    )
    assert sorted([primera.status_code, segunda.status_code]) == [200, 409]
    assert len(buzon.enviados) == 2
    async with fabrica() as bd:
        assert await bd.scalar(select(func.count()).select_from(SesionNegociacion)) == 2


async def test_si_el_correo_falla_la_sesion_lo_dice_y_el_enlace_se_entrega(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    nueva_compra: Any,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    buzon.falla = True
    evento = await nueva_compra()
    respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert respuesta.status_code == 200
    assert {e["correo_estado"] for e in respuesta.json()["enlaces"]} == {"fallido"}
    sesiones = respuesta.json()["evento"]["sesiones"]
    assert {s["correo_error"] for s in sesiones} == {
        "No se pudo entregar el correo al servidor de correo."
    }
    invitaciones = [e for e in await _outbox(fabrica) if e.tipo.endswith("invitacion_enviada")]
    assert {e.payload["estado"] for e in invitaciones} == {"fallido"}


async def test_cancelar_revoca_los_enlaces_y_cierra_las_sesiones(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, fabrica: Fabrica
) -> None:
    evento, _ = await publicar()
    ruta = f"/eventos/{evento['id']}/cancelar"
    respuesta = await cliente.post(ruta, json={"motivo": "Se pospuso la compra"}, headers=comprador)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["estado"], cuerpo["motivo_cancelacion"]) == ("cancelado", "Se pospuso la compra")
    assert {s["estado"] for s in cuerpo["sesiones"]} == {"sin_acuerdo"}
    async with fabrica() as bd:
        assert set((await bd.scalars(select(SesionNegociacion.token_hash))).all()) == {None}
        textos = (await bd.scalars(select(Mensaje.texto).where(Mensaje.autor == "sistema"))).all()
    assert list(textos) == ["La negociación se canceló. Gracias por su tiempo."] * 2
    cancelada = next(e for e in await _outbox(fabrica) if e.tipo == "negociacion.cancelada")
    assert cancelada.payload["motivo"] == "Se pospuso la compra"
    otra_vez = await cliente.post(ruta, json={"motivo": "Otra vez"}, headers=comprador)
    assert otra_vez.status_code == 409
    assert otra_vez.json()["codigo"] == "no_cancelable"


async def test_cancelar_un_borrador(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    respuesta = await cliente.post(
        f"/eventos/{evento['id']}/cancelar", json={"motivo": "Ya no se necesita"}, headers=comprador
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "cancelado"


async def test_reenviar_cambia_el_token_y_manda_otro_correo(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    _, enlaces = await publicar()
    sesion_id = enlaces[0]["sesion_id"]
    respuesta = await cliente.post(f"/sesiones/{sesion_id}/invitacion", headers=comprador)
    assert respuesta.status_code == 200, respuesta.text
    nuevo = _token(respuesta.json()["enlace"])
    assert nuevo != _token(enlaces[0]["enlace"])
    async with fabrica() as bd:
        sesion = await bd.get(SesionNegociacion, uuid.UUID(sesion_id))
    assert sesion is not None and sesion.token_hash == _hash(nuevo)
    assert len(buzon.enviados) == 3
    invitaciones = [
        e for e in await _outbox(fabrica) if e.tipo == "negociacion.invitacion_enviada"
    ]
    assert len(invitaciones) == 3
    assert [e.payload["reenvio"] for e in invitaciones].count(True) == 1


async def test_no_reenvia_en_una_negociacion_cancelada(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    evento, enlaces = await publicar()
    await cliente.post(f"/eventos/{evento['id']}/cancelar", json={"motivo": "x"}, headers=comprador)
    respuesta = await cliente.post(f"/sesiones/{enlaces[0]['sesion_id']}/invitacion", headers=comprador)
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "no_reenviable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest services/negociacion/tests/test_correo.py services/negociacion/tests/test_api_publicacion.py -q`
Expected: FAIL. `negociacion.correo` no existe y `crear_app()` no acepta `enviar_correo`.

- [ ] **Step 3: Write the implementation**

En `config.py`, agregue:

```python
    # SMTP sin autenticación: Mailpit en desarrollo, solo en la red interna.
    smtp_host: str = "localhost"
    smtp_puerto: int = 1025
    smtp_remitente: str = "compras@plataforma.example"
    # Dirección pública de la plataforma, para el enlace del portal en las invitaciones.
    url_publica: str = "http://localhost:8080"
```

`services/negociacion/src/negociacion/tokens.py`:

```python
"""Tokens de invitación: opacos, de 256 bits; en la base solo se guarda su SHA-256 (spec §8.1)."""

import hashlib
import secrets


def hash_de(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def nuevo_token() -> tuple[str, str]:
    """(token para el enlace, hash para la base)."""
    token = secrets.token_urlsafe(32)
    return token, hash_de(token)
```

`services/negociacion/src/negociacion/correo.py`:

```python
"""Correo de invitación a negociar (SMTP; Mailpit en desarrollo)."""

import asyncio
import smtplib
from collections.abc import Awaitable, Callable
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

EnviarCorreo = Callable[[EmailMessage], Awaitable[None]]
ZONA = ZoneInfo("America/Mexico_City")
TIEMPO_ESPERA_S = 10
NO_ENTREGADO = "No se pudo entregar el correo al servidor de correo."


def invitacion(
    *,
    remitente: str,
    destinatario: str,
    contacto: str,
    titulo: str,
    folio: str,
    fecha_limite: datetime,
    enlace: str,
) -> EmailMessage:
    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = f"Invitación a negociar: {titulo} ({folio})"
    limite = fecha_limite.astimezone(ZONA).strftime("%d/%m/%Y a las %H:%M")
    mensaje.set_content(
        f"Estimado(a) {contacto}:\n\n"
        f"Lo invitamos a presentar su oferta para «{titulo}» (folio {folio}).\n\n"
        f"Puede negociar en línea hasta el {limite} (hora de la Ciudad de México) en este "
        f"enlace:\n{enlace}\n\n"
        "El enlace es personal: no lo comparta. En el portal también puede pedir hablar con una "
        "persona del equipo de compras.\n"
    )
    return mensaje


def enviador_smtp(host: str, puerto: int) -> EnviarCorreo:
    """Manda el correo en un hilo aparte: smtplib es bloqueante."""

    def _enviar(mensaje: EmailMessage) -> None:
        with smtplib.SMTP(host, puerto, timeout=TIEMPO_ESPERA_S) as smtp:
            smtp.send_message(mensaje)

    async def enviar(mensaje: EmailMessage) -> None:
        await asyncio.to_thread(_enviar, mensaje)

    return enviar
```

En `textos.py`, agregue:

```python
CANCELADA = "La negociación se canceló. Gracias por su tiempo."
```

`services/negociacion/src/negociacion/publicacion.py`:

```python
"""Publicar, cancelar y reenviar invitaciones (spec §7 y §9.1).

Los correos salen fuera de la transacción: primero se confirman las sesiones y sus tokens, luego se
manda cada correo, y al final otra transacción guarda si salió y lo publica en el outbox. Si el
proceso se cae entre medio, el comprador ve el correo pendiente y usa «Reenviar invitación».
"""

import logging
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime

from comun.outbox import registrar_evento
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion import consultas, correo, textos
from negociacion.bitacora import Actor, registrar
from negociacion.config import Configuracion
from negociacion.dominio.configuracion import errores
from negociacion.errores import conflicto, invalidos, no_existe
from negociacion.modelos import FINALES, Evento, Mensaje, Outbox, Proveedor, SesionNegociacion
from negociacion.tokens import nuevo_token

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Invitacion:
    sesion_id: uuid.UUID
    proveedor_nombre: str
    contacto: str
    destinatario: str
    token: str


@dataclass(frozen=True)
class Envio:
    sesion_id: uuid.UUID
    proveedor_nombre: str
    destinatario: str
    enlace: str
    estado: str  # enviado o fallido
    error: str | None


def enlace(url_publica: str, token: str) -> str:
    """El token va en el fragmento: el navegador no lo manda al servidor ni en el Referer."""
    return f"{url_publica.rstrip('/')}/portal#t={token}"


async def preparar_publicacion(
    bd: AsyncSession, evento_id: uuid.UUID, actor: Actor, momento: datetime
) -> tuple[Evento, list[Invitacion]]:
    """Valida, crea las sesiones con su token y abre el evento, en la transacción en curso."""
    evento = await consultas.evento_o_404(bd, evento_id, bloquear=True)
    if evento.estado != "borrador":
        raise conflicto("La negociación ya se publicó o se canceló.", "no_publicable")
    lineas = await consultas.lineas_de(bd, evento.id)
    palancas = await consultas.palancas_de(bd, evento.id)
    problemas = errores(consultas.revision_de(evento, lineas, palancas), momento)
    if problemas:
        raise invalidos(
            [{"campo": p.campo, "mensaje": p.mensaje} for p in problemas], "evento_incompleto"
        )
    invitaciones: list[Invitacion] = []
    for proveedor in await consultas.proveedores_invitables(bd, evento.invitados):
        token, huella = nuevo_token()
        sesion = SesionNegociacion(
            evento_id=evento.id,
            proveedor_id=proveedor.id,
            proveedor_nombre=proveedor.nombre,
            destinatario=proveedor.contacto_email,
            token_hash=huella,
            actualizado_en=momento,
        )
        bd.add(sesion)
        await bd.flush()
        invitaciones.append(
            Invitacion(
                sesion.id,
                proveedor.nombre,
                proveedor.contacto_nombre,
                proveedor.contacto_email,
                token,
            )
        )
    evento.estado = "abierto"
    evento.publicado_en = momento
    registrar_evento(
        bd,
        Outbox,
        "negociacion.publicada",
        {
            "folio": evento.folio,
            "titulo": evento.titulo,
            "tipo": evento.tipo,
            "proveedores": len(invitaciones),
            "actor": actor.para_evento(),
        },
    )
    registrar(
        bd,
        "evento.publicado",
        actor,
        evento_id=evento.id,
        detalle={"proveedores": len(invitaciones)},
        fecha=momento,
    )
    return evento, invitaciones


async def enviar_invitaciones(
    enviar: correo.EnviarCorreo,
    config: Configuracion,
    evento: Evento,
    invitaciones: list[Invitacion],
) -> list[Envio]:
    envios: list[Envio] = []
    for invitacion in invitaciones:
        url = enlace(config.url_publica, invitacion.token)
        mensaje = correo.invitacion(
            remitente=config.smtp_remitente,
            destinatario=invitacion.destinatario,
            contacto=invitacion.contacto,
            titulo=evento.titulo,
            folio=evento.folio,
            fecha_limite=evento.fecha_limite,
            enlace=url,
        )
        try:
            await enviar(mensaje)
            estado, error = "enviado", None
        except (smtplib.SMTPException, OSError):
            log.warning("No se pudo enviar la invitación de la sesión %s", invitacion.sesion_id)
            estado, error = "fallido", correo.NO_ENTREGADO
        envios.append(
            Envio(
                invitacion.sesion_id,
                invitacion.proveedor_nombre,
                invitacion.destinatario,
                url,
                estado,
                error,
            )
        )
    return envios


async def registrar_envios(
    bd: AsyncSession,
    evento: Evento,
    envios: list[Envio],
    actor: Actor,
    momento: datetime,
    reenvio: bool,
) -> None:
    """Guarda si salió cada correo y lo publica (sin el token), en la transacción en curso."""
    for envio in envios:
        sesion = await bd.get(SesionNegociacion, envio.sesion_id)
        if sesion is None:
            raise LookupError(f"La sesión {envio.sesion_id} desapareció")
        sesion.correo_estado, sesion.correo_error, sesion.correo_en = (
            envio.estado,
            envio.error,
            momento,
        )
        registrar_evento(
            bd,
            Outbox,
            "negociacion.invitacion_enviada",
            {
                "folio": evento.folio,
                "titulo": evento.titulo,
                "proveedor": envio.proveedor_nombre,
                "destinatario": envio.destinatario,
                "estado": envio.estado,
                "error": envio.error,
                "reenvio": reenvio,
                "actor": actor.para_evento(),
            },
        )
        registrar(
            bd,
            "invitacion.reenviada" if reenvio else "invitacion.enviada",
            actor,
            evento_id=evento.id,
            sesion_id=sesion.id,
            detalle={"estado": envio.estado},
            fecha=momento,
        )


async def cancelar(
    bd: AsyncSession, evento_id: uuid.UUID, motivo: str, actor: Actor, momento: datetime
) -> None:
    evento = await consultas.evento_o_404(bd, evento_id, bloquear=True)
    if evento.estado not in ("borrador", "abierto"):
        raise conflicto(
            "Solo se puede cancelar una negociación en borrador o abierta.", "no_cancelable"
        )
    sesiones = await bd.scalars(
        select(SesionNegociacion)
        .where(SesionNegociacion.evento_id == evento.id)
        .with_for_update()
    )
    for sesion in sesiones:
        sesion.token_hash = None  # el enlace deja de servir
        if sesion.estado not in FINALES:
            sesion.estado = "sin_acuerdo"
            sesion.actualizado_en = momento
            bd.add(
                Mensaje(
                    sesion_id=sesion.id,
                    autor="sistema",
                    texto=textos.CANCELADA,
                    ronda=sesion.ronda,
                    creado_en=momento,
                )
            )
    evento.estado = "cancelado"
    evento.cerrado_en = momento
    evento.motivo_cancelacion = motivo
    registrar_evento(
        bd,
        Outbox,
        "negociacion.cancelada",
        {
            "folio": evento.folio,
            "titulo": evento.titulo,
            "motivo": motivo,
            "actor": actor.para_evento(),
        },
    )
    registrar(
        bd, "evento.cancelado", actor, evento_id=evento.id, detalle={"motivo": motivo}, fecha=momento
    )


async def preparar_reenvio(
    bd: AsyncSession, sesion_id: uuid.UUID, momento: datetime
) -> tuple[Evento, Invitacion]:
    """Un token nuevo para la sesión; el anterior deja de servir."""
    sesion = await bd.get(
        SesionNegociacion, sesion_id, with_for_update=True, populate_existing=True
    )
    if sesion is None:
        raise no_existe("La sesión no existe.")
    evento = await consultas.evento_o_404(bd, sesion.evento_id)
    if evento.estado != "abierto" or sesion.estado in FINALES:
        raise conflicto(
            "Solo se puede reenviar la invitación de una sesión en curso.", "no_reenviable"
        )
    proveedor = await bd.get(Proveedor, sesion.proveedor_id)
    if proveedor is not None and proveedor.contacto_email:
        sesion.destinatario = proveedor.contacto_email  # por si cambió el contacto
    contacto = sesion.proveedor_nombre if proveedor is None else proveedor.contacto_nombre
    token, huella = nuevo_token()
    sesion.token_hash = huella
    sesion.correo_estado = "pendiente"
    sesion.actualizado_en = momento
    return evento, Invitacion(sesion.id, sesion.proveedor_nombre, contacto, sesion.destinatario, token)
```

En `api/dependencias.py`, agregue:

```python
from negociacion.config import Configuracion
from negociacion.correo import EnviarCorreo


def _enviar_correo(request: Request) -> EnviarCorreo:
    enviar: EnviarCorreo = request.app.state.enviar_correo
    return enviar


def _config(request: Request) -> Configuracion:
    config: Configuracion = request.app.state.config
    return config


Correo = Annotated[EnviarCorreo, Depends(_enviar_correo)]
Config = Annotated[Configuracion, Depends(_config)]
```

Al final de `api/esquemas.py`, agregue:

```python
class Cancelacion(BaseModel):
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class EnlaceSalida(BaseModel):
    sesion_id: uuid.UUID
    proveedor_nombre: str
    destinatario: str
    enlace: str  # solo se muestra en esta respuesta; la base guarda el hash del token
    correo_estado: str


class Publicacion(BaseModel):
    evento: EventoSalida
    enlaces: list[EnlaceSalida]
```

En `api/eventos.py`:
1. Agregue `from negociacion import publicacion` e importe `Config` y `Correo` de las dependencias.
2. Agregue:

```python
def _enlaces(envios: list[publicacion.Envio]) -> list[esquemas.EnlaceSalida]:
    return [
        esquemas.EnlaceSalida(
            sesion_id=envio.sesion_id,
            proveedor_nombre=envio.proveedor_nombre,
            destinatario=envio.destinatario,
            enlace=envio.enlace,
            correo_estado=envio.estado,
        )
        for envio in envios
    ]


@router.post("/eventos/{evento_id}/publicar")
async def publicar_evento(
    evento_id: uuid.UUID,
    usuario: Comprador,
    bd: Bd,
    reloj: Reloj,
    enviar: Correo,
    config: Config,
) -> esquemas.Publicacion:
    momento, actor = reloj(), de_usuario(usuario)
    async with bd.begin():
        evento, invitaciones = await publicacion.preparar_publicacion(
            bd, evento_id, actor, momento
        )
    envios = await publicacion.enviar_invitaciones(enviar, config, evento, invitaciones)
    async with bd.begin():
        await publicacion.registrar_envios(bd, evento, envios, actor, momento, reenvio=False)
    return esquemas.Publicacion(
        evento=await consultas.evento_salida(bd, evento_id, momento), enlaces=_enlaces(envios)
    )


@router.post("/eventos/{evento_id}/cancelar")
async def cancelar_evento(
    evento_id: uuid.UUID,
    datos: esquemas.Cancelacion,
    usuario: Comprador,
    bd: Bd,
    reloj: Reloj,
) -> esquemas.EventoSalida:
    momento = reloj()
    async with bd.begin():
        await publicacion.cancelar(bd, evento_id, datos.motivo, de_usuario(usuario), momento)
    return await consultas.evento_salida(bd, evento_id, momento)
```

`services/negociacion/src/negociacion/api/sesiones.py`:

```python
"""Rutas del comprador sobre una sesión (y, desde la Task 10, su supervisión)."""

import uuid

from fastapi import APIRouter

from negociacion import publicacion
from negociacion.api import esquemas
from negociacion.api.dependencias import Bd, Comprador, Config, Correo, Reloj
from negociacion.bitacora import de_usuario

router = APIRouter(tags=["sesiones"])


@router.post("/sesiones/{sesion_id}/invitacion")
async def reenviar_invitacion(
    sesion_id: uuid.UUID,
    usuario: Comprador,
    bd: Bd,
    reloj: Reloj,
    enviar: Correo,
    config: Config,
) -> esquemas.EnlaceSalida:
    momento, actor = reloj(), de_usuario(usuario)
    async with bd.begin():
        evento, invitacion = await publicacion.preparar_reenvio(bd, sesion_id, momento)
    [envio] = await publicacion.enviar_invitaciones(enviar, config, evento, [invitacion])
    async with bd.begin():
        await publicacion.registrar_envios(bd, evento, [envio], actor, momento, reenvio=True)
    return esquemas.EnlaceSalida(
        sesion_id=envio.sesion_id,
        proveedor_nombre=envio.proveedor_nombre,
        destinatario=envio.destinatario,
        enlace=envio.enlace,
        correo_estado=envio.estado,
    )
```

En `main.py`:
1. Agregue `from negociacion.api import eventos, sesiones` y `from negociacion.correo import EnviarCorreo, enviador_smtp`.
2. Agregue el parámetro `enviar_correo: EnviarCorreo | None = None` a `crear_app`.
3. Después de `app.state.integraciones`, agregue `app.state.enviar_correo = enviar_correo or enviador_smtp(config.smtp_host, config.smtp_puerto)`.
4. Agregue `app.include_router(sesiones.router)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest services/negociacion -q`
Expected: PASS, incluida la prueba de permisos con las rutas nuevas.

Run: `uv run ruff format . && uv run ruff check . && uv run mypy`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add services/negociacion
git commit -m "feat(negociacion): publicar con invitaciones por correo, cancelar y reenviar el enlace" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 9: Portal del proveedor y turnos del agente

**Files:**
- Create: `services/negociacion/src/negociacion/turnos.py`
- Create: `services/negociacion/src/negociacion/api/portal.py`
- Modify: `services/negociacion/src/negociacion/textos.py`, `services/negociacion/src/negociacion/consultas.py`, `services/negociacion/src/negociacion/api/esquemas.py`, `services/negociacion/src/negociacion/api/dependencias.py`, `services/negociacion/src/negociacion/main.py`
- Modify: `services/negociacion/tests/conftest.py` (fixtures `ofertar` y `con_plazo_de_pago`), `services/negociacion/tests/test_api_permisos.py`
- Test: `services/negociacion/tests/test_portal.py`, `services/negociacion/tests/test_textos.py`

**Interfaces:**
- Consumes:
  - `decidir`, `Estado`, `BETA`, `Decision` (Task 4);
  - `Terminos`, `Valores`, `utilidad`, `es_valida`, `problema_de_valor` (Task 3);
  - `consultas.*` y `bitacora.*` (Task 6); `hash_de` (Task 8).
- Produces:
  - **`negociacion.textos`:** `CONTRAOFERTA`, `MEJOR_OFERTA`, `ULTIMA_RONDA`, `ACUERDO`, `SIN_ACUERDO`, `EN_REVISION`, `ESCALADA`, `PIDE_PERSONA` y `respuesta_del_agente(decision, nombres) -> str`.
  - **`negociacion.consultas`:** `terminos_de(bd, evento) -> Terminos`, `ultima_contraoferta(bd, sesion_id) -> Valores | None` y `vista_portal(bd, sesion_id) -> VistaPortal`.
  - **`negociacion.turnos`:**
    - `bloquear`, `exigir_en_curso`, `exigir_tasa` y `ya_recibido`;
    - `valores_de(terminos, entrada, prefijo) -> Valores`;
    - `guardar_oferta(...) -> Oferta`;
    - `responder(...)` (el agente);
    - `recibir_oferta(bd, sesion_id, entrada, clave, momento)` y `escalar(bd, sesion_id, clave, momento)`;
    - `cerrar_eventos_terminados(bd, momento, evento_id=None) -> list[uuid.UUID]`.
  - **`negociacion.api.dependencias`:** `ClaveIdempotencia`, el encabezado `Idempotency-Key` (8 a 64 caracteres `[A-Za-z0-9_-]`).
  - **Rutas:** `GET /portal/sesion`, `POST /portal/ofertas` y `POST /portal/escalar`. Las tres usan `Authorization: Invitacion <token>`.
  - **Esquemas:** `ValoresEntrada{precios: {id de línea: Decimal}, palancas: {clave: Decimal}}`, `ValoresSalida`, `OfertaPortal{valores, nota, confirmar_valores}`, `LineaPortal`, `PalancaPortal`, `MensajePortal` y `VistaPortal`.
  - **Fixtures:** `ofertar(enlace, precios, palancas=None, clave=None, **extra) -> httpx.Response` y `con_plazo_de_pago(**cambios) -> (evento, enlaces)`, que publica una compra con la palanca de plazo de pago (peso 20, ideal 60, límite 30).

- [ ] **Step 1: Write the failing tests**

En `conftest.py`, agregue:

```python
Ofertar = Callable[..., Awaitable[httpx.Response]]


def encabezados_portal(enlace: dict[str, Any], clave: str | None = None) -> dict[str, str]:
    token = enlace["enlace"].split("#t=")[1]
    return {"Authorization": f"Invitacion {token}", "Idempotency-Key": clave or uuid.uuid4().hex}


@pytest.fixture
def ofertar(cliente: httpx.AsyncClient) -> Ofertar:
    """Manda una oferta por el portal; `clave` fija la Idempotency-Key, `extra` va en el cuerpo."""

    async def _ofertar(
        enlace: dict[str, Any],
        precios: dict[str, str],
        palancas: dict[str, str] | None = None,
        clave: str | None = None,
        **extra: Any,
    ) -> httpx.Response:
        cuerpo = {"valores": {"precios": precios, "palancas": palancas or {}}} | extra
        return await cliente.post(
            "/portal/ofertas", json=cuerpo, headers=encabezados_portal(enlace, clave)
        )

    return _ofertar


@pytest.fixture
def con_plazo_de_pago(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Compra
) -> Publicar:
    """Publica una compra con la palanca de plazo de pago (peso 20, ideal 60, límite 30)."""

    async def _publicar(**cambios: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        evento = await nueva_compra(**cambios)
        palancas = [
            {"clave": "precio", "peso": 80},
            {"clave": "plazo_pago_dias", "peso": 20, "ideal": "60", "limite": "30"},
        ]
        editado = await cliente.patch(
            f"/eventos/{evento['id']}", json={"version": 1, "palancas": palancas}, headers=comprador
        )
        assert editado.status_code == 200, editado.text
        publicado = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
        assert publicado.status_code == 200, publicado.text
        return publicado.json()["evento"], publicado.json()["enlaces"]

    return _publicar
```

Para que las pruebas usen `encabezados_portal` sin importar `conftest`, agregue también:

```python
@pytest.fixture
def portal() -> Callable[..., dict[str, str]]:
    return encabezados_portal
```

En `test_api_permisos.py`, agregue:

```python
async def test_el_portal_no_acepta_jwt(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    comprador = {"Authorization": f"Bearer {claves.token('comprador')}"}
    for metodo, ruta in (
        ("GET", "/portal/sesion"),
        ("POST", "/portal/ofertas"),
        ("POST", "/portal/escalar"),
    ):
        respuesta = await cliente.request(metodo, ruta, headers=comprador)
        assert respuesta.status_code == 401, ruta
```

`services/negociacion/tests/test_textos.py`:

```python
from negociacion.dominio.motor import Decision
from negociacion.textos import respuesta_del_agente

NOMBRES = {"a": "CRM profesional", "b": "Soporte", "c": "Nube"}


def test_la_contraoferta_suma_la_presion_y_la_ultima_ronda() -> None:
    simple = Decision("contraofertar", traza={"hay_mejor_oferta": False})
    assert respuesta_del_agente(simple, NOMBRES) == (
        "Gracias por su oferta. Le proponemos los términos que aparecen en la propuesta."
    )
    completa = Decision("contraofertar", ultima_ronda=True, traza={"hay_mejor_oferta": True})
    assert respuesta_del_agente(completa, NOMBRES) == (
        "Gracias por su oferta. Le proponemos los términos que aparecen en la propuesta. "
        "Hemos recibido propuestas más competitivas. "
        "La siguiente ronda es la última: envíe su mejor y última oferta."
    )


def test_la_aclaracion_nombra_las_lineas_en_singular_o_plural() -> None:
    una = Decision("pedir_aclaracion", dudosas=("a",))
    assert respuesta_del_agente(una, NOMBRES) == (
        "El precio de CRM profesional parece fuera de lo usual. Si es correcto, márquelo como "
        "confirmado y envíelo de nuevo."
    )
    tres = Decision("pedir_aclaracion", dudosas=("a", "b", "c"))
    assert respuesta_del_agente(tres, NOMBRES).startswith(
        "Los precios de CRM profesional, Soporte y Nube parecen fuera de lo usual."
    )


def test_ningun_mensaje_lleva_cifras() -> None:
    decisiones = [
        Decision("aceptar"),
        Decision("cerrar_sin_acuerdo"),
        Decision("contraofertar", ultima_ronda=True, traza={"hay_mejor_oferta": True}),
    ]
    for decision in decisiones:
        texto = respuesta_del_agente(decision, NOMBRES)
        assert not any(caracter.isdigit() for caracter in texto)
```

`services/negociacion/tests/test_portal.py`:

```python
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
from negociacion.modelos import Bitacora, Oferta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]
SIN_ACCESO = "El enlace no es válido o ya venció."


def _linea(evento: dict[str, Any]) -> str:
    return str(evento["lineas"][0]["id"])


async def test_sin_un_enlace_valido_responde_siempre_lo_mismo(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, portal: Any, reloj: Any
) -> None:
    evento, enlaces = await publicar()
    respuestas = [
        await cliente.get("/portal/sesion"),
        await cliente.get("/portal/sesion", headers={"Authorization": "Invitacion inventado"}),
        await cliente.get("/portal/sesion", headers=comprador),  # un JWT no sirve en el portal
    ]
    reloj.momento = datetime.fromisoformat(evento["fecha_limite"])
    respuestas.append(await cliente.get("/portal/sesion", headers=portal(enlaces[0])))
    for respuesta in respuestas:
        assert respuesta.status_code == 401
        assert respuesta.json()["detail"] == SIN_ACCESO


async def test_un_enlace_reemplazado_o_cancelado_deja_de_servir(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, portal: Any
) -> None:
    evento, enlaces = await publicar()
    await cliente.post(f"/sesiones/{enlaces[0]['sesion_id']}/invitacion", headers=comprador)
    assert (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).status_code == 401
    await cliente.post(
        f"/eventos/{evento['id']}/cancelar", json={"motivo": "Se pospuso"}, headers=comprador
    )
    assert (await cliente.get("/portal/sesion", headers=portal(enlaces[1]))).status_code == 401


async def test_la_vista_muestra_lo_negociable_sin_los_limites(
    cliente: httpx.AsyncClient, publicar: Any, portal: Any
) -> None:
    evento, enlaces = await publicar()
    vista = (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).json()
    assert (vista["folio"], vista["estado"], vista["rondas_restantes"]) == (
        evento["folio"],
        "invitada",
        6,
    )
    assert (vista["atendido_por"], vista["pide_confirmacion"]) == ("agente", False)
    assert [linea["nombre"] for linea in vista["lineas"]] == ["CRM profesional"]
    assert vista["palancas"] == [] and vista["mensajes"] == []
    assert vista["ultima_propuesta"] is None
    texto = json.dumps(vista)
    for prohibido in ('"ideal"', '"limite"', '"peso"', '"utilidad"', '"referencia"', "28.00"):
        assert prohibido not in texto, prohibido


async def test_una_oferta_cara_recibe_una_contraoferta(
    publicar: Any, ofertar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    respuesta = await ofertar(enlaces[0], {linea: "40.00"}, nota="Es nuestro precio de lista")
    assert respuesta.status_code == 200, respuesta.text
    vista = respuesta.json()
    assert (vista["estado"], vista["rondas_restantes"]) == ("activa", 5)
    assert [(m["autor"], m["ronda"]) for m in vista["mensajes"]] == [
        ("proveedor", 1),
        ("agente", 1),
    ]
    assert vista["mensajes"][0]["texto"] == "Es nuestro precio de lista"
    assert vista["mensajes"][1]["texto"].startswith("Gracias por su oferta.")
    propuesta = D(vista["ultima_propuesta"]["precios"][linea])
    assert D("28.00") < propuesta < D("31.50")
    async with fabrica() as bd:
        decision = await bd.scalar(select(Bitacora).where(Bitacora.accion == "motor.decision"))
    assert decision is not None
    assert decision.detalle["accion"] == "contraofertar"
    assert decision.detalle["mensaje_id"]


async def test_aceptar_la_propuesta_deja_un_acuerdo_tentativo(
    cliente: httpx.AsyncClient, publicar: Any, ofertar: Any, portal: Any
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    propuesta = (await ofertar(enlaces[0], {linea: "40.00"})).json()["ultima_propuesta"]
    vista = (await ofertar(enlaces[0], propuesta["precios"], propuesta["palancas"])).json()
    assert vista["estado"] == "acuerdo_tentativo"
    assert vista["mensajes"][-1]["texto"].startswith(
        "Gracias. Su oferta quedó registrada como acuerdo tentativo"
    )
    assert vista["ultima_propuesta"] is None
    despues = await ofertar(enlaces[0], {linea: "30.00"})
    assert despues.status_code == 409
    assert despues.json()["codigo"] == "negociacion_terminada"
    assert (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).status_code == 200


async def test_la_misma_clave_no_se_procesa_dos_veces(
    publicar: Any, ofertar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    primera = await ofertar(enlaces[0], {linea: "40.00"}, clave="clave-fija-0001")
    segunda = await ofertar(enlaces[0], {linea: "39.00"}, clave="clave-fija-0001")
    assert segunda.status_code == 200
    assert segunda.json() == primera.json()
    async with fabrica() as bd:
        propias = select(func.count()).select_from(Oferta).where(Oferta.autor == "proveedor")
        assert await bd.scalar(propias) == 1


async def test_limita_a_10_mensajes_por_minuto(
    publicar: Any, ofertar: Any, reloj: Any
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    for _ in range(10):  # precios fuera de lo usual: piden aclaración y no consumen ronda
        assert (await ofertar(enlaces[0], {linea: "9999.00"})).status_code == 200
    excedida = await ofertar(enlaces[0], {linea: "9999.00"})
    assert excedida.status_code == 429
    assert excedida.headers["retry-after"] == "60"
    reloj.momento += timedelta(seconds=61)
    assert (await ofertar(enlaces[0], {linea: "9999.00"})).status_code == 200


async def test_pide_aclaracion_y_procesa_al_confirmar(publicar: Any, ofertar: Any) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    vista = (await ofertar(enlaces[0], {linea: "3150.00"})).json()
    assert (vista["pide_confirmacion"], vista["rondas_restantes"]) == (True, 6)
    assert vista["mensajes"][-1]["texto"] == (
        "El precio de CRM profesional parece fuera de lo usual. Si es correcto, márquelo como "
        "confirmado y envíelo de nuevo."
    )
    confirmada = (await ofertar(enlaces[0], {linea: "3150.00"}, confirmar_valores=True)).json()
    assert (confirmada["pide_confirmacion"], confirmada["rondas_restantes"]) == (False, 5)


async def test_una_oferta_con_forma_equivocada_da_422_por_campo(
    publicar: Any, ofertar: Any
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    ajena = str(uuid.uuid4())
    mala = await ofertar(enlaces[0], {linea: "30.123", ajena: "10.00"}, {"plazo_meses": "12"})
    assert mala.status_code == 422
    assert mala.json()["codigo"] == "oferta_invalida"
    assert mala.json()["errores"] == [
        {
            "campo": f"valores.precios.{ajena}",
            "mensaje": "Esta línea no es parte de la negociación.",
        },
        {"campo": "valores.palancas.plazo_meses", "mensaje": "Este término no se negocia aquí."},
        {"campo": f"valores.precios.{linea}", "mensaje": "Use como máximo 2 decimales."},
    ]
    sin_precio = await ofertar(enlaces[0], {})
    assert sin_precio.json()["errores"] == [
        {"campo": f"valores.precios.{linea}", "mensaje": "Indique el precio de esta línea."}
    ]
    cero = await ofertar(enlaces[0], {linea: "0"})
    assert cero.json()["errores"][0]["mensaje"] == "Debe ser mayor que 0."
    no_numero = await ofertar(enlaces[0], {linea: "NaN"})
    assert no_numero.status_code == 422


async def test_las_palancas_se_negocian_y_se_exigen(
    cliente: httpx.AsyncClient, con_plazo_de_pago: Any, ofertar: Any, portal: Any
) -> None:
    evento, enlaces = await con_plazo_de_pago()
    linea = _linea(evento)
    vista = (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).json()
    assert vista["palancas"] == [
        {"clave": "plazo_pago_dias", "nombre": "Plazo de pago", "unidad": "días"}
    ]
    falta = await ofertar(enlaces[0], {linea: "31.00"})
    assert falta.json()["errores"] == [
        {"campo": "valores.palancas.plazo_pago_dias", "mensaje": "Indique este valor."}
    ]
    vista = (await ofertar(enlaces[0], {linea: "31.00"}, {"plazo_pago_dias": "15"})).json()
    pago = D(vista["ultima_propuesta"]["palancas"]["plazo_pago_dias"])
    assert D(30) < pago <= D(60)  # pidió 15 días (más allá del límite) y no se le contesta el límite


async def test_escalar_pasa_la_sesion_a_una_persona(
    cliente: httpx.AsyncClient, publicar: Any, ofertar: Any, portal: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    vista = (await cliente.post("/portal/escalar", headers=portal(enlaces[0]))).json()
    assert (vista["estado"], vista["atendido_por"]) == ("escalada", "persona")
    assert [m["autor"] for m in vista["mensajes"]] == ["proveedor", "sistema"]
    despues = (await ofertar(enlaces[0], {linea: "35.00"})).json()
    assert despues["rondas_restantes"] == 5
    assert (despues["mensajes"][-1]["autor"], despues["mensajes"][-1]["texto"]) == (
        "sistema",
        "Una persona del equipo de compras revisará su oferta y le responderá.",
    )
    async with fabrica() as bd:
        decisiones = select(func.count()).where(Bitacora.accion == "motor.decision")
        assert await bd.scalar(decisiones) == 0


async def test_avisa_si_otro_proveedor_ofrece_mejor(publicar: Any, ofertar: Any) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    await ofertar(enlaces[0], {linea: "30.00"})  # válida y mejor
    vista = (await ofertar(enlaces[1], {linea: "31.00"})).json()
    assert "Hemos recibido propuestas más competitivas." in vista["mensajes"][-1]["texto"]


async def test_en_la_ultima_ronda_cierra_y_el_evento_pasa_a_evaluacion(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    ids: dict[str, str],
) -> None:
    evento, enlaces = await publicar(rondas_max=2, proveedores=[ids["nube_norte"]])
    linea = _linea(evento)
    primera = (await ofertar(enlaces[0], {linea: "40.00"})).json()
    assert "La siguiente ronda es la última" in primera["mensajes"][-1]["texto"]
    segunda = (await ofertar(enlaces[0], {linea: "40.00"})).json()
    assert segunda["estado"] == "sin_acuerdo"
    assert segunda["mensajes"][-1]["texto"] == (
        "Gracias por su tiempo. En esta ocasión no fue posible llegar a un acuerdo."
    )
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "en_evaluacion"


async def test_dos_ofertas_a_la_vez_se_procesan_una_tras_otra(
    publicar: Any, ofertar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    primera, segunda = await asyncio.gather(
        ofertar(enlaces[0], {linea: "40.00"}), ofertar(enlaces[0], {linea: "39.00"})
    )
    assert (primera.status_code, segunda.status_code) == (200, 200)
    async with fabrica() as bd:
        consulta = select(Oferta.ronda).where(Oferta.autor == "proveedor")
        assert sorted((await bd.scalars(consulta)).all()) == [1, 2]


async def test_ninguna_respuesta_del_portal_revela_limites_pesos_ni_referencia(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, portal: Any
) -> None:
    borrador = await nueva_compra()
    cambios = {
        "version": 1,
        "lineas": [
            {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "100", "ideal": "27.13", "limite": "31.17"}
        ],
        "palancas": [
            {"clave": "precio", "peso": 80},
            {"clave": "plazo_pago_dias", "peso": 20, "ideal": "57", "limite": "33"},
        ],
    }
    editado = await cliente.patch(f"/eventos/{borrador['id']}", json=cambios, headers=comprador)
    assert editado.status_code == 200, editado.text
    publicado = (
        await cliente.post(f"/eventos/{borrador['id']}/publicar", headers=comprador)
    ).json()
    linea = _linea(publicado["evento"])  # al reemplazar las líneas cambió su id
    enlace = publicado["enlaces"][0]
    textos = [(await cliente.get("/portal/sesion", headers=portal(enlace))).text]
    for precio, pago in (("40.00", "20"), ("35.00", "25"), ("33.00", "30")):
        cuerpo = {"valores": {"precios": {linea: precio}, "palancas": {"plazo_pago_dias": pago}}}
        respuesta = await cliente.post("/portal/ofertas", json=cuerpo, headers=portal(enlace))
        assert respuesta.status_code == 200, respuesta.text
        textos.append(respuesta.text)
    texto = " ".join(textos)
    for prohibido in (
        "27.13",
        "31.17",
        '"57"',
        '"33"',
        "28.0000",
        "31.5000",
        "36.0000",
        '"ideal"',
        '"limite"',
        '"peso"',
        '"utilidad"',
        '"referencia"',
    ):
        assert prohibido not in texto, prohibido
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest services/negociacion/tests/test_textos.py services/negociacion/tests/test_portal.py -q`
Expected: FAIL. `respuesta_del_agente` no existe y `/portal/sesion` responde 404.

- [ ] **Step 3: Write the implementation**

Al final de `textos.py`, agregue:

```python
from collections.abc import Mapping

from negociacion.dominio.motor import Decision

CONTRAOFERTA = "Gracias por su oferta. Le proponemos los términos que aparecen en la propuesta."
MEJOR_OFERTA = "Hemos recibido propuestas más competitivas."
ULTIMA_RONDA = "La siguiente ronda es la última: envíe su mejor y última oferta."
ACUERDO = (
    "Gracias. Su oferta quedó registrada como acuerdo tentativo; no es vinculante hasta que se "
    "apruebe la adjudicación."
)
SIN_ACUERDO = "Gracias por su tiempo. En esta ocasión no fue posible llegar a un acuerdo."
EN_REVISION = "Una persona del equipo de compras revisará su oferta y le responderá."
ESCALADA = "Avisamos al equipo de compras; una persona le responderá aquí."
PIDE_PERSONA = "Pidió hablar con una persona del equipo de compras."


def _unir(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def respuesta_del_agente(decision: Decision, nombres: Mapping[str, str]) -> str:
    """El mensaje del agente (plantillas de N1): nunca lleva límites, pesos, utilidades ni cifras."""
    if decision.accion == "aceptar":
        return ACUERDO
    if decision.accion == "cerrar_sin_acuerdo":
        return SIN_ACUERDO
    if decision.accion == "pedir_aclaracion":
        lineas = [nombres[i] for i in decision.dudosas]
        if len(lineas) == 1:
            return (
                f"El precio de {lineas[0]} parece fuera de lo usual. Si es correcto, márquelo "
                "como confirmado y envíelo de nuevo."
            )
        return (
            f"Los precios de {_unir(lineas)} parecen fuera de lo usual. Si son correctos, "
            "márquelos como confirmados y envíelos de nuevo."
        )
    partes = [CONTRAOFERTA]
    if decision.traza.get("hay_mejor_oferta"):
        partes.append(MEJOR_OFERTA)
    if decision.ultima_ronda:
        partes.append(ULTIMA_RONDA)
    return " ".join(partes)
```

(Mueva las importaciones nuevas al inicio del archivo, como pide ruff.)

En `api/dependencias.py`, agregue:

```python
from fastapi import Header

ClaveIdempotencia = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]
```

Al final de `api/esquemas.py`, agregue:

```python
class ValoresEntrada(BaseModel):
    precios: dict[uuid.UUID, Decimal]  # id de línea → precio unitario
    palancas: dict[str, Decimal] = Field(default_factory=dict)


class ValoresSalida(BaseModel):
    precios: dict[str, Decimal]
    palancas: dict[str, Decimal]


Nota = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class OfertaPortal(BaseModel):
    valores: ValoresEntrada
    nota: Nota = ""  # el comprador la ve tal cual; nadie la interpreta hasta N2
    confirmar_valores: bool = False


class LineaPortal(BaseModel):
    id: uuid.UUID
    codigo_servicio: str
    nombre: str
    unidad: str
    cantidad: Decimal


class PalancaPortal(BaseModel):
    clave: str
    nombre: str
    unidad: str


class MensajePortal(BaseModel):
    autor: str
    texto: str
    ronda: int
    fecha: datetime
    oferta: ValoresSalida | None


class VistaPortal(BaseModel):
    """Lo que ve el proveedor: nunca ideales, límites, pesos, utilidades ni la referencia."""

    folio: str
    titulo: str
    moneda: str
    fecha_limite: datetime
    rondas_max: int
    rondas_restantes: int
    estado: str
    atendido_por: Literal["agente", "persona"]
    pide_confirmacion: bool
    lineas: list[LineaPortal]
    palancas: list[PalancaPortal]
    mensajes: list[MensajePortal]
    ultima_propuesta: ValoresSalida | None
```

En `consultas.py`:
1. Agregue las importaciones:

```python
from negociacion.dominio.terminos import Linea as LineaTermino
from negociacion.dominio.terminos import Palanca as PalancaTermino
from negociacion.dominio.terminos import Rango, Terminos, Valores
from negociacion.modelos import FINALES, Mensaje
```

2. Agregue las funciones:

```python
def _rango(ideal: Decimal | None, limite: Decimal | None) -> Rango:
    if ideal is None or limite is None:
        raise RuntimeError("Un evento publicado siempre tiene ideal y límite")
    return Rango(ideal, limite)


async def terminos_de(bd: AsyncSession, evento: Evento) -> Terminos:
    """Los términos del motor a partir de la configuración guardada del evento publicado."""
    lineas = await lineas_de(bd, evento.id)
    palancas = await palancas_de(bd, evento.id)
    return Terminos(
        peso_precio=palancas["precio"].peso,
        lineas=tuple(
            LineaTermino(
                str(linea.id),
                linea.nombre,
                linea.cantidad,
                _rango(linea.ideal, linea.limite),
                None if (banda := banda_de(linea.referencia)) is None else banda.p50,
            )
            for linea in lineas
        ),
        palancas=tuple(
            PalancaTermino(p.clave, p.peso, _rango(p.ideal, p.limite))
            for p in palancas.values()
            if p.clave != "precio"
        ),
    )


async def ultima_contraoferta(bd: AsyncSession, sesion_id: uuid.UUID) -> Valores | None:
    """La última contraoferta de la sesión, del agente o del comprador."""
    fila = await bd.scalar(
        select(Oferta)
        .where(Oferta.sesion_id == sesion_id, Oferta.autor.in_(("agente", "comprador")))
        .order_by(Oferta.secuencia.desc())
        .limit(1)
    )
    return None if fila is None else Valores.de_json(fila.valores)


def valores_salida(valores: Valores) -> esquemas.ValoresSalida:
    return esquemas.ValoresSalida(precios=dict(valores.precios), palancas=dict(valores.palancas))


async def vista_portal(bd: AsyncSession, sesion_id: uuid.UUID) -> esquemas.VistaPortal:
    sesion = await bd.get(SesionNegociacion, sesion_id, populate_existing=True)
    if sesion is None:
        raise no_existe("La sesión no existe.")
    evento = await evento_o_404(bd, sesion.evento_id)
    lineas = await lineas_de(bd, evento.id)
    palancas = [p for p in (await palancas_de(bd, evento.id)).values() if p.clave != "precio"]
    filas = (
        await bd.execute(
            select(Mensaje, Oferta)
            .outerjoin(Oferta, Oferta.id == Mensaje.oferta_id)
            .where(Mensaje.sesion_id == sesion.id)
            .order_by(Mensaje.secuencia)
        )
    ).tuples().all()
    en_curso = sesion.estado not in FINALES
    conversacion = [m for m, _ in filas if m.autor != "sistema"]
    # Una respuesta del agente sin propuesta, con la sesión en curso, es una aclaración pendiente.
    pide = (
        en_curso
        and bool(conversacion)
        and conversacion[-1].autor == "agente"
        and conversacion[-1].oferta_id is None
    )
    ultima = await ultima_contraoferta(bd, sesion.id) if en_curso else None
    return esquemas.VistaPortal(
        folio=evento.folio,
        titulo=evento.titulo,
        moneda=evento.moneda,
        fecha_limite=evento.fecha_limite,
        rondas_max=evento.rondas_max,
        rondas_restantes=max(evento.rondas_max - sesion.ronda, 0),
        estado=sesion.estado,
        atendido_por="persona" if sesion.modo == "comprador" else "agente",
        pide_confirmacion=pide,
        lineas=[
            esquemas.LineaPortal(
                id=linea.id,
                codigo_servicio=linea.codigo_servicio,
                nombre=linea.nombre,
                unidad=linea.unidad,
                cantidad=linea.cantidad,
            )
            for linea in lineas
        ],
        palancas=[
            esquemas.PalancaPortal(
                clave=p.clave,
                nombre=nombre_y_unidad(p.clave, evento.moneda)[0],
                unidad=nombre_y_unidad(p.clave, evento.moneda)[1],
            )
            for p in palancas
        ],
        mensajes=[
            esquemas.MensajePortal(
                autor=mensaje.autor,
                texto=mensaje.texto,
                ronda=mensaje.ronda,
                fecha=mensaje.creado_en,
                oferta=None if oferta is None else valores_salida(Valores.de_json(oferta.valores)),
            )
            for mensaje, oferta in filas
        ],
        ultima_propuesta=None if ultima is None else valores_salida(ultima),
    )
```

`services/negociacion/src/negociacion/turnos.py`:

```python
"""Turnos de una sesión: la oferta del proveedor y la respuesta del agente (spec §8.3).

Cada turno corre en una transacción con la sesión bloqueada (FOR UPDATE): dos ofertas a la vez se
procesan una tras otra y la ronda nunca se salta.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion import consultas, textos
from negociacion.api import esquemas
from negociacion.bitacora import AGENTE, SISTEMA, Actor, registrar
from negociacion.dominio.motor import BETA, Estado, decidir
from negociacion.dominio.terminos import Terminos, Valores, es_valida, problema_de_valor, utilidad
from negociacion.errores import conflicto, invalidos, no_existe
from negociacion.modelos import FINALES, Evento, Mensaje, Oferta, SesionNegociacion

LIMITE_POR_MINUTO = 10  # mensajes del proveedor por sesión (spec §8.2)
CUATRO_DECIMALES = Decimal("0.0001")


def actor_proveedor(sesion: SesionNegociacion) -> Actor:
    return Actor("proveedor", str(sesion.proveedor_id), sesion.proveedor_nombre)


async def bloquear(
    bd: AsyncSession, sesion_id: uuid.UUID
) -> tuple[SesionNegociacion, Evento]:
    sesion = await bd.get(
        SesionNegociacion, sesion_id, with_for_update=True, populate_existing=True
    )
    if sesion is None:
        raise no_existe("La sesión no existe.")
    return sesion, await consultas.evento_o_404(bd, sesion.evento_id)


def exigir_en_curso(sesion: SesionNegociacion, evento: Evento, momento: datetime) -> None:
    if evento.estado != "abierto" or sesion.estado in FINALES or momento >= evento.fecha_limite:
        raise conflicto("La negociación terminó.", "negociacion_terminada")


async def exigir_tasa(bd: AsyncSession, sesion_id: uuid.UUID, momento: datetime) -> None:
    recientes = await bd.scalar(
        select(func.count())
        .select_from(Mensaje)
        .where(
            Mensaje.sesion_id == sesion_id,
            Mensaje.autor == "proveedor",
            Mensaje.creado_en > momento - timedelta(minutes=1),
        )
    )
    if (recientes or 0) >= LIMITE_POR_MINUTO:
        raise HTTPException(
            429,
            "Envió demasiados mensajes; espere un minuto e intente de nuevo.",
            headers={"Retry-After": "60"},
        )


async def ya_recibido(bd: AsyncSession, sesion_id: uuid.UUID, clave: str) -> bool:
    consulta = select(Mensaje.id).where(
        Mensaje.sesion_id == sesion_id, Mensaje.clave_idempotencia == clave
    )
    return (await bd.scalar(consulta)) is not None


def valores_de(terminos: Terminos, entrada: esquemas.ValoresEntrada, prefijo: str) -> Valores:
    """Los valores de una oferta, con un error por campo si no cuadran con los términos."""
    precios = {str(k): v for k, v in entrada.precios.items()}
    errores: list[dict[str, str]] = []
    for linea_id in sorted(precios.keys() - {linea.id for linea in terminos.lineas}):
        errores.append(
            {
                "campo": f"{prefijo}.precios.{linea_id}",
                "mensaje": "Esta línea no es parte de la negociación.",
            }
        )
    for clave in sorted(entrada.palancas.keys() - {p.clave for p in terminos.palancas}):
        errores.append(
            {"campo": f"{prefijo}.palancas.{clave}", "mensaje": "Este término no se negocia aquí."}
        )
    for linea in terminos.lineas:
        precio = precios.get(linea.id)
        mensaje = (
            "Indique el precio de esta línea."
            if precio is None
            else problema_de_valor("precio", precio)
        )
        if mensaje is not None:
            errores.append({"campo": f"{prefijo}.precios.{linea.id}", "mensaje": mensaje})
    for palanca in terminos.palancas:
        valor = entrada.palancas.get(palanca.clave)
        mensaje = (
            "Indique este valor." if valor is None else problema_de_valor(palanca.clave, valor)
        )
        if mensaje is not None:
            errores.append({"campo": f"{prefijo}.palancas.{palanca.clave}", "mensaje": mensaje})
    if errores:
        raise invalidos(errores, "oferta_invalida")
    return Valores(
        {linea.id: precios[linea.id] for linea in terminos.lineas},
        {p.clave: entrada.palancas[p.clave] for p in terminos.palancas},
    )


def guardar_oferta(
    bd: AsyncSession,
    sesion_id: uuid.UUID,
    autor: str,
    ronda: int,
    terminos: Terminos,
    valores: Valores,
    momento: datetime,
    confirmada: bool = False,
) -> Oferta:
    oferta = Oferta(
        sesion_id=sesion_id,
        autor=autor,
        ronda=ronda,
        valores=valores.a_json(),
        utilidad=Decimal(repr(utilidad(terminos, valores))).quantize(CUATRO_DECIMALES),
        valida=es_valida(terminos, valores),
        fuera_de_limites_confirmada=confirmada,
        creado_en=momento,
    )
    bd.add(oferta)
    return oferta


async def hay_mejor_oferta(
    bd: AsyncSession, evento_id: uuid.UUID, sesion_id: uuid.UUID, utilidad_oferta: Decimal
) -> bool:
    """Si otra sesión del evento tiene una oferta válida mejor; nunca se dice cuál ni de quién."""
    consulta = (
        select(Oferta.id)
        .join(SesionNegociacion, SesionNegociacion.id == Oferta.sesion_id)
        .where(
            SesionNegociacion.evento_id == evento_id,
            Oferta.sesion_id != sesion_id,
            Oferta.autor == "proveedor",
            Oferta.valida.is_(True),
            Oferta.utilidad > utilidad_oferta,
        )
        .limit(1)
    )
    return (await bd.scalar(consulta)) is not None


async def responder(
    bd: AsyncSession,
    evento: Evento,
    sesion: SesionNegociacion,
    terminos: Terminos,
    oferta: Valores,
    utilidad_oferta: Decimal,
    ronda: int,
    confirmar: bool,
    momento: datetime,
) -> None:
    """El agente decide con el motor y responde; la traza queda en la bitácora."""
    estado = Estado(
        ronda=ronda,
        rondas=evento.rondas_max,
        beta=BETA[evento.estilo],
        anterior=await consultas.ultima_contraoferta(bd, sesion.id),
        hay_mejor_oferta=await hay_mejor_oferta(bd, evento.id, sesion.id, utilidad_oferta),
    )
    decision = decidir(terminos, estado, oferta, confirmar)
    if decision.accion != "pedir_aclaracion":  # la aclaración no consume la ronda
        sesion.ronda = max(sesion.ronda, ronda)
    propuesta_id = None
    if decision.contraoferta is not None:
        propuesta = guardar_oferta(
            bd, sesion.id, "agente", ronda, terminos, decision.contraoferta, momento
        )
        await bd.flush()
        propuesta_id = propuesta.id
    nombres = {linea.id: linea.nombre for linea in terminos.lineas}
    mensaje = Mensaje(
        sesion_id=sesion.id,
        autor="agente",
        texto=textos.respuesta_del_agente(decision, nombres),
        ronda=ronda,
        oferta_id=propuesta_id,
        creado_en=momento,
    )
    bd.add(mensaje)
    await bd.flush()
    registrar(
        bd,
        "motor.decision",
        AGENTE,
        evento_id=evento.id,
        sesion_id=sesion.id,
        detalle=decision.traza | {"mensaje_id": str(mensaje.id)},
        fecha=momento,
    )
    if decision.accion == "aceptar":
        sesion.estado = "acuerdo_tentativo"
    elif decision.accion == "cerrar_sin_acuerdo":
        sesion.estado = "sin_acuerdo"


async def cerrar_eventos_terminados(
    bd: AsyncSession, momento: datetime, evento_id: uuid.UUID | None = None
) -> list[uuid.UUID]:
    """Pasa a evaluación los eventos abiertos sin sesiones en curso o con la fecha límite vencida.

    ponytail: dos turnos que cierran a la vez las dos últimas sesiones no se ven entre sí y ninguno
    cierra el evento; la tarea de la fecha límite (vencimientos.py) lo cierra en menos de un minuto.
    """
    en_curso = (
        select(SesionNegociacion.id)
        .where(SesionNegociacion.evento_id == Evento.id, SesionNegociacion.estado.not_in(FINALES))
        .correlate(Evento)
        .exists()
    )
    consulta = (
        update(Evento)
        .where(Evento.estado == "abierto", or_(~en_curso, Evento.fecha_limite <= momento))
        .values(estado="en_evaluacion", cerrado_en=momento)
        .returning(Evento.id)
        .execution_options(synchronize_session=False)
    )
    if evento_id is not None:
        consulta = consulta.where(Evento.id == evento_id)
    cerrados = list((await bd.scalars(consulta)).all())
    for cerrado in cerrados:
        registrar(bd, "evento.en_evaluacion", SISTEMA, evento_id=cerrado, fecha=momento)
    return cerrados


async def recibir_oferta(
    bd: AsyncSession,
    sesion_id: uuid.UUID,
    entrada: esquemas.OfertaPortal,
    clave: str,
    momento: datetime,
) -> None:
    sesion, evento = await bloquear(bd, sesion_id)
    if await ya_recibido(bd, sesion.id, clave):
        return
    exigir_en_curso(sesion, evento, momento)
    await exigir_tasa(bd, sesion.id, momento)
    terminos = await consultas.terminos_de(bd, evento)
    oferta = valores_de(terminos, entrada.valores, "valores")
    ronda = sesion.ronda + 1
    fila = guardar_oferta(bd, sesion.id, "proveedor", ronda, terminos, oferta, momento)
    await bd.flush()
    bd.add(
        Mensaje(
            sesion_id=sesion.id,
            autor="proveedor",
            texto=entrada.nota,
            ronda=ronda,
            oferta_id=fila.id,
            clave_idempotencia=clave,
            creado_en=momento,
        )
    )
    registrar(
        bd,
        "oferta.recibida",
        actor_proveedor(sesion),
        evento_id=evento.id,
        sesion_id=sesion.id,
        detalle={"ronda": ronda, "utilidad": float(fila.utilidad), "valida": fila.valida},
        fecha=momento,
    )
    if sesion.estado == "invitada":
        sesion.estado = "activa"
    sesion.actualizado_en = momento
    if sesion.modo == "comprador":  # la oferta espera a la persona
        sesion.ronda = ronda
        bd.add(
            Mensaje(
                sesion_id=sesion.id,
                autor="sistema",
                texto=textos.EN_REVISION,
                ronda=ronda,
                creado_en=momento,
            )
        )
    else:
        await responder(
            bd,
            evento,
            sesion,
            terminos,
            oferta,
            fila.utilidad,
            ronda,
            entrada.confirmar_valores,
            momento,
        )
    await cerrar_eventos_terminados(bd, momento, evento.id)


async def escalar(bd: AsyncSession, sesion_id: uuid.UUID, clave: str, momento: datetime) -> None:
    sesion, evento = await bloquear(bd, sesion_id)
    if await ya_recibido(bd, sesion.id, clave):
        return
    exigir_en_curso(sesion, evento, momento)
    await exigir_tasa(bd, sesion.id, momento)
    bd.add(
        Mensaje(
            sesion_id=sesion.id,
            autor="proveedor",
            texto=textos.PIDE_PERSONA,
            ronda=sesion.ronda,
            clave_idempotencia=clave,
            creado_en=momento,
        )
    )
    if sesion.estado == "escalada":
        return
    bd.add(
        Mensaje(
            sesion_id=sesion.id,
            autor="sistema",
            texto=textos.ESCALADA,
            ronda=sesion.ronda,
            creado_en=momento,
        )
    )
    sesion.estado, sesion.modo, sesion.actualizado_en = "escalada", "comprador", momento
    registrar(
        bd,
        "sesion.escalada",
        actor_proveedor(sesion),
        evento_id=evento.id,
        sesion_id=sesion.id,
        fecha=momento,
    )
```

`services/negociacion/src/negociacion/api/portal.py`:

```python
"""API del portal del proveedor (spec §8): autentica con el token de invitación, no con un JWT."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select

from negociacion import consultas, turnos
from negociacion.api import esquemas
from negociacion.api.dependencias import Bd, ClaveIdempotencia, Reloj
from negociacion.modelos import Evento, SesionNegociacion
from negociacion.tokens import hash_de

router = APIRouter(prefix="/portal", tags=["portal"])


def _sin_acceso() -> HTTPException:
    # Siempre la misma respuesta: no distingue un token falso, uno revocado y uno vencido.
    return HTTPException(
        401, "El enlace no es válido o ya venció.", headers={"WWW-Authenticate": "Invitacion"}
    )


async def _sesion_del_enlace(
    bd: Bd, reloj: Reloj, authorization: Annotated[str | None, Header()] = None
) -> uuid.UUID:
    esquema, _, token = (authorization or "").partition(" ")
    if esquema.lower() != "invitacion" or not token.strip():
        raise _sin_acceso()
    async with bd.begin():
        fila = (
            await bd.execute(
                select(SesionNegociacion.id, Evento.estado, Evento.fecha_limite)
                .join(Evento, Evento.id == SesionNegociacion.evento_id)
                .where(SesionNegociacion.token_hash == hash_de(token.strip()))
            )
        ).first()
    if fila is None or fila.estado == "cancelado" or reloj() >= fila.fecha_limite:
        raise _sin_acceso()
    return fila.id


SesionDelEnlace = Annotated[uuid.UUID, Depends(_sesion_del_enlace)]


@router.get("/sesion")
async def ver_sesion(sesion_id: SesionDelEnlace, bd: Bd) -> esquemas.VistaPortal:
    return await consultas.vista_portal(bd, sesion_id)


@router.post("/ofertas")
async def ofertar(
    datos: esquemas.OfertaPortal,
    sesion_id: SesionDelEnlace,
    clave: ClaveIdempotencia,
    bd: Bd,
    reloj: Reloj,
) -> esquemas.VistaPortal:
    async with bd.begin():
        await turnos.recibir_oferta(bd, sesion_id, datos, clave, reloj())
    return await consultas.vista_portal(bd, sesion_id)


@router.post("/escalar")
async def escalar(
    sesion_id: SesionDelEnlace, clave: ClaveIdempotencia, bd: Bd, reloj: Reloj
) -> esquemas.VistaPortal:
    async with bd.begin():
        await turnos.escalar(bd, sesion_id, clave, reloj())
    return await consultas.vista_portal(bd, sesion_id)
```

En `main.py`, importe `portal` junto a los otros routers (`from negociacion.api import eventos, portal, sesiones`) y agregue `app.include_router(portal.router)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest services/negociacion -q`
Expected: PASS.

Run: `uv run ruff format . && uv run ruff check . && uv run mypy`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add services/negociacion
git commit -m "feat(negociacion): portal del proveedor con turnos del agente, idempotencia y límite de tasa" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Supervisión del comprador: detalle, control y respuestas manuales

**Files:**
- Modify: `services/negociacion/src/negociacion/turnos.py`, `services/negociacion/src/negociacion/consultas.py`, `services/negociacion/src/negociacion/api/esquemas.py`, `services/negociacion/src/negociacion/api/sesiones.py`
- Modify: `services/negociacion/tests/test_api_permisos.py`
- Test: `services/negociacion/tests/test_supervision.py`

**Interfaces:**
- Consumes: todo `turnos` (Task 9), `consultas.terminos_de` y `valores_salida`.
- Produces:
  - **`turnos`:** `tomar_control(bd, sesion_id, actor, momento)`, `devolver_control(bd, sesion_id, actor, momento)`, `responder_a_mano(bd, sesion_id, datos, actor, clave, momento)`, `oferta_sin_respuesta(bd, sesion_id) -> Oferta | None` y `ultima_oferta_proveedor(bd, sesion_id) -> Oferta | None`.
  - **`consultas`:** `sesion_detalle(bd, sesion_id) -> SesionDetalle`.
  - **Rutas:**
    - `GET /sesiones/{id}` (lectores);
    - `POST /sesiones/{id}/control` con `{"accion": "tomar" | "devolver"}` (comprador);
    - `POST /sesiones/{id}/respuestas` con `Respuesta` e `Idempotency-Key` (comprador).
  - **Esquemas:** `Control`, `Respuesta`, `LineaDetalle`, `PalancaDetalle`, `OfertaDetalle`, `MensajeDetalle` y `SesionDetalle`. En `MensajeDetalle`, `decision` es la traza del motor.

- [ ] **Step 1: Write the failing tests**

En `test_api_permisos.py`, agregue a `ESPERADAS`:

```python
    ("GET", "/sesiones/{sesion_id}"),
    ("POST", "/sesiones/{sesion_id}/control"),
    ("POST", "/sesiones/{sesion_id}/respuestas"),
```

`services/negociacion/tests/test_supervision.py`:

```python
from decimal import Decimal as D
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integracion


def _linea(evento: dict[str, Any]) -> str:
    return str(evento["lineas"][0]["id"])


async def _control(
    cliente: httpx.AsyncClient, comprador: dict[str, str], sesion: str, accion: str
) -> httpx.Response:
    return await cliente.post(
        f"/sesiones/{sesion}/control", json={"accion": accion}, headers=comprador
    )


async def _responder(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    sesion: str,
    clave: str = "respuesta-0001",
    **cuerpo: Any,
) -> httpx.Response:
    return await cliente.post(
        f"/sesiones/{sesion}/respuestas",
        json=cuerpo,
        headers=comprador | {"Idempotency-Key": clave},
    )


async def test_la_sesion_muestra_la_traza_de_cada_respuesta_del_agente(
    cliente: httpx.AsyncClient, aprobador: dict[str, str], publicar: Any, ofertar: Any
) -> None:
    evento, enlaces = await publicar()
    await ofertar(enlaces[0], {_linea(evento): "40.00"})
    respuesta = await cliente.get(f"/sesiones/{enlaces[0]['sesion_id']}", headers=aprobador)
    assert respuesta.status_code == 200, respuesta.text
    detalle = respuesta.json()
    assert [m["autor"] for m in detalle["mensajes"]] == ["proveedor", "agente"]
    assert detalle["mensajes"][0]["decision"] is None
    traza = detalle["mensajes"][1]["decision"]
    assert (traza["accion"], traza["t"], traza["T"]) == ("contraofertar", 1, 6)
    assert [o["autor"] for o in detalle["ofertas"]] == ["proveedor", "agente"]
    assert detalle["ofertas"][0]["valida"] is False  # 40.00 cruza el límite de 31.50
    assert D(detalle["lineas"][0]["limite"]) == D("31.50")


async def test_con_el_control_el_comprador_responde_y_el_agente_espera(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    portal: Any,
) -> None:
    evento, enlaces = await publicar()
    linea, sesion = _linea(evento), enlaces[0]["sesion_id"]
    tomada = await _control(cliente, comprador, sesion, "tomar")
    assert tomada.json()["modo"] == "comprador"
    vista = (await ofertar(enlaces[0], {linea: "33.00"})).json()
    assert vista["atendido_por"] == "persona"
    assert vista["mensajes"][-1]["autor"] == "sistema"
    respuesta = await _responder(
        cliente,
        comprador,
        sesion,
        tipo="mensaje",
        texto="¿Puede llegar a 30?",
        contraoferta={"precios": {linea: "30.00"}},
    )
    assert respuesta.status_code == 200, respuesta.text
    vista = (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).json()
    assert (vista["mensajes"][-1]["autor"], vista["mensajes"][-1]["texto"]) == (
        "comprador",
        "¿Puede llegar a 30?",
    )
    assert D(vista["ultima_propuesta"]["precios"][linea]) == D(30)


async def test_una_contraoferta_fuera_de_limites_exige_confirmacion_y_queda_marcada(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    evento, enlaces = await publicar()
    linea, sesion = _linea(evento), enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    cuerpo = {"tipo": "mensaje", "texto": "Última propuesta", "contraoferta": {"precios": {linea: "32.00"}}}
    sin_confirmar = await _responder(cliente, comprador, sesion, "respuesta-0001", **cuerpo)
    assert sin_confirmar.status_code == 422
    assert sin_confirmar.json()["codigo"] == "fuera_de_limites"
    confirmada = await _responder(
        cliente, comprador, sesion, "respuesta-0002", confirmar_fuera_de_limites=True, **cuerpo
    )
    assert confirmada.status_code == 200, confirmada.text
    detalle = confirmada.json()
    assert detalle["fuera_de_limites"] is True
    assert detalle["ofertas"][-1]["fuera_de_limites_confirmada"] is True


async def test_responder_sin_el_control_da_409(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    _, enlaces = await publicar()
    respuesta = await _responder(
        cliente, comprador, enlaces[0]["sesion_id"], tipo="mensaje", texto="Hola"
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "sin_control"


async def test_aceptar_la_ultima_oferta_cierra_la_sesion_y_el_evento(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    ids: dict[str, str],
) -> None:
    evento, enlaces = await publicar(proveedores=[ids["nube_norte"]])
    sesion = enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    await ofertar(enlaces[0], {_linea(evento): "31.00"})
    aceptada = await _responder(cliente, comprador, sesion, tipo="aceptar")
    assert aceptada.status_code == 200, aceptada.text
    assert aceptada.json()["estado"] == "acuerdo_tentativo"
    assert aceptada.json()["mensajes"][-1]["texto"].startswith("Gracias. Su oferta quedó registrada")
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "en_evaluacion"


async def test_cerrar_sin_acuerdo(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    _, enlaces = await publicar()
    sesion = enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    cerrada = await _responder(cliente, comprador, sesion, tipo="cerrar")
    assert cerrada.json()["estado"] == "sin_acuerdo"
    assert cerrada.json()["mensajes"][-1]["texto"] == (
        "Gracias por su tiempo. En esta ocasión no fue posible llegar a un acuerdo."
    )


async def test_al_devolver_el_control_el_agente_responde_sin_retroceder(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, ofertar: Any
) -> None:
    evento, enlaces = await publicar()
    linea, sesion = _linea(evento), enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    await _responder(
        cliente,
        comprador,
        sesion,
        tipo="mensaje",
        texto="Le propongo 29",
        contraoferta={"precios": {linea: "29.00"}},
    )
    await ofertar(enlaces[0], {linea: "40.00"})  # queda pendiente: atiende una persona
    devuelta = await _control(cliente, comprador, sesion, "devolver")
    assert devuelta.status_code == 200, devuelta.text
    detalle = devuelta.json()
    assert detalle["modo"] == "agente"
    agente = [o for o in detalle["ofertas"] if o["autor"] == "agente"]
    assert len(agente) == 1
    # El comprador ya había ofrecido 29: el agente no vuelve a pedir menos.
    assert D(agente[0]["valores"]["precios"][linea]) >= D("29.00")


async def test_devolver_una_sesion_escalada_la_reactiva(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, portal: Any
) -> None:
    _, enlaces = await publicar()
    await cliente.post("/portal/escalar", headers=portal(enlaces[0]))
    devuelta = await _control(cliente, comprador, enlaces[0]["sesion_id"], "devolver")
    assert (devuelta.json()["estado"], devuelta.json()["modo"]) == ("activa", "agente")


async def test_la_misma_clave_de_respuesta_no_se_aplica_dos_veces(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    _, enlaces = await publicar()
    sesion = enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    for _ in range(2):
        respuesta = await _responder(
            cliente, comprador, sesion, "misma-clave-01", tipo="mensaje", texto="Hola"
        )
    assert [m["autor"] for m in respuesta.json()["mensajes"]] == ["comprador"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest services/negociacion/tests/test_supervision.py -q`
Expected: FAIL. `GET /sesiones/{id}` responde 405 (solo existe `POST …/invitacion`).

- [ ] **Step 3: Write the implementation**

Al final de `api/esquemas.py`, agregue:

```python
class Control(BaseModel):
    accion: Literal["tomar", "devolver"]


class Respuesta(BaseModel):
    tipo: Literal["mensaje", "aceptar", "cerrar"]
    texto: Nota = ""
    contraoferta: ValoresEntrada | None = None
    confirmar_fuera_de_limites: bool = False

    @model_validator(mode="after")
    def _segun_tipo(self) -> Self:
        if self.tipo == "mensaje" and not self.texto:
            raise ValueError("Escriba el mensaje para el proveedor.")
        if self.tipo != "mensaje" and self.contraoferta is not None:
            raise ValueError("Solo un mensaje puede llevar contraoferta.")
        return self


class LineaDetalle(BaseModel):
    id: uuid.UUID
    nombre: str
    unidad: str
    cantidad: Decimal
    ideal: Decimal | None
    limite: Decimal | None


class PalancaDetalle(BaseModel):
    clave: str
    nombre: str
    unidad: str
    peso: int
    ideal: Decimal | None
    limite: Decimal | None


class OfertaDetalle(BaseModel):
    id: uuid.UUID
    autor: str
    ronda: int
    valores: ValoresSalida
    utilidad: float
    valida: bool
    fuera_de_limites_confirmada: bool
    fecha: datetime


class MensajeDetalle(BaseModel):
    id: uuid.UUID
    autor: str
    texto: str
    ronda: int
    fecha: datetime
    oferta_id: uuid.UUID | None
    decision: dict[str, Any] | None  # la traza del motor en las respuestas del agente


class SesionDetalle(BaseModel):
    id: uuid.UUID
    evento_id: uuid.UUID
    folio: str
    titulo: str
    moneda: str
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    destinatario: str
    estado: str
    modo: str
    ronda: int
    rondas_max: int
    fuera_de_limites: bool
    correo_estado: str
    correo_error: str | None
    lineas: list[LineaDetalle]
    palancas: list[PalancaDetalle]
    mensajes: list[MensajeDetalle]
    ofertas: list[OfertaDetalle]
```

(Agregue `Any` a la importación de `typing` en `esquemas.py`.)

En `consultas.py`, agregue `Bitacora` a la importación de modelos y esta función:

```python
async def sesion_detalle(bd: AsyncSession, sesion_id: uuid.UUID) -> esquemas.SesionDetalle:
    """La sesión completa para el comprador: mensajes, ofertas con su utilidad y cada traza."""
    sesion = await bd.get(SesionNegociacion, sesion_id, populate_existing=True)
    if sesion is None:
        raise no_existe("La sesión no existe.")
    evento = await evento_o_404(bd, sesion.evento_id)
    mensajes = (
        await bd.scalars(
            select(Mensaje).where(Mensaje.sesion_id == sesion.id).order_by(Mensaje.secuencia)
        )
    ).all()
    ofertas = (
        await bd.scalars(
            select(Oferta).where(Oferta.sesion_id == sesion.id).order_by(Oferta.secuencia)
        )
    ).all()
    trazas = {
        str(fila.detalle.get("mensaje_id")): fila.detalle
        for fila in await bd.scalars(
            select(Bitacora).where(
                Bitacora.sesion_id == sesion.id, Bitacora.accion == "motor.decision"
            )
        )
    }
    return esquemas.SesionDetalle(
        id=sesion.id,
        evento_id=evento.id,
        folio=evento.folio,
        titulo=evento.titulo,
        moneda=evento.moneda,
        proveedor_id=sesion.proveedor_id,
        proveedor_nombre=sesion.proveedor_nombre,
        destinatario=sesion.destinatario,
        estado=sesion.estado,
        modo=sesion.modo,
        ronda=sesion.ronda,
        rondas_max=evento.rondas_max,
        fuera_de_limites=sesion.fuera_de_limites,
        correo_estado=sesion.correo_estado,
        correo_error=sesion.correo_error,
        lineas=[
            esquemas.LineaDetalle(
                id=linea.id,
                nombre=linea.nombre,
                unidad=linea.unidad,
                cantidad=linea.cantidad,
                ideal=linea.ideal,
                limite=linea.limite,
            )
            for linea in await lineas_de(bd, evento.id)
        ],
        palancas=[
            esquemas.PalancaDetalle(
                clave=p.clave,
                nombre=nombre_y_unidad(p.clave, evento.moneda)[0],
                unidad=nombre_y_unidad(p.clave, evento.moneda)[1],
                peso=p.peso,
                ideal=p.ideal,
                limite=p.limite,
            )
            for p in (await palancas_de(bd, evento.id)).values()
        ],
        mensajes=[
            esquemas.MensajeDetalle(
                id=m.id,
                autor=m.autor,
                texto=m.texto,
                ronda=m.ronda,
                fecha=m.creado_en,
                oferta_id=m.oferta_id,
                decision=trazas.get(str(m.id)),
            )
            for m in mensajes
        ],
        ofertas=[
            esquemas.OfertaDetalle(
                id=o.id,
                autor=o.autor,
                ronda=o.ronda,
                valores=valores_salida(Valores.de_json(o.valores)),
                utilidad=float(o.utilidad),
                valida=o.valida,
                fuera_de_limites_confirmada=o.fuera_de_limites_confirmada,
                fecha=o.creado_en,
            )
            for o in ofertas
        ],
    )
```

En `turnos.py`, agregue `from comun.errores import ErrorDominio` y estas funciones:

```python
async def tomar_control(
    bd: AsyncSession, sesion_id: uuid.UUID, actor: Actor, momento: datetime
) -> None:
    sesion, evento = await bloquear(bd, sesion_id)
    exigir_en_curso(sesion, evento, momento)
    if sesion.modo == "comprador":
        return
    sesion.modo, sesion.actualizado_en = "comprador", momento
    registrar(
        bd, "control.tomado", actor, evento_id=evento.id, sesion_id=sesion.id, fecha=momento
    )


async def oferta_sin_respuesta(bd: AsyncSession, sesion_id: uuid.UUID) -> Oferta | None:
    """La última oferta del proveedor, si nadie le respondió después."""
    ultimo = await bd.scalar(
        select(Mensaje)
        .where(Mensaje.sesion_id == sesion_id, Mensaje.autor != "sistema")
        .order_by(Mensaje.secuencia.desc())
        .limit(1)
    )
    if ultimo is None or ultimo.autor != "proveedor" or ultimo.oferta_id is None:
        return None
    return await bd.get(Oferta, ultimo.oferta_id)


async def devolver_control(
    bd: AsyncSession, sesion_id: uuid.UUID, actor: Actor, momento: datetime
) -> None:
    """El agente retoma la sesión y responde la oferta que quedó pendiente."""
    sesion, evento = await bloquear(bd, sesion_id)
    exigir_en_curso(sesion, evento, momento)
    if sesion.modo == "agente":
        return
    sesion.modo, sesion.actualizado_en = "agente", momento
    if sesion.estado == "escalada":
        sesion.estado = "activa"
    registrar(
        bd, "control.devuelto", actor, evento_id=evento.id, sesion_id=sesion.id, fecha=momento
    )
    pendiente = await oferta_sin_respuesta(bd, sesion.id)
    if pendiente is not None:
        terminos = await consultas.terminos_de(bd, evento)
        # La persona ya vio la oferta: no se pide aclaración; la ronda ya se contó al recibirla.
        await responder(
            bd,
            evento,
            sesion,
            terminos,
            Valores.de_json(pendiente.valores),
            pendiente.utilidad,
            sesion.ronda,
            True,
            momento,
        )
        await cerrar_eventos_terminados(bd, momento, evento.id)


async def ultima_oferta_proveedor(bd: AsyncSession, sesion_id: uuid.UUID) -> Oferta | None:
    return await bd.scalar(
        select(Oferta)
        .where(Oferta.sesion_id == sesion_id, Oferta.autor == "proveedor")
        .order_by(Oferta.secuencia.desc())
        .limit(1)
    )


def _fuera_de_limites(detalle: str) -> ErrorDominio:
    return ErrorDominio(422, "Solicitud inválida", detalle, {"codigo": "fuera_de_limites"})


async def responder_a_mano(
    bd: AsyncSession,
    sesion_id: uuid.UUID,
    datos: esquemas.Respuesta,
    actor: Actor,
    clave: str,
    momento: datetime,
) -> None:
    """La respuesta de la persona que tomó el control (spec §7)."""
    sesion, evento = await bloquear(bd, sesion_id)
    if await ya_recibido(bd, sesion.id, clave):
        return
    exigir_en_curso(sesion, evento, momento)
    if sesion.modo != "comprador":
        raise conflicto("Tome el control de la sesión antes de responder.", "sin_control")
    fuera, oferta_id, texto = False, None, datos.texto
    if datos.tipo == "mensaje" and datos.contraoferta is not None:
        terminos = await consultas.terminos_de(bd, evento)
        valores = valores_de(terminos, datos.contraoferta, "contraoferta")
        fuera = not es_valida(terminos, valores)
        if fuera and not datos.confirmar_fuera_de_limites:
            raise _fuera_de_limites(
                "La contraoferta sale de los límites de la negociación; confirme para enviarla."
            )
        fila = guardar_oferta(
            bd, sesion.id, "comprador", sesion.ronda, terminos, valores, momento, fuera
        )
        await bd.flush()
        oferta_id = fila.id
    elif datos.tipo == "aceptar":
        ultima = await ultima_oferta_proveedor(bd, sesion.id)
        if ultima is None:
            raise conflicto("El proveedor todavía no envía una oferta.", "sin_oferta")
        fuera = not ultima.valida
        if fuera and not datos.confirmar_fuera_de_limites:
            raise _fuera_de_limites(
                "La oferta del proveedor sale de los límites de la negociación; confirme para "
                "aceptarla."
            )
        sesion.estado = "acuerdo_tentativo"
        texto = texto or textos.ACUERDO
    elif datos.tipo == "cerrar":
        sesion.estado = "sin_acuerdo"
        texto = texto or textos.SIN_ACUERDO
    if fuera:
        sesion.fuera_de_limites = True  # el aprobador lo verá (incremento 4)
    bd.add(
        Mensaje(
            sesion_id=sesion.id,
            autor="comprador",
            texto=texto,
            ronda=sesion.ronda,
            oferta_id=oferta_id,
            clave_idempotencia=clave,
            creado_en=momento,
        )
    )
    sesion.actualizado_en = momento
    registrar(
        bd,
        "respuesta.manual",
        actor,
        evento_id=evento.id,
        sesion_id=sesion.id,
        detalle={"tipo": datos.tipo, "fuera_de_limites": fuera},
        fecha=momento,
    )
    await cerrar_eventos_terminados(bd, momento, evento.id)
```

En `api/sesiones.py`:
1. Agregue las importaciones: `from negociacion import consultas, turnos` y, de las dependencias, `ClaveIdempotencia` y `Lector`.
2. Agregue:

```python
@router.get("/sesiones/{sesion_id}")
async def ver_sesion(sesion_id: uuid.UUID, _: Lector, bd: Bd) -> esquemas.SesionDetalle:
    return await consultas.sesion_detalle(bd, sesion_id)


@router.post("/sesiones/{sesion_id}/control")
async def cambiar_control(
    sesion_id: uuid.UUID, datos: esquemas.Control, usuario: Comprador, bd: Bd, reloj: Reloj
) -> esquemas.SesionDetalle:
    actor = de_usuario(usuario)
    async with bd.begin():
        if datos.accion == "tomar":
            await turnos.tomar_control(bd, sesion_id, actor, reloj())
        else:
            await turnos.devolver_control(bd, sesion_id, actor, reloj())
    return await consultas.sesion_detalle(bd, sesion_id)


@router.post("/sesiones/{sesion_id}/respuestas")
async def responder(
    sesion_id: uuid.UUID,
    datos: esquemas.Respuesta,
    clave: ClaveIdempotencia,
    usuario: Comprador,
    bd: Bd,
    reloj: Reloj,
) -> esquemas.SesionDetalle:
    async with bd.begin():
        await turnos.responder_a_mano(bd, sesion_id, datos, de_usuario(usuario), clave, reloj())
    return await consultas.sesion_detalle(bd, sesion_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest services/negociacion -q`
Expected: PASS, incluido el recorrido de permisos con las rutas nuevas (`POST` solo para el comprador).

Run: `uv run ruff format . && uv run ruff check . && uv run mypy`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add services/negociacion
git commit -m "feat(negociacion): supervisión del comprador: tomar y devolver el control y responder a mano" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Fecha límite: tarea periódica

**Files:**
- Create: `services/negociacion/src/negociacion/vencimientos.py`
- Modify: `services/negociacion/src/negociacion/textos.py`, `services/negociacion/src/negociacion/config.py`, `services/negociacion/src/negociacion/main.py`
- Test: `services/negociacion/tests/test_vencimientos.py`

**Interfaces:**
- Consumes: `turnos.cerrar_eventos_terminados` (Task 9), `bitacora.SISTEMA` y `registrar`.
- Produces:
  - `vencimientos.cerrar_vencidos(fabrica, momento) -> int`, que devuelve las sesiones expiradas más los eventos cerrados;
  - `vencimientos.ejecutar_periodicamente(fabrica, reloj)` y la constante `INTERVALO_S = 60`;
  - `textos.EXPIRADA`;
  - `Configuracion.tareas_periodicas: bool = True`.

- [ ] **Step 1: Write the failing test**

`services/negociacion/tests/test_vencimientos.py`:

```python
import asyncio
import contextlib
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from negociacion import vencimientos
from negociacion.modelos import Bitacora, Mensaje, SesionNegociacion
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]


async def _contar(fabrica: Fabrica, consulta: Any) -> int:
    async with fabrica() as bd:
        return int(await bd.scalar(consulta) or 0)


async def test_al_vencer_expira_lo_que_sigue_en_curso_y_el_evento_pasa_a_evaluacion(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    fabrica: Fabrica,
) -> None:
    evento, enlaces = await publicar()
    linea = str(evento["lineas"][0]["id"])
    propuesta = (await ofertar(enlaces[0], {linea: "40.00"})).json()["ultima_propuesta"]
    await ofertar(enlaces[0], propuesta["precios"], propuesta["palancas"])  # acuerdo
    momento = datetime.fromisoformat(evento["fecha_limite"]) + timedelta(seconds=1)
    assert await vencimientos.cerrar_vencidos(fabrica, momento) == 2  # una sesión y el evento
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "en_evaluacion"
    assert sorted(s["estado"] for s in detalle["sesiones"]) == ["acuerdo_tentativo", "expirada"]
    expiradas = select(func.count()).where(Mensaje.texto == vencimientos.textos.EXPIRADA)
    assert await _contar(fabrica, expiradas) == 1
    for accion in ("sesion.expirada", "evento.en_evaluacion"):
        assert await _contar(fabrica, select(func.count()).where(Bitacora.accion == accion)) == 1
    assert await vencimientos.cerrar_vencidos(fabrica, momento) == 0  # repetirla no cambia nada


async def test_antes_de_la_fecha_limite_no_cambia_nada(
    publicar: Any, fabrica: Fabrica, reloj: Any
) -> None:
    await publicar()
    assert await vencimientos.cerrar_vencidos(fabrica, reloj.momento + timedelta(days=1)) == 0


async def test_cierra_un_evento_cuyas_sesiones_ya_terminaron(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    fabrica: Fabrica,
    reloj: Any,
) -> None:
    evento, _ = await publicar()
    # Como si dos turnos simultáneos hubieran cerrado las dos últimas sesiones.
    async with fabrica() as bd:
        await bd.execute(update(SesionNegociacion).values(estado="sin_acuerdo"))
        await bd.commit()
    assert await vencimientos.cerrar_vencidos(fabrica, reloj.momento) == 1
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "en_evaluacion"


async def test_la_tarea_periodica_cierra_lo_vencido(
    publicar: Any, fabrica: Fabrica, monkeypatch: pytest.MonkeyPatch
) -> None:
    evento, _ = await publicar()
    vencido = datetime.fromisoformat(evento["fecha_limite"]) + timedelta(minutes=1)
    monkeypatch.setattr(vencimientos, "INTERVALO_S", 0.01)
    tarea = asyncio.create_task(vencimientos.ejecutar_periodicamente(fabrica, lambda: vencido))
    try:
        for _ in range(200):
            consulta = select(func.count()).where(SesionNegociacion.estado == "expirada")
            if await _contar(fabrica, consulta) == 2:
                break
            await asyncio.sleep(0.02)
        else:
            pytest.fail("La tarea no expiró las sesiones")
    finally:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest services/negociacion/tests/test_vencimientos.py -q`
Expected: FAIL con `ImportError: cannot import name 'vencimientos'`.

- [ ] **Step 3: Write the implementation**

En `textos.py`, agregue:

```python
EXPIRADA = "La fecha límite pasó sin acuerdo. Gracias por su tiempo."
```

`services/negociacion/src/negociacion/vencimientos.py`:

```python
"""Cierre por fecha límite (spec §8.4): una tarea del servicio que corre cada minuto.

También cierra los eventos cuyas sesiones ya terminaron y que ningún turno alcanzó a cerrar
(ver turnos.cerrar_eventos_terminados). Es idempotente: repetirla no cambia nada.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from negociacion import textos
from negociacion.bitacora import SISTEMA, registrar
from negociacion.modelos import FINALES, Evento, Mensaje, SesionNegociacion
from negociacion.turnos import cerrar_eventos_terminados

log = logging.getLogger(__name__)
INTERVALO_S: float = 60


async def cerrar_vencidos(fabrica: async_sessionmaker[AsyncSession], momento: datetime) -> int:
    """Expira las sesiones en curso de los eventos vencidos y cierra esos eventos."""
    async with fabrica() as bd, bd.begin():
        # skip_locked: una sesión en pleno turno se expira en la siguiente vuelta.
        vencidas = (
            await bd.scalars(
                select(SesionNegociacion)
                .join(Evento, Evento.id == SesionNegociacion.evento_id)
                .where(
                    Evento.fecha_limite <= momento,
                    Evento.estado.in_(("abierto", "en_evaluacion")),
                    SesionNegociacion.estado.not_in(FINALES),
                )
                .with_for_update(of=SesionNegociacion, skip_locked=True)
            )
        ).all()
        for sesion in vencidas:
            sesion.estado, sesion.actualizado_en = "expirada", momento
            bd.add(
                Mensaje(
                    sesion_id=sesion.id,
                    autor="sistema",
                    texto=textos.EXPIRADA,
                    ronda=sesion.ronda,
                    creado_en=momento,
                )
            )
            registrar(
                bd,
                "sesion.expirada",
                SISTEMA,
                evento_id=sesion.evento_id,
                sesion_id=sesion.id,
                fecha=momento,
            )
        await bd.flush()
        cerrados = await cerrar_eventos_terminados(bd, momento)
    return len(vencidas) + len(cerrados)


async def ejecutar_periodicamente(
    fabrica: async_sessionmaker[AsyncSession], reloj: Callable[[], datetime]
) -> None:
    while True:
        try:
            await cerrar_vencidos(fabrica, reloj())
        except Exception:
            log.exception("No se pudieron cerrar las negociaciones vencidas; se reintentará")
        await asyncio.sleep(INTERVALO_S)
```

En `config.py`, agregue:

```python
    # La tarea que expira las sesiones al llegar la fecha límite (spec §8.4).
    tareas_periodicas: bool = True
```

En `main.py`:
1. Agregue `from negociacion import vencimientos`.
2. Antes de `ciclo_de_vida`, defina `ahora = reloj or (lambda: datetime.now(UTC))` y use `app.state.reloj = ahora`.
3. Dentro de `ciclo_de_vida`, después del bloque de RabbitMQ, agregue:

```python
        if config.tareas_periodicas:
            tareas.append(asyncio.create_task(vencimientos.ejecutar_periodicamente(sesiones, ahora)))
```

(Las pruebas no arrancan el ciclo de vida: `httpx.ASGITransport` no manda los eventos `lifespan`, así que la tarea no corre en ellas salvo en `test_la_tarea_periodica_cierra_lo_vencido`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest services/negociacion -q`
Expected: PASS.

Run: `uv run ruff format . && uv run ruff check . && uv run mypy`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add services/negociacion
git commit -m "feat(negociacion): la fecha límite expira las sesiones y cierra la negociación" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 12: `administracion`: Actividad y Correos de las negociaciones

**Files:**
- Create: `services/administracion/alembic/versions/0003_negociacion.py`
- Modify: `services/administracion/src/administracion/modelos.py`, `eventos.py`, `bitacora.py`, `textos.py`, `config.py`, `estado.py`
- Modify: `web/src/actividad.ts`, `web/src/paginas/Actividad.tsx`, `web/src/paginas/Correos.tsx`, `web/src/tipos.ts`
- Test: `services/administracion/tests/test_eventos.py`, `test_textos.py`, `test_actividad.py`, `test_sistema.py`; `web/src/actividad.test.ts`, `web/src/paginas/Correos.test.tsx`

**Interfaces:**
- Consumes: los payloads de la Task 8:
  - `negociacion.publicada{folio, titulo, tipo, proveedores, actor}`;
  - `negociacion.cancelada{folio, titulo, motivo, actor}`;
  - `negociacion.invitacion_enviada{folio, titulo, proveedor, destinatario, estado, error, reenvio, actor}`.
- Produces:
  - **Origen** `negociacion` en `actividad`.
  - **Correos:** el tipo `negociacion` en `correo_enviado`, con `usuario_id` que acepta nulos.
  - **Filtro de Actividad:** el grupo `negociacion` (`GET /actividad?tipo=negociacion`).
  - **`bitacora.registrar(...)`:** ahora devuelve `bool` (si insertó).
  - **`Configuracion.negociacion_url`:** el Estado del sistema revisa `negociacion` como séptimo servicio.
  - **Textos en servidor y web:**
    - «Publicó la negociación {objeto} con N proveedor(es)»;
    - «Canceló la negociación {objeto}: {motivo}»;
    - «Envió / Reenvió a {proveedor} la invitación a negociar {objeto}»;
    - «No se pudo enviar a {proveedor} la invitación a negociar {objeto}».

- [ ] **Step 1: Write the failing tests**

En `services/administracion/tests/test_eventos.py`:
1. Importe `CorreoNegociacion` junto a `Registro`, `atendedor` y `traducir`.
2. Agregue:

```python
NEGOCIACION = {"folio": "NEG-2026-0001", "titulo": "CRM 2027", "actor": {"id": "c-1", "nombre": "comprador1"}}
INVITACION = NEGOCIACION | {
    "proveedor": "Nube Norte S.A. de C.V.",
    "destinatario": "lucia@nubenorte.example",
    "estado": "enviado",
    "error": None,
    "reenvio": False,
}


def test_traduce_las_acciones_de_negociacion() -> None:
    publicada = traducir(_sobre("negociacion.publicada", NEGOCIACION | {"tipo": "compra", "proveedores": 3}, "n-1"))
    assert publicada == Registro(
        tipo="negociacion.publicada",
        actor=Actor("c-1", "comprador1"),
        objeto=Objeto("negociacion", "NEG-2026-0001", "NEG-2026-0001 «CRM 2027»"),
        detalle={"proveedores": 3},
        resultado="exito",
        clave_origen="negociacion:n-1",
        fecha=datetime(2026, 10, 9, 15, tzinfo=UTC),
        origen="negociacion",
    )
    cancelada = traducir(_sobre("negociacion.cancelada", NEGOCIACION | {"motivo": "Se pospuso"}))
    assert cancelada is not None and cancelada.detalle == {"motivo": "Se pospuso"}
    invitacion = traducir(_sobre("negociacion.invitacion_enviada", INVITACION))
    assert invitacion is not None
    assert invitacion.detalle == {
        "proveedor": "Nube Norte S.A. de C.V.",
        "destinatario": "lucia@nubenorte.example",
        "estado": "enviado",
        "reenvio": False,
    }
    assert invitacion.correo == CorreoNegociacion(
        "lucia@nubenorte.example", "comprador1", "enviado", None
    )
    fallida = traducir(
        _sobre("negociacion.invitacion_enviada", INVITACION | {"estado": "fallido", "error": "x"})
    )
    assert fallida is not None and fallida.resultado == "fallo"
    with pytest.raises(EventoInvalido):
        traducir(_sobre("negociacion.invitacion_enviada", INVITACION | {"estado": "perdido"}))


@pytest.mark.integracion
async def test_una_invitacion_queda_una_vez_en_actividad_y_en_correos(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    sobre = _sobre("negociacion.invitacion_enviada", INVITACION)
    atender = atendedor(fabrica)
    await atender(sobre)
    await atender(sobre)  # el mismo evento entregado dos veces
    async with fabrica() as sesion:
        actividad = (await sesion.execute(text("SELECT origen, tipo FROM actividad"))).all()
        correos = (
            await sesion.execute(
                text(
                    "SELECT tipo, destinatario, usuario_id, solicitado_por, estado "
                    "FROM correo_enviado"
                )
            )
        ).all()
    assert [tuple(f) for f in actividad] == [("negociacion", "negociacion.invitacion_enviada")]
    assert [tuple(f) for f in correos] == [
        ("negociacion", "lucia@nubenorte.example", None, "comprador1", "enviado")
    ]
```

En `services/administracion/tests/test_textos.py`, agregue a `CASOS`:

```python
    (
        "negociacion.publicada",
        "NEG-2026-0001 «CRM 2027»",
        {"proveedores": 3},
        "Publicó la negociación NEG-2026-0001 «CRM 2027» con 3 proveedores",
    ),
    (
        "negociacion.publicada",
        "NEG-2026-0002 «Renovación»",
        {"proveedores": 1},
        "Publicó la negociación NEG-2026-0002 «Renovación» con 1 proveedor",
    ),
    (
        "negociacion.cancelada",
        "NEG-2026-0001 «CRM 2027»",
        {"motivo": "Se pospuso"},
        "Canceló la negociación NEG-2026-0001 «CRM 2027»: Se pospuso",
    ),
    (
        "negociacion.invitacion_enviada",
        "NEG-2026-0001 «CRM 2027»",
        {"proveedor": "Nube Norte", "estado": "enviado", "reenvio": False},
        "Envió a Nube Norte la invitación a negociar NEG-2026-0001 «CRM 2027»",
    ),
    (
        "negociacion.invitacion_enviada",
        "NEG-2026-0001 «CRM 2027»",
        {"proveedor": "Nube Norte", "estado": "enviado", "reenvio": True},
        "Reenvió a Nube Norte la invitación a negociar NEG-2026-0001 «CRM 2027»",
    ),
    (
        "negociacion.invitacion_enviada",
        "NEG-2026-0001 «CRM 2027»",
        {"proveedor": "Nube Norte", "estado": "fallido", "reenvio": False},
        "No se pudo enviar a Nube Norte la invitación a negociar NEG-2026-0001 «CRM 2027»",
    ),
```

En `services/administracion/tests/test_actividad.py`, agregue:

```python
async def test_filtro_de_negociacion(
    cliente: httpx.AsyncClient, admin: dict[str, str], fabrica: async_sessionmaker[AsyncSession]
) -> None:
    async with fabrica() as sesion:
        await registrar(
            sesion,
            "negociacion.publicada",
            Actor("c-1", "comprador1"),
            objeto=Objeto("negociacion", "NEG-2026-0001", "NEG-2026-0001 «CRM 2027»"),
            detalle={"proveedores": 2},
            origen="negociacion",
        )
        await registrar(
            sesion,
            "servicio.creado",
            Actor("admin-1", "admin1"),
            objeto=Objeto("servicio", "SOP-X", "SOP-X"),
            origen="proveedores",
        )
        await sesion.commit()
    cuerpo = (
        await cliente.get("/actividad", params={"tipo": "negociacion"}, headers=admin)
    ).json()
    assert [e["tipo"] for e in cuerpo["elementos"]] == ["negociacion.publicada"]
```

En `services/administracion/tests/test_sistema.py`:
- `rutas()` devuelve también `"neg": _ok`;
- `Configuracion(...)` recibe `negociacion_url="http://neg"`;
- en `test_todo_sano`, la lista esperada de claves queda `["base_de_datos", "proveedores", "inteligencia", "negociacion", "identidad", "mensajeria", "correo"]`.

En `web/src/actividad.test.ts`, agregue dentro de `describe("describirActividad", …)`:

```ts
  it.each([
    [
      "negociacion.publicada",
      { proveedores: 3 },
      "Publicó la negociación NEG-2026-0001 «CRM 2027» con 3 proveedores",
    ],
    [
      "negociacion.publicada",
      { proveedores: 1 },
      "Publicó la negociación NEG-2026-0001 «CRM 2027» con 1 proveedor",
    ],
    [
      "negociacion.cancelada",
      { motivo: "Se pospuso" },
      "Canceló la negociación NEG-2026-0001 «CRM 2027»: Se pospuso",
    ],
    [
      "negociacion.invitacion_enviada",
      { proveedor: "Nube Norte", estado: "enviado", reenvio: false },
      "Envió a Nube Norte la invitación a negociar NEG-2026-0001 «CRM 2027»",
    ],
    [
      "negociacion.invitacion_enviada",
      { proveedor: "Nube Norte", estado: "enviado", reenvio: true },
      "Reenvió a Nube Norte la invitación a negociar NEG-2026-0001 «CRM 2027»",
    ],
    [
      "negociacion.invitacion_enviada",
      { proveedor: "Nube Norte", estado: "fallido", reenvio: false },
      "No se pudo enviar a Nube Norte la invitación a negociar NEG-2026-0001 «CRM 2027»",
    ],
  ])("negociación: %s", (tipo, detalle, esperado) => {
    const objeto_nombre = "NEG-2026-0001 «CRM 2027»"
    expect(describirActividad({ ...base, tipo, detalle, objeto_nombre })).toBe(esperado)
  })
```

En `web/src/paginas/Correos.test.tsx`, agregue dentro de `describe("Correos", …)`:

```tsx
  it("muestra las invitaciones a negociar", async () => {
    simularApi(() =>
      respuestaJson({
        total: 1,
        buzon_url: null,
        elementos: [
          {
            id: "c3",
            fecha: "2026-10-13T18:00:00Z",
            tipo: "negociacion",
            destinatario: "lucia@nubenorte.example",
            solicitado_por: "comprador1",
            estado: "enviado",
            error: null,
          },
        ],
      })
    )
    renderizarPagina(<Correos />, { ruta: "/sistema/correos" })
    expect(await screen.findByText("Invitación a negociar")).toBeInTheDocument()
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest services/administracion -q`
Expected: FAIL con `ImportError: cannot import name 'CorreoNegociacion'`.

Run: `cd web && npx vitest run src/actividad.test.ts src/paginas/Correos.test.tsx`
Expected: FAIL. Los textos de negociación caen al tipo crudo y «Invitación a negociar» no aparece.

- [ ] **Step 3: Write the implementation**

`services/administracion/alembic/versions/0003_negociacion.py`:

```python
"""La bitácora y los correos aceptan lo que publica negociacion.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_actividad_origen"), "actividad", type_="check")
    op.create_check_constraint(
        op.f("ck_actividad_origen"),
        "actividad",
        "origen IN ('keycloak', 'proveedores', 'administracion', 'inteligencia', 'negociacion')",
    )
    op.drop_constraint(op.f("ck_correo_enviado_tipo"), "correo_enviado", type_="check")
    op.create_check_constraint(
        op.f("ck_correo_enviado_tipo"),
        "correo_enviado",
        "tipo IN ('invitacion', 'restablecimiento', 'negociacion')",
    )
    # Las invitaciones a negociar van a proveedores, que no son usuarios de Keycloak.
    op.alter_column("correo_enviado", "usuario_id", existing_type=sa.String(64), nullable=True)


def downgrade() -> None:
    # Falla si ya hay registros de negociación: la bitácora no se borra.
    op.alter_column("correo_enviado", "usuario_id", existing_type=sa.String(64), nullable=False)
    op.drop_constraint(op.f("ck_correo_enviado_tipo"), "correo_enviado", type_="check")
    op.create_check_constraint(
        op.f("ck_correo_enviado_tipo"),
        "correo_enviado",
        "tipo IN ('invitacion', 'restablecimiento')",
    )
    op.drop_constraint(op.f("ck_actividad_origen"), "actividad", type_="check")
    op.create_check_constraint(
        op.f("ck_actividad_origen"),
        "actividad",
        "origen IN ('keycloak', 'proveedores', 'administracion', 'inteligencia')",
    )
```

En `administracion/modelos.py`:
- el CHECK `origen` de `Actividad` queda `"origen IN ('keycloak', 'proveedores', 'administracion', 'inteligencia', 'negociacion')"`;
- el CHECK `tipo` de `CorreoEnviado` queda `"tipo IN ('invitacion', 'restablecimiento', 'negociacion')"`;
- `usuario_id: Mapped[str | None] = mapped_column(String(64))`.

En `administracion/bitacora.py`:
1. `GrupoTipo` agrega `"negociacion"` y `PREFIJOS_GRUPO` agrega `"negociacion": ("negociacion.",)`.
2. `registrar` devuelve `bool`; su final queda:

```python
    insertado = await sesion.scalar(
        insert(Actividad)
        .values(**valores)
        .on_conflict_do_nothing(index_elements=["clave_origen"])
        .returning(Actividad.id)
    )
    return insertado is not None
```

3. La firma queda `-> bool` y el docstring dice: «Agrega un registro a la transacción en curso; devuelve False si la clave de origen ya existía.»

En `administracion/eventos.py`:
1. Agregue `from administracion.modelos import CorreoEnviado`.
2. Agregue después de `TIPOS_INTELIGENCIA`:

```python
PREFIJO_NEGOCIACION = "negociacion."  # los publica negociacion


@dataclass(frozen=True)
class CorreoNegociacion:
    """La invitación a negociar que mandó el servicio de negociación, para la página Correos."""

    destinatario: str
    solicitado_por: str
    estado: str  # enviado o fallido
    error: str | None
```

3. Agregue el campo `correo: CorreoNegociacion | None = None` al final de `Registro`.
4. Agregue:

```python
def _origen(tipo: str) -> str:
    if tipo.startswith(TIPOS_INTELIGENCIA):
        return "inteligencia"
    if tipo.startswith(PREFIJO_NEGOCIACION):
        return "negociacion"
    return "proveedores"


def _negociacion(
    tipo: str, payload: dict[str, Any], clave: str, fecha: datetime
) -> Registro | None:
    folio = str(payload["folio"])
    objeto = Objeto("negociacion", folio, f"{folio} «{payload['titulo']}»")
    actor = _actor(payload)
    if tipo == "negociacion.publicada":
        detalle: dict[str, Any] = {"proveedores": int(payload["proveedores"])}
        return Registro(tipo, actor, objeto, detalle, "exito", clave, fecha, "negociacion")
    if tipo == "negociacion.cancelada":
        detalle = {"motivo": str(payload["motivo"])}
        return Registro(tipo, actor, objeto, detalle, "exito", clave, fecha, "negociacion")
    if tipo == "negociacion.invitacion_enviada":
        estado = str(payload["estado"])
        if estado not in ("enviado", "fallido"):
            raise ValueError(f"Estado de correo desconocido: {estado}")
        error = payload.get("error")
        detalle = {
            "proveedor": str(payload["proveedor"]),
            "destinatario": str(payload["destinatario"]),
            "estado": estado,
            "reenvio": bool(payload["reenvio"]),
        }
        correo = CorreoNegociacion(
            str(payload["destinatario"]),
            actor.nombre,
            estado,
            None if error is None else str(error),
        )
        resultado = "exito" if estado == "enviado" else "fallo"
        return Registro(tipo, actor, objeto, detalle, resultado, clave, fecha, "negociacion", correo)
    return None
```

5. En `traducir`, cambie `origen = "inteligencia" if tipo.startswith(TIPOS_INTELIGENCIA) else "proveedores"` por `origen = _origen(tipo)`. Justo después de calcular `fecha`, agregue:

```python
        if tipo.startswith(PREFIJO_NEGOCIACION):
            return _negociacion(tipo, payload, clave, fecha)
```

6. `guardar` queda:

```python
async def guardar(fabrica: async_sessionmaker[AsyncSession], registro: Registro) -> None:
    """Inserta el registro (y su correo, si trae); un evento ya recibido no hace nada."""
    async with fabrica() as sesion:
        nuevo = await registrar(
            sesion,
            registro.tipo,
            registro.actor,
            objeto=registro.objeto,
            detalle=registro.detalle,
            resultado=registro.resultado,
            origen=registro.origen,
            clave_origen=registro.clave_origen,
            fecha=registro.fecha,
        )
        if nuevo and registro.correo is not None:
            sesion.add(
                CorreoEnviado(
                    fecha=registro.fecha,
                    tipo="negociacion",
                    destinatario=registro.correo.destinatario,
                    usuario_id=None,
                    solicitado_por=registro.correo.solicitado_por,
                    estado=registro.correo.estado,
                    error=registro.correo.error,
                )
            )
        await sesion.commit()
```

En `administracion/textos.py`, agregue antes de `TEXTOS`:

```python
def _proveedores(valor: object) -> str:
    cuantos = valor if isinstance(valor, int) else 0
    return "1 proveedor" if cuantos == 1 else f"{cuantos} proveedores"


def _invitacion(a: Actividad) -> str:
    proveedor = a.detalle.get("proveedor", "")
    if a.detalle.get("estado") == "fallido":
        return f"No se pudo enviar a {proveedor} la invitación a negociar {a.objeto_nombre}"
    accion = "Reenvió" if a.detalle.get("reenvio") else "Envió"
    return f"{accion} a {proveedor} la invitación a negociar {a.objeto_nombre}"
```

Y agregue al diccionario `TEXTOS`:

```python
    "negociacion.publicada": lambda a: (
        f"Publicó la negociación {a.objeto_nombre} con "
        f"{_proveedores(a.detalle.get('proveedores'))}"
    ),
    "negociacion.cancelada": lambda a: (
        f"Canceló la negociación {a.objeto_nombre}: {a.detalle.get('motivo', '')}"
    ),
    "negociacion.invitacion_enviada": _invitacion,
```

En `administracion/config.py`, agregue `negociacion_url: str = "http://localhost:8000"` junto a `inteligencia_url`.

En `administracion/estado.py`:
1. Agregue junto a `inteligencia()`:

```python
    async def negociacion() -> None:
        await obtener(f"{config.negociacion_url}/salud/listo")
```

2. En `pruebas`, después de la línea de inteligencia, agregue `("negociacion", "Servicio de negociación", negociacion),`.

En `web/src/actividad.ts`:
1. Agregue a `TIPOS_ACTIVIDAD`, después de `"modelo.entrenado"`:

```ts
  "negociacion.publicada",
  "negociacion.cancelada",
  "negociacion.invitacion_enviada",
```

2. Antes de `TEXTOS`, agregue:

```ts
function proveedores(valor: unknown): string {
  const cuantos = typeof valor === "number" ? valor : 0
  return cuantos === 1 ? "1 proveedor" : `${cuantos} proveedores`
}

function invitacion(a: RegistroActividad): string {
  const proveedor = String(a.detalle.proveedor ?? "")
  if (a.detalle.estado === "fallido")
    return `No se pudo enviar a ${proveedor} la invitación a negociar ${a.objeto_nombre}`
  const accion = a.detalle.reenvio ? "Reenvió" : "Envió"
  return `${accion} a ${proveedor} la invitación a negociar ${a.objeto_nombre}`
}
```

3. Agregue a `TEXTOS`:

```ts
  "negociacion.publicada": (a) =>
    `Publicó la negociación ${a.objeto_nombre} con ${proveedores(a.detalle.proveedores)}`,
  "negociacion.cancelada": (a) =>
    `Canceló la negociación ${a.objeto_nombre}: ${String(a.detalle.motivo ?? "")}`,
  "negociacion.invitacion_enviada": invitacion,
```

En `web/src/paginas/Actividad.tsx`, agregue `["negociacion", "Negociación"],` al final de `GRUPOS`.

En `web/src/tipos.ts`, el `tipo` del correo queda `"invitacion" | "restablecimiento" | "negociacion"`.

En `web/src/paginas/Correos.tsx`:
- agregue `negociacion: "Invitación a negociar",` a `TIPOS`;
- cambie la descripción del estado vacío a «Las invitaciones, los restablecimientos de contraseña y las invitaciones a negociar aparecerán aquí.».

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest services/administracion libs/comun -q`
Expected: PASS, incluidas `test_los_mismos_tipos_que_la_web` y `test_modelos_y_migraciones_coinciden`.

Run: `cd web && npm run lint && npx vitest run`
Expected: PASS.

Run: `uv run ruff format . && uv run ruff check . && uv run mypy`
Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add services/administracion web/src
git commit -m "feat(administracion): la Actividad y los Correos registran las negociaciones" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Infraestructura, prueba de humo y documentación

**Files:**
- Create: `infra/postgres/negociacion.sh`
- Modify: `infra/docker-compose.yml`, `infra/.env.example`, `infra/nginx/nginx.conf`, `infra/smoke_test.py`, `.github/dependabot.yml`
- Modify: `README.md`, `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md` (PRD)

**Interfaces:**
- Consumes: el servicio completo (Tasks 2–12).
- Produces: el stack con `negociacion` detrás de `/api/negociacion/`, la prueba de humo de punta a punta y la documentación.

- [ ] **Step 1: Write the failing smoke check**

En `infra/smoke_test.py`:
1. Agregue `from datetime import UTC, datetime, timedelta` a las importaciones.
2. Agregue antes de `main()`:

```python
def verificar_negociacion(cliente: httpx.Client) -> None:
    """Una compra de humo: se publica, la invitación llega a Mailpit y el agente responde."""
    comprador = token_de(cliente, "comprador1")
    servicios = cliente.get("/api/inteligencia/precios/servicios", headers=comprador).json()
    servicio = next(s for s in servicios if s["observaciones"] > 0)
    proveedores = cliente.get("/api/proveedores/proveedores", headers=comprador).json()
    proveedor = next(p for p in proveedores["elementos"] if p["activo"])
    cuerpo = {
        "tipo": "compra",
        "titulo": f"Prueba de humo {uuid.uuid4().hex[:8]}",
        "fecha_limite": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "lineas": [{"codigo_servicio": servicio["codigo"], "cantidad": "10"}],
        "proveedores": [proveedor["id"]],
    }
    # La copia de proveedores de negociacion se llena por eventos: se reintenta mientras llega.
    limite = time.monotonic() + ESPERA_EVENTOS_S
    while True:
        creado = cliente.post("/api/negociacion/eventos", json=cuerpo, headers=comprador)
        if creado.status_code == 201:
            break
        verificar(
            creado.status_code == 422 and time.monotonic() < limite,
            f"crear la negociación de humo falló: {creado.text}",
        )
        time.sleep(2)
        comprador = token_de(cliente, "comprador1")
    evento = creado.json()
    linea = evento["lineas"][0]
    verificar(linea["limite"] is not None, f"la línea no trae la referencia de precios: {linea}")
    publicado = cliente.post(
        f"/api/negociacion/eventos/{evento['id']}/publicar", headers=comprador
    )
    verificar(publicado.status_code == 200, f"publicar la negociación falló: {publicado.text}")
    [enlace] = publicado.json()["enlaces"]
    verificar(enlace["correo_estado"] == "enviado", f"la invitación no salió: {enlace}")
    portal = {"Authorization": f"Invitacion {enlace['enlace'].split('#t=')[1]}"}
    verificar(
        cliente.get("/api/negociacion/portal/sesion", headers=portal).status_code == 200,
        "el portal no abrió la sesión con el enlace de la invitación",
    )
    oferta = {"valores": {"precios": {linea["id"]: str(Decimal(linea["limite"]) * 2)}}}
    respuesta = cliente.post(
        "/api/negociacion/portal/ofertas",
        json=oferta,
        headers=portal | {"Idempotency-Key": uuid.uuid4().hex},
    )
    verificar(
        respuesta.status_code == 200 and respuesta.json()["mensajes"][-1]["autor"] == "agente",
        f"el agente no respondió en el portal: {respuesta.text}",
    )
    correos = httpx.get(
        f"{BUZON}/api/v1/search", params={"query": f'subject:"{evento["folio"]}"'}, timeout=10
    ).json()
    verificar(bool(correos.get("messages")), "la invitación a negociar no llegó a Mailpit")
    cancelada = cliente.post(
        f"/api/negociacion/eventos/{evento['id']}/cancelar",
        json={"motivo": "Prueba de humo"},
        headers=comprador,
    )
    verificar(cancelada.status_code == 200, f"cancelar la negociación falló: {cancelada.text}")
    # La publicación llega a la Actividad por RabbitMQ.
    limite = time.monotonic() + ESPERA_EVENTOS_S
    while True:
        admin = token_de(cliente, "admin1")
        actividad = cliente.get(
            "/api/administracion/actividad",
            params={"tipo": "negociacion", "tamano": 100},
            headers=admin,
        ).json()["elementos"]
        if any(
            a["objeto_id"] == evento["folio"] and a["tipo"] == "negociacion.publicada"
            for a in actividad
        ):
            return
        verificar(
            time.monotonic() < limite,
            f"la publicación de la negociación no llegó a la Actividad en {ESPERA_EVENTOS_S} s",
        )
        time.sleep(2)
```

3. En `main()`, agregue `verificar_negociacion(cliente)` después de `verificar_inteligencia(cliente)`, y cambie el mensaje final a `f"OK: SPA, Keycloak, proveedores, administración, operación, inteligencia y negociación responden "`.

Run: `uv run python infra/smoke_test.py` (con el stack anterior levantado)
Expected: FALLA en `verificar_negociacion`: `/api/negociacion/eventos` responde 404 desde el gateway.

- [ ] **Step 2: Write the infrastructure**

`infra/postgres/negociacion.sh`:

```bash
#!/bin/bash
# Base de datos del servicio de negociación con dos usuarios: el dueño (corre las migraciones)
# y el de la aplicación (los permisos por tabla los da la migración; el historial es de solo
# inserción). Es idempotente. Corre solo en volúmenes nuevos; en un volumen existente:
#   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/40-negociacion.sh
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname postgres <<EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'negociacion_dueno') THEN
    CREATE ROLE negociacion_dueno LOGIN PASSWORD '${NEGOCIACION_DUENO_DB_PASSWORD}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'negociacion') THEN
    CREATE ROLE negociacion LOGIN PASSWORD '${NEGOCIACION_DB_PASSWORD}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE negociacion_db OWNER negociacion_dueno'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'negociacion_db')\gexec
REVOKE CONNECT ON DATABASE negociacion_db FROM PUBLIC;
GRANT CONNECT ON DATABASE negociacion_db TO negociacion;
EOSQL
```

En Git Bash, márquelo como ejecutable: `git update-index --chmod=+x infra/postgres/negociacion.sh`.

En `infra/docker-compose.yml`:
1. En `postgres.environment`, agregue:

```yaml
      NEGOCIACION_DB_PASSWORD: ${NEGOCIACION_DB_PASSWORD:?Defina NEGOCIACION_DB_PASSWORD en infra/.env}
      NEGOCIACION_DUENO_DB_PASSWORD: ${NEGOCIACION_DUENO_DB_PASSWORD:?Defina NEGOCIACION_DUENO_DB_PASSWORD en infra/.env}
```

2. En `postgres.volumes`, agregue `- ./postgres/negociacion.sh:/docker-entrypoint-initdb.d/40-negociacion.sh:ro`.
3. En `administracion.environment`, agregue `NEGOCIACION_URL: http://negociacion:8000`.
4. Agregue el servicio después de `inteligencia`:

```yaml
  negociacion:
    build:
      context: ..
      dockerfile: services/negociacion/Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://negociacion:${NEGOCIACION_DB_PASSWORD}@postgres:5432/negociacion_db
      DATABASE_URL_MIGRACIONES: postgresql+asyncpg://negociacion_dueno:${NEGOCIACION_DUENO_DB_PASSWORD}@postgres:5432/negociacion_db
      RABBITMQ_URL: amqp://plataforma:${RABBITMQ_PASSWORD}@rabbitmq:5672/
      OIDC_ISSUER: http://localhost:8080/auth/realms/plataforma
      OIDC_JWKS_URL: http://keycloak:8080/auth/realms/plataforma/protocol/openid-connect/certs
      ROOT_PATH: /api/negociacion
      INTELIGENCIA_URL: http://inteligencia:8000
      PROVEEDORES_URL: http://proveedores:8000
      SMTP_HOST: mailpit
      SMTP_PUERTO: "1025"
      URL_PUBLICA: http://localhost:8080
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      rabbitmq-topologia:
        condition: service_completed_successfully
      mailpit:
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

5. En `gateway.depends_on`, agregue:

```yaml
      negociacion:
        condition: service_healthy
        restart: true
```

6. Cambie el comentario de `mailpit` por: «Buzón de desarrollo: Keycloak y negociacion le entregan los correos por SMTP (solo red interna, puerto 1025); la interfaz web queda solo en este equipo.»

En `infra/.env.example`, agregue después de las de la inteligencia:

```
NEGOCIACION_DB_PASSWORD=cambiar-negociacion
NEGOCIACION_DUENO_DB_PASSWORD=cambiar-negociacion-dueno
```

En `infra/nginx/nginx.conf`, agregue después de `location /api/inteligencia/`:

```nginx
    location /api/negociacion/ {
        limit_req zone=api burst=40 nodelay;
        limit_req_status 429;
        proxy_pass http://negociacion:8000/;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Cache-Control "no-store" always;
    }
```

En `.github/dependabot.yml`, agregue `/services/negociacion` a `directories` del ecosistema `docker`.

- [ ] **Step 3: Bring the stack up and run the smoke test**

**Este paso lo corre el controlador, no el implementador:** necesita el `infra/.env` del residente. Antes del primer comando, el residente agrega a `infra/.env` las dos variables `NEGOCIACION_*` (cópielas de `infra/.env.example`; `infra/.env` no se versiona).

En Git Bash, desde la raíz del repositorio. Los comandos 2 y 3 aplican solo si el entorno ya existía:

```bash
export MSYS_NO_PATHCONV=1
docker compose -f infra/docker-compose.yml up -d --wait postgres
docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/40-negociacion.sh
docker compose -f infra/docker-compose.yml up -d --build --wait
docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --todo
docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --instantanea
uv run python infra/smoke_test.py
```

Expected: `OK: SPA, Keycloak, proveedores, administración, operación, inteligencia y negociación responden (60 proveedores).`

Si la prueba falla esperando la copia de proveedores, revise en la consola de RabbitMQ (<http://localhost:15672>) que la cola `negociacion.eventos` reciba mensajes y que `negociacion.eventos.dlq` esté vacía.

- [ ] **Step 4: Update the documentation**

En `README.md`:
1. **Secretos.** Después de la lista «Los de la inteligencia son:», agregue:

```markdown
Los de la negociación son:

- `NEGOCIACION_DB_PASSWORD`: contraseña con la que el servicio `negociacion` entra a su base
  (nunca cambia ni borra la bitácora, los mensajes ni las ofertas).
- `NEGOCIACION_DUENO_DB_PASSWORD`: contraseña del dueño de esa base, que solo crea y migra tablas.
```

2. **Sección nueva** `### Activar la negociación en un entorno ya creado`, después de la de la inteligencia, con estos pasos:
   1. agregar las dos variables a `infra/.env` y recrear PostgreSQL;
   2. correr `40-negociacion.sh`;
   3. levantar el stack con `--build`;
   4. llenar las copias con `proveedores.reproceso --todo` y después `--instantanea` (los demás servicios ignoran lo que ya recibieron);
   5. esperar a que la cola `negociacion.eventos` quede en 0.

   Use los mismos comandos del Step 3.
3. **Tabla «Desarrollo».** Agregue dos filas:
   - `| Contrato OpenAPI de negociación | <http://localhost:8080/api/negociacion/docs> |`;
   - `| Simulación con bots (escribe docs/qa/simulacion-negociacion.md) | SIMULACION_REPORTE=docs/qa/simulacion-negociacion.md uv run pytest services/negociacion/tests/test_simulacion.py |` (esta fila la usa la Task 14).

   Y cambie la fila de Mailpit a «buzón de desarrollo de los correos de Keycloak y de las invitaciones a negociar».
4. **Tabla «Estructura».** Agregue:
   - `| services/negociacion | Microservicio de negociación: eventos, sesiones, motor de concesiones, portal del proveedor y bitácora (/api/negociacion/) |`;
   - `| tools/simulador | Bots de proveedor que negocian por el portal y miden al agente |`.
5. **«Limitaciones conocidas».** Agregue:
   - **Negociación sin interfaz todavía.** El servicio y su API están completos, pero las pantallas del comprador y el portal del proveedor llegan con N1b; mientras tanto se usan por la API (`/api/negociacion/docs`).
   - **Agente sin LLM.** Los mensajes del agente son plantillas y la nota del proveedor no se interpreta; la IA llega con N2.

En el PRD (`docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md`):
1. **§2.2, fila de `servicio.actualizado`:** los consumidores quedan `administracion, inteligencia, negociacion`.
2. **§2.2, filas nuevas**, después de `modelo.entrenado`:

```markdown
| `negociacion.publicada` · `negociacion.cancelada` | negociacion | administracion | Bitácora de las negociaciones publicadas y canceladas, con quién lo hizo. |
| `negociacion.invitacion_enviada` | negociacion | administracion | Bitácora y página Correos de cada invitación a negociar (enviada o fallida). |
```

3. **§2.2, línea de «Colas:»:** empieza con «Colas: `inteligencia.eventos`, `administracion.actividad` y `negociacion.eventos`,» y agrega al final «(N1 en `docs/superpowers/specs/2026-10-13-negociacion-determinista-design.md`, §9)».
4. **§3.3**, después del párrafo **Contraoferta:**, agregue:

```markdown
> **Precisión de N1** (`docs/superpowers/specs/2026-10-13-negociacion-determinista-design.md`, §6.4): el camino de la contraoferta va de la oferta acotada a los límites, a la oferta con la curva propia del agente en lo que cruzaba un límite (así no contesta con el límite antes de la ronda T), y de ahí al ideal; se redondea al valor más cercano, salvo que eso suba la utilidad sobre la contraoferta anterior.
```

5. **§4.1, fila `negociacion`:** queda «Evento, Linea, Palanca, Sesion, Mensaje, Oferta (origen: formulario / texto; fuera de límites confirmada sí/no), Bitacora (incluye la traza de cada decisión del motor), Proveedor y Servicio (copias), Outbox, EventoProcesado; Adjudicacion y Aprobacion (incremento 4)».
6. **§5.1, matriz:** la fila «Crear/editar eventos propios y supervisar sus sesiones» queda «Crear, editar, publicar y supervisar negociaciones (todas las del equipo de compras)».

- [ ] **Step 5: Commit**

```bash
git add infra .github/dependabot.yml README.md docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md
git commit -m "build(negociacion): servicio en el stack, gateway, prueba de humo y documentación" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Bots y simulación

**Files:**
- Create: `tools/simulador/pyproject.toml`
- Create: `tools/simulador/src/simulador/__init__.py` (vacío)
- Create: `tools/simulador/src/simulador/bots.py`, `escenarios.py`, `orquestador.py`, `reporte.py`
- Test: `tools/simulador/tests/test_bots.py`, `services/negociacion/tests/test_simulacion.py`
- Create: `docs/qa/simulacion-negociacion.md` (lo escribe la prueba)
- Modify: `pyproject.toml` (raíz) y `uv.lock`

**Interfaces:**
- Consumes:
  - la API HTTP del servicio: `POST /eventos`, `PATCH /eventos/{id}`, `POST /eventos/{id}/publicar`, `GET /portal/sesion`, `POST /portal/ofertas` y `GET /sesiones/{id}`;
  - `generador.modelo.generar`, `DatosSinteticos` y `ProveedorSintetico`.
- Produces:
  - **`simulador.bots`:** `Termino(clave, inicio, reserva, mas_es_mejor)` y `Bot(estilo, precios, palancas, rng)` con `.oferta(k, rondas)` y `.acepta(propuesta)`.
  - **`simulador.escenarios`:** `Banda`, `bandas(datos, hoy)`, `Escenario`, `escenarios(datos, hoy, compras=20, renovaciones=10, semilla=7)` y `contratos_por_proveedor(datos, ids)`.
  - **`simulador.orquestador`:** `Contexto(datos, bandas, ids, fecha_limite, semilla=11)`, `Resultado`, `dentro_de_limites(evento, valores) -> bool` y `correr(cliente, comprador, contexto, escenarios) -> list[Resultado]`. Aquí `comprador` es una función que devuelve los encabezados, porque los tokens vencen en 5 min.
  - **`simulador.reporte`:** `Metricas`, `metricas(resultados)` y `reporte(resultados, escenarios, semilla) -> str`.

- [ ] **Step 1: Write the failing tests**

`tools/simulador/tests/test_bots.py`:

```python
import random
from datetime import date
from decimal import Decimal as D

from generador.modelo import generar
from simulador.bots import Bot, Termino
from simulador.escenarios import bandas, escenarios
from simulador.orquestador import dentro_de_limites

PRECIO = Termino("precio", D("40.00"), D("30.00"), mas_es_mejor=True)


def test_el_bot_concede_de_su_inicio_a_su_reserva() -> None:
    bot = Bot("duro", {"l": PRECIO}, {}, random.Random(1))
    ofertas = [D(bot.oferta(k, 6)["precios"]["l"]) for k in range(1, 7)]
    assert ofertas[0] < D("40.00")
    assert ofertas[-1] == D("30.00")  # en la última ronda ofrece su reserva
    assert ofertas == sorted(ofertas, reverse=True)


def test_el_duro_concede_despues_que_el_flexible() -> None:
    duro = Bot("duro", {"l": PRECIO}, {}, random.Random(1))
    flexible = Bot("flexible", {"l": PRECIO}, {}, random.Random(1))
    assert D(duro.oferta(2, 6)["precios"]["l"]) > D(flexible.oferta(2, 6)["precios"]["l"])


def test_acepta_solo_lo_que_no_cruza_su_reserva() -> None:
    pago = Termino("plazo_pago_dias", D(20), D(45), mas_es_mejor=False)
    bot = Bot("flexible", {"l": PRECIO}, {"plazo_pago_dias": pago}, random.Random(1))
    assert bot.acepta({"precios": {"l": "30.00"}, "palancas": {"plazo_pago_dias": "45"}})
    assert not bot.acepta({"precios": {"l": "29.99"}, "palancas": {"plazo_pago_dias": "45"}})
    assert not bot.acepta({"precios": {"l": "35.00"}, "palancas": {"plazo_pago_dias": "46"}})


def test_la_comprobacion_de_limites_es_independiente_del_motor() -> None:
    evento = {
        "lineas": [{"id": "l", "ideal": "28.00", "limite": "31.50"}],
        "palancas": [
            {"clave": "precio", "activa": True, "ideal": None, "limite": None},
            {"clave": "plazo_pago_dias", "activa": True, "ideal": "60", "limite": "30"},
        ],
    }
    assert dentro_de_limites(evento, {"precios": {"l": "31.50"}, "palancas": {"plazo_pago_dias": "30"}})
    assert not dentro_de_limites(evento, {"precios": {"l": "31.51"}, "palancas": {"plazo_pago_dias": "30"}})
    assert not dentro_de_limites(evento, {"precios": {"l": "30.00"}, "palancas": {"plazo_pago_dias": "29"}})


def test_las_bandas_y_los_escenarios_son_reproducibles() -> None:
    datos = generar(42, n_proveedores=20)
    hoy = date(2026, 9, 15)
    referencias = bandas(datos, hoy)
    assert referencias
    assert all(b.p25 <= b.p50 <= b.p75 for b in referencias.values())
    lista = escenarios(datos, hoy, compras=5, renovaciones=3)
    assert lista == escenarios(datos, hoy, compras=5, renovaciones=3)
    assert {e.tipo for e in lista} == {"compra", "renovacion"}
    for escenario in lista:
        if escenario.tipo == "compra":
            assert 1 <= len(escenario.lineas) <= 3
            assert 2 <= len(escenario.rfcs) <= 5
```

`services/negociacion/tests/test_simulacion.py`:

```python
"""Simulación con bots (spec §13): negocian por el portal contra la app real, dentro del proceso."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import httpx
import pytest
from comun.pruebas import ClavesPrueba
from generador.modelo import generar
from negociacion.config import Configuracion
from negociacion.eventos import aplicar
from negociacion.main import crear_app
from simulador.escenarios import bandas, contratos_por_proveedor, escenarios
from simulador.orquestador import Contexto, correr
from simulador.reporte import metricas, reporte
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
HOY = datetime(2026, 9, 15, 15, tzinfo=UTC)  # dos semanas después del último mes generado
SEMILLA = 42  # la misma de `python -m generador`: son los datos de datos/
ESPACIO = uuid.UUID("5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42")


def _id(clave: str) -> str:
    """Un id estable por RFC, código o folio."""
    return str(uuid.uuid5(ESPACIO, clave))


async def test_los_bots_nunca_cierran_fuera_de_limites(
    urls_bd: tuple[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    claves: ClavesPrueba,
) -> None:
    datos = generar(SEMILLA)
    referencias = bandas(datos, HOY.date())
    contratos = contratos_por_proveedor(datos, _id)
    async with fabrica() as bd, bd.begin():
        for s in datos.servicios:
            payload = {
                "id": _id(s.codigo),
                "codigo": s.codigo,
                "nombre": s.nombre,
                "categoria": s.categoria,
                "unidad": s.unidad,
                "moneda": s.moneda,
                "activo": True,
            }
            await aplicar(bd, {"event_id": str(uuid.uuid4()), "type": "servicio.actualizado", "payload": payload})
        for p in datos.proveedores:
            payload = {
                "id": _id(p.rfc),
                "nombre": p.nombre,
                "categorias": list(p.categorias),
                "contacto_nombre": p.contacto_nombre,
                "contacto_email": p.contacto_email,
                "activo": p.activo,
            }
            await aplicar(bd, {"event_id": str(uuid.uuid4()), "type": "proveedor.actualizado", "payload": payload})

    async def externos(peticion: httpx.Request) -> httpx.Response:
        partes = peticion.url.path.strip("/").split("/")
        if peticion.url.host == "intel":
            banda = referencias.get(partes[2])
            if banda is None:
                return httpx.Response(404, json={"codigo": "sin_observaciones"})
            return httpx.Response(
                200,
                json={
                    "p25": str(banda.p25),
                    "p50": str(banda.p50),
                    "p75": str(banda.p75),
                    "metodo": "linea_base",
                    "version": None,
                    "confianza": "normal",
                    "observaciones": 0,
                },
            )
        return httpx.Response(200, json=contratos.get(partes[1], []))

    async def sin_correo(_mensaje: EmailMessage) -> None:
        return None

    app = crear_app(
        Configuracion(
            database_url=urls_bd[1],
            usar_rabbitmq=False,
            inteligencia_url="http://intel",
            proveedores_url="http://prov",
        ),
        claves.validador(),
        fabrica,
        transporte=httpx.MockTransport(externos),
        enviar_correo=sin_correo,
        reloj=lambda: HOY,
    )

    def comprador() -> dict[str, str]:
        return {"Authorization": f"Bearer {claves.token('comprador', sub='comprador-sim')}"}

    lista = escenarios(datos, HOY.date())
    contexto = Contexto(datos, referencias, _id, HOY + timedelta(days=7))
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        resultados = await correr(cliente, comprador, contexto, lista)
    total = metricas(resultados)
    assert total.sesiones > 50
    assert total.fuera_de_limites == 0  # la meta dura del PRD §1.6
    ruta = os.environ.get("SIMULACION_REPORTE")
    if ruta:
        Path(ruta).write_text(reporte(resultados, lista, SEMILLA), encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tools/simulador services/negociacion/tests/test_simulacion.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'simulador'`.

- [ ] **Step 3: Write the implementation**

`tools/simulador/pyproject.toml`:

```toml
[project]
name = "simulador"
version = "0.1.0"
description = "Bots de proveedor que negocian por el portal para medir al agente"
requires-python = ">=3.13"
dependencies = ["generador", "httpx>=0.28"]

[tool.uv.sources]
generador = { workspace = true }

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

`tools/simulador/src/simulador/bots.py`:

```python
"""Bots de proveedor (spec §13): conceden según su estilo hasta su precio de reserva oculto.

El orquestador les da su verdad oculta (lista, reserva y estilo) y hacia dónde le conviene mover
cada término; del portal solo ven lo que vería un proveedor.
"""

import random
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any

PASO = {
    "precio": Decimal("0.01"),
    "plazo_meses": Decimal(1),
    "plazo_pago_dias": Decimal(1),
    "sla_disponibilidad": Decimal("0.01"),
    "tope_aumento_pct": Decimal("0.1"),
    "cuota_implementacion": Decimal("0.01"),
}
RANGOS = {
    "precio": (Decimal("0.01"), Decimal(10_000_000)),
    "plazo_meses": (Decimal(1), Decimal(60)),
    "plazo_pago_dias": (Decimal(0), Decimal(180)),
    "sla_disponibilidad": (Decimal(0), Decimal(100)),
    "tope_aumento_pct": (Decimal(0), Decimal(100)),
    "cuota_implementacion": (Decimal(0), Decimal(10_000_000)),
}
# Estilo → (β de sus concesiones, margen de su primera oferta sobre su precio de lista).
ESTILOS: dict[str, tuple[float, Decimal]] = {
    "duro": (0.4, Decimal("0.15")),
    "flexible": (2.0, Decimal("0.05")),
    "erratico": (1.0, Decimal("0.10")),
    "manipulador": (0.4, Decimal("0.15")),  # sus ataques de texto llegan en N2
}


def cuantizar(clave: str, valor: Decimal, mas_es_mejor: bool) -> Decimal:
    """En la precisión del término, redondeado a favor del bot y dentro del rango que se acepta."""
    minimo, maximo = RANGOS[clave]
    redondeado = valor.quantize(PASO[clave], rounding=ROUND_CEILING if mas_es_mejor else ROUND_FLOOR)
    return min(maximo, max(minimo, redondeado))


@dataclass(frozen=True)
class Termino:
    """Lo que el bot pide al empezar, lo peor que acepta y si a él le conviene más."""

    clave: str  # "precio" en las líneas
    inicio: Decimal
    reserva: Decimal
    mas_es_mejor: bool

    def en(self, avance: float) -> Decimal:
        """El valor a cierta fracción del camino de su inicio a su reserva."""
        valor = self.inicio + Decimal(repr(avance)) * (self.reserva - self.inicio)
        return cuantizar(self.clave, valor, self.mas_es_mejor)

    def acepta(self, valor: Decimal) -> bool:
        return valor >= self.reserva if self.mas_es_mejor else valor <= self.reserva


@dataclass
class Bot:
    estilo: str
    precios: dict[str, Termino]  # por id de línea
    palancas: dict[str, Termino]
    rng: random.Random
    _avance: float = field(default=0.0, repr=False)

    def oferta(self, k: int, rondas: int) -> dict[str, dict[str, str]]:
        """Su oferta número k; en la última ronda ofrece su reserva (mejor y última)."""
        beta, _ = ESTILOS[self.estilo]
        if self.estilo == "erratico":
            beta = self.rng.uniform(0.3, 2.0)
        avance = 1.0 if k >= rondas else (k / rondas) ** (1 / beta)
        if self.estilo == "erratico" and k < rondas and self.rng.random() < 0.2:
            avance = max(0.0, self._avance - 0.1)  # a veces retrocede
        self._avance = avance
        return {
            "precios": {linea: str(t.en(avance)) for linea, t in self.precios.items()},
            "palancas": {clave: str(t.en(avance)) for clave, t in self.palancas.items()},
        }

    def acepta(self, propuesta: dict[str, Any]) -> bool:
        return all(
            t.acepta(Decimal(str(propuesta["precios"][linea]))) for linea, t in self.precios.items()
        ) and all(
            t.acepta(Decimal(str(propuesta["palancas"][clave])))
            for clave, t in self.palancas.items()
        )
```

`tools/simulador/src/simulador/escenarios.py`:

```python
"""Escenarios de la simulación a partir del generador: compras y renovaciones con semilla fija."""

import random
import statistics
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from generador.modelo import DatosSinteticos

VENTANA_DIAS = 730  # 24 meses, como el benchmark de inteligencia
CUATRO_DECIMALES = Decimal("0.0001")


@dataclass(frozen=True)
class Banda:
    p25: Decimal
    p50: Decimal
    p75: Decimal


def bandas(datos: DatosSinteticos, hoy: date) -> dict[str, Banda]:
    """P25/P50/P75 del precio unitario de cada servicio en los contratos de los últimos 24 meses."""
    precios: dict[str, list[float]] = defaultdict(list)
    for fila in datos.contratos:
        if 0 <= (hoy - date.fromisoformat(fila["fecha_inicio"])).days <= VENTANA_DIAS:
            precios[fila["codigo_servicio"]].append(float(fila["precio_unitario"]))
    resultado: dict[str, Banda] = {}
    for codigo, valores in precios.items():
        if len(valores) >= 4:
            p25, p50, p75 = statistics.quantiles(valores, n=4, method="inclusive")
            resultado[codigo] = Banda(
                *(Decimal(repr(v)).quantize(CUATRO_DECIMALES) for v in (p25, p50, p75))
            )
    return resultado


@dataclass(frozen=True)
class LineaEscenario:
    codigo: str
    cantidad: Decimal


@dataclass(frozen=True)
class Escenario:
    tipo: str  # compra o renovacion
    titulo: str
    rfcs: tuple[str, ...]
    lineas: tuple[LineaEscenario, ...] = ()  # compra
    folio: str | None = None  # renovación: el contrato vigente
    con_plazo_de_pago: bool = False


def _vigente(fila: dict[str, str], hoy: date) -> bool:
    return date.fromisoformat(fila["fecha_inicio"]) <= hoy <= date.fromisoformat(fila["fecha_fin"])


def escenarios(
    datos: DatosSinteticos,
    hoy: date,
    compras: int = 20,
    renovaciones: int = 10,
    semilla: int = 7,
) -> list[Escenario]:
    rng = random.Random(semilla)  # noqa: S311 - simulación reproducible, no criptografía
    referencias = bandas(datos, hoy)
    servicios = {s.codigo: s for s in datos.servicios}
    activos = [p for p in datos.proveedores if p.activo]
    cantidades: dict[str, list[Decimal]] = defaultdict(list)
    for fila in datos.contratos:
        cantidades[fila["codigo_servicio"]].append(Decimal(fila["cantidad"]))
    resultado: list[Escenario] = []
    categorias = sorted({s.categoria for s in datos.servicios})
    for numero in range(compras):
        categoria = rng.choice(categorias)
        candidatos = [p for p in activos if categoria in p.categorias]
        codigos = sorted(
            c for c, s in servicios.items() if s.categoria == categoria and c in referencias
        )
        if len(candidatos) < 2 or not codigos:
            continue
        moneda = servicios[rng.choice(codigos)].moneda
        codigos = [c for c in codigos if servicios[c].moneda == moneda]
        elegidos = rng.sample(codigos, k=min(len(codigos), rng.randint(1, 3)))
        invitados = rng.sample(candidatos, k=min(len(candidatos), rng.randint(2, 5)))
        resultado.append(
            Escenario(
                "compra",
                f"Compra simulada {numero + 1}",
                tuple(p.rfc for p in invitados),
                tuple(
                    LineaEscenario(c, statistics.median_low(cantidades[c])) for c in elegidos
                ),
                con_plazo_de_pago=numero % 2 == 1,
            )
        )
    rfcs_activos = {p.rfc for p in activos}
    vigentes = sorted(
        {
            fila["folio"]: fila
            for fila in datos.contratos
            if _vigente(fila, hoy) and fila["rfc_proveedor"] in rfcs_activos
        }.items()
    )
    for folio, fila in rng.sample(vigentes, k=min(len(vigentes), renovaciones)):
        resultado.append(
            Escenario(
                "renovacion",
                f"Renovación simulada {folio}",
                (fila["rfc_proveedor"],),
                folio=folio,
                con_plazo_de_pago=True,
            )
        )
    return resultado


def contratos_por_proveedor(
    datos: DatosSinteticos, ids: Callable[[str], str]
) -> dict[str, list[dict[str, Any]]]:
    """Los contratos como los devuelve GET /proveedores/{id}/contratos de proveedores."""
    servicios = {s.codigo: s for s in datos.servicios}
    por_folio: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fila in datos.contratos:
        por_folio[fila["folio"]].append(fila)
    resultado: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for folio, filas in por_folio.items():
        cabecera = filas[0]
        resultado[ids(cabecera["rfc_proveedor"])].append(
            {
                "id": ids(folio),
                "folio": folio,
                "tipo": cabecera["tipo"],
                "fecha_inicio": cabecera["fecha_inicio"],
                "fecha_fin": cabecera["fecha_fin"],
                "moneda": cabecera["moneda"],
                "plazo_pago_dias": int(cabecera["plazo_pago_dias"]),
                "sla_disponibilidad": cabecera["sla_disponibilidad"] or None,
                "tope_aumento_pct": cabecera["tope_aumento_pct"] or None,
                "cuota_implementacion": cabecera["cuota_implementacion"],
                "lineas": [
                    {
                        "codigo_servicio": fila["codigo_servicio"],
                        "nombre_servicio": servicios[fila["codigo_servicio"]].nombre,
                        "unidad": servicios[fila["codigo_servicio"]].unidad,
                        "cantidad": fila["cantidad"],
                        "precio_unitario": fila["precio_unitario"],
                    }
                    for fila in filas
                ],
            }
        )
    return dict(resultado)
```

`tools/simulador/src/simulador/orquestador.py`:

```python
"""Corre los escenarios por la API (comprador y portal) y mide cada sesión (spec §13).

Solo usa HTTP: en las pruebas el cliente va a la app dentro del proceso; en N2, al stack real con
el token de servicio.
"""

import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
from generador.modelo import DatosSinteticos, ProveedorSintetico

from simulador.bots import ESTILOS, Bot, Termino, cuantizar
from simulador.escenarios import Banda, Escenario

FINALES = {"acuerdo_tentativo", "sin_acuerdo", "expirada"}
Encabezados = Callable[[], dict[str, str]]


@dataclass(frozen=True)
class Contexto:
    datos: DatosSinteticos
    bandas: dict[str, Banda]
    ids: Callable[[str], str]  # id estable por RFC, código o folio
    fecha_limite: datetime
    semilla: int = 11


@dataclass(frozen=True)
class Resultado:
    tipo: str
    estilo: str
    estado: str
    posible: bool  # la reserva del bot cabe en los límites del comprador
    primera: Decimal  # gasto de la primera oferta del proveedor: Σ cantidad × precio
    acordado: Decimal | None  # gasto del acuerdo tentativo
    fuera_de_limites: bool  # el acuerdo cruza algún límite del comprador

    @property
    def ahorro(self) -> float | None:
        return None if self.acordado is None else float(1 - self.acordado / self.primera)


def _ok(respuesta: httpx.Response, estado: int = 200) -> dict[str, Any]:
    if respuesta.status_code != estado:
        raise RuntimeError(
            f"{respuesta.request.method} {respuesta.request.url.path}: "
            f"{respuesta.status_code} {respuesta.text}"
        )
    return dict(respuesta.json())


def _cruza(ideal: Any, limite: Any, valor: Any) -> bool:
    ideal, limite, valor = Decimal(str(ideal)), Decimal(str(limite)), Decimal(str(valor))
    return valor > limite if ideal < limite else valor < limite


def dentro_de_limites(evento: dict[str, Any], valores: dict[str, Any]) -> bool:
    """Comprobación independiente del motor: ningún valor cruza el límite del comprador."""
    for linea in evento["lineas"]:
        if _cruza(linea["ideal"], linea["limite"], valores["precios"][str(linea["id"])]):
            return False
    for palanca in evento["palancas"]:
        if palanca["activa"] and palanca["clave"] != "precio":
            if _cruza(palanca["ideal"], palanca["limite"], valores["palancas"][palanca["clave"]]):
                return False
    return True


async def _crear(
    cliente: httpx.AsyncClient, comprador: Encabezados, contexto: Contexto, escenario: Escenario
) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "tipo": escenario.tipo,
        "titulo": escenario.titulo,
        "fecha_limite": contexto.fecha_limite.isoformat(),
    }
    if escenario.tipo == "compra":
        cuerpo["lineas"] = [
            {"codigo_servicio": linea.codigo, "cantidad": str(linea.cantidad)}
            for linea in escenario.lineas
        ]
        cuerpo["proveedores"] = [contexto.ids(rfc) for rfc in escenario.rfcs]
    else:
        cuerpo["proveedor_id"] = contexto.ids(escenario.rfcs[0])
        cuerpo["contrato_id"] = contexto.ids(str(escenario.folio))
    evento = _ok(await cliente.post("/eventos", json=cuerpo, headers=comprador()), 201)
    if escenario.con_plazo_de_pago:
        vigente = next(p["vigente"] for p in evento["palancas"] if p["clave"] == "plazo_pago_dias")
        base = Decimal(30) if vigente is None else Decimal(str(vigente))
        palancas = [
            {"clave": "precio", "peso": 80},
            {
                "clave": "plazo_pago_dias",
                "peso": 20,
                "ideal": str(min(base + 30, Decimal(180))),
                "limite": str(base),
            },
        ]
        evento = _ok(
            await cliente.patch(
                f"/eventos/{evento['id']}",
                json={"version": evento["version"], "palancas": palancas},
                headers=comprador(),
            )
        )
    if evento["errores"]:
        raise RuntimeError(f"La negociación simulada no se puede publicar: {evento['errores']}")
    return evento


def _bot(
    proveedor: ProveedorSintetico, evento: dict[str, Any], contexto: Contexto, rng: random.Random
) -> Bot:
    _, margen = ESTILOS[proveedor.estilo]
    precios: dict[str, Termino] = {}
    for linea in evento["lineas"]:
        banda = contexto.bandas.get(linea["codigo_servicio"])
        base = banda.p50 if banda is not None else Decimal(str(linea["precio_vigente"] or linea["limite"]))
        lista = base * Decimal(repr(proveedor.nivel_precio))
        precios[str(linea["id"])] = Termino(
            "precio",
            cuantizar("precio", lista * (1 + margen), True),
            cuantizar("precio", lista * (1 - Decimal(repr(proveedor.flexibilidad))), True),
            True,
        )
    palancas: dict[str, Termino] = {}
    for palanca in evento["palancas"]:
        if not palanca["activa"] or palanca["clave"] == "precio":
            continue
        clave = palanca["clave"]
        ideal, limite = Decimal(str(palanca["ideal"])), Decimal(str(palanca["limite"]))
        mas = ideal < limite  # al proveedor le conviene lo contrario que al comprador
        reserva = ideal + Decimal(repr(rng.uniform(0.2, 1.0))) * (limite - ideal)
        inicio = limite + (limite - ideal) / 4  # pide algo más allá del límite del comprador
        palancas[clave] = Termino(
            clave, cuantizar(clave, inicio, mas), cuantizar(clave, reserva, mas), mas
        )
    return Bot(proveedor.estilo, precios, palancas, rng)


def _cabe(bot: Bot, evento: dict[str, Any]) -> bool:
    """Si la reserva del bot cabe en los límites del comprador: si hay acuerdo posible."""
    reservas = {
        "precios": {linea: t.reserva for linea, t in bot.precios.items()},
        "palancas": {clave: t.reserva for clave, t in bot.palancas.items()},
    }
    return dentro_de_limites(evento, reservas)


async def _medir(
    cliente: httpx.AsyncClient,
    comprador: Encabezados,
    evento: dict[str, Any],
    sesion_id: str,
    bot: Bot,
) -> Resultado:
    detalle = _ok(await cliente.get(f"/sesiones/{sesion_id}", headers=comprador()))
    propias = [o for o in detalle["ofertas"] if o["autor"] == "proveedor"]
    cantidades = {str(linea["id"]): Decimal(str(linea["cantidad"])) for linea in evento["lineas"]}

    def gasto(valores: dict[str, Any]) -> Decimal:
        return sum(
            (cantidades[linea] * Decimal(str(p)) for linea, p in valores["precios"].items()),
            Decimal(0),
        )

    acuerdo = detalle["estado"] == "acuerdo_tentativo"
    return Resultado(
        tipo=evento["tipo"],
        estilo=bot.estilo,
        estado=detalle["estado"],
        posible=_cabe(bot, evento),
        primera=gasto(propias[0]["valores"]),
        acordado=gasto(propias[-1]["valores"]) if acuerdo else None,
        fuera_de_limites=acuerdo and not dentro_de_limites(evento, propias[-1]["valores"]),
    )


async def _negociar(
    cliente: httpx.AsyncClient,
    comprador: Encabezados,
    contexto: Contexto,
    escenario: Escenario,
    rng: random.Random,
) -> list[Resultado]:
    borrador = await _crear(cliente, comprador, contexto, escenario)
    publicado = _ok(await cliente.post(f"/eventos/{borrador['id']}/publicar", headers=comprador()))
    evento = publicado["evento"]
    verdad = {p.rfc: p for p in contexto.datos.proveedores}
    rfc_de = {contexto.ids(rfc): rfc for rfc in escenario.rfcs}
    proveedor_de = {str(s["id"]): str(s["proveedor_id"]) for s in evento["sesiones"]}
    bots: dict[str, Bot] = {}
    portales: dict[str, dict[str, str]] = {}
    for enlace in publicado["enlaces"]:
        sesion_id = str(enlace["sesion_id"])
        bots[sesion_id] = _bot(verdad[rfc_de[proveedor_de[sesion_id]]], evento, contexto, rng)
        portales[sesion_id] = {"Authorization": f"Invitacion {enlace['enlace'].split('#t=')[1]}"}
    pendientes = set(portales)
    for _ in range(2 * int(evento["rondas_max"]) + 2):  # tope por si una sesión no termina
        for sesion_id in sorted(pendientes):
            vista = _ok(await cliente.get("/portal/sesion", headers=portales[sesion_id]))
            if vista["estado"] in FINALES:
                pendientes.discard(sesion_id)
                continue
            bot = bots[sesion_id]
            propuesta = vista["ultima_propuesta"]
            if propuesta is not None and bot.acepta(propuesta):
                valores = propuesta  # acepta reenviando la propuesta del agente
            else:
                k = vista["rondas_max"] - vista["rondas_restantes"] + 1
                valores = bot.oferta(k, vista["rondas_max"])
            cuerpo = {"valores": valores, "confirmar_valores": vista["pide_confirmacion"]}
            _ok(
                await cliente.post(
                    "/portal/ofertas",
                    json=cuerpo,
                    headers=portales[sesion_id] | {"Idempotency-Key": uuid.uuid4().hex},
                )
            )
        if not pendientes:
            break
    return [
        await _medir(cliente, comprador, evento, sesion_id, bots[sesion_id])
        for sesion_id in sorted(portales)
    ]


async def correr(
    cliente: httpx.AsyncClient,
    comprador: Encabezados,
    contexto: Contexto,
    escenarios: list[Escenario],
) -> list[Resultado]:
    resultados: list[Resultado] = []
    for numero, escenario in enumerate(escenarios):
        rng = random.Random(contexto.semilla + numero)  # noqa: S311 - simulación reproducible
        resultados += await _negociar(cliente, comprador, contexto, escenario, rng)
    return resultados
```

`tools/simulador/src/simulador/reporte.py`:

```python
"""Métricas de la simulación y su reporte en Markdown (docs/qa/simulacion-negociacion.md)."""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from simulador.escenarios import Escenario
from simulador.orquestador import Resultado


@dataclass(frozen=True)
class Metricas:
    sesiones: int
    posibles: int
    acuerdos: int
    fuera_de_limites: int
    ahorro: float | None  # promedio sobre los acuerdos

    @property
    def tasa(self) -> float:
        return self.acuerdos / self.sesiones if self.sesiones else 0.0


def metricas(resultados: Sequence[Resultado]) -> Metricas:
    acuerdos = [r for r in resultados if r.estado == "acuerdo_tentativo"]
    ahorros = [r.ahorro for r in acuerdos if r.ahorro is not None]
    return Metricas(
        sesiones=len(resultados),
        posibles=sum(r.posible for r in resultados),
        acuerdos=len(acuerdos),
        fuera_de_limites=sum(r.fuera_de_limites for r in resultados),
        ahorro=statistics.fmean(ahorros) if ahorros else None,
    )


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor * 100:.1f} %"


def _fila(nombre: str, m: Metricas) -> str:
    return (
        f"| {nombre} | {m.sesiones} | {m.posibles} | {m.acuerdos} "
        f"| {_pct(m.tasa)} | {_pct(m.ahorro)} |"
    )


def reporte(resultados: Sequence[Resultado], escenarios: Sequence[Escenario], semilla: int) -> str:
    total = metricas(resultados)
    compras = sum(e.tipo == "compra" for e in escenarios)
    lineas = [
        "# Simulación de negociación con bots (N1)",
        "",
        f"- **Escenarios:** {compras} compras y {len(escenarios) - compras} renovaciones; "
        f"{total.sesiones} sesiones.",
        f"- **Datos:** `generador.modelo.generar({semilla})`, los mismos que escribe "
        "`python -m generador` en `datos/`.",
        "- **Cómo se corrió:** `SIMULACION_REPORTE=docs/qa/simulacion-negociacion.md uv run pytest "
        "services/negociacion/tests/test_simulacion.py`.",
        "- **Acuerdo posible:** la reserva del bot cabe en los límites del comprador. Sin ese "
        "traslape no hay acuerdo y lo correcto es cerrar sin acuerdo.",
        "",
        "| Métrica | Meta (PRD §1.6) | Resultado |",
        "|---|---|---|",
        f"| Acuerdos fuera de los límites del comprador | 0 | {total.fuera_de_limites} |",
        f"| Tasa de acuerdo | ≥ 70 % | {_pct(total.tasa)} |",
        "| Ahorro frente a la primera oferta (promedio de los acuerdos) | ≥ 8 % "
        f"| {_pct(total.ahorro)} |",
        f"| Sesiones con acuerdo posible | — | {total.posibles} de {total.sesiones} |",
        "",
        "## Por estilo de proveedor",
        "",
        "| Estilo | Sesiones | Acuerdo posible | Acuerdos | Tasa | Ahorro |",
        "|---|---|---|---|---|---|",
    ]
    for estilo in sorted({r.estilo for r in resultados}):
        lineas.append(_fila(estilo, metricas([r for r in resultados if r.estilo == estilo])))
    lineas += [
        "",
        "## Por tipo de negociación",
        "",
        "| Tipo | Sesiones | Acuerdo posible | Acuerdos | Tasa | Ahorro |",
        "|---|---|---|---|---|---|",
    ]
    for tipo in ("compra", "renovacion"):
        lineas.append(_fila(tipo, metricas([r for r in resultados if r.tipo == tipo])))
    return "\n".join(lineas) + "\n"
```

En el `pyproject.toml` de la raíz:
1. Agregue `"simulador",` al grupo `dev`.
2. Agregue `simulador = { workspace = true }` en `[tool.uv.sources]`.
3. Agregue `"simulador"` a `source` de `[tool.coverage.run]` y a `packages` de `[tool.mypy]`.

Después:

```bash
uv lock
uv sync --all-packages
```

- [ ] **Step 4: Run tests and write the report**

Run: `uv run pytest tools/simulador -q`
Expected: PASS.

Run (Git Bash): `SIMULACION_REPORTE=docs/qa/simulacion-negociacion.md uv run pytest services/negociacion/tests/test_simulacion.py -q`
Expected: PASS, con 0 acuerdos fuera de límites. Se crea `docs/qa/simulacion-negociacion.md`.

Lea el reporte y agregue al final una sección `## Lectura` con dos a cuatro oraciones que digan:
- los números obtenidos;
- si se alcanzan las metas de tasa de acuerdo y de ahorro;
- cuánto de la tasa se explica por las sesiones sin acuerdo posible.

Use solo cifras del reporte. **Si alguna meta no se cumple, no cambie el motor ni los valores sugeridos en esta tarea.** La lectura lo dice con sus números y propone el ajuste del PRD §3.2: un límite sugerido cercano a P60, o los valores de β. El controlador lo decide con el residente (spec §1).

Run: `uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest -q`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add tools/simulador services/negociacion/tests/test_simulacion.py docs/qa/simulacion-negociacion.md pyproject.toml uv.lock
git commit -m "feat(simulador): bots de proveedor y simulación de la negociación con su reporte" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
