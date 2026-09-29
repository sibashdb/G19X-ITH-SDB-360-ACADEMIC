# Incremento 1 — Esqueleto funcional + servicio de proveedores: Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levantar con `docker compose` la base de la plataforma (PostgreSQL, RabbitMQ, Keycloak, gateway Nginx) con el primer microservicio real (`proveedores`), el cual importa los CSV del "ERP" simulado, publica eventos vía outbox y se consulta desde la SPA en React con inicio de sesión OIDC.

**Architecture:** Monorepo con workspace de uv. `libs/comun` concentra la infraestructura transversal (logs JSON con correlation id, errores RFC 9457, validación JWT contra JWKS de Keycloak, salud, outbox transaccional). `services/proveedores` separa lógica pura (parseo/validación de CSV) de adaptadores (SQLAlchemy async, FastAPI, aio-pika). `tools/generador` produce datos sintéticos reproducibles. `web/` es una SPA React servida por el gateway Nginx, que también enruta `/api/*` y `/auth/*`.

**Tech Stack:** Python 3.13, uv, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2 (asyncpg), Alembic, PyJWT, aio-pika, pytest + pytest-asyncio + Testcontainers, ruff, mypy · React + TypeScript + Vite, Tailwind + shadcn/ui, React Router, TanStack Query, react-oidc-context, Vitest · PostgreSQL 17, RabbitMQ 4.1, Keycloak 26.5, Nginx · GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md` (secciones 2, 4.1, 4.2, 5.1–5.4, 6.1–6.3 y fila "Incremento 1" de 6.6).

## Global Constraints

- Python **3.13** fijado en `.python-version`; dependencias con **uv** (un solo `uv.lock` para todo el workspace).
- Dinero en `NUMERIC(14,4)` + código de moneda; `Decimal` en Python. **Nunca `float`** para montos.
- Fechas-hora en UTC (`timestamptz`).
- **Ningún servicio lee la base de datos de otro**: una base de datos y un usuario por servicio; `REVOKE CONNECT … FROM PUBLIC`.
- Eventos con **outbox transaccional**; exchange *topic* `eventos`; envelope: `event_id`, `type`, `version`, `occurred_at`, `correlation_id`, `payload`.
- Errores HTTP en formato **Problem Details (RFC 9457)** con `correlation_id`; nunca trazas de pila en respuestas.
- Logs **JSON** con `correlation_id` tomado de `X-Request-ID`; nunca tokens ni secretos en logs.
- Identidad: Keycloak OIDC *authorization code + PKCE*; roles de realm `admin`, `comprador`, `aprobador`; JWT RS256 validado (firma vía JWKS, `iss`, `aud`, `exp`); **OTP obligatorio** para admin y aprobador; token de acceso de 5 min.
- CSV de importación **≤ 10 MB**.
- Gateway: límite de tasa, cabeceras CSP, `X-Content-Type-Options`, `frame-ancestors 'none'`, `Referrer-Policy: no-referrer`; todo bajo el mismo origen (sin CORS).
- Datos sintéticos **sin marcas reales**, RFC ficticios con formato válido, semilla reproducible.
- Interfaz y mensajes en **español (México)**.
- Secretos en `.env` fuera de git; `.env.example` versionado.
- Cobertura de pruebas ≥ **80 %**.

## Review Focus

1. **CSV guardado con Excel en español** (separador `;` y BOM UTF-8) → debe importarse igual que un CSV con comas. Prueba en la Tarea 8.
2. **Archivo que no está en UTF-8** (Excel "CSV delimitado por comas" en cp1252) → error 422 claro "El archivo debe estar codificado en UTF-8", nunca un 500. Pruebas en las Tareas 8 y 10.
3. **Reimportar el mismo archivo** → idempotente: no duplica contratos ni emite `contrato.registrado` otra vez. Prueba en la Tarea 9.
4. **Búsqueda con `%` o `_`** → se trata como texto literal, no como comodín. Prueba en la Tarea 10.
5. **Token vencido, de otro emisor o de otra audiencia** → 401; comprador que intenta importar → 403. Pruebas en las Tareas 4 y 10.

## Diferido conscientemente (fuera de este incremento)

| Qué | Cuándo | Por qué |
|---|---|---|
| Ollama y servicio `ia` | Incremento 3 | Nada lo consume antes. |
| FastStream y consumidores idempotentes con DLQ | Incremento 2 | El primer suscriptor aparece con `inteligencia`. El relay del outbox publica con aio-pika (el transporte que usa FastStream) para controlar persistencia y confirmaciones. |
| Reproceso del outbox | Incremento 2 | Sin colas enlazadas, RabbitMQ descarta los eventos; los datos siguen en `proveedores_db` y el outbox permite republicarlos. |
| Token de servicio (*client credentials*) | Incremento 3 | Aún no hay llamadas entre servicios. |
| Observabilidad (`otel-lgtm`), Playwright, ZAP, Trivy, Locust | Incrementos 4–5 | Según la tabla 6.6 del spec. |
| Alta/edición manual de proveedores | — | El ERP es la fuente de verdad; se alimenta por importación. |

## Prerrequisitos (los instala el residente)

- Docker Desktop con WSL 2 (ya instalado y verificado).
- Node 24 (ya instalado).
- **uv**: `winget install --id=astral-sh.uv -e` y abrir una terminal nueva; verificar con `uv --version`.

## Estructura de archivos

```
.gitattributes · .gitignore · .editorconfig · .dockerignore · .gitleaks.toml
.python-version · pyproject.toml · uv.lock · README.md
libs/comun/
  pyproject.toml
  src/comun/__init__.py      versión del paquete
  src/comun/config.py        ConfiguracionBase (pydantic-settings)
  src/comun/logs.py          FormatoJSON, configurar_logs, correlation_id, middleware_correlacion
  src/comun/errores.py       ErrorDominio, registrar_manejadores (RFC 9457)
  src/comun/auth.py          Usuario, ValidadorJWT, validador_desde_jwks, usuario_actual, requiere_rol
  src/comun/pruebas.py       ClavesPrueba (tokens firmados para pruebas)
  src/comun/salud.py         crear_router_salud
  src/comun/outbox.py        ColumnasOutbox, registrar_evento, sobre_evento, RelayOutbox
  tests/test_paquete.py · test_logs.py · test_errores.py · test_auth.py · test_salud.py · test_outbox.py
services/proveedores/
  pyproject.toml · Dockerfile · alembic.ini
  alembic/env.py · alembic/script.py.mako · alembic/versions/0001_esquema_inicial.py
  src/proveedores/__init__.py
  src/proveedores/config.py            Configuracion
  src/proveedores/db.py                Base, obtener_sesion
  src/proveedores/modelos.py           entidades ORM
  src/proveedores/importacion/esquemas.py   filas Pydantic por entidad
  src/proveedores/importacion/parseo.py     CSV → filas válidas + errores (puro)
  src/proveedores/importacion/aplicar.py    upserts + eventos (BD)
  src/proveedores/importacion/cli.py        carga masiva desde carpeta
  src/proveedores/api/esquemas.py · api/rutas.py
  src/proveedores/main.py              crear_app
  tests/conftest.py · test_migraciones.py · test_parseo.py · test_aplicar.py · test_api.py · test_datos_generados.py
tools/generador/
  pyproject.toml
  src/generador/catalogo.py · modelo.py · salida.py · __main__.py · __init__.py
  tests/test_generador.py
infra/
  docker-compose.yml · .env.example · smoke_test.py
  postgres/init.sh · keycloak/realm-plataforma.json · nginx/nginx.conf
web/                                   (andamiaje de shadcn + Vite)
  Dockerfile · vite.config.ts
  src/main.tsx · src/auth.ts · src/api.ts · src/tipos.ts · src/rutas.tsx
  src/componentes/Layout.tsx
  src/paginas/Inicio.tsx · Proveedores.tsx · ProveedorDetalle.tsx · Importacion.tsx · NoEncontrado.tsx
  src/auth.test.ts · src/paginas/Importacion.test.tsx · src/setupPruebas.ts
.github/workflows/ci.yml · .github/dependabot.yml · .github/pull_request_template.md
```

**Comandos:** todos se ejecutan desde la raíz del repositorio. Las pruebas marcadas como de integración levantan contenedores con Testcontainers, así que **Docker Desktop debe estar encendido**.

---

### Task 1: Cimientos del repositorio y workspace de uv

**Files:**
- Create: `.gitattributes`, `.gitignore`, `.editorconfig`, `.dockerignore`, `.python-version`, `pyproject.toml`
- Create: `libs/comun/pyproject.toml`, `libs/comun/src/comun/__init__.py`
- Test: `libs/comun/tests/test_paquete.py`

**Interfaces:**
- Produces: paquete instalable `comun` (`comun.__version__ == "0.1.0"`); configuración compartida de pytest, ruff, mypy y coverage en `pyproject.toml` raíz.

- [ ] **Step 1: Crear los archivos de configuración del repositorio**

`.gitattributes`:
```
* text=auto eol=lf
*.pdf binary
*.png binary
*.ps1 text eol=crlf
```

`.gitignore`:
```
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
# Node
node_modules/
web/dist/
# Entorno y datos generados
.env
infra/.env
datos/
# Documento base con datos de la empresa
*.pdf
# Editores
.vscode/
.idea/
```

`.editorconfig`:
```
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 4

[*.{ts,tsx,js,json,yml,yaml,css,html}]
indent_size = 2
```

`.dockerignore`:
```
.git
**/.venv
**/__pycache__
**/node_modules
web/dist
datos
**/.pytest_cache
**/.mypy_cache
**/.ruff_cache
.env
infra/.env
*.pdf
```

`.python-version`:
```
3.13
```

- [ ] **Step 2: Crear el `pyproject.toml` raíz (workspace, herramientas y dependencias de desarrollo)**

```toml
[project]
name = "plataforma-negociacion"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = []

[dependency-groups]
dev = [
    "comun",
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "pytest-cov>=6.0",
    "httpx>=0.28",
    "testcontainers[postgres,rabbitmq]>=4.9",
    "ruff>=0.8",
    "mypy>=1.13",
]

[tool.uv]
package = false

[tool.uv.workspace]
members = ["libs/*", "services/*", "tools/*"]

[tool.uv.sources]
comun = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["libs", "services", "tools"]
addopts = "--import-mode=importlib"
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
markers = ["integracion: requiere Docker (Testcontainers)"]

[tool.coverage.run]
branch = true
source = ["comun"]

[tool.coverage.report]
fail_under = 80
show_missing = true
skip_covered = true

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "S", "ASYNC", "RUF"]

[tool.ruff.lint.per-file-ignores]
"**/tests/**" = ["S101", "S105", "S106"]

[tool.mypy]
python_version = "3.13"
strict = true
packages = ["comun"]
plugins = ["pydantic.mypy"]
```

> Las tareas 7 y 11 agregan `proveedores` y `generador` a `dev`, a `[tool.uv.sources]`, a `coverage.run.source` y a `mypy.packages`.

- [ ] **Step 3: Crear el paquete `comun`**

`libs/comun/pyproject.toml`:
```toml
[project]
name = "comun"
version = "0.1.0"
description = "Infraestructura transversal de los microservicios"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "pydantic-settings>=2.6",
    "pyjwt[crypto]>=2.10",
    "sqlalchemy[asyncio]>=2.0.36",
    "aio-pika>=9.5",
]

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

`libs/comun/src/comun/__init__.py`:
```python
"""Infraestructura transversal compartida por los microservicios."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Escribir la prueba de empaquetado**

`libs/comun/tests/test_paquete.py`:
```python
import comun


def test_paquete_se_importa_con_su_version() -> None:
    assert comun.__version__ == "0.1.0"
```

- [ ] **Step 5: Sincronizar el entorno y correr las verificaciones**

Run: `uv sync --all-packages`
Expected: crea `.venv` y `uv.lock` sin errores.

Run: `uv run pytest -v`
Expected: `1 passed`.

Run: `uv run ruff check . ; uv run ruff format --check . ; uv run mypy`
Expected: sin errores (`Success: no issues found`).

- [ ] **Step 6: Normalizar finales de línea y hacer commit**

```bash
git add --renormalize .
git add .gitattributes .gitignore .editorconfig .dockerignore .python-version pyproject.toml uv.lock libs/
git commit -m "chore: crear workspace de uv y paquete comun"
```

---

### Task 2: Logs JSON con correlation id

**Files:**
- Create: `libs/comun/src/comun/logs.py`
- Test: `libs/comun/tests/test_logs.py`

**Interfaces:**
- Produces:
  - `correlation_id: ContextVar[str]` (valor por defecto `"-"`).
  - `CABECERA_CORRELACION = "X-Request-ID"`.
  - `class FormatoJSON(logging.Formatter)` con `__init__(servicio: str)`.
  - `configurar_logs(servicio: str, nivel: str = "INFO") -> None`.
  - `async middleware_correlacion(request, call_next) -> Response`, que se registra con `app.middleware("http")(middleware_correlacion)`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`libs/comun/tests/test_logs.py`:
```python
import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from comun.logs import (
    CABECERA_CORRELACION,
    FormatoJSON,
    configurar_logs,
    correlation_id,
    middleware_correlacion,
)


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(middleware_correlacion)

    @app.get("/eco")
    async def eco() -> dict[str, str]:
        return {"correlation_id": correlation_id.get()}

    return app


def test_formato_json_incluye_servicio_mensaje_y_correlation_id() -> None:
    token = correlation_id.set("abc-123")
    try:
        registro = logging.LogRecord(
            "prueba", logging.INFO, __file__, 1, "hola %s", ("mundo",), None
        )
        linea = json.loads(FormatoJSON("proveedores").format(registro))
    finally:
        correlation_id.reset(token)
    assert linea["mensaje"] == "hola mundo"
    assert linea["servicio"] == "proveedores"
    assert linea["correlation_id"] == "abc-123"
    assert linea["nivel"] == "INFO"


def test_configurar_logs_instala_un_solo_manejador_json() -> None:
    raiz = logging.getLogger()
    anteriores = raiz.handlers[:]
    try:
        configurar_logs("proveedores", "WARNING")
        assert len(raiz.handlers) == 1
        assert isinstance(raiz.handlers[0].formatter, FormatoJSON)
        assert raiz.level == logging.WARNING
    finally:
        raiz.handlers = anteriores


def test_middleware_reutiliza_el_id_valido_del_gateway() -> None:
    respuesta = TestClient(_app()).get("/eco", headers={CABECERA_CORRELACION: "req-42"})
    assert respuesta.headers[CABECERA_CORRELACION] == "req-42"
    assert respuesta.json() == {"correlation_id": "req-42"}


def test_middleware_reemplaza_un_id_con_caracteres_no_permitidos() -> None:
    malicioso = 'x" {"nivel": "CRITICAL"}'
    respuesta = TestClient(_app()).get("/eco", headers={CABECERA_CORRELACION: malicioso})
    generado = respuesta.headers[CABECERA_CORRELACION]
    assert generado != malicioso
    assert len(generado) == 32
    assert respuesta.json() == {"correlation_id": generado}


def test_middleware_genera_id_si_no_llega() -> None:
    respuesta = TestClient(_app()).get("/eco")
    assert len(respuesta.headers[CABECERA_CORRELACION]) == 32
```

- [ ] **Step 2: Ejecutar para verificar que fallan**

Run: `uv run pytest libs/comun/tests/test_logs.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'comun.logs'`.

- [ ] **Step 3: Implementar**

`libs/comun/src/comun/logs.py`:
```python
"""Logs JSON estructurados con identificador de correlación por petición."""

import json
import logging
import re
import sys
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import Request, Response

CABECERA_CORRELACION = "X-Request-ID"
_CORRELACION_VALIDA = re.compile(r"^[A-Za-z0-9-]{1,64}$")

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class FormatoJSON(logging.Formatter):
    """Una línea JSON por registro, con el servicio y el correlation id vigente."""

    def __init__(self, servicio: str) -> None:
        super().__init__()
        self.servicio = servicio

    def format(self, record: logging.LogRecord) -> str:
        datos = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "servicio": self.servicio,
            "logger": record.name,
            "mensaje": record.getMessage(),
            "correlation_id": correlation_id.get(),
        }
        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False)


def configurar_logs(servicio: str, nivel: str = "INFO") -> None:
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormatoJSON(servicio))
    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(nivel)


async def middleware_correlacion(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Toma X-Request-ID del gateway (o genera uno) y lo devuelve en la respuesta."""
    recibido = request.headers.get(CABECERA_CORRELACION, "")
    valor = recibido if _CORRELACION_VALIDA.fullmatch(recibido) else uuid.uuid4().hex
    # Sin reset: cada petición corre en su propia tarea, y así el manejador de
    # errores 500 (que corre fuera de este middleware) todavía ve el valor.
    correlation_id.set(valor)
    respuesta = await call_next(request)
    respuesta.headers[CABECERA_CORRELACION] = valor
    return respuesta
```

- [ ] **Step 4: Ejecutar para verificar que pasan**

Run: `uv run pytest libs/comun/tests/test_logs.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add libs/comun/src/comun/logs.py libs/comun/tests/test_logs.py
git commit -m "feat(comun): logs JSON con correlation id por peticion"
```

---

### Task 3: Errores en formato Problem Details (RFC 9457)

**Files:**
- Create: `libs/comun/src/comun/errores.py`
- Test: `libs/comun/tests/test_errores.py`

**Interfaces:**
- Consumes: `comun.logs.correlation_id`, `comun.logs.middleware_correlacion`.
- Produces:
  - `class ErrorDominio(Exception)`, con `__init__(estado: int, titulo: str, detalle: str, extra: dict[str, Any] | None = None)`.
  - `registrar_manejadores(app: FastAPI) -> None`.
  - Cuerpo de respuesta: `type`, `title`, `status`, `detail`, `instance`, `correlation_id`, más las claves de `extra`. Media type: `application/problem+json`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`libs/comun/tests/test_errores.py`:
```python
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from comun.errores import ErrorDominio, registrar_manejadores
from comun.logs import middleware_correlacion


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    @app.get("/dominio")
    async def dominio() -> None:
        raise ErrorDominio(409, "Conflicto", "El folio ya existe", {"folio": "C-1"})

    @app.get("/no-autenticado")
    async def no_autenticado() -> None:
        raise HTTPException(401, "Se requiere iniciar sesión", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/numero/{n}")
    async def numero(n: int) -> dict[str, int]:
        return {"n": n}

    @app.get("/falla")
    async def falla() -> None:
        raise RuntimeError("detalle interno secreto")

    return app


cliente = TestClient(_app(), raise_server_exceptions=False)


def test_error_de_dominio_usa_problem_details() -> None:
    respuesta = cliente.get("/dominio", headers={"X-Request-ID": "req-1"})
    assert respuesta.status_code == 409
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.json() == {
        "type": "about:blank",
        "title": "Conflicto",
        "status": 409,
        "detail": "El folio ya existe",
        "instance": "/dominio",
        "correlation_id": "req-1",
        "folio": "C-1",
    }


def test_http_exception_conserva_cabeceras_y_titulo_en_espanol() -> None:
    respuesta = cliente.get("/no-autenticado")
    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
    assert respuesta.json()["title"] == "No autenticado"
    assert respuesta.json()["detail"] == "Se requiere iniciar sesión"


def test_ruta_inexistente_responde_404_en_espanol() -> None:
    respuesta = cliente.get("/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.json()["title"] == "No encontrado"


def test_validacion_lista_los_campos_con_error() -> None:
    respuesta = cliente.get("/numero/abc")
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["title"] == "Solicitud inválida"
    assert cuerpo["errores"][0]["campo"] == "path.n"


def test_error_inesperado_no_filtra_detalles_internos() -> None:
    respuesta = cliente.get("/falla", headers={"X-Request-ID": "req-9"})
    assert respuesta.status_code == 500
    assert "secreto" not in respuesta.text
    assert respuesta.json()["title"] == "Error interno"
    assert respuesta.json()["correlation_id"] == "req-9"
```

- [ ] **Step 2: Ejecutar para verificar que fallan**

Run: `uv run pytest libs/comun/tests/test_errores.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'comun.errores'`.

- [ ] **Step 3: Implementar**

`libs/comun/src/comun/errores.py`:
```python
"""Respuestas de error en formato Problem Details (RFC 9457)."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from comun.logs import correlation_id

log = logging.getLogger(__name__)

TITULOS = {
    400: "Solicitud incorrecta",
    401: "No autenticado",
    403: "Sin permiso",
    404: "No encontrado",
    405: "Método no permitido",
    413: "Contenido demasiado grande",
    422: "Solicitud inválida",
    429: "Demasiadas solicitudes",
    503: "Servicio no disponible",
}


class ErrorDominio(Exception):
    """Error esperado del negocio; se devuelve al cliente tal cual."""

    def __init__(
        self, estado: int, titulo: str, detalle: str, extra: dict[str, Any] | None = None
    ) -> None:
        super().__init__(detalle)
        self.estado = estado
        self.titulo = titulo
        self.detalle = detalle
        self.extra = extra or {}


def _problema(
    request: Request,
    estado: int,
    titulo: str,
    detalle: str,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    cuerpo: dict[str, Any] = {
        "type": "about:blank",
        "title": titulo,
        "status": estado,
        "detail": detalle,
        "instance": request.url.path,
        "correlation_id": correlation_id.get(),
        **(extra or {}),
    }
    return JSONResponse(
        cuerpo, status_code=estado, media_type="application/problem+json", headers=headers
    )


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDominio)
    async def _dominio(request: Request, exc: ErrorDominio) -> JSONResponse:
        return _problema(request, exc.estado, exc.titulo, exc.detalle, exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        titulo = TITULOS.get(exc.status_code, HTTPStatus(exc.status_code).phrase)
        return _problema(request, exc.status_code, titulo, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        errores = [
            {"campo": ".".join(str(parte) for parte in e["loc"]), "mensaje": e["msg"]}
            for e in exc.errors()
        ]
        return _problema(
            request, 422, TITULOS[422], "Revise los campos indicados.", {"errores": errores}
        )

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Error no controlado en %s", request.url.path)
        return _problema(
            request,
            500,
            "Error interno",
            "Ocurrió un error inesperado. Reporte el correlation_id a soporte.",
        )
```

- [ ] **Step 4: Ejecutar para verificar que pasan**

Run: `uv run pytest libs/comun/tests/test_errores.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add libs/comun/src/comun/errores.py libs/comun/tests/test_errores.py
git commit -m "feat(comun): errores en formato Problem Details"
```

---

### Task 4: Validación de JWT y autorización por roles

**Files:**
- Create: `libs/comun/src/comun/auth.py`, `libs/comun/src/comun/pruebas.py`
- Test: `libs/comun/tests/test_auth.py`

**Interfaces:**
- Consumes: `comun.errores.registrar_manejadores` (en las pruebas).
- Produces:
  - `ROLES_INTERNOS = ("admin", "comprador", "aprobador")`.
  - `@dataclass(frozen=True) class Usuario(id: str, nombre: str, roles: frozenset[str])`.
  - `class ValidadorJWT(emisor: str, audiencia: str, obtener_clave: Callable[[str], Any])`, con el método `validar(token: str) -> Usuario`.
  - `validador_desde_jwks(emisor: str, audiencia: str, url_jwks: str) -> ValidadorJWT`.
  - Dependencia `usuario_actual(request, credenciales) -> Usuario`. Lee el validador de `request.app.state.validador`.
  - `requiere_rol(*roles: str) -> Callable[[Usuario], Usuario]`, para usar con `Depends(requiere_rol(...))`.
  - `class ClavesPrueba` (en `comun.pruebas`):
    - `EMISOR = "http://prueba/realms/plataforma"` y `AUDIENCIA = "plataforma-api"`.
    - `validador() -> ValidadorJWT`.
    - `token(*roles: str, sub: str = "usuario-prueba", **extra: Any) -> str`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`libs/comun/tests/test_auth.py`:
```python
import time
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import Response

from comun.auth import Usuario, requiere_rol, usuario_actual, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.pruebas import ClavesPrueba

claves = ClavesPrueba()


def _app() -> FastAPI:
    app = FastAPI()
    registrar_manejadores(app)
    app.state.validador = claves.validador()

    @app.get("/yo")
    def yo(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> dict[str, Any]:
        return {"id": usuario.id, "nombre": usuario.nombre, "roles": sorted(usuario.roles)}

    @app.get("/solo-admin")
    def solo_admin(usuario: Annotated[Usuario, Depends(requiere_rol("admin"))]) -> dict[str, str]:
        return {"id": usuario.id}

    return app


cliente = TestClient(_app())


def _get(ruta: str, token: str | None = None) -> Response:
    cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.get(ruta, headers=cabeceras)


def test_token_valido_devuelve_usuario_y_roles() -> None:
    respuesta = _get("/yo", claves.token("comprador", sub="u-1"))
    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": "u-1", "nombre": "u-1", "roles": ["comprador"]}


def test_sin_token_responde_401_con_www_authenticate() -> None:
    respuesta = _get("/yo")
    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "extra",
    [{"exp": int(time.time()) - 10}, {"iss": "http://otro-emisor"}, {"aud": "otra-api"}],
    ids=["vencido", "otro-emisor", "otra-audiencia"],
)
def test_token_vencido_o_ajeno_responde_401(extra: dict[str, Any]) -> None:
    assert _get("/yo", claves.token("admin", **extra)).status_code == 401


def test_token_firmado_con_otra_clave_responde_401() -> None:
    assert _get("/yo", ClavesPrueba().token("admin")).status_code == 401


def test_token_basura_responde_401() -> None:
    assert _get("/yo", "no-es-un-jwt").status_code == 401


def test_rol_insuficiente_responde_403() -> None:
    respuesta = _get("/solo-admin", claves.token("comprador"))
    assert respuesta.status_code == 403
    assert respuesta.json()["title"] == "Sin permiso"


def test_rol_suficiente_responde_200() -> None:
    assert _get("/solo-admin", claves.token("admin", sub="a-1")).json() == {"id": "a-1"}


def test_jwks_inaccesible_responde_503() -> None:
    validador = validador_desde_jwks(
        ClavesPrueba.EMISOR, ClavesPrueba.AUDIENCIA, "http://127.0.0.1:9/certs"
    )
    with pytest.raises(HTTPException) as error:
        validador.validar(claves.token("admin"))
    assert error.value.status_code == 503
```

- [ ] **Step 2: Ejecutar para verificar que fallan**

Run: `uv run pytest libs/comun/tests/test_auth.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'comun.auth'`.

- [ ] **Step 3: Implementar la validación y las dependencias**

`libs/comun/src/comun/auth.py`:
```python
"""Validación de JWT emitidos por Keycloak y autorización por roles de realm."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWKClientConnectionError

ROLES_INTERNOS = ("admin", "comprador", "aprobador")


@dataclass(frozen=True)
class Usuario:
    id: str
    nombre: str
    roles: frozenset[str]


def _no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detalle, headers={"WWW-Authenticate": "Bearer"}
    )


class ValidadorJWT:
    """Valida firma RS256, emisor, audiencia y vigencia.

    `obtener_clave` recibe el token y devuelve la clave pública con la que se firmó.
    """

    def __init__(self, emisor: str, audiencia: str, obtener_clave: Callable[[str], Any]) -> None:
        self._emisor = emisor
        self._audiencia = audiencia
        self._obtener_clave = obtener_clave

    def validar(self, token: str) -> Usuario:
        try:
            datos = jwt.decode(
                token,
                self._obtener_clave(token),
                algorithms=["RS256"],
                audience=self._audiencia,
                issuer=self._emisor,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except PyJWKClientConnectionError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "El servicio de identidad no está disponible"
            ) from exc
        except jwt.PyJWTError as exc:
            raise _no_autenticado("Token inválido o vencido") from exc
        roles = datos.get("realm_access", {}).get("roles", [])
        return Usuario(
            id=datos["sub"],
            nombre=datos.get("preferred_username", datos["sub"]),
            roles=frozenset(roles),
        )


def validador_desde_jwks(emisor: str, audiencia: str, url_jwks: str) -> ValidadorJWT:
    cliente = jwt.PyJWKClient(url_jwks, cache_keys=True)
    return ValidadorJWT(emisor, audiencia, lambda token: cliente.get_signing_key_from_jwt(token).key)


_esquema_bearer = HTTPBearer(auto_error=False)


def usuario_actual(
    request: Request,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_esquema_bearer)],
) -> Usuario:
    # Dependencia síncrona a propósito: PyJWKClient hace HTTP bloqueante y FastAPI
    # ejecuta las dependencias `def` en el threadpool.
    if credenciales is None:
        raise _no_autenticado("Se requiere iniciar sesión")
    validador: ValidadorJWT = request.app.state.validador
    return validador.validar(credenciales.credentials)


def requiere_rol(*roles: str) -> Callable[[Usuario], Usuario]:
    permitidos = frozenset(roles)

    def verificar(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> Usuario:
        if not usuario.roles & permitidos:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permiso para esta acción")
        return usuario

    return verificar
```

- [ ] **Step 4: Implementar el ayudante de pruebas**

`libs/comun/src/comun/pruebas.py`:
```python
"""Claves RSA efímeras y tokens firmados para pruebas automatizadas."""

import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from comun.auth import ValidadorJWT


class ClavesPrueba:
    EMISOR = "http://prueba/realms/plataforma"
    AUDIENCIA = "plataforma-api"

    def __init__(self) -> None:
        self._privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def validador(self) -> ValidadorJWT:
        publica = self._privada.public_key()
        return ValidadorJWT(self.EMISOR, self.AUDIENCIA, lambda _token: publica)

    def token(self, *roles: str, sub: str = "usuario-prueba", **extra: Any) -> str:
        ahora = int(time.time())
        datos: dict[str, Any] = {
            "sub": sub,
            "preferred_username": sub,
            "iss": self.EMISOR,
            "aud": self.AUDIENCIA,
            "iat": ahora,
            "exp": ahora + 300,
            "realm_access": {"roles": list(roles)},
            **extra,
        }
        return jwt.encode(datos, self._privada, algorithm="RS256")
```

- [ ] **Step 5: Ejecutar para verificar que pasan**

Run: `uv run pytest libs/comun/tests/test_auth.py -v`
Expected: `10 passed`.

- [ ] **Step 6: Commit**

```bash
git add libs/comun/src/comun/auth.py libs/comun/src/comun/pruebas.py libs/comun/tests/test_auth.py
git commit -m "feat(comun): validacion de JWT de Keycloak y roles"
```

---

### Task 5: Configuración base y endpoints de salud

**Files:**
- Create: `libs/comun/src/comun/config.py`, `libs/comun/src/comun/salud.py`
- Test: `libs/comun/tests/test_salud.py`

**Interfaces:**
- Produces:
  - `class ConfiguracionBase(BaseSettings)` con los campos:
    - `nombre_servicio: str` y `database_url: str` (obligatorios).
    - `rabbitmq_url`, `oidc_issuer`, `oidc_jwks_url`, `oidc_audience`, `root_path` y `log_level`, con valores por defecto.
  - `crear_router_salud(verificaciones: dict[str, Callable[[], Awaitable[None]]]) -> APIRouter`. Expone `GET /salud/vivo` y `GET /salud/listo`; este último responde 503 si alguna dependencia falla.

- [ ] **Step 1: Escribir las pruebas que fallan**

`libs/comun/tests/test_salud.py`:
```python
from collections.abc import Awaitable, Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from comun.config import ConfiguracionBase
from comun.salud import crear_router_salud


async def sana() -> None:
    return None


async def caida() -> None:
    raise ConnectionError("sin conexión")


def _cliente(verificaciones: dict[str, Callable[[], Awaitable[None]]]) -> TestClient:
    app = FastAPI()
    app.include_router(crear_router_salud(verificaciones))
    return TestClient(app)


def test_vivo_responde_ok_aunque_falle_una_dependencia() -> None:
    respuesta = _cliente({"postgres": caida}).get("/salud/vivo")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_listo_con_dependencias_sanas() -> None:
    respuesta = _cliente({"postgres": sana, "rabbitmq": sana}).get("/salud/listo")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "dependencias": {"postgres": "ok", "rabbitmq": "ok"}}


def test_listo_con_una_dependencia_caida_responde_503() -> None:
    respuesta = _cliente({"postgres": sana, "rabbitmq": caida}).get("/salud/listo")
    assert respuesta.status_code == 503
    assert respuesta.json() == {
        "estado": "degradado",
        "dependencias": {"postgres": "ok", "rabbitmq": "error"},
    }


def test_configuracion_lee_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOMBRE_SERVICIO", "prueba")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/bd")
    configuracion = ConfiguracionBase()  # type: ignore[call-arg]
    assert configuracion.nombre_servicio == "prueba"
    assert configuracion.database_url.endswith("/bd")
    assert configuracion.oidc_audience == "plataforma-api"
```

- [ ] **Step 2: Ejecutar para verificar que fallan**

Run: `uv run pytest libs/comun/tests/test_salud.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'comun.config'`.

- [ ] **Step 3: Implementar**

`libs/comun/src/comun/config.py`:
```python
"""Configuración común leída de variables de entorno (o de un archivo .env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfiguracionBase(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nombre_servicio: str
    database_url: str
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    oidc_issuer: str = "http://localhost:8080/auth/realms/plataforma"
    oidc_jwks_url: str = (
        "http://localhost:8080/auth/realms/plataforma/protocol/openid-connect/certs"
    )
    oidc_audience: str = "plataforma-api"
    root_path: str = ""
    log_level: str = "INFO"
```

`libs/comun/src/comun/salud.py`:
```python
"""Endpoints de salud para los healthchecks de Docker Compose."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Response

log = logging.getLogger(__name__)


def crear_router_salud(verificaciones: dict[str, Callable[[], Awaitable[None]]]) -> APIRouter:
    router = APIRouter(prefix="/salud", tags=["salud"])

    @router.get("/vivo")
    async def vivo() -> dict[str, str]:
        return {"estado": "ok"}

    @router.get("/listo")
    async def listo(response: Response) -> dict[str, object]:
        dependencias: dict[str, str] = {}
        for nombre, verificar in verificaciones.items():
            try:
                await asyncio.wait_for(verificar(), timeout=2)
                dependencias[nombre] = "ok"
            except Exception:
                log.warning("Dependencia no disponible: %s", nombre, exc_info=True)
                dependencias[nombre] = "error"
        sano = all(estado == "ok" for estado in dependencias.values())
        if not sano:
            response.status_code = 503
        return {"estado": "ok" if sano else "degradado", "dependencias": dependencias}

    return router
```

- [ ] **Step 4: Ejecutar para verificar que pasan**

Run: `uv run pytest libs/comun/tests/test_salud.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add libs/comun/src/comun/config.py libs/comun/src/comun/salud.py libs/comun/tests/test_salud.py
git commit -m "feat(comun): configuracion base y endpoints de salud"
```

---

### Task 6: Outbox transaccional y relay hacia RabbitMQ

**Files:**
- Create: `libs/comun/src/comun/outbox.py`
- Test: `libs/comun/tests/test_outbox.py` (integración: PostgreSQL + RabbitMQ con Testcontainers)

**Interfaces:**
- Consumes: `comun.logs.correlation_id`.
- Produces:
  - `EXCHANGE_EVENTOS = "eventos"`.
  - `class ColumnasOutbox`: mixin con `id: UUID`, `tipo`, `version`, `payload: dict` (JSONB), `correlation_id`, `ocurrido_en` y `publicado_en: datetime | None`. Cada servicio lo usa así: `class Outbox(ColumnasOutbox, Base): __tablename__ = "outbox"`.
  - `registrar_evento(sesion, modelo, tipo: str, payload: dict[str, Any], version: int = 1) -> None`. Convierte `Decimal`, `date` y `UUID` a JSON y toma el `correlation_id` vigente.
  - `sobre_evento(fila) -> dict`, con las claves `event_id`, `type`, `version`, `occurred_at`, `correlation_id` y `payload`.
  - `class RelayOutbox(fabrica, modelo, url_rabbitmq: str, lote: int = 100)`, con:
    - `async conectar()`.
    - `conectado() -> bool`.
    - `async publicar_pendientes() -> int`.
    - `async ejecutar(intervalo: float = 1.0)`: bucle infinito.
    - `async cerrar()`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`libs/comun/tests/test_outbox.py`:
```python
import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from typing import Any

import aio_pika
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer
from testcontainers.rabbitmq import RabbitMqContainer

from comun.logs import correlation_id
from comun.outbox import EXCHANGE_EVENTOS, ColumnasOutbox, RelayOutbox, registrar_evento

pytestmark = pytest.mark.integracion


class Base(DeclarativeBase):
    pass


class OutboxPrueba(ColumnasOutbox, Base):
    __tablename__ = "outbox"


@pytest.fixture(scope="module")
def url_postgres() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as contenedor:
        yield contenedor.get_connection_url()


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


@pytest.fixture
async def fabrica(url_postgres: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    motor = create_async_engine(url_postgres, poolclass=NullPool)
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
        await conexion.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(motor, expire_on_commit=False)
    await motor.dispose()


async def _todas(fabrica: async_sessionmaker[AsyncSession]) -> list[OutboxPrueba]:
    async with fabrica() as sesion:
        return list((await sesion.scalars(select(OutboxPrueba))).all())


async def test_registrar_evento_serializa_payload_y_guarda_correlation_id(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    token = correlation_id.set("req-77")
    try:
        async with fabrica() as sesion, sesion.begin():
            registrar_evento(
                sesion,
                OutboxPrueba,
                "proveedor.actualizado",
                {"precio": Decimal("12.5000"), "id": uuid.UUID(int=1)},
            )
    finally:
        correlation_id.reset(token)
    [fila] = await _todas(fabrica)
    assert fila.payload == {"precio": "12.5000", "id": "00000000-0000-0000-0000-000000000001"}
    assert fila.correlation_id == "req-77"
    assert fila.publicado_en is None


async def test_evento_no_se_guarda_si_la_transaccion_falla(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    with contextlib.suppress(RuntimeError):
        async with fabrica() as sesion, sesion.begin():
            registrar_evento(sesion, OutboxPrueba, "proveedor.actualizado", {"n": 1})
            raise RuntimeError("falla del negocio")
    assert await _todas(fabrica) == []


async def test_relay_publica_cada_pendiente_una_sola_vez(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    async with fabrica() as sesion, sesion.begin():
        for n in range(3):
            registrar_evento(sesion, OutboxPrueba, "contrato.registrado", {"n": n})

    relay = RelayOutbox(fabrica, OutboxPrueba, url_rabbitmq)
    await relay.conectar()
    conexion = await aio_pika.connect_robust(url_rabbitmq)
    recibidos: list[dict[str, Any]] = []
    try:
        canal = await conexion.channel()
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        cola = await canal.declare_queue(exclusive=True)
        await cola.bind(exchange, routing_key="#")

        assert relay.conectado()
        assert await relay.publicar_pendientes() == 3
        assert await relay.publicar_pendientes() == 0
        for _ in range(3):
            mensaje = await cola.get(timeout=5)
            await mensaje.ack()
            recibidos.append(json.loads(mensaje.body))
    finally:
        await conexion.close()
        await relay.cerrar()

    assert sorted(r["payload"]["n"] for r in recibidos) == [0, 1, 2]
    assert {r["type"] for r in recibidos} == {"contrato.registrado"}
    assert set(recibidos[0]) == {
        "event_id", "type", "version", "occurred_at", "correlation_id", "payload"
    }
    assert all(fila.publicado_en is not None for fila in await _todas(fabrica))


async def test_ejecutar_publica_en_segundo_plano(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    relay = RelayOutbox(fabrica, OutboxPrueba, url_rabbitmq)
    await relay.conectar()
    async with fabrica() as sesion, sesion.begin():
        registrar_evento(sesion, OutboxPrueba, "desempeno.registrado", {"n": 1})
    tarea = asyncio.create_task(relay.ejecutar(intervalo=0.05))
    try:
        for _ in range(100):
            [fila] = await _todas(fabrica)
            if fila.publicado_en is not None:
                break
            await asyncio.sleep(0.05)
        assert fila.publicado_en is not None
    finally:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
        await relay.cerrar()


async def test_publicar_sin_conectar_es_un_error(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(RuntimeError, match="conectar"):
        await RelayOutbox(fabrica, OutboxPrueba, "amqp://nadie").publicar_pendientes()
```

- [ ] **Step 2: Ejecutar para verificar que fallan**

Run: `uv run pytest libs/comun/tests/test_outbox.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'comun.outbox'`. La primera ejecución descarga las imágenes `postgres:17-alpine` y `rabbitmq:4.1-alpine`.

- [ ] **Step 3: Implementar**

`libs/comun/src/comun/outbox.py`:
```python
"""Outbox transaccional: el evento se guarda en la misma transacción que el cambio
de datos y un relay lo publica después en RabbitMQ (entrega al menos una vez)."""

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractRobustConnection
from pydantic_core import to_jsonable_python
from sqlalchemy import DateTime, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from comun.logs import correlation_id

log = logging.getLogger(__name__)

EXCHANGE_EVENTOS = "eventos"


class ColumnasOutbox:
    """Mixin. Uso: `class Outbox(ColumnasOutbox, Base): __tablename__ = "outbox"`."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tipo: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    correlation_id: Mapped[str] = mapped_column(String(64))
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def registrar_evento(
    sesion: AsyncSession,
    modelo: Callable[..., ColumnasOutbox],
    tipo: str,
    payload: dict[str, Any],
    version: int = 1,
) -> None:
    """Agrega el evento a la transacción en curso; solo existe si la transacción confirma."""
    sesion.add(
        modelo(
            tipo=tipo,
            version=version,
            payload=to_jsonable_python(payload),
            correlation_id=correlation_id.get(),
        )
    )


def sobre_evento(fila: ColumnasOutbox) -> dict[str, Any]:
    return {
        "event_id": str(fila.id),
        "type": fila.tipo,
        "version": fila.version,
        "occurred_at": fila.ocurrido_en.isoformat(),
        "correlation_id": fila.correlation_id,
        "payload": fila.payload,
    }


class RelayOutbox:
    def __init__(
        self,
        fabrica: async_sessionmaker[AsyncSession],
        modelo: type[ColumnasOutbox],
        url_rabbitmq: str,
        lote: int = 100,
    ) -> None:
        self._fabrica = fabrica
        self._modelo = modelo
        self._url = url_rabbitmq
        self._lote = lote
        self._conexion: AbstractRobustConnection | None = None
        self._exchange: AbstractExchange | None = None

    async def conectar(self) -> None:
        self._conexion = await aio_pika.connect_robust(self._url)
        canal = await self._conexion.channel(publisher_confirms=True)
        self._exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )

    def conectado(self) -> bool:
        return self._conexion is not None and not self._conexion.is_closed

    async def cerrar(self) -> None:
        if self._conexion is not None:
            await self._conexion.close()

    async def publicar_pendientes(self) -> int:
        if self._exchange is None:
            raise RuntimeError("Llame a conectar() antes de publicar")
        modelo = self._modelo
        async with self._fabrica() as sesion, sesion.begin():
            consulta = (
                select(modelo)
                .where(modelo.publicado_en.is_(None))
                .order_by(modelo.ocurrido_en)
                .limit(self._lote)
                .with_for_update(skip_locked=True)
            )
            filas = (await sesion.scalars(consulta)).all()
            for fila in filas:
                mensaje = aio_pika.Message(
                    json.dumps(sobre_evento(fila)).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    message_id=str(fila.id),
                    correlation_id=fila.correlation_id,
                    type=fila.tipo,
                )
                # mandatory=False: mientras no haya colas enlazadas (incremento 2),
                # RabbitMQ descarta el mensaje en lugar de devolverlo.
                await self._exchange.publish(mensaje, routing_key=fila.tipo, mandatory=False)
                fila.publicado_en = datetime.now(UTC)
        return len(filas)

    async def ejecutar(self, intervalo: float = 1.0) -> None:
        # ponytail: sondeo cada `intervalo` s; cambiar a LISTEN/NOTIFY si la latencia importa.
        while True:
            try:
                publicados = await self.publicar_pendientes()
            except Exception:
                log.exception("No se pudieron publicar eventos del outbox; se reintentará")
                publicados = 0
            if publicados < self._lote:
                await asyncio.sleep(intervalo)
```

- [ ] **Step 4: Ejecutar para verificar que pasan**

Run: `uv run pytest libs/comun/tests/test_outbox.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Verificar toda la librería con lint, tipos y cobertura**

Run: `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run pytest --cov`
Expected: sin errores; cobertura de `comun` ≥ 80 %.

- [ ] **Step 6: Commit**

```bash
git add libs/comun/src/comun/outbox.py libs/comun/tests/test_outbox.py
git commit -m "feat(comun): outbox transaccional con relay a RabbitMQ"
```

---

### Task 7: Paquete `proveedores`: modelos y migración inicial

**Files:**
- Create: `services/proveedores/pyproject.toml`, `services/proveedores/alembic.ini`
- Create: `services/proveedores/alembic/env.py`, `services/proveedores/alembic/script.py.mako`, `services/proveedores/alembic/versions/0001_esquema_inicial.py`
- Create: `services/proveedores/src/proveedores/__init__.py`, `config.py`, `db.py`, `modelos.py`
- Modify: `pyproject.toml` (raíz)
- Test: `services/proveedores/tests/conftest.py`, `services/proveedores/tests/test_migraciones.py`

**Interfaces:**
- Consumes: `comun.config.ConfiguracionBase`, `comun.outbox.ColumnasOutbox`, `comun.pruebas.ClavesPrueba`.
- Produces:
  - `proveedores.config.Configuracion`.
  - `proveedores.db.Base`, con convención de nombres para las restricciones.
  - `proveedores.db.obtener_sesion(request) -> AsyncIterator[AsyncSession]`. Usa `request.app.state.fabrica`.
  - Modelos: `Proveedor`, `ServicioCatalogo`, `Contrato` (con `.lineas`), `LineaContrato` (con `.servicio`), `RegistroDesempeno`, `TipoCambio` y `Outbox`.
  - Fixtures de pytest:
    - `url_bd` (sesión): PostgreSQL en contenedor, ya migrado.
    - `fabrica` (función): trunca todas las tablas al terminar.
    - `claves` (sesión): `ClavesPrueba`.

- [ ] **Step 1: Crear el paquete y registrarlo en el workspace**

`services/proveedores/pyproject.toml`:
```toml
[project]
name = "proveedores"
version = "0.1.0"
description = "Proveedores, contratos, historial de precios y desempeño"
requires-python = ">=3.13"
dependencies = [
    "comun",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "python-multipart>=0.0.18",
]

[tool.uv.sources]
comun = { workspace = true }

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

`services/proveedores/src/proveedores/__init__.py`:
```python
"""Servicio de proveedores, contratos, historial de precios y desempeño."""
```

En `pyproject.toml` (raíz), aplicar estos cuatro cambios:
```toml
[dependency-groups]
dev = [
    "comun",
    "proveedores",
    # … resto sin cambios
]

[tool.uv.sources]
comun = { workspace = true }
proveedores = { workspace = true }

[tool.coverage.run]
branch = true
source = ["comun", "proveedores"]

[tool.mypy]
# … resto sin cambios
packages = ["comun", "proveedores"]
```

Run: `uv sync --all-packages`
Expected: instala `proveedores` en modo editable, sin errores.

- [ ] **Step 2: Configuración, base declarativa y sesión**

`services/proveedores/src/proveedores/config.py`:
```python
from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "proveedores"
    database_url: str = (
        "postgresql+asyncpg://proveedores:proveedores@localhost:5432/proveedores_db"
    )
```

`services/proveedores/src/proveedores/db.py`:
```python
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
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

- [ ] **Step 3: Modelos ORM**

`services/proveedores/src/proveedores/modelos.py`:
```python
"""Entidades del servicio de proveedores. La fuente de verdad es el ERP (importación CSV)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from comun.outbox import ColumnasOutbox
from proveedores.db import Base

DINERO = Numeric(14, 4)
PORCENTAJE = Numeric(5, 2)


class Proveedor(Base):
    __tablename__ = "proveedor"
    __table_args__ = (
        CheckConstraint("tamano IN ('micro', 'pequena', 'mediana', 'grande')", name="tamano"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rfc: Mapped[str] = mapped_column(String(13), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    tamano: Mapped[str] = mapped_column(String(10))
    categorias: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    contacto_nombre: Mapped[str] = mapped_column(String(120))
    contacto_email: Mapped[str] = mapped_column(String(254))
    activo: Mapped[bool] = mapped_column(default=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ServicioCatalogo(Base):
    __tablename__ = "servicio_catalogo"
    __table_args__ = (
        CheckConstraint(
            "categoria IN ('licencia_saas', 'nube', 'consultoria', 'soporte')", name="categoria"
        ),
        CheckConstraint("moneda IN ('MXN', 'USD')", name="moneda"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(20))
    unidad: Mapped[str] = mapped_column(String(20))
    moneda: Mapped[str] = mapped_column(String(3))


class Contrato(Base):
    __tablename__ = "contrato"
    __table_args__ = (
        CheckConstraint("tipo IN ('nuevo', 'renovacion')", name="tipo"),
        CheckConstraint("moneda IN ('MXN', 'USD')", name="moneda"),
        CheckConstraint("fecha_fin > fecha_inicio", name="vigencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    folio: Mapped[str] = mapped_column(String(30), unique=True)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proveedor.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(10))
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    moneda: Mapped[str] = mapped_column(String(3))
    plazo_pago_dias: Mapped[int]
    sla_disponibilidad: Mapped[Decimal | None] = mapped_column(PORCENTAJE)
    tope_aumento_pct: Mapped[Decimal | None] = mapped_column(PORCENTAJE)
    cuota_implementacion: Mapped[Decimal] = mapped_column(DINERO, default=Decimal(0))

    lineas: Mapped[list["LineaContrato"]] = relationship(
        back_populates="contrato", cascade="all, delete-orphan"
    )


class LineaContrato(Base):
    __tablename__ = "linea_contrato"
    __table_args__ = (
        CheckConstraint("cantidad > 0 AND precio_unitario > 0", name="positivos"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contrato.id", ondelete="CASCADE"), index=True
    )
    servicio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("servicio_catalogo.id"))
    cantidad: Mapped[Decimal] = mapped_column(DINERO)
    precio_unitario: Mapped[Decimal] = mapped_column(DINERO)

    contrato: Mapped[Contrato] = relationship(back_populates="lineas")
    servicio: Mapped[ServicioCatalogo] = relationship()


class RegistroDesempeno(Base):
    __tablename__ = "registro_desempeno"
    __table_args__ = (UniqueConstraint("proveedor_id", "periodo"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proveedor.id"))
    periodo: Mapped[date] = mapped_column(Date)
    sla_cumplimiento_pct: Mapped[Decimal] = mapped_column(PORCENTAJE)
    tiempo_resolucion_h: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    incidentes_criticos: Mapped[int]
    entregas_a_tiempo_pct: Mapped[Decimal] = mapped_column(PORCENTAJE)
    satisfaccion: Mapped[Decimal] = mapped_column(Numeric(3, 2))


class TipoCambio(Base):
    __tablename__ = "tipo_cambio"

    periodo: Mapped[date] = mapped_column(Date, primary_key=True)
    usd_mxn: Mapped[Decimal] = mapped_column(Numeric(10, 4))


class Outbox(ColumnasOutbox, Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_pendientes", "ocurrido_en", postgresql_where=text("publicado_en IS NULL")),
    )
```

- [ ] **Step 4: Configurar Alembic**

`services/proveedores/alembic.ini`:
```ini
[alembic]
script_location = %(here)s/alembic
```

`services/proveedores/alembic/env.py`:
```python
import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from proveedores import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from proveedores.config import Configuracion
from proveedores.db import Base

config = context.config
# configparser interpreta "%": se escapa por si la contraseña lo contiene.
config.set_main_option("sqlalchemy.url", Configuracion().database_url.replace("%", "%%"))
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

`services/proveedores/alembic/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: Escribir la migración inicial**

`services/proveedores/alembic/versions/0001_esquema_inicial.py`:
```python
"""Esquema inicial del servicio de proveedores.

Revision ID: 0001
Revises:
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DINERO = sa.Numeric(14, 4)
PORCENTAJE = sa.Numeric(5, 2)


def upgrade() -> None:
    op.create_table(
        "proveedor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rfc", sa.String(13), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("tamano", sa.String(10), nullable=False),
        sa.Column("categorias", postgresql.ARRAY(sa.String(20)), nullable=False),
        sa.Column("contacto_nombre", sa.String(120), nullable=False),
        sa.Column("contacto_email", sa.String(254), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tamano IN ('micro', 'pequena', 'mediana', 'grande')",
            name=op.f("ck_proveedor_tamano"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proveedor")),
        sa.UniqueConstraint("rfc", name=op.f("uq_proveedor_rfc")),
    )
    op.create_table(
        "servicio_catalogo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.CheckConstraint(
            "categoria IN ('licencia_saas', 'nube', 'consultoria', 'soporte')",
            name=op.f("ck_servicio_catalogo_categoria"),
        ),
        sa.CheckConstraint(
            "moneda IN ('MXN', 'USD')", name=op.f("ck_servicio_catalogo_moneda")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_servicio_catalogo")),
        sa.UniqueConstraint("codigo", name=op.f("uq_servicio_catalogo_codigo")),
    )
    op.create_table(
        "contrato",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("folio", sa.String(30), nullable=False),
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False),
        sa.Column("plazo_pago_dias", sa.Integer(), nullable=False),
        sa.Column("sla_disponibilidad", PORCENTAJE, nullable=True),
        sa.Column("tope_aumento_pct", PORCENTAJE, nullable=True),
        sa.Column("cuota_implementacion", DINERO, nullable=False),
        sa.CheckConstraint("tipo IN ('nuevo', 'renovacion')", name=op.f("ck_contrato_tipo")),
        sa.CheckConstraint("moneda IN ('MXN', 'USD')", name=op.f("ck_contrato_moneda")),
        sa.CheckConstraint("fecha_fin > fecha_inicio", name=op.f("ck_contrato_vigencia")),
        sa.ForeignKeyConstraint(
            ["proveedor_id"], ["proveedor.id"], name=op.f("fk_contrato_proveedor_id_proveedor")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato")),
        sa.UniqueConstraint("folio", name=op.f("uq_contrato_folio")),
    )
    op.create_index(op.f("ix_contrato_proveedor_id"), "contrato", ["proveedor_id"])
    op.create_table(
        "linea_contrato",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contrato_id", sa.Uuid(), nullable=False),
        sa.Column("servicio_id", sa.Uuid(), nullable=False),
        sa.Column("cantidad", DINERO, nullable=False),
        sa.Column("precio_unitario", DINERO, nullable=False),
        sa.CheckConstraint(
            "cantidad > 0 AND precio_unitario > 0", name=op.f("ck_linea_contrato_positivos")
        ),
        sa.ForeignKeyConstraint(
            ["contrato_id"],
            ["contrato.id"],
            name=op.f("fk_linea_contrato_contrato_id_contrato"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["servicio_id"],
            ["servicio_catalogo.id"],
            name=op.f("fk_linea_contrato_servicio_id_servicio_catalogo"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_linea_contrato")),
    )
    op.create_index(op.f("ix_linea_contrato_contrato_id"), "linea_contrato", ["contrato_id"])
    op.create_table(
        "registro_desempeno",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("sla_cumplimiento_pct", PORCENTAJE, nullable=False),
        sa.Column("tiempo_resolucion_h", sa.Numeric(8, 2), nullable=False),
        sa.Column("incidentes_criticos", sa.Integer(), nullable=False),
        sa.Column("entregas_a_tiempo_pct", PORCENTAJE, nullable=False),
        sa.Column("satisfaccion", sa.Numeric(3, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["proveedor_id"],
            ["proveedor.id"],
            name=op.f("fk_registro_desempeno_proveedor_id_proveedor"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registro_desempeno")),
        sa.UniqueConstraint(
            "proveedor_id", "periodo", name=op.f("uq_registro_desempeno_proveedor_id")
        ),
    )
    op.create_table(
        "tipo_cambio",
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("usd_mxn", sa.Numeric(10, 4), nullable=False),
        sa.PrimaryKeyConstraint("periodo", name=op.f("pk_tipo_cambio")),
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


def downgrade() -> None:
    op.drop_index("ix_outbox_pendientes", table_name="outbox")
    op.drop_table("outbox")
    op.drop_table("tipo_cambio")
    op.drop_table("registro_desempeno")
    op.drop_index(op.f("ix_linea_contrato_contrato_id"), table_name="linea_contrato")
    op.drop_table("linea_contrato")
    op.drop_index(op.f("ix_contrato_proveedor_id"), table_name="contrato")
    op.drop_table("contrato")
    op.drop_table("servicio_catalogo")
    op.drop_table("proveedor")
```

- [ ] **Step 6: Escribir las fixtures y la prueba de migraciones**

`services/proveedores/tests/conftest.py`:
```python
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from comun.pruebas import ClavesPrueba

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
```

`services/proveedores/tests/test_migraciones.py`:
```python
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from proveedores import modelos  # noqa: F401
from proveedores.db import Base

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


def test_migracion_se_revierte_y_se_reaplica(url_bd: str) -> None:
    configuracion = Config(str(ALEMBIC_INI))
    command.downgrade(configuracion, "base")
    command.upgrade(configuracion, "head")
```

- [ ] **Step 7: Ejecutar las pruebas**

Run: `uv run pytest services/proveedores/tests/test_migraciones.py -v`
Expected: `2 passed`. Si `test_modelos_y_migraciones_coinciden` falla, la lista de diferencias indica qué tabla o columna de la migración no coincide con `modelos.py`; corregir la migración, no la prueba.

- [ ] **Step 8: Lint y tipos**

Run: `uv run ruff check . ; uv run ruff format --check . ; uv run mypy`
Expected: sin errores.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock services/proveedores
git commit -m "feat(proveedores): modelos y migracion inicial"
```

---

### Task 8: Importación — esquemas de fila y parseo de CSV (lógica pura)

**Files:**
- Create: `services/proveedores/src/proveedores/importacion/__init__.py`, `importacion/esquemas.py`, `importacion/parseo.py`
- Test: `services/proveedores/tests/test_parseo.py`

**Interfaces:**
- Produces:
  - En `esquemas`: `FilaServicio`, `FilaProveedor`, `FilaTipoCambio`, `FilaDesempeno` y `FilaContrato`. `FilaContrato` tiene `cabecera() -> tuple[object, ...]`.
  - Columnas CSV = nombres de campo. En `FilaProveedor`, `categorias` va separado por `|`.
  - En `parseo`:
    - `ErrorFila(fila: int, campo: str, mensaje: str)`: `fila` 1 = encabezado y `fila` 0 = archivo completo.
    - `ResultadoParseo[M]`, con `filas: list[tuple[int, M]]` y `errores: list[ErrorFila]`.
    - `MAX_FILAS = 50_000`.
    - `leer_csv(contenido: bytes, esquema: type[M]) -> ResultadoParseo[M]`.
    - `duplicados(resultado, clave, campo) -> list[ErrorFila]`.
    - `agrupar_contratos(filas) -> tuple[dict[str, list[tuple[int, FilaContrato]]], list[ErrorFila]]`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`services/proveedores/tests/test_parseo.py`:
```python
from decimal import Decimal

import pytest

from proveedores.importacion import parseo
from proveedores.importacion.esquemas import (
    FilaContrato,
    FilaDesempeno,
    FilaProveedor,
    FilaServicio,
)
from proveedores.importacion.parseo import ErrorFila, agrupar_contratos, duplicados, leer_csv

SERVICIOS = (
    "codigo,nombre,categoria,unidad,moneda\n"
    "SAAS-OFI-EMP,Suite de productividad en la nube - plan empresarial,"
    "licencia_saas,usuario_mes,USD\n"
    "CONS-DEV-SR,Desarrollador(a) senior - hora,consultoria,hora,MXN\n"
)

CONTRATO_ENC = (
    "folio,rfc_proveedor,tipo,fecha_inicio,fecha_fin,moneda,plazo_pago_dias,"
    "sla_disponibilidad,tope_aumento_pct,cuota_implementacion,codigo_servicio,"
    "cantidad,precio_unitario\n"
)


def _contrato(folio: str = "C-0001", servicio: str = "SAAS-OFI-EMP", **cambios: str) -> str:
    valores = {
        "folio": folio,
        "rfc_proveedor": "NAZ210315AB1",
        "tipo": "nuevo",
        "fecha_inicio": "2025-01-01",
        "fecha_fin": "2025-12-31",
        "moneda": "USD",
        "plazo_pago_dias": "30",
        "sla_disponibilidad": "99.9",
        "tope_aumento_pct": "5",
        "cuota_implementacion": "",
        "codigo_servicio": servicio,
        "cantidad": "250",
        "precio_unitario": "21.5",
    }
    valores.update(cambios)
    return ",".join(valores.values()) + "\n"


def test_csv_valido_con_comas() -> None:
    resultado = leer_csv(SERVICIOS.encode(), FilaServicio)
    assert resultado.errores == []
    assert [numero for numero, _ in resultado.filas] == [2, 3]
    assert resultado.filas[0][1].codigo == "SAAS-OFI-EMP"


def test_csv_de_excel_en_espanol_con_bom_y_punto_y_coma() -> None:
    excel = SERVICIOS.replace(",", ";").encode("utf-8-sig")
    resultado = leer_csv(excel, FilaServicio)
    assert resultado.errores == []
    assert len(resultado.filas) == 2


def test_archivo_que_no_es_utf8_da_un_error_claro() -> None:
    contenido = SERVICIOS.replace("Suite", "Compañía").encode("cp1252")
    resultado = leer_csv(contenido, FilaServicio)
    assert resultado.filas == []
    assert resultado.errores == [
        ErrorFila(0, "archivo", "El archivo debe estar codificado en UTF-8")
    ]


def test_encabezado_con_columnas_faltantes_y_desconocidas() -> None:
    [error] = leer_csv(b"codigo,nombre,precio\nX,Y,1\n", FilaServicio).errores
    assert (error.fila, error.campo) == (1, "encabezado")
    assert "faltan: categoria, moneda, unidad" in error.mensaje
    assert "no reconocidas: precio" in error.mensaje


def test_errores_por_fila_en_espanol() -> None:
    texto = (
        CONTRATO_ENC
        + _contrato(precio_unitario="-3")
        + _contrato(folio="C-0002", fecha_inicio="2025-02-30")
    )
    errores = leer_csv(texto.encode(), FilaContrato).errores
    assert ErrorFila(2, "precio_unitario", "Debe ser mayor que 0") in errores
    assert ErrorFila(3, "fecha_inicio", "Fecha inválida; use AAAA-MM-DD") in errores


def test_opcionales_vacios_toman_su_valor_por_defecto() -> None:
    texto = CONTRATO_ENC + _contrato(sla_disponibilidad="", tope_aumento_pct="")
    [(_, fila)] = leer_csv(texto.encode(), FilaContrato).filas
    assert fila.sla_disponibilidad is None
    assert fila.tope_aumento_pct is None
    assert fila.cuota_implementacion == Decimal(0)


def test_obligatorio_vacio_y_fila_con_valores_de_mas() -> None:
    texto = (
        CONTRATO_ENC
        + _contrato(rfc_proveedor="")
        + _contrato(folio="C-0003").replace("\n", ",extra\n")
    )
    errores = leer_csv(texto.encode(), FilaContrato).errores
    assert ErrorFila(2, "rfc_proveedor", "Campo obligatorio") in errores
    assert ErrorFila(3, "fila", "La fila tiene más valores que columnas") in errores


def test_vigencia_invertida() -> None:
    texto = CONTRATO_ENC + _contrato(fecha_fin="2024-01-01")
    assert leer_csv(texto.encode(), FilaContrato).errores == [
        ErrorFila(2, "fila", "fecha_fin debe ser posterior a fecha_inicio")
    ]


def test_periodo_debe_ser_primer_dia_del_mes() -> None:
    texto = (
        "rfc_proveedor,periodo,sla_cumplimiento_pct,tiempo_resolucion_h,"
        "incidentes_criticos,entregas_a_tiempo_pct,satisfaccion\n"
        "NAZ210315AB1,2025-03-15,99.5,4.25,0,97,4.6\n"
    )
    assert leer_csv(texto.encode(), FilaDesempeno).errores == [
        ErrorFila(2, "periodo", "El periodo debe ser el primer día del mes")
    ]


def test_categorias_separadas_por_barra_y_activo_por_defecto() -> None:
    texto = (
        "rfc,nombre,tamano,categorias,contacto_nombre,contacto_email\n"
        "NAZ210315AB1,Nube Azteca S.A. de C.V.,mediana,licencia_saas|nube,"
        "Laura Méndez,ventas01@proveedor01.example\n"
    )
    [(_, fila)] = leer_csv(texto.encode(), FilaProveedor).filas
    assert fila.categorias == ["licencia_saas", "nube"]
    assert fila.activo is True


def test_limite_de_filas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parseo, "MAX_FILAS", 1)
    resultado = leer_csv(SERVICIOS.encode(), FilaServicio)
    assert len(resultado.filas) == 1
    assert resultado.errores == [ErrorFila(3, "archivo", "El archivo excede 1 filas")]


def test_duplicados_por_clave() -> None:
    repetida = SERVICIOS.splitlines(keepends=True)[1]
    resultado = leer_csv((SERVICIOS + repetida).encode(), FilaServicio)
    assert duplicados(resultado, lambda fila: fila.codigo, "codigo") == [
        ErrorFila(4, "codigo", "Duplicado de la fila 2")
    ]


def test_agrupar_contratos_detecta_cabeceras_distintas_y_servicios_repetidos() -> None:
    texto = (
        CONTRATO_ENC
        + _contrato()
        + _contrato(servicio="CONS-DEV-SR", plazo_pago_dias="60")
        + _contrato()
    )
    grupos, errores = agrupar_contratos(leer_csv(texto.encode(), FilaContrato).filas)
    assert list(grupos) == ["C-0001"]
    assert (
        ErrorFila(3, "folio", "Los datos del contrato C-0001 no coinciden con la fila 2")
        in errores
    )
    assert ErrorFila(4, "codigo_servicio", "Servicio repetido en el contrato C-0001") in errores
```

- [ ] **Step 2: Ejecutar para verificar que fallan**

Run: `uv run pytest services/proveedores/tests/test_parseo.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'proveedores.importacion'`.

- [ ] **Step 3: Implementar los esquemas de fila**

`services/proveedores/src/proveedores/importacion/__init__.py`:
```python
"""Adaptador de importación del ERP/SRM simulado (archivos CSV)."""
```

`services/proveedores/src/proveedores/importacion/esquemas.py`:
```python
"""Filas de los CSV del ERP simulado. Los nombres de campo son los nombres de columna."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Categoria = Literal["licencia_saas", "nube", "consultoria", "soporte"]
Moneda = Literal["MXN", "USD"]
Unidad = Literal["usuario_mes", "vcpu_mes", "gb_mes", "mes", "hora", "ticket"]
Porcentaje = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Dinero = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)]

RFC = r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$"
CORREO = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
CODIGO = r"^[A-Z0-9-]{3,30}$"


def _primer_dia_del_mes(valor: date) -> date:
    if valor.day != 1:
        raise ValueError("El periodo debe ser el primer día del mes")
    return valor


class Fila(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def omitir_vacios(cls, datos: Any) -> Any:
        # Una celda vacía equivale a "sin dato": aplica el valor por defecto o
        # produce el error "Campo obligatorio".
        if isinstance(datos, dict):
            return {clave: valor for clave, valor in datos.items() if valor not in ("", None)}
        return datos


class FilaServicio(Fila):
    codigo: str = Field(pattern=CODIGO)
    nombre: str = Field(min_length=1, max_length=200)
    categoria: Categoria
    unidad: Unidad
    moneda: Moneda


class FilaProveedor(Fila):
    rfc: str = Field(pattern=RFC)
    nombre: str = Field(min_length=1, max_length=200)
    tamano: Literal["micro", "pequena", "mediana", "grande"]
    categorias: list[Categoria] = Field(min_length=1)
    contacto_nombre: str = Field(min_length=1, max_length=120)
    contacto_email: str = Field(pattern=CORREO, max_length=254)
    activo: bool = True

    @field_validator("categorias", mode="before")
    @classmethod
    def separar_categorias(cls, valor: Any) -> Any:
        if isinstance(valor, str):
            return [parte.strip() for parte in valor.split("|") if parte.strip()]
        return valor


class FilaTipoCambio(Fila):
    periodo: date
    usd_mxn: Decimal = Field(gt=0, lt=100, max_digits=10, decimal_places=4)

    @field_validator("periodo")
    @classmethod
    def validar_periodo(cls, valor: date) -> date:
        return _primer_dia_del_mes(valor)


class FilaDesempeno(Fila):
    rfc_proveedor: str = Field(pattern=RFC)
    periodo: date
    sla_cumplimiento_pct: Porcentaje
    tiempo_resolucion_h: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    incidentes_criticos: int = Field(ge=0)
    entregas_a_tiempo_pct: Porcentaje
    satisfaccion: Decimal = Field(ge=1, le=5, max_digits=3, decimal_places=2)

    @field_validator("periodo")
    @classmethod
    def validar_periodo(cls, valor: date) -> date:
        return _primer_dia_del_mes(valor)


class FilaContrato(Fila):
    """Una fila por línea de contrato; las filas con el mismo folio forman un contrato."""

    folio: str = Field(pattern=CODIGO)
    rfc_proveedor: str = Field(pattern=RFC)
    tipo: Literal["nuevo", "renovacion"]
    fecha_inicio: date
    fecha_fin: date
    moneda: Moneda
    plazo_pago_dias: int = Field(ge=0, le=180)
    sla_disponibilidad: Decimal | None = Field(
        default=None, ge=90, le=100, max_digits=5, decimal_places=2
    )
    tope_aumento_pct: Porcentaje | None = None
    cuota_implementacion: Decimal = Field(
        default=Decimal(0), ge=0, max_digits=14, decimal_places=4
    )
    codigo_servicio: str = Field(pattern=CODIGO)
    cantidad: Dinero
    precio_unitario: Dinero

    @model_validator(mode="after")
    def validar_vigencia(self) -> "FilaContrato":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self

    def cabecera(self) -> tuple[object, ...]:
        """Datos que deben ser idénticos en todas las líneas de un mismo folio."""
        return (
            self.rfc_proveedor,
            self.tipo,
            self.fecha_inicio,
            self.fecha_fin,
            self.moneda,
            self.plazo_pago_dias,
            self.sla_disponibilidad,
            self.tope_aumento_pct,
            self.cuota_implementacion,
        )
```

- [ ] **Step 4: Implementar el parseo**

`services/proveedores/src/proveedores/importacion/parseo.py`:
```python
"""Convierte el contenido de un CSV en filas validadas y errores por fila. Sin I/O."""

import csv
import io
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from proveedores.importacion.esquemas import FilaContrato

MAX_FILAS = 50_000

MENSAJES = {
    "missing": "Campo obligatorio",
    "string_pattern_mismatch": "Formato inválido",
    "string_too_long": "Máximo {max_length} caracteres",
    "string_too_short": "No puede estar vacío",
    "too_short": "Debe tener al menos {min_length} elemento(s)",
    "literal_error": "Valor no permitido; opciones: {expected}",
    "greater_than": "Debe ser mayor que {gt}",
    "greater_than_equal": "Debe ser mayor o igual que {ge}",
    "less_than": "Debe ser menor que {lt}",
    "less_than_equal": "Debe ser menor o igual que {le}",
    "decimal_parsing": "Debe ser un número (punto decimal, sin separador de miles)",
    "decimal_max_places": "Máximo {decimal_places} decimales",
    "decimal_max_digits": "Máximo {max_digits} dígitos",
    "decimal_whole_digits": "Demasiados dígitos enteros",
    "int_parsing": "Debe ser un número entero",
    "date_parsing": "Fecha inválida; use AAAA-MM-DD",
    "date_from_datetime_parsing": "Fecha inválida; use AAAA-MM-DD",
    "bool_parsing": "Debe ser true o false",
    "extra_forbidden": "Columna no reconocida",
}


@dataclass(frozen=True)
class ErrorFila:
    fila: int  # 0 = archivo completo, 1 = encabezado, 2+ = registros
    campo: str
    mensaje: str


@dataclass
class ResultadoParseo[M: BaseModel]:
    filas: list[tuple[int, M]] = field(default_factory=list)
    errores: list[ErrorFila] = field(default_factory=list)


def _mensaje(error: ErrorDetails) -> str:
    plantilla = MENSAJES.get(error["type"])
    if plantilla is None:
        return error["msg"].removeprefix("Value error, ")
    try:
        return plantilla.format(**error.get("ctx", {}))
    except (KeyError, IndexError):
        return error["msg"]


def leer_csv[M: BaseModel](contenido: bytes, esquema: type[M]) -> ResultadoParseo[M]:
    resultado: ResultadoParseo[M] = ResultadoParseo()
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        resultado.errores.append(
            ErrorFila(0, "archivo", "El archivo debe estar codificado en UTF-8")
        )
        return resultado

    primera_linea = texto.split("\n", 1)[0]
    separador = ";" if primera_linea.count(";") > primera_linea.count(",") else ","
    lector = csv.DictReader(io.StringIO(texto, newline=""), delimiter=separador)
    lector.fieldnames = [columna.strip() for columna in lector.fieldnames or []]

    columnas = set(lector.fieldnames)
    obligatorias = {n for n, campo in esquema.model_fields.items() if campo.is_required()}
    faltantes = sorted(obligatorias - columnas)
    desconocidas = sorted(columnas - set(esquema.model_fields))
    if faltantes or desconocidas:
        partes = []
        if faltantes:
            partes.append("faltan: " + ", ".join(faltantes))
        if desconocidas:
            partes.append("no reconocidas: " + ", ".join(desconocidas))
        resultado.errores.append(
            ErrorFila(1, "encabezado", "Columnas inválidas; " + "; ".join(partes))
        )
        return resultado

    for numero, fila in enumerate(lector, start=2):
        if numero - 1 > MAX_FILAS:
            resultado.errores.append(
                ErrorFila(numero, "archivo", f"El archivo excede {MAX_FILAS} filas")
            )
            break
        if None in fila:
            resultado.errores.append(
                ErrorFila(numero, "fila", "La fila tiene más valores que columnas")
            )
            continue
        try:
            resultado.filas.append((numero, esquema.model_validate(fila)))
        except ValidationError as exc:
            for error in exc.errors():
                campo = ".".join(str(parte) for parte in error["loc"]) or "fila"
                resultado.errores.append(ErrorFila(numero, campo, _mensaje(error)))
    return resultado


def duplicados[M: BaseModel](
    resultado: ResultadoParseo[M], clave: Callable[[M], Hashable], campo: str
) -> list[ErrorFila]:
    vistos: dict[Hashable, int] = {}
    errores: list[ErrorFila] = []
    for numero, fila in resultado.filas:
        valor = clave(fila)
        if valor in vistos:
            errores.append(ErrorFila(numero, campo, f"Duplicado de la fila {vistos[valor]}"))
        else:
            vistos[valor] = numero
    return errores


def agrupar_contratos(
    filas: list[tuple[int, FilaContrato]],
) -> tuple[dict[str, list[tuple[int, FilaContrato]]], list[ErrorFila]]:
    grupos: dict[str, list[tuple[int, FilaContrato]]] = {}
    errores: list[ErrorFila] = []
    for numero, fila in filas:
        grupo = grupos.setdefault(fila.folio, [])
        if grupo:
            numero_primera, primera = grupo[0]
            if fila.cabecera() != primera.cabecera():
                errores.append(
                    ErrorFila(
                        numero,
                        "folio",
                        f"Los datos del contrato {fila.folio} no coinciden "
                        f"con la fila {numero_primera}",
                    )
                )
            if any(otra.codigo_servicio == fila.codigo_servicio for _, otra in grupo):
                errores.append(
                    ErrorFila(
                        numero, "codigo_servicio", f"Servicio repetido en el contrato {fila.folio}"
                    )
                )
        grupo.append((numero, fila))
    return grupos, errores
```

- [ ] **Step 5: Ejecutar para verificar que pasan**

Run: `uv run pytest services/proveedores/tests/test_parseo.py -v`
Expected: `13 passed`. Si un mensaje sale en inglés, el tipo de error de Pydantic no está en `MENSAJES`. Hay que agregarlo con la clave que muestra `exc.errors()[i]["type"]`.

- [ ] **Step 6: Commit**

```bash
git add services/proveedores/src/proveedores/importacion services/proveedores/tests/test_parseo.py
git commit -m "feat(proveedores): parseo y validacion de CSV del ERP"
```

---

### Task 9: Importación — aplicar en la base de datos y emitir eventos

**Files:**
- Create: `services/proveedores/src/proveedores/importacion/aplicar.py`
- Test: `services/proveedores/tests/test_aplicar.py` (integración)

**Interfaces:**
- Consumes:
  - `leer_csv`, `duplicados`, `agrupar_contratos` y `ErrorFila` (Tarea 8).
  - Los modelos de la Tarea 7.
  - `registrar_evento` (Tarea 6) y `ErrorDominio` (Tarea 3).
  - Fixture `fabrica` (Tarea 7).
- Produces:
  - `class Entidad(StrEnum)`: `servicios`, `proveedores`, `tipo_cambio`, `contratos`, `desempeno`.
  - `ORDEN_CARGA: tuple[Entidad, ...]`.
  - `@dataclass(frozen=True) class ResumenImportacion(entidad: str, filas: int, registros: int, omitidos: int, eventos: int)`.
  - `class ErrorImportacion(ErrorDominio)`: estado 422, con `extra = {"errores": [...], "total_errores": n}` y el atributo `.errores: list[ErrorFila]`.
  - `async importar(sesion: AsyncSession, entidad: Entidad, contenido: bytes) -> ResumenImportacion`. Es todo o nada: el llamador abre y confirma la transacción.
  - Eventos (payloads):
    - `proveedor.actualizado`: `id`, `rfc`, `nombre`, `tamano`, `categorias`, `contacto_nombre`, `contacto_email`, `activo`.
    - `contrato.registrado`: `id`, `folio`, `tipo`, `proveedor_id`, `rfc_proveedor`, fechas, `moneda`, condiciones y `lineas[]` (`codigo_servicio`, `nombre_servicio`, `categoria`, `unidad`, `cantidad`, `precio_unitario`).
    - `desempeno.registrado`: `proveedor_id` y los campos de `FilaDesempeno`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`services/proveedores/tests/test_aplicar.py`:
```python
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from proveedores.importacion.aplicar import (
    Entidad,
    ErrorImportacion,
    ResumenImportacion,
    importar,
)
from proveedores.modelos import Contrato, Outbox, Proveedor, RegistroDesempeno, TipoCambio

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]

SERVICIOS = (
    "codigo,nombre,categoria,unidad,moneda\n"
    "SAAS-OFI-EMP,Suite de productividad en la nube - plan empresarial,"
    "licencia_saas,usuario_mes,USD\n"
    "CONS-DEV-SR,Desarrollador(a) senior - hora,consultoria,hora,MXN\n"
)
PROVEEDORES = (
    "rfc,nombre,tamano,categorias,contacto_nombre,contacto_email,activo\n"
    "NAZ210315AB1,Nube Azteca S.A. de C.V.,mediana,licencia_saas|nube,"
    "Laura Méndez,ventas01@proveedor01.example,true\n"
    "SDN190822K7P,Sistemas del Norte S.A. de C.V.,grande,consultoria,"
    "Jorge Ruiz,ventas02@proveedor02.example,true\n"
)
CONTRATO_ENC = (
    "folio,rfc_proveedor,tipo,fecha_inicio,fecha_fin,moneda,plazo_pago_dias,"
    "sla_disponibilidad,tope_aumento_pct,cuota_implementacion,codigo_servicio,"
    "cantidad,precio_unitario\n"
)
CONTRATOS = (
    CONTRATO_ENC
    + "C-0001,NAZ210315AB1,nuevo,2025-01-01,2025-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,250,21.5\n"
    + "C-0002,SDN190822K7P,nuevo,2025-03-01,2025-08-31,MXN,45,,,0,CONS-DEV-SR,160,1050\n"
)
DESEMPENO_ENC = (
    "rfc_proveedor,periodo,sla_cumplimiento_pct,tiempo_resolucion_h,"
    "incidentes_criticos,entregas_a_tiempo_pct,satisfaccion\n"
)
DESEMPENO = (
    DESEMPENO_ENC
    + "NAZ210315AB1,2025-01-01,99.5,4.25,0,97,4.6\n"
    + "NAZ210315AB1,2025-02-01,98.75,6.5,1,93,4.1\n"
)


async def _importar(fabrica: Fabrica, entidad: Entidad, texto: str) -> ResumenImportacion:
    async with fabrica() as sesion, sesion.begin():
        return await importar(sesion, entidad, texto.encode())


async def _contar(fabrica: Fabrica, modelo: type[object]) -> int:
    async with fabrica() as sesion:
        return int(await sesion.scalar(select(func.count()).select_from(modelo)) or 0)


async def _eventos(fabrica: Fabrica, tipo: str) -> list[Outbox]:
    async with fabrica() as sesion:
        return list((await sesion.scalars(select(Outbox).where(Outbox.tipo == tipo))).all())


async def _catalogo_y_proveedores(fabrica: Fabrica) -> None:
    await _importar(fabrica, Entidad.SERVICIOS, SERVICIOS)
    await _importar(fabrica, Entidad.PROVEEDORES, PROVEEDORES)


async def test_importar_proveedores_crea_registros_y_eventos(fabrica: Fabrica) -> None:
    await _importar(fabrica, Entidad.SERVICIOS, SERVICIOS)
    resumen = await _importar(fabrica, Entidad.PROVEEDORES, PROVEEDORES)
    assert resumen == ResumenImportacion("proveedores", 2, 2, 0, 2)
    eventos = await _eventos(fabrica, "proveedor.actualizado")
    assert sorted(e.payload["rfc"] for e in eventos) == ["NAZ210315AB1", "SDN190822K7P"]
    assert eventos[0].payload["categorias"] in (["licencia_saas", "nube"], ["consultoria"])


async def test_reimportar_proveedores_actualiza_sin_duplicar(fabrica: Fabrica) -> None:
    await _importar(fabrica, Entidad.PROVEEDORES, PROVEEDORES)
    await _importar(fabrica, Entidad.PROVEEDORES, PROVEEDORES.replace("Nube Azteca", "Nube Maya"))
    assert await _contar(fabrica, Proveedor) == 2
    async with fabrica() as sesion:
        nombre = await sesion.scalar(
            select(Proveedor.nombre).where(Proveedor.rfc == "NAZ210315AB1")
        )
    assert nombre == "Nube Maya S.A. de C.V."


async def test_importar_contratos_crea_lineas_y_evento_con_detalle(fabrica: Fabrica) -> None:
    await _catalogo_y_proveedores(fabrica)
    resumen = await _importar(fabrica, Entidad.CONTRATOS, CONTRATOS)
    assert resumen == ResumenImportacion("contratos", 2, 2, 0, 2)
    [evento] = [
        e for e in await _eventos(fabrica, "contrato.registrado") if e.payload["folio"] == "C-0001"
    ]
    assert evento.payload["rfc_proveedor"] == "NAZ210315AB1"
    assert evento.payload["lineas"] == [
        {
            "codigo_servicio": "SAAS-OFI-EMP",
            "nombre_servicio": "Suite de productividad en la nube - plan empresarial",
            "categoria": "licencia_saas",
            "unidad": "usuario_mes",
            "cantidad": "250",
            "precio_unitario": "21.5",
        }
    ]
    async with fabrica() as sesion:
        precio = await sesion.scalar(
            select(Contrato.cuota_implementacion).where(Contrato.folio == "C-0002")
        )
    assert precio == Decimal("0.0000")


async def test_reimportar_contratos_es_idempotente(fabrica: Fabrica) -> None:
    await _catalogo_y_proveedores(fabrica)
    await _importar(fabrica, Entidad.CONTRATOS, CONTRATOS)
    segunda = await _importar(fabrica, Entidad.CONTRATOS, CONTRATOS)
    assert segunda == ResumenImportacion("contratos", 2, 0, 2, 0)
    assert await _contar(fabrica, Contrato) == 2
    assert len(await _eventos(fabrica, "contrato.registrado")) == 2


async def test_referencias_inexistentes_no_escriben_nada(fabrica: Fabrica) -> None:
    await _catalogo_y_proveedores(fabrica)
    texto = (
        CONTRATO_ENC
        + "C-0003,XAX010101AB1,nuevo,2025-01-01,2025-12-31,USD,30,,,0,SAAS-OFI-EMP,10,20\n"
        + "C-0004,NAZ210315AB1,nuevo,2025-01-01,2025-12-31,USD,30,,,0,NO-EXISTE,10,20\n"
        + "C-0005,NAZ210315AB1,nuevo,2025-01-01,2025-12-31,MXN,30,,,0,SAAS-OFI-EMP,10,20\n"
    )
    with pytest.raises(ErrorImportacion) as error:
        await _importar(fabrica, Entidad.CONTRATOS, texto)
    assert [(e.fila, e.campo) for e in error.value.errores] == [
        (2, "rfc_proveedor"),
        (3, "codigo_servicio"),
        (4, "moneda"),
    ]
    assert error.value.estado == 422
    assert await _contar(fabrica, Contrato) == 0
    assert await _eventos(fabrica, "contrato.registrado") == []


async def test_un_error_de_formato_cancela_todo_el_archivo(fabrica: Fabrica) -> None:
    texto = PROVEEDORES + "MAL210315AB1,Otro,mediana,nube,Ana,correo-invalido,true\n"
    with pytest.raises(ErrorImportacion) as error:
        await _importar(fabrica, Entidad.PROVEEDORES, texto)
    assert error.value.extra["total_errores"] == 1
    assert error.value.extra["errores"][0]["campo"] == "contacto_email"
    assert await _contar(fabrica, Proveedor) == 0


async def test_desempeno_se_actualiza_por_periodo(fabrica: Fabrica) -> None:
    await _catalogo_y_proveedores(fabrica)
    await _importar(fabrica, Entidad.DESEMPENO, DESEMPENO)
    resumen = await _importar(fabrica, Entidad.DESEMPENO, DESEMPENO.replace("4.6", "4.9"))
    assert resumen == ResumenImportacion("desempeno", 2, 2, 0, 2)
    assert await _contar(fabrica, RegistroDesempeno) == 2
    async with fabrica() as sesion:
        satisfacciones = (await sesion.scalars(select(RegistroDesempeno.satisfaccion))).all()
    assert Decimal("4.90") in satisfacciones
    assert len(await _eventos(fabrica, "desempeno.registrado")) == 4


async def test_tipo_cambio_se_actualiza_sin_eventos(fabrica: Fabrica) -> None:
    await _importar(fabrica, Entidad.TIPO_CAMBIO, "periodo,usd_mxn\n2025-01-01,20.4512\n")
    await _importar(fabrica, Entidad.TIPO_CAMBIO, "periodo,usd_mxn\n2025-01-01,20.1000\n")
    async with fabrica() as sesion:
        [valor] = (await sesion.scalars(select(TipoCambio.usd_mxn))).all()
    assert valor == Decimal("20.1000")
    assert await _contar(fabrica, Outbox) == 0


async def test_archivo_solo_con_encabezado_no_hace_nada(fabrica: Fabrica) -> None:
    resumen = await _importar(fabrica, Entidad.SERVICIOS, "codigo,nombre,categoria,unidad,moneda\n")
    assert resumen == ResumenImportacion("servicios", 0, 0, 0, 0)
```

- [ ] **Step 2: Ejecutar para verificar que fallan**

Run: `uv run pytest services/proveedores/tests/test_aplicar.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'proveedores.importacion.aplicar'`.

- [ ] **Step 3: Implementar**

`services/proveedores/src/proveedores/importacion/aplicar.py`:
```python
"""Aplica en la BD los CSV validados y registra los eventos en el outbox. Todo o nada."""

import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from comun.errores import ErrorDominio
from comun.outbox import registrar_evento
from proveedores.importacion.esquemas import (
    FilaContrato,
    FilaDesempeno,
    FilaProveedor,
    FilaServicio,
    FilaTipoCambio,
)
from proveedores.importacion.parseo import ErrorFila, agrupar_contratos, duplicados, leer_csv
from proveedores.modelos import (
    Contrato,
    LineaContrato,
    Outbox,
    Proveedor,
    RegistroDesempeno,
    ServicioCatalogo,
    TipoCambio,
)

MAX_ERRORES_REPORTADOS = 200


class Entidad(StrEnum):
    SERVICIOS = "servicios"
    PROVEEDORES = "proveedores"
    TIPO_CAMBIO = "tipo_cambio"
    CONTRATOS = "contratos"
    DESEMPENO = "desempeno"


# Contratos y desempeño referencian proveedores y servicios: se cargan después.
ORDEN_CARGA = (
    Entidad.SERVICIOS,
    Entidad.PROVEEDORES,
    Entidad.TIPO_CAMBIO,
    Entidad.CONTRATOS,
    Entidad.DESEMPENO,
)


@dataclass(frozen=True)
class ResumenImportacion:
    """`filas`: registros del CSV · `registros`: entidades creadas o actualizadas ·
    `omitidos`: contratos que ya existían (los contratos no se modifican) · `eventos`."""

    entidad: str
    filas: int
    registros: int
    omitidos: int
    eventos: int


class ErrorImportacion(ErrorDominio):
    def __init__(self, errores: list[ErrorFila]) -> None:
        super().__init__(
            422,
            "Archivo con errores",
            f"Se encontraron {len(errores)} error(es); no se importó ninguna fila.",
            {
                "errores": [asdict(e) for e in errores[:MAX_ERRORES_REPORTADOS]],
                "total_errores": len(errores),
            },
        )
        self.errores = errores


def _exigir_sin_errores(errores: list[ErrorFila]) -> None:
    if errores:
        raise ErrorImportacion(sorted(errores, key=lambda e: (e.fila, e.campo)))


async def _ids_proveedores(sesion: AsyncSession) -> dict[str, uuid.UUID]:
    filas = await sesion.execute(select(Proveedor.rfc, Proveedor.id))
    return dict(filas.tuples().all())


async def importar(
    sesion: AsyncSession, entidad: Entidad, contenido: bytes
) -> ResumenImportacion:
    match entidad:
        case Entidad.SERVICIOS:
            return await _servicios(sesion, contenido)
        case Entidad.PROVEEDORES:
            return await _proveedores(sesion, contenido)
        case Entidad.TIPO_CAMBIO:
            return await _tipo_cambio(sesion, contenido)
        case Entidad.CONTRATOS:
            return await _contratos(sesion, contenido)
        case Entidad.DESEMPENO:
            return await _desempeno(sesion, contenido)


async def _servicios(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaServicio)
    _exigir_sin_errores(resultado.errores + duplicados(resultado, lambda f: f.codigo, "codigo"))
    datos = [fila.model_dump() for _, fila in resultado.filas]
    if datos:
        consulta = insert(ServicioCatalogo)
        consulta = consulta.on_conflict_do_update(
            index_elements=[ServicioCatalogo.codigo],
            set_={c: consulta.excluded[c] for c in ("nombre", "categoria", "unidad", "moneda")},
        )
        await sesion.execute(consulta, datos)
    return ResumenImportacion(Entidad.SERVICIOS, len(datos), len(datos), 0, 0)


async def _proveedores(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaProveedor)
    _exigir_sin_errores(resultado.errores + duplicados(resultado, lambda f: f.rfc, "rfc"))
    datos = [fila.model_dump() for _, fila in resultado.filas]
    if not datos:
        return ResumenImportacion(Entidad.PROVEEDORES, 0, 0, 0, 0)
    columnas = ("nombre", "tamano", "categorias", "contacto_nombre", "contacto_email", "activo")
    consulta = insert(Proveedor)
    consulta = consulta.on_conflict_do_update(
        index_elements=[Proveedor.rfc],
        set_={
            **{c: consulta.excluded[c] for c in columnas},
            "actualizado_en": func.now(),
        },
    ).returning(Proveedor)
    proveedores = (
        await sesion.scalars(consulta, datos, execution_options={"populate_existing": True})
    ).all()
    for proveedor in proveedores:
        registrar_evento(
            sesion,
            Outbox,
            "proveedor.actualizado",
            {"id": proveedor.id, "rfc": proveedor.rfc}
            | {c: getattr(proveedor, c) for c in columnas},
        )
    return ResumenImportacion(
        Entidad.PROVEEDORES, len(datos), len(proveedores), 0, len(proveedores)
    )


async def _tipo_cambio(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaTipoCambio)
    _exigir_sin_errores(
        resultado.errores + duplicados(resultado, lambda f: f.periodo, "periodo")
    )
    datos = [fila.model_dump() for _, fila in resultado.filas]
    if datos:
        consulta = insert(TipoCambio)
        consulta = consulta.on_conflict_do_update(
            index_elements=[TipoCambio.periodo], set_={"usd_mxn": consulta.excluded.usd_mxn}
        )
        await sesion.execute(consulta, datos)
    return ResumenImportacion(Entidad.TIPO_CAMBIO, len(datos), len(datos), 0, 0)


async def _desempeno(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaDesempeno)
    ids = await _ids_proveedores(sesion)
    errores = resultado.errores + duplicados(
        resultado, lambda f: (f.rfc_proveedor, f.periodo), "periodo"
    )
    errores += [
        ErrorFila(numero, "rfc_proveedor", f"Proveedor no registrado: {fila.rfc_proveedor}")
        for numero, fila in resultado.filas
        if fila.rfc_proveedor not in ids
    ]
    _exigir_sin_errores(errores)
    datos = [
        {"proveedor_id": ids[fila.rfc_proveedor]} | fila.model_dump(exclude={"rfc_proveedor"})
        for _, fila in resultado.filas
    ]
    if datos:
        metricas = (
            "sla_cumplimiento_pct",
            "tiempo_resolucion_h",
            "incidentes_criticos",
            "entregas_a_tiempo_pct",
            "satisfaccion",
        )
        consulta = insert(RegistroDesempeno)
        consulta = consulta.on_conflict_do_update(
            index_elements=[RegistroDesempeno.proveedor_id, RegistroDesempeno.periodo],
            set_={c: consulta.excluded[c] for c in metricas},
        )
        await sesion.execute(consulta, datos)
    for fila_datos in datos:
        registrar_evento(sesion, Outbox, "desempeno.registrado", fila_datos)
    return ResumenImportacion(Entidad.DESEMPENO, len(datos), len(datos), 0, len(datos))


async def _contratos(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaContrato)
    grupos, errores = agrupar_contratos(resultado.filas)
    errores = resultado.errores + errores
    ids = await _ids_proveedores(sesion)
    servicios = {s.codigo: s for s in (await sesion.scalars(select(ServicioCatalogo))).all()}
    for numero, fila in resultado.filas:
        if fila.rfc_proveedor not in ids:
            errores.append(
                ErrorFila(numero, "rfc_proveedor", f"Proveedor no registrado: {fila.rfc_proveedor}")
            )
        servicio = servicios.get(fila.codigo_servicio)
        if servicio is None:
            errores.append(
                ErrorFila(numero, "codigo_servicio", f"Servicio no registrado: {fila.codigo_servicio}")
            )
        elif servicio.moneda != fila.moneda:
            errores.append(
                ErrorFila(
                    numero, "moneda", f"Debe coincidir con la moneda del servicio ({servicio.moneda})"
                )
            )
    _exigir_sin_errores(errores)

    # ponytail: carga todos los folios existentes; filtrar por lote si llegan a cientos de miles.
    existentes = set((await sesion.scalars(select(Contrato.folio))).all())
    nuevos = 0
    for folio, lineas in grupos.items():
        if folio in existentes:
            continue
        cabecera = lineas[0][1]
        contrato = Contrato(
            id=uuid.uuid4(),
            folio=folio,
            proveedor_id=ids[cabecera.rfc_proveedor],
            tipo=cabecera.tipo,
            fecha_inicio=cabecera.fecha_inicio,
            fecha_fin=cabecera.fecha_fin,
            moneda=cabecera.moneda,
            plazo_pago_dias=cabecera.plazo_pago_dias,
            sla_disponibilidad=cabecera.sla_disponibilidad,
            tope_aumento_pct=cabecera.tope_aumento_pct,
            cuota_implementacion=cabecera.cuota_implementacion,
            lineas=[
                LineaContrato(
                    servicio_id=servicios[fila.codigo_servicio].id,
                    cantidad=fila.cantidad,
                    precio_unitario=fila.precio_unitario,
                )
                for _, fila in lineas
            ],
        )
        sesion.add(contrato)
        registrar_evento(sesion, Outbox, "contrato.registrado", _payload_contrato(contrato, cabecera, lineas, servicios))
        nuevos += 1
    return ResumenImportacion(
        Entidad.CONTRATOS, len(resultado.filas), nuevos, len(grupos) - nuevos, nuevos
    )


def _payload_contrato(
    contrato: Contrato,
    cabecera: FilaContrato,
    lineas: list[tuple[int, FilaContrato]],
    servicios: dict[str, ServicioCatalogo],
) -> dict[str, Any]:
    return {
        "id": contrato.id,
        "proveedor_id": contrato.proveedor_id,
        **cabecera.model_dump(exclude={"codigo_servicio", "cantidad", "precio_unitario"}),
        "lineas": [
            {
                "codigo_servicio": fila.codigo_servicio,
                "nombre_servicio": servicios[fila.codigo_servicio].nombre,
                "categoria": servicios[fila.codigo_servicio].categoria,
                "unidad": servicios[fila.codigo_servicio].unidad,
                "cantidad": fila.cantidad,
                "precio_unitario": fila.precio_unitario,
            }
            for _, fila in lineas
        ],
    }
```

- [ ] **Step 4: Ejecutar para verificar que pasan**

Run: `uv run pytest services/proveedores/tests/test_aplicar.py -v`
Expected: `9 passed`.

- [ ] **Step 5: Lint, formato y tipos**

Run: `uv run ruff format . ; uv run ruff check . ; uv run mypy`
Expected: sin errores. `ruff format` va primero porque reacomoda las líneas largas de `_contratos` antes de que `ruff check` revise su longitud.

- [ ] **Step 6: Commit**

```bash
git add services/proveedores/src/proveedores/importacion/aplicar.py services/proveedores/tests/test_aplicar.py
git commit -m "feat(proveedores): importacion todo-o-nada con eventos en el outbox"
```

---

### Task 10: API REST del servicio de proveedores

**Files:**
- Create: `services/proveedores/src/proveedores/api/__init__.py`, `api/esquemas.py`, `api/rutas.py`, `services/proveedores/src/proveedores/main.py`
- Modify: `services/proveedores/tests/conftest.py` (agregar la fixture `cliente`)
- Test: `services/proveedores/tests/test_api.py` (integración)

**Interfaces:**
- Consumes: Tareas 2–9.
- Produces:
  - `crear_app(configuracion=None, validador=None, fabrica=None) -> FastAPI`. En producción: `uvicorn proveedores.main:crear_app --factory`.
  - Rutas (bajo el gateway con el prefijo `/api/proveedores`). Las de lectura exigen cualquier rol interno:
    - `GET /proveedores?q=&categoria=&activo=&limite=25&desplazamiento=0` → `{total, elementos: [ProveedorResumen]}`.
    - `GET /proveedores/{id}` → `ProveedorDetalle`, que agrega `contacto_nombre`, `contacto_email` y `contratos_vigentes`.
    - `GET /proveedores/{id}/contratos` → `[ContratoSalida]`, con `lineas[]`, ordenados del más reciente al más antiguo.
    - `GET /proveedores/{id}/desempeno?meses=12` → `[Desempeno]`, del más reciente al más antiguo.
    - `GET /servicios` → `[Servicio]`.
    - `POST /importaciones/{entidad}` (solo `admin`), con multipart y el campo `archivo` → `ResumenImportacion`.
    - `GET /salud/vivo` y `GET /salud/listo`.
  - Los montos se serializan como texto decimal (p. ej. `"21.5000"`).

- [ ] **Step 1: Agregar la fixture `cliente` a `conftest.py`**

Al final de `services/proveedores/tests/conftest.py`:
```python
import httpx

from proveedores.config import Configuracion
from proveedores.main import crear_app


@pytest.fixture
async def cliente(
    url_bd: str, fabrica: async_sessionmaker[AsyncSession], claves: ClavesPrueba
) -> AsyncIterator[httpx.AsyncClient]:
    app = crear_app(Configuracion(database_url=url_bd), claves.validador(), fabrica)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente
```
(Mover los dos `import`/`from` nuevos al bloque de importaciones del inicio del archivo.)

- [ ] **Step 2: Escribir las pruebas que fallan**

`services/proveedores/tests/test_api.py`:
```python
import uuid

import httpx
import pytest

from comun.pruebas import ClavesPrueba

pytestmark = pytest.mark.integracion

SERVICIOS = (
    "codigo,nombre,categoria,unidad,moneda\n"
    "SAAS-OFI-EMP,Suite de productividad en la nube - plan empresarial,"
    "licencia_saas,usuario_mes,USD\n"
    "SOP-MESA-TK,Mesa de ayuda - ticket,soporte,ticket,MXN\n"
)
PROVEEDORES = (
    "rfc,nombre,tamano,categorias,contacto_nombre,contacto_email,activo\n"
    "NAZ210315AB1,Nube Azteca S.A. de C.V.,mediana,licencia_saas|nube,"
    "Laura Méndez,ventas01@proveedor01.example,true\n"
    "SDN190822K7P,Sistemas del Norte S.A. de C.V.,grande,consultoria,"
    "Jorge Ruiz,ventas02@proveedor02.example,true\n"
    "CPC200101QW3,Cien Por Ciento Soporte S.A. de C.V.,pequena,soporte,"
    "Ana Torres,ventas03@proveedor03.example,false\n"
)
CONTRATOS = (
    "folio,rfc_proveedor,tipo,fecha_inicio,fecha_fin,moneda,plazo_pago_dias,"
    "sla_disponibilidad,tope_aumento_pct,cuota_implementacion,codigo_servicio,"
    "cantidad,precio_unitario\n"
    "C-0001,NAZ210315AB1,nuevo,2020-01-01,2020-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,200,20\n"
    "C-0002,NAZ210315AB1,renovacion,2021-01-01,2099-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,250,21.5\n"
)
DESEMPENO = (
    "rfc_proveedor,periodo,sla_cumplimiento_pct,tiempo_resolucion_h,"
    "incidentes_criticos,entregas_a_tiempo_pct,satisfaccion\n"
    "NAZ210315AB1,2025-01-01,99.5,4.25,0,97,4.6\n"
    "NAZ210315AB1,2025-02-01,98.75,6.5,1,93,4.1\n"
)


def _auth(claves: ClavesPrueba, *roles: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token(*roles)}"}


async def _subir(
    cliente: httpx.AsyncClient,
    claves: ClavesPrueba,
    entidad: str,
    contenido: bytes,
    rol: str = "admin",
) -> httpx.Response:
    return await cliente.post(
        f"/importaciones/{entidad}",
        files={"archivo": (f"{entidad}.csv", contenido, "text/csv")},
        headers=_auth(claves, rol),
    )


@pytest.fixture
async def con_datos(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> httpx.AsyncClient:
    for entidad, texto in (
        ("servicios", SERVICIOS),
        ("proveedores", PROVEEDORES),
        ("contratos", CONTRATOS),
        ("desempeno", DESEMPENO),
    ):
        respuesta = await _subir(cliente, claves, entidad, texto.encode())
        assert respuesta.status_code == 200, respuesta.text
    return cliente


async def _id_de(cliente: httpx.AsyncClient, claves: ClavesPrueba, rfc: str) -> str:
    respuesta = await cliente.get(
        "/proveedores", params={"q": rfc}, headers=_auth(claves, "comprador")
    )
    [proveedor] = respuesta.json()["elementos"]
    return str(proveedor["id"])


async def test_sin_token_responde_401(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/proveedores")
    assert respuesta.status_code == 401
    assert respuesta.headers["content-type"] == "application/problem+json"


async def test_comprador_no_puede_importar(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await _subir(cliente, claves, "servicios", SERVICIOS.encode(), rol="comprador")
    assert respuesta.status_code == 403


async def test_importar_devuelve_resumen(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await _subir(cliente, claves, "servicios", SERVICIOS.encode())
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "entidad": "servicios", "filas": 2, "registros": 2, "omitidos": 0, "eventos": 0
    }


async def test_importar_con_errores_devuelve_422_con_detalle(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    texto = PROVEEDORES.replace("ventas01@proveedor01.example", "correo-invalido")
    respuesta = await _subir(cliente, claves, "proveedores", texto.encode())
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["title"] == "Archivo con errores"
    assert cuerpo["errores"] == [
        {"fila": 2, "campo": "contacto_email", "mensaje": "Formato inválido"}
    ]


async def test_archivo_no_utf8_devuelve_422(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await _subir(cliente, claves, "proveedores", PROVEEDORES.encode("cp1252"))
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"][0]["mensaje"] == "El archivo debe estar codificado en UTF-8"


async def test_archivo_mayor_a_10_mb_devuelve_413(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await _subir(cliente, claves, "servicios", b"a" * (10 * 1024 * 1024 + 1))
    assert respuesta.status_code == 413


async def test_entidad_desconocida_devuelve_422(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await _subir(cliente, claves, "facturas", SERVICIOS.encode())
    assert respuesta.status_code == 422


async def test_listar_filtrar_y_buscar(con_datos: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    async def buscar(**params: str) -> dict[str, object]:
        respuesta = await con_datos.get(
            "/proveedores", params=params, headers=_auth(claves, "aprobador")
        )
        assert respuesta.status_code == 200
        return dict(respuesta.json())

    todos = await buscar()
    assert todos["total"] == 3
    assert [p["nombre"] for p in todos["elementos"]] == [  # type: ignore[attr-defined]
        "Cien Por Ciento Soporte S.A. de C.V.",
        "Nube Azteca S.A. de C.V.",
        "Sistemas del Norte S.A. de C.V.",
    ]
    assert (await buscar(q="norte"))["total"] == 1
    assert (await buscar(q="%"))["total"] == 0
    assert (await buscar(q="_"))["total"] == 0
    assert (await buscar(categoria="soporte"))["total"] == 1
    assert (await buscar(activo="false"))["total"] == 1


async def test_paginacion(con_datos: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await con_datos.get(
        "/proveedores",
        params={"limite": 2, "desplazamiento": 2},
        headers=_auth(claves, "comprador"),
    )
    assert respuesta.json()["total"] == 3
    assert len(respuesta.json()["elementos"]) == 1


async def test_detalle_contratos_y_desempeno(
    con_datos: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    cabeceras = _auth(claves, "comprador")
    proveedor_id = await _id_de(con_datos, claves, "NAZ210315AB1")

    detalle = (await con_datos.get(f"/proveedores/{proveedor_id}", headers=cabeceras)).json()
    assert detalle["contratos_vigentes"] == 1
    assert detalle["contacto_email"] == "ventas01@proveedor01.example"

    contratos = (
        await con_datos.get(f"/proveedores/{proveedor_id}/contratos", headers=cabeceras)
    ).json()
    assert [c["folio"] for c in contratos] == ["C-0002", "C-0001"]
    assert contratos[0]["lineas"] == [
        {
            "codigo_servicio": "SAAS-OFI-EMP",
            "nombre_servicio": "Suite de productividad en la nube - plan empresarial",
            "unidad": "usuario_mes",
            "cantidad": "250.0000",
            "precio_unitario": "21.5000",
        }
    ]

    desempeno = (
        await con_datos.get(
            f"/proveedores/{proveedor_id}/desempeno", params={"meses": 1}, headers=cabeceras
        )
    ).json()
    assert [d["periodo"] for d in desempeno] == ["2025-02-01"]


async def test_proveedor_inexistente_o_id_invalido(
    con_datos: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    cabeceras = _auth(claves, "comprador")
    inexistente = uuid.uuid4()
    assert (await con_datos.get(f"/proveedores/{inexistente}", headers=cabeceras)).status_code == 404
    assert (
        await con_datos.get(f"/proveedores/{inexistente}/contratos", headers=cabeceras)
    ).status_code == 404
    assert (await con_datos.get("/proveedores/no-es-uuid", headers=cabeceras)).status_code == 422


async def test_catalogo_de_servicios(con_datos: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await con_datos.get("/servicios", headers=_auth(claves, "comprador"))
    assert [s["codigo"] for s in respuesta.json()] == ["SAAS-OFI-EMP", "SOP-MESA-TK"]


async def test_salud(cliente: httpx.AsyncClient) -> None:
    assert (await cliente.get("/salud/vivo")).status_code == 200
    listo = await cliente.get("/salud/listo")
    # En pruebas no corre el ciclo de vida, así que el relay no está conectado.
    assert listo.status_code == 503
    assert listo.json()["dependencias"] == {"postgres": "ok", "rabbitmq": "error"}
```

- [ ] **Step 3: Ejecutar para verificar que fallan**

Run: `uv run pytest services/proveedores/tests/test_api.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'proveedores.main'`.

- [ ] **Step 4: Esquemas de respuesta**

`services/proveedores/src/proveedores/api/__init__.py`:
```python
"""API HTTP del servicio de proveedores."""
```

`services/proveedores/src/proveedores/api/esquemas.py`:
```python
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesdeOrm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProveedorResumen(DesdeOrm):
    id: UUID
    rfc: str
    nombre: str
    tamano: str
    categorias: list[str]
    activo: bool


class PaginaProveedores(BaseModel):
    total: int
    elementos: list[ProveedorResumen]


class ProveedorDetalle(ProveedorResumen):
    contacto_nombre: str
    contacto_email: str
    contratos_vigentes: int


class Servicio(DesdeOrm):
    id: UUID
    codigo: str
    nombre: str
    categoria: str
    unidad: str
    moneda: str


class LineaContratoSalida(BaseModel):
    codigo_servicio: str
    nombre_servicio: str
    unidad: str
    cantidad: Decimal
    precio_unitario: Decimal


class ContratoSalida(BaseModel):
    id: UUID
    folio: str
    tipo: str
    fecha_inicio: date
    fecha_fin: date
    moneda: str
    plazo_pago_dias: int
    sla_disponibilidad: Decimal | None
    tope_aumento_pct: Decimal | None
    cuota_implementacion: Decimal
    lineas: list[LineaContratoSalida]


class Desempeno(DesdeOrm):
    periodo: date
    sla_cumplimiento_pct: Decimal
    tiempo_resolucion_h: Decimal
    incidentes_criticos: int
    entregas_a_tiempo_pct: Decimal
    satisfaccion: Decimal
```

- [ ] **Step 5: Rutas**

`services/proveedores/src/proveedores/api/rutas.py`:
```python
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comun.auth import ROLES_INTERNOS, Usuario, requiere_rol
from comun.errores import ErrorDominio
from proveedores.api import esquemas
from proveedores.db import obtener_sesion
from proveedores.importacion.aplicar import Entidad, ResumenImportacion, importar
from proveedores.importacion.esquemas import Categoria
from proveedores.modelos import (
    Contrato,
    LineaContrato,
    Proveedor,
    RegistroDesempeno,
    ServicioCatalogo,
)

MAX_BYTES_CSV = 10 * 1024 * 1024

Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]
Interno = Annotated[Usuario, Depends(requiere_rol(*ROLES_INTERNOS))]
Admin = Annotated[Usuario, Depends(requiere_rol("admin"))]

router = APIRouter()


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _proveedor_o_404(sesion: AsyncSession, proveedor_id: UUID) -> Proveedor:
    proveedor = await sesion.get(Proveedor, proveedor_id)
    if proveedor is None:
        raise ErrorDominio(404, "No encontrado", "El proveedor no existe")
    return proveedor


@router.get("/proveedores", tags=["proveedores"])
async def listar_proveedores(
    sesion: Sesion,
    _: Interno,
    q: Annotated[str | None, Query(max_length=100)] = None,
    categoria: Categoria | None = None,
    activo: bool | None = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 25,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> esquemas.PaginaProveedores:
    condiciones = []
    if q:
        patron = f"%{_escapar_like(q)}%"
        condiciones.append(
            or_(
                Proveedor.nombre.ilike(patron, escape="\\"),
                Proveedor.rfc.ilike(patron, escape="\\"),
            )
        )
    if categoria:
        condiciones.append(Proveedor.categorias.contains([categoria]))
    if activo is not None:
        condiciones.append(Proveedor.activo.is_(activo))
    total = await sesion.scalar(
        select(func.count()).select_from(Proveedor).where(*condiciones)
    )
    filas = await sesion.scalars(
        select(Proveedor)
        .where(*condiciones)
        .order_by(Proveedor.nombre)
        .limit(limite)
        .offset(desplazamiento)
    )
    return esquemas.PaginaProveedores(
        total=total or 0,
        elementos=[esquemas.ProveedorResumen.model_validate(p) for p in filas],
    )


@router.get("/proveedores/{proveedor_id}", tags=["proveedores"])
async def obtener_proveedor(
    proveedor_id: UUID, sesion: Sesion, _: Interno
) -> esquemas.ProveedorDetalle:
    proveedor = await _proveedor_o_404(sesion, proveedor_id)
    hoy = date.today()
    vigentes = await sesion.scalar(
        select(func.count())
        .select_from(Contrato)
        .where(
            Contrato.proveedor_id == proveedor_id,
            Contrato.fecha_inicio <= hoy,
            Contrato.fecha_fin >= hoy,
        )
    )
    return esquemas.ProveedorDetalle(
        **esquemas.ProveedorResumen.model_validate(proveedor).model_dump(),
        contacto_nombre=proveedor.contacto_nombre,
        contacto_email=proveedor.contacto_email,
        contratos_vigentes=vigentes or 0,
    )


@router.get("/proveedores/{proveedor_id}/contratos", tags=["proveedores"])
async def contratos_del_proveedor(
    proveedor_id: UUID, sesion: Sesion, _: Interno
) -> list[esquemas.ContratoSalida]:
    await _proveedor_o_404(sesion, proveedor_id)
    contratos = await sesion.scalars(
        select(Contrato)
        .where(Contrato.proveedor_id == proveedor_id)
        .order_by(Contrato.fecha_inicio.desc())
        .options(selectinload(Contrato.lineas).selectinload(LineaContrato.servicio))
    )
    return [
        esquemas.ContratoSalida(
            id=c.id,
            folio=c.folio,
            tipo=c.tipo,
            fecha_inicio=c.fecha_inicio,
            fecha_fin=c.fecha_fin,
            moneda=c.moneda,
            plazo_pago_dias=c.plazo_pago_dias,
            sla_disponibilidad=c.sla_disponibilidad,
            tope_aumento_pct=c.tope_aumento_pct,
            cuota_implementacion=c.cuota_implementacion,
            lineas=[
                esquemas.LineaContratoSalida(
                    codigo_servicio=linea.servicio.codigo,
                    nombre_servicio=linea.servicio.nombre,
                    unidad=linea.servicio.unidad,
                    cantidad=linea.cantidad,
                    precio_unitario=linea.precio_unitario,
                )
                for linea in c.lineas
            ],
        )
        for c in contratos
    ]


@router.get("/proveedores/{proveedor_id}/desempeno", tags=["proveedores"])
async def desempeno_del_proveedor(
    proveedor_id: UUID,
    sesion: Sesion,
    _: Interno,
    meses: Annotated[int, Query(ge=1, le=60)] = 12,
) -> list[esquemas.Desempeno]:
    await _proveedor_o_404(sesion, proveedor_id)
    registros = await sesion.scalars(
        select(RegistroDesempeno)
        .where(RegistroDesempeno.proveedor_id == proveedor_id)
        .order_by(RegistroDesempeno.periodo.desc())
        .limit(meses)
    )
    return [esquemas.Desempeno.model_validate(r) for r in registros]


@router.get("/servicios", tags=["catalogo"])
async def listar_servicios(sesion: Sesion, _: Interno) -> list[esquemas.Servicio]:
    servicios = await sesion.scalars(
        select(ServicioCatalogo).order_by(ServicioCatalogo.categoria, ServicioCatalogo.codigo)
    )
    return [esquemas.Servicio.model_validate(s) for s in servicios]


@router.post("/importaciones/{entidad}", tags=["importacion"])
async def importar_archivo(
    entidad: Entidad,
    archivo: Annotated[UploadFile, File()],
    sesion: Sesion,
    _: Admin,
) -> ResumenImportacion:
    contenido = await archivo.read(MAX_BYTES_CSV + 1)
    if len(contenido) > MAX_BYTES_CSV:
        raise ErrorDominio(413, "Archivo demasiado grande", "El archivo excede el límite de 10 MB")
    async with sesion.begin():
        return await importar(sesion, entidad, contenido)
```

> Nota: el catálogo se ordena por `categoria` y luego `codigo`. En la prueba, `licencia_saas` < `soporte`, por eso el orden esperado es `SAAS-OFI-EMP`, `SOP-MESA-TK`.

- [ ] **Step 6: Fábrica de la aplicación**

`services/proveedores/src/proveedores/main.py`:
```python
"""Aplicación FastAPI del servicio de proveedores."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.outbox import RelayOutbox
from comun.salud import crear_router_salud
from proveedores.api.rutas import router
from proveedores.config import Configuracion
from proveedores.modelos import Outbox


def crear_app(
    configuracion: Configuracion | None = None,
    validador: ValidadorJWT | None = None,
    fabrica: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    config = configuracion or Configuracion()
    configurar_logs(config.nombre_servicio, config.log_level)
    sesiones = fabrica or async_sessionmaker(
        create_async_engine(config.database_url, pool_pre_ping=True), expire_on_commit=False
    )
    relay = RelayOutbox(sesiones, Outbox, config.rabbitmq_url)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        await relay.conectar()
        tarea = asyncio.create_task(relay.ejecutar())
        yield
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
        await relay.cerrar()

    app = FastAPI(
        title="Servicio de proveedores",
        version="0.1.0",
        root_path=config.root_path,
        lifespan=ciclo_de_vida,
    )
    app.state.fabrica = sesiones
    app.state.validador = validador or validador_desde_jwks(
        config.oidc_issuer, config.oidc_audience, config.oidc_jwks_url
    )
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    async def verificar_postgres() -> None:
        async with sesiones() as sesion:
            await sesion.execute(text("SELECT 1"))

    async def verificar_rabbitmq() -> None:
        if not relay.conectado():
            raise ConnectionError("Sin conexión con RabbitMQ")

    app.include_router(
        crear_router_salud({"postgres": verificar_postgres, "rabbitmq": verificar_rabbitmq})
    )
    app.include_router(router)
    return app
```

- [ ] **Step 7: Ejecutar para verificar que pasan**

Run: `uv run pytest services/proveedores/tests/test_api.py -v`
Expected: `13 passed`.

- [ ] **Step 8: Suite completa, lint, tipos y cobertura**

Run: `uv run ruff format . ; uv run ruff check . ; uv run mypy ; uv run pytest --cov`
Expected: todo en verde; cobertura total ≥ 80 %.

- [ ] **Step 9: Commit**

```bash
git add services/proveedores
git commit -m "feat(proveedores): API de consulta e importacion de CSV"
```

---

### Task 11: Generador de datos sintéticos y carga masiva

**Files:**
- Create: `tools/generador/pyproject.toml`, `tools/generador/src/generador/__init__.py`, `catalogo.py`, `modelo.py`, `salida.py`, `__main__.py`
- Create: `services/proveedores/src/proveedores/importacion/cli.py`
- Modify: `pyproject.toml` (raíz)
- Test: `tools/generador/tests/test_generador.py`, `services/proveedores/tests/test_datos_generados.py` (integración)

**Interfaces:**
- Consumes: `importar`, `ORDEN_CARGA`, `ErrorImportacion` y `ResumenImportacion` (Tarea 9); fixture `fabrica`.
- Produces:
  - `generador.catalogo.SERVICIOS: tuple[ServicioBase, ...]`, con 40 servicios.
  - `generador.modelo.generar(semilla=42, n_proveedores=60, anios=5, hasta=date(2026, 9, 1)) -> DatosSinteticos`. Contiene `.proveedores: list[ProveedorSintetico]` (con las variables ocultas `calidad`, `nivel_precio`, `flexibilidad` y `estilo`) y `.contratos`, `.desempeno` y `.tipo_cambio`, cada uno como `list[dict[str, str]]`.
  - `generador.salida.escribir(datos, carpeta: Path) -> None`. Escribe `servicios.csv`, `proveedores.csv`, `tipo_cambio.csv`, `contratos.csv`, `desempeno.csv` y `verdad_oculta.json`.
  - CLI: `uv run python -m generador --semilla 42 --salida datos`.
  - `proveedores.importacion.cli.cargar_carpeta(fabrica, carpeta: Path) -> list[ResumenImportacion]`. También se ejecuta como CLI: `python -m proveedores.importacion.cli <carpeta>`.

- [ ] **Step 1: Crear el paquete y registrarlo en el workspace**

`tools/generador/pyproject.toml`:
```toml
[project]
name = "generador"
version = "0.1.0"
description = "Generador reproducible de datos sintéticos del ERP simulado"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

`tools/generador/src/generador/__init__.py`:
```python
"""Datos sintéticos realistas y reproducibles para la plataforma (sin marcas reales)."""
```

En `pyproject.toml` (raíz): agregar `"generador"` a `dependency-groups.dev`, `generador = { workspace = true }` a `[tool.uv.sources]`, y `"generador"` a `coverage.run.source` y a `mypy.packages`. Luego:

Run: `uv sync --all-packages`
Expected: sin errores.

- [ ] **Step 2: Escribir las pruebas del generador que fallan**

`tools/generador/tests/test_generador.py`:
```python
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from generador.__main__ import main
from generador.catalogo import SERVICIOS
from generador.modelo import generar
from generador.salida import escribir


def test_misma_semilla_produce_los_mismos_archivos(tmp_path: Path) -> None:
    escribir(generar(7, n_proveedores=10), tmp_path / "a")
    escribir(generar(7, n_proveedores=10), tmp_path / "b")
    escribir(generar(8, n_proveedores=10), tmp_path / "c")
    for nombre in ("proveedores.csv", "contratos.csv", "desempeno.csv", "tipo_cambio.csv"):
        assert (tmp_path / "a" / nombre).read_bytes() == (tmp_path / "b" / nombre).read_bytes()
    contratos_a = (tmp_path / "a" / "contratos.csv").read_bytes()
    assert contratos_a != (tmp_path / "c" / "contratos.csv").read_bytes()


def test_volumen_por_defecto() -> None:
    datos = generar()
    folios = {fila["folio"] for fila in datos.contratos}
    assert len(SERVICIOS) == 40
    assert len(datos.proveedores) == 60
    assert len({p.rfc for p in datos.proveedores}) == 60
    assert len({p.nombre for p in datos.proveedores}) == 60
    assert 1_500 <= len(folios) <= 2_500
    assert len(datos.desempeno) > 1_500


def test_integridad_referencial_y_reglas_de_negocio() -> None:
    datos = generar(3, n_proveedores=15)
    rfcs = {p.rfc for p in datos.proveedores}
    monedas = {s.codigo: s.moneda for s in SERVICIOS}
    for fila in datos.contratos:
        assert fila["rfc_proveedor"] in rfcs
        assert fila["moneda"] == monedas[fila["codigo_servicio"]]
        assert fila["fecha_fin"] > fila["fecha_inicio"]
        assert float(fila["precio_unitario"]) > 0
        assert float(fila["cantidad"]) > 0


def test_kpis_reflejan_la_calidad_oculta() -> None:
    datos = generar(11)
    satisfaccion: dict[str, list[float]] = defaultdict(list)
    for fila in datos.desempeno:
        satisfaccion[fila["rfc_proveedor"]].append(float(fila["satisfaccion"]))
    calidad = [p.calidad for p in datos.proveedores]
    promedio = [statistics.fmean(satisfaccion[p.rfc]) for p in datos.proveedores]
    assert statistics.correlation(calidad, promedio, method="ranked") > 0.8


def test_cli_escribe_los_seis_archivos(tmp_path: Path) -> None:
    main(["--semilla", "5", "--proveedores", "5", "--salida", str(tmp_path)])
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "contratos.csv",
        "desempeno.csv",
        "proveedores.csv",
        "servicios.csv",
        "tipo_cambio.csv",
        "verdad_oculta.json",
    ]
    verdad = json.loads((tmp_path / "verdad_oculta.json").read_text(encoding="utf-8"))
    assert len(verdad["proveedores"]) == 5
    with (tmp_path / "proveedores.csv").open(encoding="utf-8", newline="") as archivo:
        assert next(csv.reader(archivo)) == [
            "rfc", "nombre", "tamano", "categorias", "contacto_nombre", "contacto_email", "activo"
        ]
```

Run: `uv run pytest tools/generador -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'generador.catalogo'`.

- [ ] **Step 3: Catálogo de servicios**

`tools/generador/src/generador/catalogo.py`:
```python
"""Catálogo base de servicios de TI con precios de referencia. Nombres genéricos, sin marcas."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ServicioBase:
    codigo: str
    nombre: str
    categoria: str
    unidad: str
    moneda: str
    precio_base: Decimal


def _s(codigo: str, nombre: str, categoria: str, unidad: str, moneda: str, precio: str) -> ServicioBase:
    return ServicioBase(codigo, nombre, categoria, unidad, moneda, Decimal(precio))


SAAS, NUBE, CONS, SOP = "licencia_saas", "nube", "consultoria", "soporte"

SERVICIOS: tuple[ServicioBase, ...] = (
    _s("SAAS-OFI-BAS", "Suite de productividad en la nube - plan básico", SAAS, "usuario_mes", "USD", "7"),
    _s("SAAS-OFI-EMP", "Suite de productividad en la nube - plan empresarial", SAAS, "usuario_mes", "USD", "22"),
    _s("SAAS-OFI-PRE", "Suite de productividad en la nube - plan premium", SAAS, "usuario_mes", "USD", "38"),
    _s("SAAS-CRM-PRO", "CRM en la nube - plan profesional", SAAS, "usuario_mes", "USD", "65"),
    _s("SAAS-CRM-ENT", "CRM en la nube - plan corporativo", SAAS, "usuario_mes", "USD", "150"),
    _s("SAAS-ERP-USR", "ERP en la nube - usuario completo", SAAS, "usuario_mes", "USD", "120"),
    _s("SAAS-PRY-EST", "Gestión de proyectos - plan estándar", SAAS, "usuario_mes", "USD", "12"),
    _s("SAAS-VID-EMP", "Videoconferencia empresarial", SAAS, "usuario_mes", "USD", "15"),
    _s("SAAS-EDR-USR", "Protección de estaciones de trabajo (EDR)", SAAS, "usuario_mes", "USD", "9"),
    _s("SAAS-BI-USR", "Inteligencia de negocios - usuario analista", SAAS, "usuario_mes", "USD", "14"),
    _s("NUBE-CPU-GEN", "Cómputo de propósito general", NUBE, "vcpu_mes", "USD", "28"),
    _s("NUBE-CPU-MEM", "Cómputo optimizado para memoria", NUBE, "vcpu_mes", "USD", "38"),
    _s("NUBE-BD-ADM", "Base de datos administrada", NUBE, "vcpu_mes", "USD", "70"),
    _s("NUBE-OBJ-GB", "Almacenamiento de objetos", NUBE, "gb_mes", "USD", "0.023"),
    _s("NUBE-BLQ-SSD", "Almacenamiento en bloque SSD", NUBE, "gb_mes", "USD", "0.10"),
    _s("NUBE-RSP-GB", "Respaldo en la nube", NUBE, "gb_mes", "USD", "0.05"),
    _s("NUBE-CDN-GB", "Red de distribución de contenido - transferencia", NUBE, "gb_mes", "USD", "0.08"),
    _s("NUBE-K8S-CLU", "Clúster de Kubernetes administrado", NUBE, "mes", "USD", "73"),
    _s("NUBE-LB-STD", "Balanceador de carga", NUBE, "mes", "USD", "18"),
    _s("NUBE-VPN-S2S", "VPN sitio a sitio", NUBE, "mes", "USD", "36"),
    _s("CONS-DEV-JR", "Desarrollador(a) junior", CONS, "hora", "MXN", "450"),
    _s("CONS-DEV-SS", "Desarrollador(a) semi-senior", CONS, "hora", "MXN", "700"),
    _s("CONS-DEV-SR", "Desarrollador(a) senior", CONS, "hora", "MXN", "1000"),
    _s("CONS-ARQ-SW", "Arquitecto(a) de software", CONS, "hora", "MXN", "1500"),
    _s("CONS-DAT-SR", "Consultor(a) senior de datos", CONS, "hora", "MXN", "1250"),
    _s("CONS-CIE-DAT", "Científico(a) de datos", CONS, "hora", "MXN", "1300"),
    _s("CONS-SEG-ESP", "Especialista en ciberseguridad", CONS, "hora", "MXN", "1400"),
    _s("CONS-GER-PRY", "Gerente de proyecto", CONS, "hora", "MXN", "1200"),
    _s("CONS-QA-ANL", "Analista de calidad (QA)", CONS, "hora", "MXN", "550"),
    _s("CONS-ERP-FUN", "Consultor(a) funcional de ERP", CONS, "hora", "MXN", "1100"),
    _s("SOP-MESA-TK", "Mesa de ayuda - ticket", SOP, "ticket", "MXN", "180"),
    _s("SOP-N2-TK", "Soporte de segundo nivel - ticket", SOP, "ticket", "MXN", "420"),
    _s("SOP-SITIO-HR", "Soporte en sitio - hora", SOP, "hora", "MXN", "520"),
    _s("SOP-MON-SRV", "Monitoreo 24x7 por servidor", SOP, "mes", "MXN", "1500"),
    _s("SOP-ADM-SRV", "Administración de servidores", SOP, "mes", "MXN", "3200"),
    _s("SOP-DBA-MES", "Soporte de base de datos", SOP, "mes", "MXN", "6500"),
    _s("SOP-EQP-MES", "Mantenimiento de equipos de cómputo", SOP, "mes", "MXN", "250"),
    _s("SOP-RED-SIT", "Gestión de red por sitio", SOP, "mes", "MXN", "4800"),
    _s("SOP-APP-HR", "Soporte a aplicaciones - hora", SOP, "hora", "MXN", "650"),
    _s("SOP-POL-SAAS", "Póliza de soporte de plataformas SaaS", SOP, "mes", "MXN", "9000"),
)
```

- [ ] **Step 4: Modelo de generación**

`tools/generador/src/generador/modelo.py`:
```python
"""Genera proveedores con variables latentes ocultas, contratos, desempeño y tipo de cambio.

Las variables latentes (calidad, nivel de precio, flexibilidad, estilo) explican los
datos observados con ruido, de modo que después se puede medir si la plataforma
"acierta" sin que las vea nunca.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from generador.catalogo import SERVICIOS, ServicioBase

CATEGORIAS = ("licencia_saas", "nube", "consultoria", "soporte")
ESTILOS = ("duro", "flexible", "erratico", "manipulador")
TAMANOS = ("micro", "pequena", "mediana", "grande")
PREFIJOS = ("Nube", "Datos", "Soluciones", "Sistemas", "Tecno", "Red", "Código", "Servicios", "Infra", "Nodo")
SUFIJOS = ("Azteca", "del Norte", "Integrales", "del Pacífico", "Digitales", "Globales", "del Bajío", "Maya")
NOMBRES = ("Laura", "Jorge", "Ana", "Carlos", "María", "Luis", "Sofía", "Diego", "Fernanda", "Ricardo")
APELLIDOS = ("Méndez", "Ruiz", "Torres", "García", "Hernández", "López", "Martínez", "Ramírez", "Flores", "Castillo")
LETRAS_RFC = "ABCDEFGHJKLMNPRSTUVWXYZ"
INFLACION_ANUAL = 0.045
PLAZOS = {"licencia_saas": (12, 24, 36), "nube": (12, 24, 36), "soporte": (12, 24, 36), "consultoria": (3, 6, 9, 12)}
DESCUENTO_PLAZO = {3: 1.0, 6: 1.0, 9: 1.0, 12: 1.0, 24: 0.95, 36: 0.92}
RANGO_CANTIDAD = {
    "usuario_mes": (10, 800),
    "vcpu_mes": (4, 256),
    "gb_mes": (500, 50_000),
    "mes": (1, 20),
    "hora": (40, 1_500),
    "ticket": (100, 5_000),
}


@dataclass(frozen=True)
class ProveedorSintetico:
    rfc: str
    nombre: str
    tamano: str
    categorias: tuple[str, ...]
    contacto_nombre: str
    contacto_email: str
    activo: bool
    calidad: float  # oculta: 0 (mala) a 1 (excelente)
    nivel_precio: float  # oculta: 0.85 (barato) a 1.25 (caro)
    flexibilidad: float  # oculta: fracción que puede bajar desde su precio de lista
    estilo: str  # oculto: estilo del bot en el simulador de negociación


@dataclass
class DatosSinteticos:
    semilla: int
    servicios: tuple[ServicioBase, ...] = SERVICIOS
    proveedores: list[ProveedorSintetico] = field(default_factory=list)
    contratos: list[dict[str, str]] = field(default_factory=list)  # una fila por línea
    desempeno: list[dict[str, str]] = field(default_factory=list)
    tipo_cambio: list[dict[str, str]] = field(default_factory=list)


def _sumar_meses(fecha: date, meses: int) -> date:
    indice = fecha.year * 12 + fecha.month - 1 + meses
    return date(indice // 12, indice % 12 + 1, 1)


def _meses_entre(inicio: date, fin: date) -> int:
    return (fin.year - inicio.year) * 12 + fin.month - inicio.month


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def _dec(valor: float, decimales: int) -> str:
    return str(Decimal(str(valor)).quantize(Decimal(1).scaleb(-decimales), ROUND_HALF_UP))


def generar(
    semilla: int = 42, n_proveedores: int = 60, anios: int = 5, hasta: date = date(2026, 9, 1)
) -> DatosSinteticos:
    rng = random.Random(semilla)
    datos = DatosSinteticos(semilla)
    inicio = _sumar_meses(hasta, -12 * anios)
    datos.tipo_cambio = _tipo_cambio(rng, inicio, hasta)
    usados: set[str] = set()
    folio = 0
    for indice in range(1, n_proveedores + 1):
        proveedor = _proveedor(rng, indice, usados)
        datos.proveedores.append(proveedor)
        contratos = _contratos(rng, proveedor, inicio, hasta)
        for lineas in contratos:
            folio += 1
            datos.contratos.extend({"folio": f"C-{folio:06d}"} | linea for linea in lineas)
        primer_mes = date.fromisoformat(contratos[0][0]["fecha_inicio"])
        datos.desempeno.extend(_desempeno(rng, proveedor, primer_mes, hasta))
    return datos


def _rfc(rng: random.Random, usados: set[str]) -> str:
    while True:
        rfc = (
            "".join(rng.choice(LETRAS_RFC) for _ in range(3))
            + f"{rng.randint(0, 99):02d}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}"
            + "".join(rng.choice(LETRAS_RFC + "0123456789") for _ in range(3))
        )
        if rfc not in usados:
            usados.add(rfc)
            return rfc


def _proveedor(rng: random.Random, indice: int, usados: set[str]) -> ProveedorSintetico:
    calidad = rng.betavariate(2, 2)
    prefijo = PREFIJOS[(indice - 1) % len(PREFIJOS)]
    sufijo = SUFIJOS[(indice - 1) // len(PREFIJOS) % len(SUFIJOS)]
    repeticion = (indice - 1) // (len(PREFIJOS) * len(SUFIJOS))
    nombre = f"{prefijo} {sufijo}{f' {repeticion + 1}' if repeticion else ''} S.A. de C.V."
    return ProveedorSintetico(
        rfc=_rfc(rng, usados),
        nombre=nombre,
        tamano=rng.choice(TAMANOS),
        categorias=tuple(sorted(rng.sample(CATEGORIAS, 2 if rng.random() < 0.3 else 1))),
        contacto_nombre=f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}",
        contacto_email=f"ventas{indice:03d}@proveedor{indice:03d}.example",
        activo=rng.random() > 0.05,
        calidad=round(calidad, 4),
        nivel_precio=round(0.85 + 0.2 * calidad + rng.uniform(0, 0.2), 4),
        flexibilidad=round(rng.uniform(0.03, 0.20), 4),
        estilo=rng.choice(ESTILOS),
    )


def _cantidad(rng: random.Random, unidad: str) -> int:
    minimo, maximo = RANGO_CANTIDAD[unidad]
    return round(math.exp(rng.uniform(math.log(minimo), math.log(maximo))))


def _precio(
    rng: random.Random,
    servicio: ServicioBase,
    proveedor: ProveedorSintetico,
    cantidad: int,
    plazo: int,
    meses_desde_inicio: int,
) -> str:
    minimo = RANGO_CANTIDAD[servicio.unidad][0]
    descuento_volumen = max(0.85, 1 - 0.04 * math.log10(max(cantidad, minimo) / minimo))
    inflacion = (1 + INFLACION_ANUAL) ** (meses_desde_inicio / 12)
    valor = (
        float(servicio.precio_base)
        * proveedor.nivel_precio
        * descuento_volumen
        * DESCUENTO_PLAZO[plazo]
        * inflacion
        * rng.lognormvariate(0, 0.08)
    )
    return _dec(max(valor, 0.0001), 4)


def _contratos(
    rng: random.Random, proveedor: ProveedorSintetico, inicio: date, hasta: date
) -> list[list[dict[str, str]]]:
    ofrecidos = [s for s in SERVICIOS if s.categoria in proveedor.categorias]
    catalogo = rng.sample(ofrecidos, k=min(len(ofrecidos), rng.randint(3, 5)))
    total_meses = _meses_entre(inicio, hasta)
    arranques = sorted(rng.randrange(total_meses) for _ in range(rng.randint(20, 46)))
    contratos: list[list[dict[str, str]]] = []
    for numero, mes in enumerate(arranques):
        base = rng.choice(catalogo)
        misma_categoria = [s for s in catalogo if s.categoria == base.categoria]
        servicios = rng.sample(misma_categoria, k=rng.randint(1, min(4, len(misma_categoria))))
        plazo = rng.choice(PLAZOS[base.categoria])
        fecha_inicio = _sumar_meses(inicio, mes)
        continuo = base.categoria != "consultoria"
        cabecera = {
            "rfc_proveedor": proveedor.rfc,
            "tipo": "renovacion" if numero and rng.random() < 0.4 else "nuevo",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": (_sumar_meses(fecha_inicio, plazo) - timedelta(days=1)).isoformat(),
            "moneda": base.moneda,
            "plazo_pago_dias": str(rng.choice((15, 30, 45, 60))),
            "sla_disponibilidad": rng.choice(("99.00", "99.50", "99.90", "99.95")) if continuo else "",
            "tope_aumento_pct": rng.choice(("", "3.00", "5.00", "7.00", "10.00")) if continuo else "",
            "cuota_implementacion": (
                _dec(rng.uniform(500, 8_000), 4)
                if base.categoria == "licencia_saas" and rng.random() < 0.3
                else "0"
            ),
        }
        lineas = []
        for servicio in servicios:
            cantidad = _cantidad(rng, servicio.unidad)
            precio = _precio(rng, servicio, proveedor, cantidad, plazo, mes)
            lineas.append(
                cabecera
                | {
                    "codigo_servicio": servicio.codigo,
                    "cantidad": str(cantidad),
                    "precio_unitario": precio,
                }
            )
        contratos.append(lineas)
    return contratos


def _desempeno(
    rng: random.Random, proveedor: ProveedorSintetico, desde: date, hasta: date
) -> list[dict[str, str]]:
    q = proveedor.calidad
    filas = []
    mes = desde
    while mes <= hasta:
        filas.append(
            {
                "rfc_proveedor": proveedor.rfc,
                "periodo": mes.isoformat(),
                "sla_cumplimiento_pct": _dec(_limitar(95 + 5 * q + rng.gauss(0, 0.8), 80, 100), 2),
                "tiempo_resolucion_h": _dec(max(0.5, 24 - 18 * q + rng.gauss(0, 2.5)), 2),
                "incidentes_criticos": str(max(0, round(rng.gauss(3 * (1 - q), 1)))),
                "entregas_a_tiempo_pct": _dec(_limitar(80 + 20 * q + rng.gauss(0, 4), 0, 100), 2),
                "satisfaccion": _dec(_limitar(1.5 + 3.5 * q + rng.gauss(0, 0.4), 1, 5), 2),
            }
        )
        mes = _sumar_meses(mes, 1)
    return filas


def _tipo_cambio(rng: random.Random, inicio: date, hasta: date) -> list[dict[str, str]]:
    valor = 20.0
    filas = []
    mes = inicio
    while mes <= hasta:
        filas.append({"periodo": mes.isoformat(), "usd_mxn": _dec(valor, 4)})
        valor = _limitar(valor + rng.gauss(0, 0.35), 16.5, 22.5)
        mes = _sumar_meses(mes, 1)
    return filas
```

- [ ] **Step 5: Escritura de archivos y CLI**

`tools/generador/src/generador/salida.py`:
```python
"""Escribe los CSV con el formato de exportación del ERP y el archivo de verdad oculta."""

import csv
import json
from collections.abc import Iterable
from pathlib import Path

from generador.modelo import DatosSinteticos

COLUMNAS_CONTRATO = (
    "folio", "rfc_proveedor", "tipo", "fecha_inicio", "fecha_fin", "moneda",
    "plazo_pago_dias", "sla_disponibilidad", "tope_aumento_pct", "cuota_implementacion",
    "codigo_servicio", "cantidad", "precio_unitario",
)
COLUMNAS_DESEMPENO = (
    "rfc_proveedor", "periodo", "sla_cumplimiento_pct", "tiempo_resolucion_h",
    "incidentes_criticos", "entregas_a_tiempo_pct", "satisfaccion",
)


def _escribir(ruta: Path, columnas: tuple[str, ...], filas: Iterable[dict[str, str]]) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def escribir(datos: DatosSinteticos, carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    _escribir(
        carpeta / "servicios.csv",
        ("codigo", "nombre", "categoria", "unidad", "moneda"),
        (
            {"codigo": s.codigo, "nombre": s.nombre, "categoria": s.categoria,
             "unidad": s.unidad, "moneda": s.moneda}
            for s in datos.servicios
        ),
    )
    _escribir(
        carpeta / "proveedores.csv",
        ("rfc", "nombre", "tamano", "categorias", "contacto_nombre", "contacto_email", "activo"),
        (
            {"rfc": p.rfc, "nombre": p.nombre, "tamano": p.tamano,
             "categorias": "|".join(p.categorias), "contacto_nombre": p.contacto_nombre,
             "contacto_email": p.contacto_email, "activo": "true" if p.activo else "false"}
            for p in datos.proveedores
        ),
    )
    _escribir(carpeta / "tipo_cambio.csv", ("periodo", "usd_mxn"), datos.tipo_cambio)
    _escribir(carpeta / "contratos.csv", COLUMNAS_CONTRATO, datos.contratos)
    _escribir(carpeta / "desempeno.csv", COLUMNAS_DESEMPENO, datos.desempeno)
    verdad = {
        "semilla": datos.semilla,
        "advertencia": "Solo para validación. Nunca cargar este archivo a la plataforma.",
        "proveedores": [
            {"rfc": p.rfc, "calidad": p.calidad, "nivel_precio": p.nivel_precio,
             "flexibilidad": p.flexibilidad, "estilo": p.estilo}
            for p in datos.proveedores
        ],
    }
    (carpeta / "verdad_oculta.json").write_text(
        json.dumps(verdad, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

`tools/generador/src/generador/__main__.py`:
```python
import argparse
from pathlib import Path

from generador.modelo import generar
from generador.salida import escribir


def main(argumentos: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Genera datos sintéticos del ERP simulado")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--proveedores", type=int, default=60)
    parser.add_argument("--anios", type=int, default=5)
    parser.add_argument("--salida", type=Path, default=Path("datos"))
    args = parser.parse_args(argumentos)
    datos = generar(args.semilla, args.proveedores, args.anios)
    escribir(datos, args.salida)
    folios = len({fila["folio"] for fila in datos.contratos})
    print(
        f"{len(datos.proveedores)} proveedores, {folios} contratos "
        f"({len(datos.contratos)} líneas), {len(datos.desempeno)} registros de desempeño "
        f"-> {args.salida}"
    )


if __name__ == "__main__":
    main()
```

Run: `uv run pytest tools/generador -v`
Expected: `5 passed`.

- [ ] **Step 6: Escribir la prueba de integración de la carga masiva (falla)**

`services/proveedores/tests/test_datos_generados.py`:
```python
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from generador.modelo import generar
from generador.salida import escribir
from proveedores.importacion.aplicar import ORDEN_CARGA
from proveedores.importacion.cli import cargar_carpeta
from proveedores.modelos import Contrato, Outbox

pytestmark = pytest.mark.integracion


async def test_los_datos_generados_se_importan_sin_errores(
    fabrica: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    datos = generar(21, n_proveedores=8)
    escribir(datos, tmp_path)
    resumenes = await cargar_carpeta(fabrica, tmp_path)
    assert [r.entidad for r in resumenes] == list(ORDEN_CARGA)
    folios = len({fila["folio"] for fila in datos.contratos})
    async with fabrica() as sesion:
        contratos = await sesion.scalar(select(func.count()).select_from(Contrato))
        eventos = await sesion.scalar(
            select(func.count()).select_from(Outbox).where(Outbox.tipo == "contrato.registrado")
        )
    assert contratos == folios
    assert eventos == folios
```

Run: `uv run pytest services/proveedores/tests/test_datos_generados.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'proveedores.importacion.cli'`.

- [ ] **Step 7: Implementar la carga masiva**

`services/proveedores/src/proveedores/importacion/cli.py`:
```python
"""Carga masiva de una carpeta con los CSV del ERP.

Uso (dentro del contenedor): python -m proveedores.importacion.cli /datos
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from proveedores.config import Configuracion
from proveedores.importacion.aplicar import (
    ORDEN_CARGA,
    ErrorImportacion,
    ResumenImportacion,
    importar,
)


async def cargar_carpeta(
    fabrica: async_sessionmaker[AsyncSession], carpeta: Path
) -> list[ResumenImportacion]:
    """Importa en ORDEN_CARGA; cada archivo en su propia transacción."""
    resumenes = []
    for entidad in ORDEN_CARGA:
        contenido = (carpeta / f"{entidad}.csv").read_bytes()
        async with fabrica() as sesion, sesion.begin():
            resumenes.append(await importar(sesion, entidad, contenido))
    return resumenes


async def _principal(carpeta: Path) -> int:
    faltantes = [f"{e}.csv" for e in ORDEN_CARGA if not (carpeta / f"{e}.csv").is_file()]
    if faltantes:
        print(f"Faltan archivos en {carpeta}: {', '.join(faltantes)}", file=sys.stderr)
        return 1
    motor = create_async_engine(Configuracion().database_url)
    try:
        resumenes = await cargar_carpeta(async_sessionmaker(motor, expire_on_commit=False), carpeta)
    except ErrorImportacion as error:
        print(error.detalle, file=sys.stderr)
        for e in error.errores[:20]:
            print(f"  fila {e.fila}, {e.campo}: {e.mensaje}", file=sys.stderr)
        return 1
    finally:
        await motor.dispose()
    for r in resumenes:
        print(f"{r.entidad}: {r.registros} registros, {r.omitidos} omitidos, {r.eventos} eventos")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python -m proveedores.importacion.cli <carpeta>")
    sys.exit(asyncio.run(_principal(Path(sys.argv[1]))))
```

- [ ] **Step 8: Ejecutar para verificar que pasa y generar los datos locales**

Run: `uv run pytest services/proveedores/tests/test_datos_generados.py -v`
Expected: `1 passed`.

Run: `uv run python -m generador --salida datos`
Expected: una línea como `60 proveedores, ~2000 contratos (… líneas), … registros de desempeño -> datos`. La carpeta `datos/` está en `.gitignore`.

- [ ] **Step 9: Suite completa, lint y tipos**

Run: `uv run ruff format . ; uv run ruff check . ; uv run mypy ; uv run pytest --cov`
Expected: todo en verde; cobertura ≥ 80 %.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml uv.lock tools/generador services/proveedores/src/proveedores/importacion/cli.py services/proveedores/tests/test_datos_generados.py
git commit -m "feat(generador): datos sinteticos reproducibles y carga masiva"
```

---

### Task 12: Infraestructura con Docker Compose (backend)

**Files:**
- Create: `infra/docker-compose.yml`, `infra/.env.example`, `infra/postgres/init.sh`, `infra/keycloak/realm-plataforma.json`
- Create: `services/proveedores/Dockerfile`

**Interfaces:**
- Consumes: `proveedores.main:crear_app` y `alembic.ini` (Tareas 7 y 10); `proveedores.importacion.cli` (Tarea 11); carpeta `datos/` generada en la Tarea 11.
- Produces:
  - Servicios de Compose: `postgres`, `rabbitmq`, `keycloak` y `proveedores`. El gateway se agrega en la Tarea 13.
  - Realm `plataforma`:
    - Roles `admin`, `comprador` y `aprobador`.
    - Cliente público `web` (PKCE S256) y cliente `pruebas-humo` (solo desarrollo; *direct access grants*).
    - Audiencia `plataforma-api` en el token de acceso.
    - Usuarios de desarrollo `admin1`, `comprador1` y `aprobador1`. Admin y aprobador deben configurar OTP en su primer inicio de sesión.
  - Emisor de tokens: `http://localhost:8080/auth/realms/plataforma`. Este valor solo es alcanzable a través del gateway (Tarea 13).

- [ ] **Step 1: Variables de entorno de ejemplo**

`infra/.env.example`:
```
# Copie este archivo como infra/.env y cambie los valores.
# Use solo letras, números y guiones: los valores se insertan en URLs de conexión.
POSTGRES_PASSWORD=cambiar-postgres
PROVEEDORES_DB_PASSWORD=cambiar-proveedores
KEYCLOAK_DB_PASSWORD=cambiar-keycloak
KEYCLOAK_ADMIN_PASSWORD=cambiar-admin-keycloak
RABBITMQ_PASSWORD=cambiar-rabbitmq
```

- [ ] **Step 2: Una base de datos y un usuario por servicio**

`infra/postgres/init.sh`:
```bash
#!/bin/bash
# Crea una base de datos y un usuario por servicio. Solo corre con el volumen vacío.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<EOSQL
CREATE USER proveedores WITH PASSWORD '${PROVEEDORES_DB_PASSWORD}';
CREATE DATABASE proveedores_db OWNER proveedores;
REVOKE CONNECT ON DATABASE proveedores_db FROM PUBLIC;

CREATE USER keycloak WITH PASSWORD '${KEYCLOAK_DB_PASSWORD}';
CREATE DATABASE keycloak_db OWNER keycloak;
REVOKE CONNECT ON DATABASE keycloak_db FROM PUBLIC;
EOSQL
```

- [ ] **Step 3: Realm de Keycloak para desarrollo**

`infra/keycloak/realm-plataforma.json` (credenciales **solo de desarrollo**; el realm de producción se documenta en el manual técnico):
```json
{
  "realm": "plataforma",
  "enabled": true,
  "displayName": "Plataforma de Negociación",
  "internationalizationEnabled": true,
  "supportedLocales": ["es"],
  "defaultLocale": "es",
  "bruteForceProtected": true,
  "passwordPolicy": "length(12) and notUsername",
  "accessTokenLifespan": 300,
  "ssoSessionIdleTimeout": 1800,
  "revokeRefreshToken": true,
  "refreshTokenMaxReuse": 0,
  "roles": {
    "realm": [
      { "name": "admin", "description": "Configura catálogos, pesos, umbrales, usuarios e importaciones" },
      { "name": "comprador", "description": "Crea y supervisa eventos de negociación" },
      { "name": "aprobador", "description": "Aprueba adjudicaciones" }
    ]
  },
  "clients": [
    {
      "clientId": "web",
      "name": "Plataforma web",
      "enabled": true,
      "publicClient": true,
      "standardFlowEnabled": true,
      "implicitFlowEnabled": false,
      "directAccessGrantsEnabled": false,
      "redirectUris": ["http://localhost:5173/*", "http://localhost:8080/*"],
      "webOrigins": ["http://localhost:5173", "http://localhost:8080"],
      "attributes": {
        "pkce.code.challenge.method": "S256",
        "post.logout.redirect.uris": "+"
      },
      "protocolMappers": [
        {
          "name": "audiencia-plataforma-api",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-audience-mapper",
          "config": {
            "included.custom.audience": "plataforma-api",
            "access.token.claim": "true",
            "id.token.claim": "false",
            "introspection.token.claim": "true"
          }
        }
      ]
    },
    {
      "clientId": "pruebas-humo",
      "name": "Pruebas de humo (solo desarrollo)",
      "enabled": true,
      "publicClient": true,
      "standardFlowEnabled": false,
      "directAccessGrantsEnabled": true,
      "protocolMappers": [
        {
          "name": "audiencia-plataforma-api",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-audience-mapper",
          "config": {
            "included.custom.audience": "plataforma-api",
            "access.token.claim": "true",
            "id.token.claim": "false",
            "introspection.token.claim": "true"
          }
        }
      ]
    }
  ],
  "users": [
    {
      "username": "admin1",
      "enabled": true,
      "email": "admin1@plataforma.example",
      "emailVerified": true,
      "firstName": "Andrea",
      "lastName": "Administradora",
      "credentials": [{ "type": "password", "value": "Admin-Dev-2026!", "temporary": false }],
      "realmRoles": ["admin"],
      "requiredActions": ["CONFIGURE_TOTP"]
    },
    {
      "username": "comprador1",
      "enabled": true,
      "email": "comprador1@plataforma.example",
      "emailVerified": true,
      "firstName": "Carlos",
      "lastName": "Comprador",
      "credentials": [{ "type": "password", "value": "Comprador-Dev-2026!", "temporary": false }],
      "realmRoles": ["comprador"]
    },
    {
      "username": "aprobador1",
      "enabled": true,
      "email": "aprobador1@plataforma.example",
      "emailVerified": true,
      "firstName": "Alicia",
      "lastName": "Aprobadora",
      "credentials": [{ "type": "password", "value": "Aprobador-Dev-2026!", "temporary": false }],
      "realmRoles": ["aprobador"],
      "requiredActions": ["CONFIGURE_TOTP"]
    }
  ]
}
```

> No se declaran `clientScopes` a propósito: si el JSON los incluye, Keycloak deja de crear los *scopes* por defecto (`basic`, `roles`, `web-origins`…). Sin ellos desaparecen los claims `sub` y `realm_access`.

- [ ] **Step 4: Imagen del servicio de proveedores**

`services/proveedores/Dockerfile`:
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
    uv sync --locked --no-dev --package proveedores

ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 servicio
USER servicio
EXPOSE 8000

# ponytail: migra al arrancar; con varias réplicas, mover a un job de migración previo al despliegue.
CMD ["sh", "-c", "alembic -c services/proveedores/alembic.ini upgrade head && exec uvicorn proveedores.main:crear_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
```

- [ ] **Step 5: Docker Compose**

`infra/docker-compose.yml`:
```yaml
name: plataforma

services:
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Defina POSTGRES_PASSWORD en infra/.env}
      PROVEEDORES_DB_PASSWORD: ${PROVEEDORES_DB_PASSWORD:?Defina PROVEEDORES_DB_PASSWORD en infra/.env}
      KEYCLOAK_DB_PASSWORD: ${KEYCLOAK_DB_PASSWORD:?Defina KEYCLOAK_DB_PASSWORD en infra/.env}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./postgres/init.sh:/docker-entrypoint-initdb.d/10-bases.sh:ro
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 20

  rabbitmq:
    image: rabbitmq:4.1-management-alpine
    environment:
      RABBITMQ_DEFAULT_USER: plataforma
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:?Defina RABBITMQ_PASSWORD en infra/.env}
    volumes:
      - rabbitdata:/var/lib/rabbitmq
    ports:
      - "127.0.0.1:15672:15672"
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 12

  keycloak:
    image: quay.io/keycloak/keycloak:26.5
    command: ["start-dev", "--import-realm"]
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: admin
      KC_BOOTSTRAP_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD:?Defina KEYCLOAK_ADMIN_PASSWORD en infra/.env}
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://postgres:5432/keycloak_db
      KC_DB_USERNAME: keycloak
      KC_DB_PASSWORD: ${KEYCLOAK_DB_PASSWORD}
      KC_HTTP_RELATIVE_PATH: /auth
      KC_HOSTNAME: http://localhost:8080/auth
      KC_HOSTNAME_BACKCHANNEL_DYNAMIC: "true"
      KC_PROXY_HEADERS: xforwarded
    volumes:
      - ./keycloak:/opt/keycloak/data/import:ro
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      # La imagen no trae curl: se consulta el documento de descubrimiento del realm con bash.
      test:
        - CMD-SHELL
        - >-
          exec 3<>/dev/tcp/127.0.0.1/8080 &&
          printf 'GET /auth/realms/plataforma/.well-known/openid-configuration HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' >&3 &&
          grep -q issuer <&3
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 30s

  proveedores:
    build:
      context: ..
      dockerfile: services/proveedores/Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://proveedores:${PROVEEDORES_DB_PASSWORD}@postgres:5432/proveedores_db
      RABBITMQ_URL: amqp://plataforma:${RABBITMQ_PASSWORD}@rabbitmq:5672/
      OIDC_ISSUER: http://localhost:8080/auth/realms/plataforma
      OIDC_JWKS_URL: http://keycloak:8080/auth/realms/plataforma/protocol/openid-connect/certs
      ROOT_PATH: /api/proveedores
    volumes:
      - ../datos:/datos:ro
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
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

volumes:
  pgdata:
  rabbitdata:
```

- [ ] **Step 6: Levantar la infraestructura**

Run: `cp infra/.env.example infra/.env`
Run: `docker compose -f infra/docker-compose.yml up -d --build`
Run: `docker compose -f infra/docker-compose.yml ps`
Expected: tras ~1–2 minutos, los cuatro servicios en estado `healthy`. Keycloak es el más lento. Si alguno queda `unhealthy`, revisar con `docker compose -f infra/docker-compose.yml logs <servicio>`.

- [ ] **Step 7: Cargar los datos sintéticos y verificar el outbox**

Run: `docker compose -f infra/docker-compose.yml exec proveedores python -m proveedores.importacion.cli /datos`
Expected: cinco líneas (`servicios`, `proveedores`, `tipo_cambio`, `contratos` y `desempeno`) con sus conteos.

Run: `docker compose -f infra/docker-compose.yml exec postgres psql -U postgres -d proveedores_db -c "SELECT count(*) AS total, count(*) FILTER (WHERE publicado_en IS NULL) AS pendientes FROM outbox;"`
Expected: después de unos segundos, `pendientes = 0`. Esto indica que el relay publicó todo en RabbitMQ. En `http://localhost:15672` → *Exchanges* → `eventos` se ve la actividad de publicación (usuario `plataforma`, contraseña de `infra/.env`).

- [ ] **Step 8: Verificar el aislamiento entre bases de datos**

Run: `docker compose -f infra/docker-compose.yml exec postgres psql -U proveedores -d keycloak_db -c "SELECT 1;"`
Expected: `FATAL: permission denied for database "keycloak_db"`. Así se cumple la regla "ningún servicio lee la base de datos de otro".

- [ ] **Step 9: Commit**

```bash
git add infra services/proveedores/Dockerfile
git commit -m "build: docker compose con postgres, rabbitmq, keycloak y proveedores"
```

---

### Task 13: SPA base con inicio de sesión OIDC y gateway Nginx

**Files:**
- Create (andamiaje): `web/` con `npx shadcn@latest init`, más los componentes `button`, `card`, `input`, `table`, `badge` y `alert`
- Create: `web/src/auth.ts`, `web/src/api.ts`, `web/src/tipos.ts`, `web/src/rutas.tsx`, `web/src/setupPruebas.ts`
- Create: `web/src/componentes/Layout.tsx`, `web/src/paginas/Inicio.tsx`, `web/src/paginas/NoEncontrado.tsx`
- Replace: `web/src/main.tsx`, `web/vite.config.ts`. Delete: `web/src/App.tsx` (y su CSS si el andamiaje lo creó)
- Create: `infra/nginx/nginx.conf`, `web/Dockerfile`, `infra/smoke_test.py`
- Modify: `infra/docker-compose.yml` (servicio `gateway`)
- Test: `web/src/auth.test.ts`

**Interfaces:**
- Consumes: realm y clientes de la Tarea 12; API de la Tarea 10.
- Produces:
  - En `@/auth`:
    - `configuracionOidc`.
    - `type Rol = "admin" | "comprador" | "aprobador"`.
    - `NOMBRES_ROL: Record<Rol, string>`.
    - `rolesDeToken(token?: string): Rol[]`.
    - Hooks `useToken(): string | undefined` y `useRoles(): Rol[]`.
  - En `@/api`:
    - `pedir<T>(ruta: string, token: string | undefined, init?: RequestInit): Promise<T>`. Antepone `/api` a la ruta.
    - `class ErrorApi`, con `estado`, `titulo`, `message` (el detalle) y `errores: ErrorFila[]`.
    - `type ErrorFila`.
  - En `@/tipos`: tipos de la API, `NOMBRES_CATEGORIA`, `formatoMoneda(valor, moneda)` y `formatoFecha(iso)`.
  - `@/rutas` exporta `router`. `Layout` es la ruta raíz; la Tarea 14 le agrega hijos.
  - Gateway en `http://localhost:8080`:
    - `/` → SPA.
    - `/api/proveedores/` → servicio `proveedores`.
    - `/auth/` → Keycloak.

- [ ] **Step 1: Andamiaje de la SPA con Vite + Tailwind + shadcn/ui**

Run (desde la raíz): `npx shadcn@latest init -t vite -n web -b radix --no-monorepo`
Expected: crea `web/` con Vite, React, TypeScript, Tailwind, `components.json` y el alias `@` → `src`. Si el CLI hace alguna pregunta, aceptar la opción por defecto.

Run: `npx shadcn@latest add button card input table badge alert -c web -y`
Expected: crea `web/src/components/ui/{button,card,input,table,badge,alert}.tsx`.

Run (en `web/`):
```bash
npm install react-router @tanstack/react-query react-oidc-context oidc-client-ts
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
npm pkg set scripts.test="vitest"
```

- [ ] **Step 2: Configurar Vite (proxy de desarrollo y pruebas)**

`web/vite.config.ts` (reemplazar completo):
```ts
/// <reference types="vitest/config" />
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    // En desarrollo la API se consume a través del gateway (mismo camino que en producción).
    proxy: { "/api": "http://localhost:8080" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupPruebas.ts"],
  },
})
```

`web/src/setupPruebas.ts`:
```ts
import "@testing-library/jest-dom/vitest"
```

- [ ] **Step 3: Escribir la prueba que falla de `rolesDeToken`**

`web/src/auth.test.ts`:
```ts
import { describe, expect, it } from "vitest"
import { rolesDeToken } from "@/auth"

function tokenCon(carga: object): string {
  const base64url = btoa(JSON.stringify(carga))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "")
  return `cabecera.${base64url}.firma`
}

describe("rolesDeToken", () => {
  it("devuelve solo los roles de la plataforma", () => {
    const token = tokenCon({ realm_access: { roles: ["comprador", "offline_access", "admin"] } })
    expect(rolesDeToken(token)).toEqual(["comprador", "admin"])
  })

  it("tolera tokens ausentes o mal formados", () => {
    expect(rolesDeToken(undefined)).toEqual([])
    expect(rolesDeToken("no-es-un-jwt")).toEqual([])
    expect(rolesDeToken("a.%%%.c")).toEqual([])
  })

  it("tolera tokens sin realm_access", () => {
    expect(rolesDeToken(tokenCon({ sub: "u-1" }))).toEqual([])
  })
})
```

Run (en `web/`): `npm test -- --run`
Expected: FAIL: no se puede resolver `@/auth`.

- [ ] **Step 4: Autenticación, cliente de API y tipos**

`web/src/auth.ts`:
```ts
import { useAuth, type AuthProviderProps } from "react-oidc-context"

export type Rol = "admin" | "comprador" | "aprobador"

const ROLES: readonly Rol[] = ["admin", "comprador", "aprobador"]

export const NOMBRES_ROL: Record<Rol, string> = {
  admin: "Administración",
  comprador: "Compras",
  aprobador: "Aprobación",
}

export const configuracionOidc: AuthProviderProps = {
  authority:
    import.meta.env.VITE_OIDC_AUTHORITY ?? "http://localhost:8080/auth/realms/plataforma",
  client_id: "web",
  redirect_uri: `${window.location.origin}/`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  automaticSilentRenew: true,
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname)
  },
}

/** Lee los roles del token solo para decidir qué mostrar; la API vuelve a validarlos. */
export function rolesDeToken(token: string | undefined): Rol[] {
  const partes = token?.split(".") ?? []
  if (partes.length !== 3) return []
  try {
    const base64 = partes[1].replace(/-/g, "+").replace(/_/g, "/")
    const carga = JSON.parse(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "=")))
    const roles: unknown = carga?.realm_access?.roles
    // Conserva el orden del token y descarta roles ajenos a la plataforma (p. ej. offline_access).
    return Array.isArray(roles) ? roles.filter((r): r is Rol => ROLES.includes(r as Rol)) : []
  } catch {
    return []
  }
}

export function useToken(): string | undefined {
  return useAuth().user?.access_token
}

export function useRoles(): Rol[] {
  return rolesDeToken(useToken())
}
```

`web/src/api.ts`:
```ts
export type ErrorFila = { fila: number; campo: string; mensaje: string }

/** Error de la API con los datos de Problem Details (RFC 9457). */
export class ErrorApi extends Error {
  readonly estado: number
  readonly titulo: string
  readonly errores: ErrorFila[]

  constructor(estado: number, titulo: string, detalle: string, errores: ErrorFila[] = []) {
    super(detalle)
    this.estado = estado
    this.titulo = titulo
    this.errores = errores
  }
}

export async function pedir<T>(
  ruta: string,
  token: string | undefined,
  init: RequestInit = {},
): Promise<T> {
  const cabeceras = new Headers(init.headers)
  if (token) cabeceras.set("Authorization", `Bearer ${token}`)
  const respuesta = await fetch(`/api${ruta}`, { ...init, headers: cabeceras })
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}))
    throw new ErrorApi(
      respuesta.status,
      cuerpo.title ?? "Error",
      cuerpo.detail ?? respuesta.statusText,
      cuerpo.errores ?? [],
    )
  }
  return (await respuesta.json()) as T
}
```

`web/src/tipos.ts`:
```ts
export type Categoria = "licencia_saas" | "nube" | "consultoria" | "soporte"

export const NOMBRES_CATEGORIA: Record<Categoria, string> = {
  licencia_saas: "Licencias SaaS",
  nube: "Nube",
  consultoria: "Consultoría",
  soporte: "Soporte",
}

export type ProveedorResumen = {
  id: string
  rfc: string
  nombre: string
  tamano: string
  categorias: Categoria[]
  activo: boolean
}

export type PaginaProveedores = { total: number; elementos: ProveedorResumen[] }

export type ProveedorDetalle = ProveedorResumen & {
  contacto_nombre: string
  contacto_email: string
  contratos_vigentes: number
}

export type LineaContrato = {
  codigo_servicio: string
  nombre_servicio: string
  unidad: string
  cantidad: string
  precio_unitario: string
}

export type Contrato = {
  id: string
  folio: string
  tipo: "nuevo" | "renovacion"
  fecha_inicio: string
  fecha_fin: string
  moneda: "MXN" | "USD"
  plazo_pago_dias: number
  sla_disponibilidad: string | null
  tope_aumento_pct: string | null
  cuota_implementacion: string
  lineas: LineaContrato[]
}

export type Desempeno = {
  periodo: string
  sla_cumplimiento_pct: string
  tiempo_resolucion_h: string
  incidentes_criticos: number
  entregas_a_tiempo_pct: string
  satisfaccion: string
}

export type ResumenImportacion = {
  entidad: string
  filas: number
  registros: number
  omitidos: number
  eventos: number
}

/** Solo para mostrar: los montos llegan como texto decimal y no se operan en el navegador. */
export function formatoMoneda(valor: string, moneda: string): string {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: moneda,
    maximumFractionDigits: 4,
  }).format(Number(valor))
}

export function formatoFecha(iso: string): string {
  const [anio, mes, dia] = iso.split("-").map(Number)
  return new Date(anio, mes - 1, dia).toLocaleDateString("es-MX", { dateStyle: "medium" })
}
```

Run (en `web/`): `npm test -- --run`
Expected: `3 passed`.

- [ ] **Step 5: Layout, páginas base, rutas y arranque**

`web/src/componentes/Layout.tsx`:
```tsx
import { useEffect } from "react"
import { NavLink, Outlet } from "react-router"
import { hasAuthParams, useAuth } from "react-oidc-context"
import { Button } from "@/components/ui/button"

function claseEnlace({ isActive }: { isActive: boolean }): string {
  return isActive ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
}

export function Layout() {
  const auth = useAuth()

  useEffect(() => {
    const puedeRedirigir =
      !hasAuthParams() && !auth.isAuthenticated && !auth.activeNavigator && !auth.isLoading
    if (puedeRedirigir && !auth.error) void auth.signinRedirect()
  }, [auth])

  if (auth.error) {
    return (
      <p role="alert" className="p-6">
        No se pudo iniciar sesión: {auth.error.message}
      </p>
    )
  }
  if (!auth.isAuthenticated) return <p className="p-6">Redirigiendo al inicio de sesión…</p>

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <nav aria-label="Principal" className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <span className="font-semibold">Plataforma de Negociación</span>
          <NavLink to="/" end className={claseEnlace}>
            Inicio
          </NavLink>
          <span className="ml-auto text-sm text-muted-foreground">
            {auth.user?.profile.preferred_username}
          </span>
          <Button variant="outline" size="sm" onClick={() => void auth.signoutRedirect()}>
            Cerrar sesión
          </Button>
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
```

`web/src/paginas/Inicio.tsx`:
```tsx
import { useAuth } from "react-oidc-context"
import { NOMBRES_ROL, useRoles } from "@/auth"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function Inicio() {
  const auth = useAuth()
  const roles = useRoles()
  const nombre = auth.user?.profile.given_name ?? auth.user?.profile.preferred_username
  return (
    <Card>
      <CardHeader>
        <CardTitle>Hola, {nombre}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">Tus roles:</span>
        {roles.map((rol) => (
          <Badge key={rol}>{NOMBRES_ROL[rol]}</Badge>
        ))}
      </CardContent>
    </Card>
  )
}
```

`web/src/paginas/NoEncontrado.tsx`:
```tsx
import { Link } from "react-router"

export function NoEncontrado() {
  return (
    <section className="space-y-2">
      <h1 className="text-2xl font-semibold">Página no encontrada</h1>
      <Link to="/" className="underline">
        Volver al inicio
      </Link>
    </section>
  )
}
```

`web/src/rutas.tsx`:
```tsx
import { createBrowserRouter } from "react-router"
import { Layout } from "@/componentes/Layout"
import { Inicio } from "@/paginas/Inicio"
import { NoEncontrado } from "@/paginas/NoEncontrado"

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Inicio },
      { path: "*", Component: NoEncontrado },
    ],
  },
])
```

`web/src/main.tsx` (reemplazar completo):
```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthProvider } from "react-oidc-context"
import { RouterProvider } from "react-router/dom"
import { configuracionOidc } from "@/auth"
import { router } from "@/rutas"
import "./index.css"

const clienteConsultas = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider {...configuracionOidc}>
      <QueryClientProvider client={clienteConsultas}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </AuthProvider>
  </StrictMode>,
)
```

Borrar `web/src/App.tsx` y `web/src/App.css` si existen. En `web/index.html`, cambiar `<html lang="en">` por `<html lang="es">` y el `<title>` por `Plataforma de Negociación`.

Run (en `web/`): `npm run lint ; npm run build ; npm test -- --run`
Expected: lint sin errores (se aceptan advertencias de `react-refresh`), build correcto, `3 passed`.

- [ ] **Step 6: Gateway Nginx**

`infra/nginx/nginx.conf`:
```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=20r/s;

# Conserva el X-Request-ID del cliente o genera uno nuevo.
map $http_x_request_id $id_peticion {
    ""      $request_id;
    default $http_x_request_id;
}

server {
    listen 8080;
    server_tokens off;
    client_max_body_size 10m;

    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_set_header X-Request-ID $id_peticion;

    location /api/proveedores/ {
        limit_req zone=api burst=40 nodelay;
        limit_req_status 429;
        proxy_pass http://proveedores:8000/;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Cache-Control "no-store" always;
    }

    # Keycloak envía sus propias cabeceras de seguridad para sus páginas.
    location /auth/ {
        proxy_pass http://keycloak:8080;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    location / {
        root /usr/share/nginx/html;
        try_files $uri /index.html;
        add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "no-referrer" always;
        add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    }
}
```

`web/Dockerfile`:
```dockerfile
# Contexto: raíz del repositorio. Construye la SPA y la sirve desde el gateway Nginx.
FROM node:24-alpine AS construccion
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY infra/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=construccion /web/dist /usr/share/nginx/html
EXPOSE 8080
```

En `infra/docker-compose.yml`, agregar dentro de `services:` (después de `proveedores`):
```yaml
  gateway:
    build:
      context: ..
      dockerfile: web/Dockerfile
    ports:
      - "127.0.0.1:8080:8080"
    depends_on:
      proveedores:
        condition: service_healthy
      keycloak:
        condition: service_healthy
```

- [ ] **Step 7: Prueba de humo del stack**

`infra/smoke_test.py`:
```python
"""Prueba de humo contra el stack de Docker Compose: uv run python infra/smoke_test.py"""

import json
import sys
from pathlib import Path

import httpx

BASE = "http://localhost:8080"
REALM = Path(__file__).parent / "keycloak" / "realm-plataforma.json"


def verificar(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise SystemExit(f"FALLA: {mensaje}")


def contrasena_de_desarrollo(usuario: str) -> str:
    realm = json.loads(REALM.read_text(encoding="utf-8"))
    [datos] = [u for u in realm["users"] if u["username"] == usuario]
    return str(datos["credentials"][0]["value"])


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=10) as cliente:
        spa = cliente.get("/")
        verificar(spa.status_code == 200 and 'id="root"' in spa.text, "el gateway no sirve la SPA")
        verificar(
            "frame-ancestors 'none'" in spa.headers.get("content-security-policy", ""),
            "falta la cabecera CSP",
        )
        sin_token = cliente.get("/api/proveedores/proveedores")
        verificar(sin_token.status_code == 401, f"sin token se esperaba 401: {sin_token.text}")

        token = cliente.post(
            "/auth/realms/plataforma/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "pruebas-humo",
                "username": "comprador1",
                "password": contrasena_de_desarrollo("comprador1"),
            },
        )
        verificar(token.status_code == 200, f"Keycloak no emitió token: {token.text}")
        cabeceras = {"Authorization": f"Bearer {token.json()['access_token']}"}

        lista = cliente.get("/api/proveedores/proveedores", headers=cabeceras)
        verificar(lista.status_code == 200, f"listar proveedores falló: {lista.text}")
        verificar(bool(lista.headers.get("x-request-id")), "falta X-Request-ID en la respuesta")

        importar = cliente.post(
            "/api/proveedores/importaciones/servicios",
            headers=cabeceras,
            files={"archivo": ("s.csv", b"codigo,nombre,categoria,unidad,moneda\n", "text/csv")},
        )
        verificar(importar.status_code == 403, f"un comprador no debe importar: {importar.text}")

        openapi = cliente.get("/api/proveedores/openapi.json")
        verificar(openapi.status_code == 200, "no se publica el contrato OpenAPI")

    print(f"OK: SPA, Keycloak y proveedores responden ({lista.json()['total']} proveedores).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: Levantar el stack completo y verificar**

Run: `docker compose -f infra/docker-compose.yml up -d --build`
Run: `uv run python infra/smoke_test.py`
Expected: `OK: SPA, Keycloak y proveedores responden (60 proveedores).`

Verificación manual en el navegador:
1. Abrir `http://localhost:8080`. Debe redirigir al inicio de sesión de Keycloak, en español.
2. Entrar como `comprador1` (contraseña en `infra/keycloak/realm-plataforma.json`). Debe mostrarse "Hola, Carlos" con la insignia "Compras".
3. Cerrar sesión y entrar como `admin1`. Keycloak pide configurar OTP (con Google Authenticator, Microsoft Authenticator o similar); después se ve la insignia "Administración".
4. Desarrollo con recarga en caliente: `npm run dev` en `web/` y abrir `http://localhost:5173`. Mismo flujo; la API pasa por el proxy de Vite hacia el gateway.

- [ ] **Step 9: Commit**

```bash
git add web infra/nginx infra/smoke_test.py infra/docker-compose.yml
git commit -m "feat(web): SPA con login OIDC y gateway Nginx"
```

---

### Task 14: Páginas de proveedores e importación

**Files:**
- Create: `web/src/paginas/Proveedores.tsx`, `web/src/paginas/ProveedorDetalle.tsx`, `web/src/paginas/Importacion.tsx`
- Modify: `web/src/tipos.ts` (agregar `NOMBRES_TAMANO`), `web/src/rutas.tsx`, `web/src/componentes/Layout.tsx`
- Test: `web/src/paginas/Importacion.test.tsx`

**Interfaces:**
- Consumes: `pedir`, `ErrorApi`, `useToken`, `useRoles`, los tipos de `@/tipos` (Tarea 13) y las rutas de la API (Tarea 10).
- Produces:
  - Rutas `/proveedores`, `/proveedores/:id` e `/importacion`. Esta última solo aparece en el menú para `admin`; la API la protege de todos modos.
  - Claves de TanStack Query `["proveedores", …]` y `["proveedor", id, …]`. Una importación exitosa invalida `["proveedores"]`.

- [ ] **Step 1: Escribir la prueba que falla de la página de importación**

`web/src/paginas/Importacion.test.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Importacion } from "@/paginas/Importacion"

vi.mock("react-oidc-context", () => {
  const carga = btoa(JSON.stringify({ realm_access: { roles: ["admin"] } }))
  return { useAuth: () => ({ user: { access_token: `cabecera.${carga}.firma` } }) }
})

function respuestaJson(cuerpo: object, estado: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { "Content-Type": "application/json" },
  })
}

function renderizar() {
  const cliente = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <Importacion />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Importacion", () => {
  it("muestra los errores por fila que devuelve la API", async () => {
    const simulado = vi.fn().mockResolvedValue(
      respuestaJson(
        {
          title: "Archivo con errores",
          detail: "Se encontraron 1 error(es); no se importó ninguna fila.",
          errores: [{ fila: 2, campo: "contacto_email", mensaje: "Formato inválido" }],
        },
        422,
      ),
    )
    vi.stubGlobal("fetch", simulado)
    renderizar()

    await userEvent.selectOptions(screen.getByLabelText("Tipo de archivo"), "proveedores")
    await userEvent.upload(
      screen.getByLabelText("Archivo CSV"),
      new File(["rfc\n"], "proveedores.csv", { type: "text/csv" }),
    )
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    expect(await screen.findByText("Formato inválido")).toBeInTheDocument()
    expect(screen.getByText("contacto_email")).toBeInTheDocument()
    const [url, init] = simulado.mock.calls[0]
    expect(url).toBe("/api/proveedores/importaciones/proveedores")
    expect(init.method).toBe("POST")
  })

  it("muestra el resumen cuando la importación es correcta", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        respuestaJson({ entidad: "servicios", filas: 40, registros: 40, omitidos: 0, eventos: 0 }, 200),
      ),
    )
    renderizar()

    await userEvent.upload(
      screen.getByLabelText("Archivo CSV"),
      new File(["x"], "servicios.csv", { type: "text/csv" }),
    )
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    expect(await screen.findByText(/40 registros/)).toBeInTheDocument()
  })
})
```

Run (en `web/`): `npm test -- --run`
Expected: FAIL: no se puede resolver `@/paginas/Importacion`.

- [ ] **Step 2: Página de importación**

`web/src/paginas/Importacion.tsx`:
```tsx
import { useState, type FormEvent } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ErrorApi, pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { ResumenImportacion } from "@/tipos"

const ENTIDADES = [
  ["servicios", "1. Catálogo de servicios"],
  ["proveedores", "2. Proveedores"],
  ["tipo_cambio", "3. Tipo de cambio"],
  ["contratos", "4. Contratos"],
  ["desempeno", "5. Desempeño"],
] as const

function DetalleError({ error }: { error: Error }) {
  const deApi = error instanceof ErrorApi ? error : null
  return (
    <Alert variant="destructive">
      <AlertTitle>{deApi?.titulo ?? "No se pudo importar"}</AlertTitle>
      <AlertDescription>
        <p>{error.message}</p>
        {deApi && deApi.errores.length > 0 && (
          <Table className="mt-2">
            <TableHeader>
              <TableRow>
                <TableHead>Fila</TableHead>
                <TableHead>Campo</TableHead>
                <TableHead>Problema</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deApi.errores.map((e) => (
                <TableRow key={`${e.fila}-${e.campo}-${e.mensaje}`}>
                  <TableCell>{e.fila}</TableCell>
                  <TableCell className="font-mono">{e.campo}</TableCell>
                  <TableCell>{e.mensaje}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </AlertDescription>
    </Alert>
  )
}

export function Importacion() {
  const token = useToken()
  const roles = useRoles()
  const clienteConsultas = useQueryClient()
  const [entidad, setEntidad] = useState<string>("servicios")
  const [archivo, setArchivo] = useState<File | null>(null)

  const importacion = useMutation({
    mutationFn: (datos: { entidad: string; archivo: File }) => {
      const formulario = new FormData()
      formulario.append("archivo", datos.archivo)
      return pedir<ResumenImportacion>(`/proveedores/importaciones/${datos.entidad}`, token, {
        method: "POST",
        body: formulario,
      })
    },
    onSuccess: () => clienteConsultas.invalidateQueries({ queryKey: ["proveedores"] }),
  })

  if (!roles.includes("admin")) {
    return <p role="alert">Solo los administradores pueden importar datos.</p>
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (archivo) importacion.mutate({ entidad, archivo })
  }

  const resumen = importacion.data
  return (
    <section className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">Importar datos del ERP</h1>
      <p className="text-sm text-muted-foreground">
        Cargue los archivos en el orden indicado: contratos y desempeño hacen referencia a
        proveedores y servicios ya importados. Si un archivo tiene errores, no se importa ninguna
        fila. Se aceptan CSV en UTF-8 separados por coma o punto y coma (máximo 10 MB).
      </p>
      <form onSubmit={enviar} className="space-y-3">
        <div className="space-y-1">
          <label htmlFor="entidad" className="text-sm font-medium">
            Tipo de archivo
          </label>
          <select
            id="entidad"
            value={entidad}
            onChange={(e) => setEntidad(e.target.value)}
            className="block h-9 w-full rounded-md border bg-background px-2 text-sm"
          >
            {ENTIDADES.map(([valor, nombre]) => (
              <option key={valor} value={valor}>
                {nombre}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="archivo" className="text-sm font-medium">
            Archivo CSV
          </label>
          <Input
            id="archivo"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
          />
        </div>
        <Button type="submit" disabled={!archivo || importacion.isPending}>
          {importacion.isPending ? "Importando…" : "Importar"}
        </Button>
      </form>

      {resumen && (
        <Alert>
          <AlertTitle>Importación completada</AlertTitle>
          <AlertDescription>
            {resumen.filas} filas leídas · {resumen.registros} registros · {resumen.omitidos}{" "}
            omitidos · {resumen.eventos} eventos
          </AlertDescription>
        </Alert>
      )}
      {importacion.error && <DetalleError error={importacion.error} />}
    </section>
  )
}
```

Run (en `web/`): `npm test -- --run`
Expected: `5 passed`.

- [ ] **Step 3: Lista de proveedores**

En `web/src/tipos.ts`, agregar:
```ts
export const NOMBRES_TAMANO: Record<string, string> = {
  micro: "Micro",
  pequena: "Pequeña",
  mediana: "Mediana",
  grande: "Grande",
}
```

`web/src/paginas/Proveedores.tsx`:
```tsx
import { useState, type FormEvent } from "react"
import { Link } from "react-router"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { NOMBRES_CATEGORIA, NOMBRES_TAMANO, type Categoria, type PaginaProveedores } from "@/tipos"

const POR_PAGINA = 25

export function Proveedores() {
  const token = useToken()
  const [texto, setTexto] = useState("")
  const [q, setQ] = useState("")
  const [categoria, setCategoria] = useState<Categoria | "">("")
  const [pagina, setPagina] = useState(0)

  const consulta = useQuery({
    queryKey: ["proveedores", { q, categoria, pagina }],
    queryFn: () => {
      const parametros = new URLSearchParams({
        limite: String(POR_PAGINA),
        desplazamiento: String(pagina * POR_PAGINA),
      })
      if (q) parametros.set("q", q)
      if (categoria) parametros.set("categoria", categoria)
      return pedir<PaginaProveedores>(`/proveedores/proveedores?${parametros}`, token)
    },
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setPagina(0)
    setQ(texto.trim())
  }

  const total = consulta.data?.total ?? 0
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA))

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Proveedores</h1>
      <form role="search" onSubmit={buscar} className="flex flex-wrap items-center gap-2">
        <label htmlFor="busqueda" className="sr-only">
          Buscar por nombre o RFC
        </label>
        <Input
          id="busqueda"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Nombre o RFC"
          maxLength={100}
          className="max-w-xs"
        />
        <label htmlFor="categoria" className="sr-only">
          Categoría
        </label>
        <select
          id="categoria"
          value={categoria}
          onChange={(e) => {
            setPagina(0)
            setCategoria(e.target.value as Categoria | "")
          }}
          className="h-9 rounded-md border bg-background px-2 text-sm"
        >
          <option value="">Todas las categorías</option>
          {(Object.keys(NOMBRES_CATEGORIA) as Categoria[]).map((c) => (
            <option key={c} value={c}>
              {NOMBRES_CATEGORIA[c]}
            </option>
          ))}
        </select>
        <Button type="submit">Buscar</Button>
      </form>

      {consulta.isError && (
        <p role="alert" className="text-destructive">
          {consulta.error.message}
        </p>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nombre</TableHead>
            <TableHead>RFC</TableHead>
            <TableHead>Tamaño</TableHead>
            <TableHead>Categorías</TableHead>
            <TableHead>Estado</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {consulta.data?.elementos.map((p) => (
            <TableRow key={p.id}>
              <TableCell>
                <Link to={`/proveedores/${p.id}`} className="font-medium hover:underline">
                  {p.nombre}
                </Link>
              </TableCell>
              <TableCell className="font-mono text-sm">{p.rfc}</TableCell>
              <TableCell>{NOMBRES_TAMANO[p.tamano] ?? p.tamano}</TableCell>
              <TableCell className="space-x-1">
                {p.categorias.map((c) => (
                  <Badge key={c} variant="secondary">
                    {NOMBRES_CATEGORIA[c]}
                  </Badge>
                ))}
              </TableCell>
              <TableCell>{p.activo ? "Activo" : "Inactivo"}</TableCell>
            </TableRow>
          ))}
          {consulta.data?.elementos.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground">
                Sin resultados
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between text-sm">
        <span>
          {total} proveedores · página {pagina + 1} de {paginas}
        </span>
        <div className="space-x-2">
          <Button
            variant="outline"
            size="sm"
            disabled={pagina === 0}
            onClick={() => setPagina((n) => n - 1)}
          >
            Anterior
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={pagina + 1 >= paginas}
            onClick={() => setPagina((n) => n + 1)}
          >
            Siguiente
          </Button>
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 4: Detalle del proveedor**

`web/src/paginas/ProveedorDetalle.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query"
import { Link, useParams } from "react-router"
import { ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  NOMBRES_CATEGORIA,
  NOMBRES_TAMANO,
  formatoFecha,
  formatoMoneda,
  type Contrato,
  type Desempeno,
  type ProveedorDetalle as Detalle,
} from "@/tipos"

export function ProveedorDetalle() {
  const { id = "" } = useParams()
  const token = useToken()
  const ruta = `/proveedores/proveedores/${id}`

  const detalle = useQuery({
    queryKey: ["proveedor", id],
    queryFn: () => pedir<Detalle>(ruta, token),
    enabled: Boolean(token),
  })
  const contratos = useQuery({
    queryKey: ["proveedor", id, "contratos"],
    queryFn: () => pedir<Contrato[]>(`${ruta}/contratos`, token),
    enabled: detalle.isSuccess,
  })
  const desempeno = useQuery({
    queryKey: ["proveedor", id, "desempeno"],
    queryFn: () => pedir<Desempeno[]>(`${ruta}/desempeno?meses=12`, token),
    enabled: detalle.isSuccess,
  })

  if (detalle.isPending) return <p>Cargando…</p>
  if (detalle.isError) {
    const noExiste = detalle.error instanceof ErrorApi && detalle.error.estado === 404
    return (
      <section className="space-y-2">
        <p role="alert">{noExiste ? "El proveedor no existe." : detalle.error.message}</p>
        <Link to="/proveedores" className="underline">
          Volver a proveedores
        </Link>
      </section>
    )
  }

  const p = detalle.data
  return (
    <section className="space-y-6">
      <Link to="/proveedores" className="text-sm underline">
        ← Proveedores
      </Link>
      <Card>
        <CardHeader>
          <CardTitle>{p.nombre}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
          <span>
            RFC: <span className="font-mono">{p.rfc}</span>
          </span>
          <span>Tamaño: {NOMBRES_TAMANO[p.tamano] ?? p.tamano}</span>
          <span>
            Contacto: {p.contacto_nombre} · {p.contacto_email}
          </span>
          <span>Contratos vigentes: {p.contratos_vigentes}</span>
          <span className="space-x-1">
            {p.categorias.map((c) => (
              <Badge key={c} variant="secondary">
                {NOMBRES_CATEGORIA[c]}
              </Badge>
            ))}
          </span>
          <span>{p.activo ? "Activo" : "Inactivo"}</span>
        </CardContent>
      </Card>

      <h2 className="text-xl font-semibold">Contratos</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Folio</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead>Vigencia</TableHead>
            <TableHead>Servicio</TableHead>
            <TableHead className="text-right">Cantidad</TableHead>
            <TableHead className="text-right">Precio unitario</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {contratos.data?.flatMap((c) =>
            c.lineas.map((linea, i) => (
              <TableRow key={`${c.id}-${linea.codigo_servicio}`}>
                <TableCell className="font-mono">{i === 0 ? c.folio : ""}</TableCell>
                <TableCell>{i === 0 ? (c.tipo === "nuevo" ? "Nuevo" : "Renovación") : ""}</TableCell>
                <TableCell>
                  {i === 0 ? `${formatoFecha(c.fecha_inicio)} – ${formatoFecha(c.fecha_fin)}` : ""}
                </TableCell>
                <TableCell>{linea.nombre_servicio}</TableCell>
                <TableCell className="text-right">
                  {Number(linea.cantidad).toLocaleString("es-MX")} {linea.unidad}
                </TableCell>
                <TableCell className="text-right">
                  {formatoMoneda(linea.precio_unitario, c.moneda)}
                </TableCell>
              </TableRow>
            )),
          )}
        </TableBody>
      </Table>

      <h2 className="text-xl font-semibold">Desempeño (últimos 12 meses)</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Periodo</TableHead>
            <TableHead className="text-right">Cumplimiento SLA</TableHead>
            <TableHead className="text-right">Resolución (h)</TableHead>
            <TableHead className="text-right">Incidentes críticos</TableHead>
            <TableHead className="text-right">Entregas a tiempo</TableHead>
            <TableHead className="text-right">Satisfacción (1–5)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {desempeno.data?.map((d) => (
            <TableRow key={d.periodo}>
              <TableCell>{formatoFecha(d.periodo)}</TableCell>
              <TableCell className="text-right">{d.sla_cumplimiento_pct} %</TableCell>
              <TableCell className="text-right">{d.tiempo_resolucion_h}</TableCell>
              <TableCell className="text-right">{d.incidentes_criticos}</TableCell>
              <TableCell className="text-right">{d.entregas_a_tiempo_pct} %</TableCell>
              <TableCell className="text-right">{d.satisfaccion}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  )
}
```

- [ ] **Step 5: Registrar rutas y menú**

`web/src/rutas.tsx` (reemplazar el arreglo `children`):
```tsx
import { createBrowserRouter } from "react-router"
import { Layout } from "@/componentes/Layout"
import { Importacion } from "@/paginas/Importacion"
import { Inicio } from "@/paginas/Inicio"
import { NoEncontrado } from "@/paginas/NoEncontrado"
import { ProveedorDetalle } from "@/paginas/ProveedorDetalle"
import { Proveedores } from "@/paginas/Proveedores"

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Inicio },
      { path: "proveedores", Component: Proveedores },
      { path: "proveedores/:id", Component: ProveedorDetalle },
      { path: "importacion", Component: Importacion },
      { path: "*", Component: NoEncontrado },
    ],
  },
])
```

En `web/src/componentes/Layout.tsx`:
- Importar `useRoles` desde `@/auth`.
- Declarar `const roles = useRoles()` justo después de `const auth = useAuth()`, antes de cualquier `return`.
- Después del `NavLink` de "Inicio", agregar:
```tsx
          <NavLink to="/proveedores" className={claseEnlace}>
            Proveedores
          </NavLink>
          {roles.includes("admin") && (
            <NavLink to="/importacion" className={claseEnlace}>
              Importación
            </NavLink>
          )}
```

- [ ] **Step 6: Verificar**

Run (en `web/`): `npm run lint ; npm run build ; npm test -- --run`
Expected: sin errores; `5 passed`.

Run: `docker compose -f infra/docker-compose.yml up -d --build gateway`

Verificación manual en `http://localhost:8080`:
1. Como `comprador1`:
   - "Proveedores" muestra 60 registros en 3 páginas.
   - Buscar `%` muestra "Sin resultados".
   - El filtro "Soporte" reduce la lista.
   - El detalle de un proveedor muestra sus contratos (montos con formato de moneda) y 12 meses de desempeño.
   - El menú **no** muestra "Importación".
2. Como `admin1`:
   - Aparece "Importación".
   - Subir `datos/servicios.csv` muestra el resumen `40 filas leídas · 40 registros…`.
   - Subir un CSV con un correo inválido en `proveedores` muestra la tabla de errores con fila, campo y problema.

- [ ] **Step 7: Commit**

```bash
git add web
git commit -m "feat(web): consulta de proveedores e importacion de CSV"
```

---

### Task 15: CI/CD, dependencias y documentación de arranque

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.github/pull_request_template.md`, `.gitleaks.toml`, `README.md`

**Interfaces:**
- Consumes: comandos verificados en las tareas 1–14.
- Produces:
  - Pipeline con cinco trabajos: `python`, `web`, `stack` (construcción de imágenes y prueba de humo del stack completo), `secretos` (gitleaks) y actualizaciones semanales con Dependabot.
  - README con el arranque en 5 comandos.

- [ ] **Step 1: Workflow de integración continua**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv sync --all-packages --locked
      - run: uv run ruff format --check .
      - run: uv run ruff check .
      - run: uv run mypy
      - run: uv run pytest --cov --cov-report=term-missing

  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 24
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run build
      - run: npm test -- --run

  stack:
    runs-on: ubuntu-latest
    needs: [python, web]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --all-packages --locked
      - run: cp infra/.env.example infra/.env
      - run: uv run python -m generador --salida datos
      - run: docker compose -f infra/docker-compose.yml up -d --build --wait --wait-timeout 300
      - run: docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.importacion.cli /datos
      - run: uv run python infra/smoke_test.py
      - if: failure()
        run: docker compose -f infra/docker-compose.yml logs --no-color

  secretos:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Dependabot, plantilla de PR y reglas de gitleaks**

`.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: weekly
  - package-ecosystem: npm
    directory: /web
    schedule:
      interval: weekly
  - package-ecosystem: docker
    directories: [/services/proveedores, /web]
    schedule:
      interval: weekly
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

`.github/pull_request_template.md`:
```markdown
## Qué cambia y por qué

## Cómo se probó

## Definición de Terminado
- [ ] Pruebas en verde y cobertura ≥ 80 %
- [ ] Contratos OpenAPI/AsyncAPI actualizados (si cambió una API o un evento)
- [ ] Documentación actualizada (manual o ADR si hubo una decisión)
- [ ] Funciona en el stack de Docker Compose (`uv run python infra/smoke_test.py`)
- [ ] Revisión de código hecha
```

`.gitleaks.toml`:
```toml
[extend]
useDefault = true

[allowlist]
description = "Credenciales de prueba del realm de desarrollo y valores de ejemplo"
paths = [
  '''infra/keycloak/realm-plataforma\.json''',
  '''infra/\.env\.example''',
]
```

- [ ] **Step 3: README**

`README.md`:
````markdown
# Plataforma de Negociación Automática con Proveedores

Proyecto 064 de residencias profesionales (ITH) para PluriOne. Plataforma de apoyo a compras
de servicios de TI: inteligencia de precios, desempeño de proveedores, negociación asistida por
IA con límites fijados por el comprador y adjudicación con aprobación humana.

- Requerimientos y diseño: [`docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md`](docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md)
- Planes de implementación: [`docs/superpowers/plans/`](docs/superpowers/plans/)

## Requisitos

- Docker Desktop (WSL 2 en Windows)
- [uv](https://docs.astral.sh/uv/) y Node 24

## Arranque rápido

```bash
cp infra/.env.example infra/.env
uv sync --all-packages
uv run python -m generador --salida datos
docker compose -f infra/docker-compose.yml up -d --build --wait
docker compose -f infra/docker-compose.yml exec proveedores python -m proveedores.importacion.cli /datos
```

Abrir <http://localhost:8080>. Los usuarios de desarrollo (`admin1`, `comprador1`,
`aprobador1`) y sus contraseñas están en `infra/keycloak/realm-plataforma.json`; admin y
aprobador configuran OTP en su primer inicio de sesión. Verificación automática:
`uv run python infra/smoke_test.py`.

## Desarrollo

| Tarea | Comando |
|---|---|
| Pruebas de Python (requieren Docker) | `uv run pytest --cov` |
| Lint, formato y tipos | `uv run ruff format . && uv run ruff check . && uv run mypy` |
| SPA con recarga en caliente | `cd web && npm run dev` → <http://localhost:5173> |
| Pruebas del frontend | `cd web && npm test` |
| Contrato OpenAPI de proveedores | <http://localhost:8080/api/proveedores/docs> |
| Consola de RabbitMQ | <http://localhost:15672> |

## Estructura

| Carpeta | Contenido |
|---|---|
| `libs/comun` | Infraestructura compartida: logs, errores RFC 9457, JWT, salud, outbox |
| `services/proveedores` | Microservicio de proveedores, contratos, precios y desempeño |
| `tools/generador` | Datos sintéticos reproducibles del ERP simulado |
| `web` | SPA en React servida por el gateway |
| `infra` | Docker Compose, Nginx, Keycloak, PostgreSQL |

## Convenciones

- *Trunk-based*: ramas cortas `feat/…` o `fix/…` y PR hacia `main`.
- Mensajes con [Conventional Commits](https://www.conventionalcommits.org/es/).
- Toda regla de negocio nueva se desarrolla con TDD.
````

- [ ] **Step 4: Verificar localmente lo que correrá el CI**

Run: `uv sync --all-packages --locked ; uv run ruff format --check . ; uv run ruff check . ; uv run mypy ; uv run pytest --cov`
Expected: todo en verde.

Run (en `web/`): `npm ci ; npm run lint ; npm run build ; npm test -- --run`
Expected: todo en verde.

Run: `docker compose -f infra/docker-compose.yml up -d --build --wait --wait-timeout 300 ; uv run python infra/smoke_test.py`
Expected: `OK: …`.

- [ ] **Step 5: Commit**

```bash
git add .github .gitleaks.toml README.md
git commit -m "ci: pipeline de integracion continua, dependabot y README"
```

Si el repositorio ya tiene remoto en GitHub, hacer push de la rama y confirmar que los cinco trabajos del workflow pasan. Si todavía no hay remoto, el workflow se validará en el primer push.

---

## Autorrevisión del plan frente al spec

| Requisito del spec para el Incremento 1 | Tarea |
|---|---|
| Monorepo con workspace de uv | 1 |
| `libs/comun`: JWT, logs, errores, outbox (+ salud y configuración) | 2–6 |
| Una BD y un usuario por servicio; `REVOKE CONNECT` | 12 (paso 8 lo verifica) |
| Servicio `proveedores` con importación CSV (adaptador ERP/SRM) y eventos | 7–11 |
| Eventos `proveedor.actualizado`, `contrato.registrado`, `desempeno.registrado` con envelope | 6, 9 |
| Generador de datos sintéticos con verdad oculta | 11 |
| Keycloak (roles, PKCE, audiencia, OTP admin/aprobador), gateway con CSP y límite de tasa | 12, 13 |
| UI de proveedores e importación | 13, 14 |
| CI base, Dependabot, gitleaks, plantilla de PR con Definición de Terminado | 15 |
| Ollama, `ia`, FastStream, consumidores, observabilidad, E2E | Diferidos (ver tabla al inicio) |

