# Operación del sistema — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El administrador mantiene el catálogo de servicios, ve en una sola bitácora quién importó o cambió qué (con filtros y exportación a CSV), sabe si cada servicio de la plataforma está sano, tiene un panel de inicio y todos encuentran ayuda dentro de la app.

**Architecture:**
- `proveedores` gana un catálogo editable (alta, edición y estado) y publica por el outbox `servicio.actualizado`, `importacion.completada` e `importacion.rechazada`, siempre con quién lo hizo.
- `administracion` consume esos eventos de RabbitMQ (cola quorum `administracion.actividad`) y los guarda en su bitácora de solo inserción, de forma idempotente.
- `administracion` agrega la exportación CSV de la bitácora, el estado de los servicios (`/estado`) y los conteos del panel (`/resumen`). La lectura de eventos de Keycloak pasa a milisegundos y orden ascendente.
- La SPA agrega Panel, Actividad, Catálogo y Estado del sistema al área "Sistema", y el área "Soporte" con el Centro de ayuda para todos.

**Tech Stack:**
- Backend: Python 3.13, FastAPI, SQLAlchemy async + asyncpg, Alembic, aio-pika (RabbitMQ 4.1), httpx, pytest + Testcontainers (PostgreSQL y RabbitMQ).
- Web: React 19 + TS, TanStack Query 5, shadcn (radix-nova), Vitest + Testing Library + axe.

**Spec:** `docs/superpowers/specs/2026-10-08-gestion-administracion-design.md`. Este plan cubre el plan 2, "Operación del sistema" (sección 10), más estos agregados aprobados por el residente:
- lectura de eventos de Keycloak en milisegundos y en orden ascendente;
- validar las fechas de `/actividad` (hoy `hasta=9999-12-31` da 500);
- corregir el spec (§3.4 y §3.7) y marcarlo aprobado;
- Dependabot para la imagen de `administracion`;
- foco en Importación (`aria-disabled` en lugar de `disabled`);
- la prueba de rutas solo para admin cubre las rutas nuevas.

## Global Constraints

**Rama y entorno**
- Rama `feat/operacion-sistema`, creada desde `main` (`f9169bd`).
- Windows + Git Bash. Comandos de Docker con `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"; export MSYS_NO_PATHCONV=1`.
- Comandos de uv con `export PATH="/c/Users/sebas/AppData/Local/Microsoft/WinGet/Links:$PATH"; export UV_PYTHON="C:/Users/sebas/AppData/Roaming/uv/python/cpython-3.13.15-windows-x86_64-none/python.exe"`.

**Autorización**
- Todos los endpoints de `administracion` exigen el rol `admin`, salvo `/salud/*`.
- Catálogo en `proveedores`: `GET /servicios` para los tres roles internos; `incluir_inactivos=true`, `POST /servicios` y `PATCH /servicios/{codigo}` solo `admin`.

**Eventos (sobre existente: `event_id`, `type`, `version`, `occurred_at`, `correlation_id`, `payload`)**
- `servicio.actualizado`: `id`, `codigo`, `nombre`, `categoria`, `unidad`, `moneda`, `activo`, `cambio` (`creado` / `actualizado` / `desactivado` / `activado`), `campos` (lista de campos cambiados, vacía si no aplica) y `actor` `{id, nombre}`.
- `importacion.completada`: `entidad`, `filas`, `registros`, `omitidos`, `actor`.
- `importacion.rechazada`: `entidad`, `errores` (total), `actor`.
- Importaciones por línea de comandos: actor `{"id": null, "nombre": "Sistema (línea de comandos)"}`.
- Cola de `administracion`: `administracion.actividad`, quorum, `x-delivery-limit` 5, enlazada a `importacion.*` y `servicio.*` del exchange `eventos`.
- En la bitácora: `origen` `proveedores` y `clave_origen` `proveedores:{event_id}`.

**Catálogo**
- El código no cambia después de crearse: `^[A-Z0-9-]{3,30}$` (se acepta en minúsculas y se guarda en mayúsculas).
- Categoría y moneda solo cambian si el servicio no tiene contratos.
- Unidades: `usuario_mes`, `vcpu_mes`, `gb_mes`, `mes`, `hora`, `ticket`. Monedas: `MXN`, `USD`.
- Los servicios se desactivan, no se borran.

**Estado del sistema**
- Sano: responde en menos de 1 s.
- Con problemas: tarda 1 s o más, o una cola de RabbitMQ tiene más de 100 mensajes listos.
- Caído: no responde en 2 s o devuelve error.
- Comprobaciones en paralelo: base de datos propia, `proveedores` (`/salud/listo`), Keycloak (documento de descubrimiento del realm), RabbitMQ (API de administración, colas) y Mailpit (`/readyz`).

**Bitácora**
- Exportación CSV: mismos filtros que la lista, UTF-8 con BOM, máximo 10,000 filas (las más recientes).
- Fechas de los filtros entre `2000-01-01` y `2100-12-31`.

**Interfaz**
- Español de México, de usted; solo tokens de color.
- 0 violaciones de axe; usable de 375 a 1440 px sin scroll horizontal.
- Filtros en la URL.
- Fechas en UTC en la BD; se muestran en `America/Mexico_City`.
- Los botones que siguen en pantalla mientras corre una petición usan `aria-disabled` con guardia en el manejador, no `disabled` (un botón deshabilitado pierde el foco).

**Dependencias nuevas**
- Backend: `aio-pika>=9.5` como dependencia declarada de `administracion` (ya está en `uv.lock` por `comun`).
- Web: ninguna.

**Seguridad de credenciales**
- Nunca escriba contraseñas ni secretos en comandos, archivos versionados o reportes. `infra/.env` no se versiona.
- Las contraseñas de desarrollo están en `infra/keycloak/realm-plataforma.json`; no las repita.

**Calidad**
- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` y `uv run pytest` sin errores.
- En `web/`: `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check "src/**/*.{ts,tsx}"` limpios. La salida de las pruebas no lleva advertencias.

**Commits**
- Conventional Commits en español.
- Mensaje: asunto, una línea en blanco y `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (dos `-m`).
- Verifique con `git log -1 --format=%B`.

## Review Focus

1. **Fórmulas en el CSV.** Un intento de inicio de sesión con usuario `=HIPERVINCULO(...)` llega a la bitácora tal cual y Excel lo ejecutaría al abrir la exportación. Toda celda que empiece con `=`, `+`, `-`, `@`, tabulador o retorno se escribe con un apóstrofo delante. Prueba: Task 5 (`test_exportar_neutraliza_formulas`).
2. **Eventos repetidos o mal formados.** RabbitMQ entrega al menos una vez: el mismo evento dos veces deja un solo registro, y un mensaje mal formado se descarta sin detener la cola. Pruebas: Task 3 (`test_un_evento_repetido_deja_un_solo_registro` y `test_un_mensaje_mal_formado_no_detiene_la_cola`).
3. **Cambiar categoría o moneda de un servicio con contratos.** Se rechaza con 409 y el error junto al campo; sin contratos sí se permite. Pruebas: Task 1 (`test_categoria_y_moneda_bloqueadas_con_contratos`) y Task 8 (campos bloqueados con explicación).
4. **Una importación rechazada deja rastro.** El archivo con errores no guarda nada, pero la bitácora debe decir quién lo intentó y cuántos errores tenía. Prueba: Task 2 (`test_importacion_rechazada_registra_el_intento`).
5. **Una dependencia que no responde.** Cada comprobación tiene su propio límite de 2 s: la pantalla muestra ese servicio como "Caído" y los demás con su estado, sin que falle la página. Pruebas: Task 6 (`test_un_servicio_caido_no_tumba_el_estado`) y Task 9 (`muestra cada servicio con su estado`).

## Fuera de este plan

Pendientes del plan 1 que ningún archivo de este plan toca y siguen siendo de bajo riesgo a esta escala:
- `correo_enviado.solicitado_por` guarda el usuario del admin sin recortar (`String(200)`).
- Eventos LOGOUT sin nombre hacen que la sincronización de sesiones llame a `listar_usuarios` en cada ciclo.
- La prueba "todas las rutas exigen admin" recorre `app.openapi()`; una ruta con `include_in_schema=False` se le escaparía (ninguna de este plan lo usa).
- En las pantallas de usuarios, el teclado puede abrir un `ConfirmarAccion` mientras otra acción está en curso.

---

### Task 1: Catálogo editable en `proveedores`

**Files:**
- Create:
  - `services/proveedores/alembic/versions/0003_servicio_activo.py`
  - `services/proveedores/src/proveedores/api/catalogo.py`
  - `services/proveedores/tests/test_catalogo.py`
- Modify:
  - `services/proveedores/src/proveedores/modelos.py` (`ServicioCatalogo.activo`)
  - `services/proveedores/src/proveedores/api/esquemas.py` (`Servicio`, `ServicioNuevo`, `CambioServicio`)
  - `services/proveedores/src/proveedores/api/rutas.py` (quitar `GET /servicios`, que pasa a `catalogo.py`)
  - `services/proveedores/src/proveedores/main.py` (incluir el router del catálogo)

**Interfaces:**
- Produces:
  - `GET /servicios?incluir_inactivos=false` → `list[Servicio]`; `Servicio` = `{id, codigo, nombre, categoria, unidad, moneda, activo, tiene_contratos}`.
  - `POST /servicios` (`ServicioNuevo`: `codigo`, `nombre`, `categoria`, `unidad`, `moneda`) → 201 `Servicio`; 409 `servicio_duplicado` con `errores: [{campo: "codigo", ...}]`.
  - `PATCH /servicios/{codigo}` (`CambioServicio`: `nombre?`, `categoria?`, `unidad?`, `moneda?`, `activo?`) → `Servicio`; 404 `servicio_no_encontrado`; 409 `servicio_con_contratos` con `errores` por campo.
  - Evento `servicio.actualizado` con el payload de Global Constraints.

- [ ] **Step 1: Pruebas (fallan)**

`services/proveedores/tests/test_catalogo.py`:

```python
import httpx
import pytest
from comun.pruebas import ClavesPrueba
from proveedores.modelos import Outbox
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

SERVICIOS = (
    "codigo,nombre,categoria,unidad,moneda\n"
    "SAAS-OFI-EMP,Suite de productividad,licencia_saas,usuario_mes,USD\n"
    "SOP-MESA-TK,Mesa de ayuda - ticket,soporte,ticket,MXN\n"
)
PROVEEDORES = (
    "rfc,nombre,tamano,categorias,contacto_nombre,contacto_email,activo\n"
    "NAZ210315AB1,Nube Azteca S.A. de C.V.,mediana,licencia_saas,"
    "Laura Méndez,ventas01@proveedor01.example,true\n"
)
CONTRATOS = (
    "folio,rfc_proveedor,tipo,fecha_inicio,fecha_fin,moneda,plazo_pago_dias,"
    "sla_disponibilidad,tope_aumento_pct,cuota_implementacion,codigo_servicio,"
    "cantidad,precio_unitario\n"
    "C-0001,NAZ210315AB1,nuevo,2020-01-01,2099-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,200,20\n"
)


def _auth(claves: ClavesPrueba, rol: str, sub: str = "admin-7") -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token(rol, sub=sub)}"}


@pytest.fixture
async def con_catalogo(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> httpx.AsyncClient:
    for entidad, texto in (
        ("servicios", SERVICIOS),
        ("proveedores", PROVEEDORES),
        ("contratos", CONTRATOS),
    ):
        respuesta = await cliente.post(
            f"/importaciones/{entidad}",
            files={"archivo": (f"{entidad}.csv", texto.encode(), "text/csv")},
            headers=_auth(claves, "admin"),
        )
        assert respuesta.status_code == 200, respuesta.text
    return cliente


async def _eventos_servicio(fabrica: async_sessionmaker[AsyncSession]) -> list[dict[str, object]]:
    async with fabrica() as sesion:
        filas = await sesion.scalars(
            select(Outbox).where(Outbox.tipo == "servicio.actualizado").order_by(Outbox.ocurrido_en)
        )
        return [f.payload for f in filas]


async def test_lista_solo_activos_y_marca_los_que_tienen_contratos(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    lista = (await con_catalogo.get("/servicios", headers=_auth(claves, "comprador"))).json()
    assert [(s["codigo"], s["activo"], s["tiene_contratos"]) for s in lista] == [
        ("SAAS-OFI-EMP", True, True),
        ("SOP-MESA-TK", True, False),
    ]


async def test_solo_admin_ve_los_inactivos(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await con_catalogo.get(
        "/servicios", params={"incluir_inactivos": "true"}, headers=_auth(claves, "comprador")
    )
    assert respuesta.status_code == 403


async def test_alta_normaliza_el_codigo_y_publica_el_evento(
    cliente: httpx.AsyncClient,
    claves: ClavesPrueba,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await cliente.post(
        "/servicios",
        json={
            "codigo": "nube-vm-2",
            "nombre": "Máquina virtual de 2 vCPU",
            "categoria": "nube",
            "unidad": "vcpu_mes",
            "moneda": "USD",
        },
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["codigo"] == "NUBE-VM-2"
    assert respuesta.json()["activo"] is True
    [evento] = await _eventos_servicio(fabrica)
    assert evento["cambio"] == "creado"
    assert evento["codigo"] == "NUBE-VM-2"
    assert evento["campos"] == []
    assert evento["actor"] == {"id": "admin-7", "nombre": "admin-7"}


async def test_alta_con_codigo_repetido(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await con_catalogo.post(
        "/servicios",
        json={
            "codigo": "SOP-MESA-TK",
            "nombre": "Otro",
            "categoria": "soporte",
            "unidad": "ticket",
            "moneda": "MXN",
        },
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "servicio_duplicado"
    assert respuesta.json()["errores"] == [
        {"campo": "codigo", "mensaje": "Ya existe un servicio con ese código."}
    ]


async def test_alta_con_datos_invalidos(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await cliente.post(
        "/servicios",
        json={"codigo": "x", "nombre": "", "categoria": "nube", "unidad": "litro", "moneda": "EUR"},
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 422
    assert {e["campo"] for e in respuesta.json()["errores"]} == {
        "body.codigo",
        "body.nombre",
        "body.unidad",
        "body.moneda",
    }


async def test_editar_publica_los_campos_cambiados(
    con_catalogo: httpx.AsyncClient,
    claves: ClavesPrueba,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await con_catalogo.patch(
        "/servicios/sop-mesa-tk",
        json={"nombre": "Mesa de ayuda por ticket", "unidad": "ticket"},
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["nombre"] == "Mesa de ayuda por ticket"
    [evento] = await _eventos_servicio(fabrica)
    assert (evento["cambio"], evento["campos"]) == ("actualizado", ["nombre"])


async def test_desactivar_lo_oculta_y_activar_lo_devuelve(
    con_catalogo: httpx.AsyncClient,
    claves: ClavesPrueba,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    admin = _auth(claves, "admin")
    await con_catalogo.patch("/servicios/SOP-MESA-TK", json={"activo": False}, headers=admin)
    activos = (await con_catalogo.get("/servicios", headers=admin)).json()
    assert [s["codigo"] for s in activos] == ["SAAS-OFI-EMP"]
    todos = (
        await con_catalogo.get("/servicios", params={"incluir_inactivos": "true"}, headers=admin)
    ).json()
    assert [(s["codigo"], s["activo"]) for s in todos] == [
        ("SAAS-OFI-EMP", True),
        ("SOP-MESA-TK", False),
    ]
    await con_catalogo.patch("/servicios/SOP-MESA-TK", json={"activo": True}, headers=admin)
    assert [e["cambio"] for e in await _eventos_servicio(fabrica)] == ["desactivado", "activado"]


async def test_categoria_y_moneda_bloqueadas_con_contratos(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    admin = _auth(claves, "admin")
    bloqueado = await con_catalogo.patch(
        "/servicios/SAAS-OFI-EMP", json={"categoria": "nube", "moneda": "MXN"}, headers=admin
    )
    assert bloqueado.status_code == 409
    assert bloqueado.json()["codigo"] == "servicio_con_contratos"
    assert [e["campo"] for e in bloqueado.json()["errores"]] == ["categoria", "moneda"]
    libre = await con_catalogo.patch(
        "/servicios/SOP-MESA-TK", json={"categoria": "consultoria"}, headers=admin
    )
    assert libre.status_code == 200
    assert libre.json()["categoria"] == "consultoria"


async def test_editar_sin_cambios_no_publica_nada(
    con_catalogo: httpx.AsyncClient,
    claves: ClavesPrueba,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await con_catalogo.patch(
        "/servicios/SOP-MESA-TK",
        json={"nombre": "Mesa de ayuda - ticket", "activo": True},
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 200
    assert await _eventos_servicio(fabrica) == []


async def test_servicio_inexistente(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await cliente.patch(
        "/servicios/NO-EXISTE", json={"nombre": "x"}, headers=_auth(claves, "admin")
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "servicio_no_encontrado"


async def test_comprador_no_edita_el_catalogo(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    comprador = _auth(claves, "comprador")
    alta = await con_catalogo.post(
        "/servicios",
        json={
            "codigo": "X-1",
            "nombre": "X",
            "categoria": "nube",
            "unidad": "mes",
            "moneda": "MXN",
        },
        headers=comprador,
    )
    assert alta.status_code == 403
    edicion = await con_catalogo.patch(
        "/servicios/SOP-MESA-TK", json={"nombre": "x"}, headers=comprador
    )
    assert edicion.status_code == 403
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest services/proveedores/tests/test_catalogo.py -q`
Expected: FAIL (`activo` y `tiene_contratos` no existen; `POST /servicios` responde 405).

- [ ] **Step 3: Migración y modelo**

`services/proveedores/alembic/versions/0003_servicio_activo.py`:

```python
"""Estado activo de los servicios del catálogo (se desactivan, no se borran).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "servicio_catalogo",
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("servicio_catalogo", "activo")
```

En `modelos.py`, importe `true` de `sqlalchemy` y agregue a `ServicioCatalogo`:

```python
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())
```

- [ ] **Step 4: Esquemas**

En `api/esquemas.py`:

```python
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from proveedores.importacion.esquemas import Categoria, Moneda, Unidad

# Pydantic valida el patrón antes de pasar a mayúsculas: se aceptan minúsculas y se normalizan.
CodigoServicio = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9-]{3,30}$"),
]
NombreServicio = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
```

Reemplace `Servicio` y agregue los dos modelos de entrada:

```python
class Servicio(DesdeOrm):
    id: UUID
    codigo: str
    nombre: str
    categoria: str
    unidad: str
    moneda: str
    activo: bool
    tiene_contratos: bool = False


class ServicioNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: CodigoServicio
    nombre: NombreServicio
    categoria: Categoria
    unidad: Unidad
    moneda: Moneda


class CambioServicio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: NombreServicio | None = None
    categoria: Categoria | None = None
    unidad: Unidad | None = None
    moneda: Moneda | None = None
    activo: bool | None = None
```

- [ ] **Step 5: Router del catálogo**

`services/proveedores/src/proveedores/api/catalogo.py`:

```python
"""Catálogo de servicios: consulta para los roles internos; alta, edición y estado para admin."""

import uuid
from typing import Annotated, Any

from comun.auth import ROLES_INTERNOS, Usuario, requiere_rol
from comun.errores import ErrorDominio
from comun.outbox import registrar_evento
from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from proveedores.api import esquemas
from proveedores.db import obtener_sesion
from proveedores.modelos import LineaContrato, Outbox, ServicioCatalogo

Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]
Interno = Annotated[Usuario, Depends(requiere_rol(*ROLES_INTERNOS))]
Admin = Annotated[Usuario, Depends(requiere_rol("admin"))]
CodigoEnRuta = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{3,30}$")]
CAMPOS_CON_CONTRATOS = ("categoria", "moneda")  # los precios históricos dependen de ellos

router = APIRouter(tags=["catalogo"])


def _actor(usuario: Usuario) -> dict[str, str]:
    return {"id": usuario.id, "nombre": usuario.nombre}


async def _con_contratos(sesion: AsyncSession, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    filas = await sesion.scalars(
        select(LineaContrato.servicio_id).where(LineaContrato.servicio_id.in_(ids)).distinct()
    )
    return set(filas)


def _salida(servicio: ServicioCatalogo, tiene_contratos: bool) -> esquemas.Servicio:
    return esquemas.Servicio.model_validate(servicio).model_copy(
        update={"tiene_contratos": tiene_contratos}
    )


def _publicar(
    sesion: AsyncSession,
    servicio: ServicioCatalogo,
    cambio: str,
    actor: dict[str, str],
    campos: list[str] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "id": servicio.id,
        "codigo": servicio.codigo,
        "nombre": servicio.nombre,
        "categoria": servicio.categoria,
        "unidad": servicio.unidad,
        "moneda": servicio.moneda,
        "activo": servicio.activo,
        "cambio": cambio,
        "campos": campos or [],
        "actor": actor,
    }
    registrar_evento(sesion, Outbox, "servicio.actualizado", payload)


def _duplicado() -> ErrorDominio:
    mensaje = "Ya existe un servicio con ese código."
    return ErrorDominio(
        409,
        "Conflicto",
        mensaje,
        {"codigo": "servicio_duplicado", "errores": [{"campo": "codigo", "mensaje": mensaje}]},
    )


@router.get("/servicios")
async def listar_servicios(
    sesion: Sesion, usuario: Interno, incluir_inactivos: bool = False
) -> list[esquemas.Servicio]:
    if incluir_inactivos and "admin" not in usuario.roles:
        raise ErrorDominio(
            403, "Sin permiso", "Solo administración puede ver los servicios inactivos."
        )
    consulta = select(ServicioCatalogo).order_by(ServicioCatalogo.categoria, ServicioCatalogo.codigo)
    if not incluir_inactivos:
        consulta = consulta.where(ServicioCatalogo.activo.is_(True))
    servicios = list((await sesion.scalars(consulta)).all())
    usados = await _con_contratos(sesion, [s.id for s in servicios])
    return [_salida(s, s.id in usados) for s in servicios]


@router.post("/servicios", status_code=201)
async def crear_servicio(
    datos: esquemas.ServicioNuevo, sesion: Sesion, usuario: Admin
) -> esquemas.Servicio:
    servicio = ServicioCatalogo(id=uuid.uuid4(), activo=True, **datos.model_dump())
    try:
        async with sesion.begin():
            existente = await sesion.scalar(
                select(ServicioCatalogo.id).where(ServicioCatalogo.codigo == datos.codigo)
            )
            if existente is not None:
                raise _duplicado()
            sesion.add(servicio)
            _publicar(sesion, servicio, "creado", _actor(usuario))
    except IntegrityError as error:  # dos altas simultáneas del mismo código
        raise _duplicado() from error
    return _salida(servicio, tiene_contratos=False)


@router.patch("/servicios/{codigo}")
async def editar_servicio(
    codigo: CodigoEnRuta, datos: esquemas.CambioServicio, sesion: Sesion, usuario: Admin
) -> esquemas.Servicio:
    async with sesion.begin():
        servicio = await sesion.scalar(
            select(ServicioCatalogo)
            .where(ServicioCatalogo.codigo == codigo.upper())
            .with_for_update()
        )
        if servicio is None:
            raise ErrorDominio(
                404, "No encontrado", "El servicio no existe.", {"codigo": "servicio_no_encontrado"}
            )
        tiene_contratos = bool(await _con_contratos(sesion, [servicio.id]))
        cambios = {
            campo: valor
            for campo, valor in datos.model_dump(exclude_none=True).items()
            if getattr(servicio, campo) != valor
        }
        bloqueados = [c for c in CAMPOS_CON_CONTRATOS if c in cambios]
        if bloqueados and tiene_contratos:
            raise ErrorDominio(
                409,
                "Conflicto",
                "El servicio ya tiene contratos: su categoría y su moneda no se pueden cambiar.",
                {
                    "codigo": "servicio_con_contratos",
                    "errores": [
                        {
                            "campo": campo,
                            "mensaje": "No se puede cambiar porque el servicio ya tiene contratos.",
                        }
                        for campo in bloqueados
                    ],
                },
            )
        activo = cambios.pop("activo", None)
        actor = _actor(usuario)
        for campo, valor in cambios.items():
            setattr(servicio, campo, valor)
        if cambios:
            _publicar(sesion, servicio, "actualizado", actor, sorted(cambios))
        if activo is not None:
            servicio.activo = activo
            _publicar(sesion, servicio, "activado" if activo else "desactivado", actor)
    return _salida(servicio, tiene_contratos)
```

En `api/rutas.py` borre la función `listar_servicios` (la ruta pasa al router nuevo) y quite `ServicioCatalogo` de los imports si queda sin uso.

En `main.py`:

```python
from proveedores.api.catalogo import router as router_catalogo
...
    app.include_router(router)
    app.include_router(router_catalogo)
```

- [ ] **Step 6: Correr las pruebas**

Run: `uv run pytest services/proveedores -q`
Expected: PASS, incluidas `test_migraciones.py` (modelo y migración coinciden; la migración se revierte y se reaplica) y `test_api.py::test_catalogo_de_servicios`.

- [ ] **Step 7: Calidad y commit**

```bash
uv run ruff format services/proveedores && uv run ruff check services/proveedores && uv run mypy
git add services/proveedores
git commit -m "feat(proveedores): catálogo editable con alta, edición y estado, y evento servicio.actualizado" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Eventos de importación con quién lo hizo

**Files:**
- Modify:
  - `services/proveedores/src/proveedores/importacion/aplicar.py` (`ACTOR_LINEA_DE_COMANDOS`, `registrar_importacion`, `registrar_rechazo`)
  - `services/proveedores/src/proveedores/api/rutas.py` (`importar_archivo`)
  - `services/proveedores/src/proveedores/importacion/cli.py` (`cargar_carpeta`)
- Test:
  - `services/proveedores/tests/test_api.py`
  - `services/proveedores/tests/test_cli.py`

**Interfaces:**
- Consumes: `ErrorImportacion.errores` (lista completa de `ErrorFila`), `ResumenImportacion`.
- Produces:
  - `ACTOR_LINEA_DE_COMANDOS: dict[str, str | None]`.
  - `registrar_importacion(sesion, resumen, actor) -> None` y `registrar_rechazo(sesion, entidad, total_errores, actor) -> None`.
  - Eventos `importacion.completada` (en la misma transacción que los datos) e `importacion.rechazada` (en una transacción aparte, porque la de los datos se revierte).

- [ ] **Step 1: Pruebas (fallan)**

Agregue a `services/proveedores/tests/test_api.py` (importe `from proveedores.modelos import Outbox`, `from sqlalchemy import select` y `from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker`):

```python
async def _payloads(
    fabrica: async_sessionmaker[AsyncSession], tipo: str
) -> list[dict[str, Any]]:
    async with fabrica() as sesion:
        filas = await sesion.scalars(select(Outbox).where(Outbox.tipo == tipo))
        return [f.payload for f in filas]


async def test_importacion_completada_registra_quien_y_cuanto(
    cliente: httpx.AsyncClient, claves: ClavesPrueba, fabrica: async_sessionmaker[AsyncSession]
) -> None:
    respuesta = await cliente.post(
        "/importaciones/servicios",
        files={"archivo": ("servicios.csv", SERVICIOS.encode(), "text/csv")},
        headers={"Authorization": f"Bearer {claves.token('admin', sub='admin-42')}"},
    )
    assert respuesta.status_code == 200
    assert await _payloads(fabrica, "importacion.completada") == [
        {
            "entidad": "servicios",
            "filas": 2,
            "registros": 2,
            "omitidos": 0,
            "actor": {"id": "admin-42", "nombre": "admin-42"},
        }
    ]


async def test_importacion_rechazada_registra_el_intento(
    cliente: httpx.AsyncClient, claves: ClavesPrueba, fabrica: async_sessionmaker[AsyncSession]
) -> None:
    texto = PROVEEDORES.replace("ventas01@proveedor01.example", "correo-invalido")
    respuesta = await _subir(cliente, claves, "proveedores", texto.encode())
    assert respuesta.status_code == 422
    [rechazo] = await _payloads(fabrica, "importacion.rechazada")
    assert rechazo["entidad"] == "proveedores"
    assert rechazo["errores"] == 1
    assert rechazo["actor"]["id"] == "usuario-prueba"
    # Los datos del archivo no se guardaron: ni proveedores ni sus eventos.
    assert await _payloads(fabrica, "proveedor.actualizado") == []
    assert await _payloads(fabrica, "importacion.completada") == []
```

Agregue a `services/proveedores/tests/test_cli.py` (importe `from proveedores.modelos import Outbox`):

```python
@pytest.mark.integracion
async def test_la_carga_registra_cada_archivo_con_el_actor_de_linea_de_comandos(
    fabrica: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    _carpeta_con_contratos_invalidos(tmp_path)
    with pytest.raises(ErrorCarga):
        await cargar_carpeta(fabrica, tmp_path)
    async with fabrica() as sesion:
        filas = list(
            (
                await sesion.scalars(
                    select(Outbox)
                    .where(Outbox.tipo.startswith("importacion."))
                    .order_by(Outbox.ocurrido_en)
                )
            ).all()
        )
    assert [(f.tipo, f.payload["entidad"]) for f in filas] == [
        ("importacion.completada", "servicios"),
        ("importacion.completada", "proveedores"),
        ("importacion.completada", "tipo_cambio"),
        ("importacion.rechazada", "contratos"),
    ]
    assert {f.payload["actor"]["nombre"] for f in filas} == {"Sistema (línea de comandos)"}
    assert filas[-1].payload["errores"] == 1
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest services/proveedores/tests/test_api.py services/proveedores/tests/test_cli.py -q`
Expected: FAIL (no hay eventos `importacion.*`).

- [ ] **Step 3: Funciones de registro**

En `importacion/aplicar.py`, después de `ResumenImportacion`:

```python
ACTOR_LINEA_DE_COMANDOS: dict[str, str | None] = {
    "id": None,
    "nombre": "Sistema (línea de comandos)",
}


def registrar_importacion(
    sesion: AsyncSession, resumen: ResumenImportacion, actor: dict[str, str | None]
) -> None:
    """Deja en el outbox, en la transacción de los datos, que la importación se completó."""
    registrar_evento(
        sesion,
        Outbox,
        "importacion.completada",
        {
            "entidad": resumen.entidad,
            "filas": resumen.filas,
            "registros": resumen.registros,
            "omitidos": resumen.omitidos,
            "actor": actor,
        },
    )


def registrar_rechazo(
    sesion: AsyncSession, entidad: str, total_errores: int, actor: dict[str, str | None]
) -> None:
    """La transacción de los datos se revirtió: el intento se registra en una propia."""
    registrar_evento(
        sesion,
        Outbox,
        "importacion.rechazada",
        {"entidad": entidad, "errores": total_errores, "actor": actor},
    )
```

- [ ] **Step 4: Usarlas en la API y en la línea de comandos**

En `api/rutas.py`, importe `ErrorImportacion`, `registrar_importacion` y `registrar_rechazo` de `proveedores.importacion.aplicar` y cambie el bloque de `importar_archivo`:

```python
    actor: dict[str, str | None] = {"id": usuario.id, "nombre": usuario.nombre}
    try:
        async with sesion.begin():
            resumen = await importar(sesion, entidad, contenido)
            registrar_importacion(sesion, resumen, actor)
    except ErrorImportacion as error:
        async with sesion.begin():
            registrar_rechazo(sesion, entidad, len(error.errores), actor)
        raise
    except IntegrityError as error:
```

(el resto del `except IntegrityError` y el log no cambian).

En `importacion/cli.py`, importe `ACTOR_LINEA_DE_COMANDOS`, `registrar_importacion` y `registrar_rechazo` y cambie el ciclo de `cargar_carpeta`:

```python
    for entidad in ORDEN_CARGA:
        contenido = (carpeta / f"{entidad}.csv").read_bytes()
        try:
            async with fabrica() as sesion, sesion.begin():
                resumen = await importar(sesion, entidad, contenido)
                registrar_importacion(sesion, resumen, ACTOR_LINEA_DE_COMANDOS)
        except ErrorImportacion as error:
            async with fabrica() as sesion, sesion.begin():
                registrar_rechazo(sesion, entidad, len(error.errores), ACTOR_LINEA_DE_COMANDOS)
            raise ErrorCarga(error, entidad, [r.entidad for r in resumenes]) from error
        resumenes.append(resumen)
    return resumenes
```

- [ ] **Step 5: Correr las pruebas**

Run: `uv run pytest services/proveedores -q`
Expected: PASS. `test_la_cli_imprime_un_resumen_por_entidad` no cambia: la columna "eventos" del resumen cuenta solo los eventos de los datos.

- [ ] **Step 6: Calidad y commit**

```bash
uv run ruff format services/proveedores && uv run ruff check services/proveedores && uv run mypy
git add services/proveedores
git commit -m "feat(proveedores): eventos de importación completada y rechazada con quién la hizo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `administracion` consume los eventos de importación y de catálogo

**Files:**
- Create:
  - `services/administracion/src/administracion/eventos.py`
  - `services/administracion/tests/test_eventos.py`
- Modify:
  - `services/administracion/pyproject.toml` (dependencia `aio-pika>=9.5`) y `uv.lock`
  - `services/administracion/src/administracion/config.py` (`consumir_eventos`)
  - `services/administracion/src/administracion/main.py` (tarea del consumidor en el ciclo de vida)
  - `services/administracion/tests/conftest.py` y `services/administracion/tests/test_sesiones.py` (`consumir_eventos=False`)
  - `infra/docker-compose.yml` (`RABBITMQ_URL` y dependencia de `rabbitmq` en `administracion`)

**Interfaces:**
- Consumes: eventos de las Tasks 1 y 2; `bitacora.registrar(..., origen, clave_origen, fecha)`; `comun.outbox.EXCHANGE_EVENTOS`.
- Produces:
  - `administracion.eventos.traducir(sobre: dict[str, Any]) -> Registro | None` (lanza `EventoInvalido` si el sobre no tiene la forma esperada).
  - `ConsumidorEventos(fabrica, url_rabbitmq)` con `ejecutar()` (reconecta solo), `conectado() -> bool` y `cerrar()`.
  - Registros en la bitácora:
    - `importacion.completada` / `importacion.rechazada`: `objeto_tipo` `importacion`, `objeto_id` la entidad, `objeto_nombre` su nombre legible ("servicios del catálogo", "proveedores", "tipos de cambio", "contratos", "registros de desempeño"); `detalle` `{filas, registros, omitidos}` o `{errores}`.
    - `servicio.creado` / `.actualizado` / `.desactivado` / `.activado`: `objeto_tipo` `servicio`, `objeto_id` y `objeto_nombre` el código; `detalle` `{campos}` solo en `actualizado`.

- [ ] **Step 1: Pruebas (fallan)**

`services/administracion/tests/test_eventos.py`:

```python
import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import aio_pika
import pytest
from administracion.bitacora import Actor, Objeto
from administracion.eventos import (
    COLA,
    ConsumidorEventos,
    EventoInvalido,
    Registro,
    traducir,
)
from comun.outbox import EXCHANGE_EVENTOS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.rabbitmq import RabbitMqContainer

ADMIN = {"id": "admin-1", "nombre": "admin1"}
FECHA = "2026-10-09T15:00:00+00:00"


def _sobre(tipo: str, payload: dict[str, Any], event_id: str | None = None) -> dict[str, Any]:
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "type": tipo,
        "version": 1,
        "occurred_at": FECHA,
        "correlation_id": "c-1",
        "payload": payload,
    }


def test_traduce_una_importacion_completada() -> None:
    sobre = _sobre(
        "importacion.completada",
        {"entidad": "proveedores", "filas": 60, "registros": 60, "omitidos": 0, "actor": ADMIN},
        "e-1",
    )
    assert traducir(sobre) == Registro(
        tipo="importacion.completada",
        actor=Actor("admin-1", "admin1"),
        objeto=Objeto("importacion", "proveedores", "proveedores"),
        detalle={"filas": 60, "registros": 60, "omitidos": 0},
        resultado="exito",
        clave_origen="proveedores:e-1",
        fecha=datetime(2026, 10, 9, 15, tzinfo=UTC),
    )


def test_traduce_una_importacion_rechazada_de_la_linea_de_comandos() -> None:
    sobre = _sobre(
        "importacion.rechazada",
        {
            "entidad": "tipo_cambio",
            "errores": 3,
            "actor": {"id": None, "nombre": "Sistema (línea de comandos)"},
        },
    )
    registro = traducir(sobre)
    assert registro is not None
    assert registro.resultado == "fallo"
    assert registro.detalle == {"errores": 3}
    assert registro.objeto.nombre == "tipos de cambio"
    assert registro.actor == Actor(None, "Sistema (línea de comandos)")


@pytest.mark.parametrize(
    ("cambio", "detalle"),
    [
        ("creado", {}),
        ("actualizado", {"campos": ["nombre"]}),
        ("desactivado", {}),
        ("activado", {}),
    ],
)
def test_traduce_los_cambios_del_catalogo(cambio: str, detalle: dict[str, Any]) -> None:
    sobre = _sobre(
        "servicio.actualizado",
        {"codigo": "SOP-MESA-TK", "cambio": cambio, "campos": ["nombre"], "actor": ADMIN},
    )
    registro = traducir(sobre)
    assert registro is not None
    assert registro.tipo == f"servicio.{cambio}"
    assert registro.objeto == Objeto("servicio", "SOP-MESA-TK", "SOP-MESA-TK")
    assert registro.detalle == detalle


def test_ignora_lo_que_no_va_a_la_bitacora() -> None:
    assert traducir(_sobre("proveedor.actualizado", {"id": "x"})) is None
    # Un servicio.actualizado sin cambio ni actor (p. ej. una instantánea del Plan B) no es una acción.
    assert traducir(_sobre("servicio.actualizado", {"codigo": "X"})) is None


def test_un_sobre_mal_formado_es_invalido() -> None:
    with pytest.raises(EventoInvalido):
        traducir({"type": "importacion.completada", "payload": {}})


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


async def _publicar(url: str, cuerpo: bytes, clave: str) -> None:
    conexion = await aio_pika.connect_robust(url)
    async with conexion:
        canal = await conexion.channel()
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        await exchange.publish(aio_pika.Message(cuerpo), routing_key=clave)


async def _tipos(fabrica: async_sessionmaker[AsyncSession]) -> list[str]:
    async with fabrica() as sesion:
        return list(
            (await sesion.scalars(text("SELECT tipo FROM actividad ORDER BY fecha, tipo"))).all()
        )


async def _esperar(fabrica: async_sessionmaker[AsyncSession], cuantos: int) -> list[str]:
    for _ in range(200):
        tipos = await _tipos(fabrica)
        if len(tipos) >= cuantos:
            return tipos
        await asyncio.sleep(0.05)
    pytest.fail(f"No llegaron {cuantos} registros a la bitácora")


@contextlib.asynccontextmanager
async def _consumidor(
    fabrica: async_sessionmaker[AsyncSession], url: str
) -> AsyncIterator[ConsumidorEventos]:
    consumidor = ConsumidorEventos(fabrica, url)
    tarea = asyncio.create_task(consumidor.ejecutar())
    try:
        for _ in range(200):  # que la cola exista y esté enlazada antes de publicar
            if consumidor.conectado():
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("El consumidor no se conectó a RabbitMQ")
        yield consumidor
    finally:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
        await consumidor.cerrar()


@pytest.mark.integracion
async def test_un_evento_repetido_deja_un_solo_registro(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    sobre = _sobre(
        "servicio.actualizado",
        {"codigo": "NUBE-VM-2", "cambio": "creado", "campos": [], "actor": ADMIN},
        "repetido",
    )
    async with _consumidor(fabrica, url_rabbitmq):
        await _publicar(url_rabbitmq, json.dumps(sobre).encode(), "servicio.actualizado")
        await _publicar(url_rabbitmq, json.dumps(sobre).encode(), "servicio.actualizado")
        await _esperar(fabrica, 1)
        await asyncio.sleep(0.5)  # tiempo para que la segunda entrega llegue si se fuera a duplicar
    assert await _tipos(fabrica) == ["servicio.creado"]


@pytest.mark.integracion
async def test_un_mensaje_mal_formado_no_detiene_la_cola(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    valido = _sobre(
        "importacion.completada",
        {"entidad": "contratos", "filas": 5, "registros": 2, "omitidos": 0, "actor": ADMIN},
    )
    async with _consumidor(fabrica, url_rabbitmq):
        await _publicar(url_rabbitmq, b"no es json", "importacion.completada")
        await _publicar(url_rabbitmq, json.dumps(valido).encode(), "importacion.completada")
        assert await _esperar(fabrica, 1) == ["importacion.completada"]


@pytest.mark.integracion
async def test_la_cola_es_durable_de_tipo_quorum(
    fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str
) -> None:
    async with _consumidor(fabrica, url_rabbitmq):
        conexion = await aio_pika.connect_robust(url_rabbitmq)
        async with conexion:
            canal = await conexion.channel()
            # Redeclarar con argumentos distintos falla (PRECONDITION_FAILED): si pasa, coinciden.
            cola = await canal.declare_queue(
                COLA, durable=True, arguments={"x-queue-type": "quorum", "x-delivery-limit": 5}
            )
            assert cola.name == COLA
```

En `tests/conftest.py`, en el fixture `app`, pase `consumir_eventos=False` a `Configuracion(...)`. En `tests/test_sesiones.py`, en `test_el_ciclo_de_vida_copia_los_eventos_y_se_apaga`, use `Configuracion(database_url=urls_bd[1], consumir_eventos=False)`.

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest services/administracion/tests/test_eventos.py -q`
Expected: FAIL (`ModuleNotFoundError: administracion.eventos`).

- [ ] **Step 3: Dependencia y configuración**

En `services/administracion/pyproject.toml`, agregue `"aio-pika>=9.5",` a `dependencies` y corra `uv lock`.

En `config.py`, agregue a `Configuracion`:

```python
    # Las pruebas que levantan el ciclo de vida lo apagan: no hay RabbitMQ en ellas.
    consumir_eventos: bool = True
```

- [ ] **Step 4: Consumidor**

`services/administracion/src/administracion/eventos.py`:

```python
"""Copia a la bitácora los eventos de importación y de catálogo que publica proveedores."""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection
from comun.outbox import EXCHANGE_EVENTOS
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from administracion.bitacora import Actor, Objeto, registrar

log = logging.getLogger(__name__)

COLA = "administracion.actividad"
CLAVES = ("importacion.*", "servicio.*")
# ponytail: tras 5 entregas fallidas RabbitMQ descarta el mensaje (no hay cola de fallidos todavía);
# el Plan B declara eventos.dlx y la cola de fallidos para todos los consumidores.
ARGUMENTOS_COLA = {"x-queue-type": "quorum", "x-delivery-limit": 5}
REINTENTO_CONEXION_S = 5
NOMBRES_ENTIDAD = {
    "servicios": "servicios del catálogo",
    "proveedores": "proveedores",
    "tipo_cambio": "tipos de cambio",
    "contratos": "contratos",
    "desempeno": "registros de desempeño",
}
CAMBIOS_SERVICIO = frozenset({"creado", "actualizado", "desactivado", "activado"})


class EventoInvalido(ValueError):
    """El mensaje no tiene la forma esperada: reintentarlo no lo arregla."""


@dataclass(frozen=True)
class Registro:
    tipo: str
    actor: Actor
    objeto: Objeto
    detalle: dict[str, Any]
    resultado: str
    clave_origen: str
    fecha: datetime


def _actor(payload: dict[str, Any]) -> Actor:
    actor = payload.get("actor") or {}
    return Actor(actor.get("id"), str(actor.get("nombre") or "Sistema"))


def traducir(sobre: dict[str, Any]) -> Registro | None:
    """El registro de bitácora de un sobre de evento; None si el evento no es una acción."""
    try:
        tipo = sobre["type"]
        payload = sobre["payload"]
        clave = f"proveedores:{sobre['event_id']}"
        fecha = datetime.fromisoformat(sobre["occurred_at"])
        if tipo in ("importacion.completada", "importacion.rechazada"):
            entidad = str(payload["entidad"])
            objeto = Objeto("importacion", entidad, NOMBRES_ENTIDAD.get(entidad, entidad))
            if tipo == "importacion.completada":
                detalle = {c: int(payload[c]) for c in ("filas", "registros", "omitidos")}
                return Registro(tipo, _actor(payload), objeto, detalle, "exito", clave, fecha)
            detalle = {"errores": int(payload["errores"])}
            return Registro(tipo, _actor(payload), objeto, detalle, "fallo", clave, fecha)
        if tipo == "servicio.actualizado":
            cambio = payload.get("cambio")
            if cambio not in CAMBIOS_SERVICIO or "actor" not in payload:
                return None
            codigo = str(payload["codigo"])
            detalle = {"campos": list(payload.get("campos") or [])} if cambio == "actualizado" else {}
            return Registro(
                f"servicio.{cambio}",
                _actor(payload),
                Objeto("servicio", codigo, codigo),
                detalle,
                "exito",
                clave,
                fecha,
            )
        return None
    except (KeyError, TypeError, ValueError) as exc:
        raise EventoInvalido(str(exc)) from exc


async def guardar(fabrica: async_sessionmaker[AsyncSession], registro: Registro) -> None:
    """Inserta el registro; un evento ya recibido (misma clave de origen) no hace nada."""
    async with fabrica() as sesion:
        await registrar(
            sesion,
            registro.tipo,
            registro.actor,
            objeto=registro.objeto,
            detalle=registro.detalle,
            resultado=registro.resultado,
            origen="proveedores",
            clave_origen=registro.clave_origen,
            fecha=registro.fecha,
        )
        await sesion.commit()


async def atender(
    fabrica: async_sessionmaker[AsyncSession], mensaje: AbstractIncomingMessage
) -> None:
    try:
        registro = traducir(json.loads(mensaje.body))
    except ValueError:  # JSON inválido o EventoInvalido
        log.warning("Evento con forma inesperada; se descarta (mensaje %s)", mensaje.message_id)
        await mensaje.reject(requeue=False)
        return
    if registro is not None:
        try:
            await guardar(fabrica, registro)
        except SQLAlchemyError:
            log.exception("No se pudo guardar el evento %s; se reintentará", mensaje.message_id)
            await mensaje.nack(requeue=True)
            return
    await mensaje.ack()


class ConsumidorEventos:
    def __init__(self, fabrica: async_sessionmaker[AsyncSession], url_rabbitmq: str) -> None:
        self._fabrica = fabrica
        self._url = url_rabbitmq
        self._conexion: AbstractRobustConnection | None = None
        self._enlazada = False

    def conectado(self) -> bool:
        """Conectado y con la cola ya enlazada: desde aquí no se pierde ningún evento."""
        return self._enlazada and self._conexion is not None and not self._conexion.is_closed

    async def cerrar(self) -> None:
        self._enlazada = False
        if self._conexion is not None:
            await self._conexion.close()
            self._conexion = None

    async def _consumir(self) -> None:
        self._conexion = await aio_pika.connect_robust(self._url)
        canal = await self._conexion.channel()
        await canal.set_qos(prefetch_count=10)
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        cola = await canal.declare_queue(COLA, durable=True, arguments=ARGUMENTOS_COLA)
        for clave in CLAVES:
            await cola.bind(exchange, clave)
        self._enlazada = True
        async with cola.iterator() as mensajes:
            async for mensaje in mensajes:
                await atender(self._fabrica, mensaje)

    async def ejecutar(self) -> None:
        """Consume sin fin; si RabbitMQ no está, reintenta cada pocos segundos."""
        while True:
            try:
                await self._consumir()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception(
                    "Sin conexión con RabbitMQ; se reintentará en %s s", REINTENTO_CONEXION_S
                )
                await self.cerrar()
                await asyncio.sleep(REINTENTO_CONEXION_S)
```

- [ ] **Step 5: Arrancarlo con la aplicación**

En `main.py`, importe `ConsumidorEventos` y cambie el ciclo de vida:

```python
    consumidor = ConsumidorEventos(sesiones, config.rabbitmq_url)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        tareas = [
            asyncio.create_task(
                ejecutar_periodicamente(proveedor, sesiones, config.intervalo_eventos_s)
            )
        ]
        if config.consumir_eventos:
            tareas.append(asyncio.create_task(consumidor.ejecutar()))
        yield
        for tarea in tareas:
            tarea.cancel()
        for tarea in tareas:
            with contextlib.suppress(asyncio.CancelledError):
                await tarea
        await consumidor.cerrar()
        if isinstance(proveedor, IdentidadKeycloak):
            await proveedor.cerrar()
```

y guarde el consumidor para el estado del sistema: `app.state.consumidor = consumidor`.

La salud (`/salud/listo`) sigue revisando solo PostgreSQL: un RabbitMQ caído no debe dejar a la administración fuera del gateway; el Estado del sistema (Task 6) lo muestra.

- [ ] **Step 6: Infraestructura**

En `infra/docker-compose.yml`, servicio `administracion`:
- en `environment`, agregue `RABBITMQ_URL: amqp://plataforma:${RABBITMQ_PASSWORD}@rabbitmq:5672/`;
- en `depends_on`, agregue

```yaml
      rabbitmq:
        condition: service_healthy
```

- [ ] **Step 7: Correr las pruebas**

Run: `uv run pytest services/administracion -q`
Expected: PASS.

- [ ] **Step 8: Calidad y commit**

```bash
uv run ruff format services/administracion && uv run ruff check services/administracion && uv run mypy
git add services/administracion uv.lock infra/docker-compose.yml
git commit -m "feat(administracion): bitácora de importaciones y del catálogo a partir de los eventos de proveedores" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Lectura de eventos de Keycloak en milisegundos y en orden ascendente

Comprobado contra el Keycloak 26.5 del stack: `GET /admin/realms/plataforma/events` acepta `dateFrom` en milisegundos, respeta `direction=asc` y no devuelve eventos anteriores a `dateFrom`.

**Files:**
- Modify:
  - `services/administracion/src/administracion/keycloak.py` (`eventos_de_sesion`)
  - `services/administracion/src/administracion/sesiones.py` (comentario del límite)
- Test: `services/administracion/tests/test_keycloak.py`

**Interfaces:**
- Consumes/Produces: `ProveedorIdentidad.eventos_de_sesion(desde) -> list[EventoSesion]` no cambia de firma; ahora pide solo lo nuevo y del más viejo al más nuevo. Con más de 10,000 eventos devuelve los 10,000 más viejos y la siguiente lectura sigue desde el último copiado.

- [ ] **Step 1: Pruebas (fallan)**

En `tests/test_keycloak.py`, cambie la aserción de `dateFrom` de `test_eventos_pagina_traduce_y_filtra_por_fecha`:

```python
    def eventos(peticion: httpx.Request) -> httpx.Response:
        assert peticion.url.params.get_list("type") == ["LOGIN", "LOGIN_ERROR", "LOGOUT"]
        assert peticion.url.params["dateFrom"] == str(ms)
        assert peticion.url.params["direction"] == "asc"
        return httpx.Response(200, json=pagina1 if peticion.url.params["first"] == "0" else pagina2)
```

y agregue (importe `MAX_PAGINAS_EVENTOS` y `TAMANO_PAGINA_EVENTOS` de `administracion.keycloak`):

```python
async def test_eventos_se_detiene_en_el_tope_y_devuelve_los_mas_viejos() -> None:
    desde = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    ms = int(desde.timestamp() * 1000)

    def eventos(peticion: httpx.Request) -> httpx.Response:
        primero = int(peticion.url.params["first"])
        return httpx.Response(
            200,
            json=[
                {"id": f"e{primero + i}", "time": ms + (primero + i) * 1000, "type": "LOGIN"}
                for i in range(TAMANO_PAGINA_EVENTOS)
            ],
        )

    identidad, peticiones = _keycloak({("GET", f"{ADMIN}/events"): eventos})
    lista = await identidad.eventos_de_sesion(desde)
    assert len([p for p in peticiones if p.url.path == f"{ADMIN}/events"]) == MAX_PAGINAS_EVENTOS
    assert len(lista) == MAX_PAGINAS_EVENTOS * TAMANO_PAGINA_EVENTOS
    assert lista[0].id == "e0"  # los más viejos primero: la siguiente lectura sigue desde el último
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest services/administracion/tests/test_keycloak.py -q`
Expected: FAIL (`dateFrom` va como fecha y no hay `direction`).

- [ ] **Step 3: Implementación**

En `keycloak.py`, reemplace `eventos_de_sesion`:

```python
    async def eventos_de_sesion(self, desde: datetime) -> list[EventoSesion]:
        """Eventos desde `desde`, del más viejo al más nuevo.

        ponytail: hasta 10,000 por lectura (50 páginas de 200). Si hay más, la siguiente lectura
        sigue desde el último copiado: nada se pierde, solo se retrasa.
        """
        eventos: list[EventoSesion] = []
        desde_ms = str(int(desde.timestamp() * 1000))
        for pagina in range(MAX_PAGINAS_EVENTOS):
            parametros = [
                *(("type", tipo) for tipo in TIPOS_EVENTO),
                ("dateFrom", desde_ms),
                ("direction", "asc"),
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

En `sesiones.py`, borre el comentario `ponytail` de las líneas 30-32 (el límite ya se explica en el adaptador y ya no se saltan eventos).

- [ ] **Step 4: Correr las pruebas**

Run: `uv run pytest services/administracion/tests/test_keycloak.py services/administracion/tests/test_sesiones.py -q`
Expected: PASS.

- [ ] **Step 5: Calidad y commit**

```bash
uv run ruff format services/administracion && uv run ruff check services/administracion && uv run mypy
git add services/administracion
git commit -m "perf(administracion): leer solo los eventos de Keycloak nuevos y en orden ascendente" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Actividad: fechas validadas y exportación a CSV

**Files:**
- Create:
  - `services/administracion/src/administracion/textos.py`
  - `services/administracion/tests/test_textos.py`
- Modify: `services/administracion/src/administracion/api/rutas.py` (`_filtro_actividad`, `listar_actividad`, `exportar_actividad`)
- Test: `services/administracion/tests/test_actividad.py`

**Interfaces:**
- Consumes: `bitacora.consultar`, `FiltroActividad`, los tipos de `web/src/actividad.ts` (`TIPOS_ACTIVIDAD`).
- Produces:
  - `administracion.textos.describir(actividad: Actividad) -> str` (los mismos textos que `describirActividad` de la web).
  - `GET /actividad/exportar?persona&tipo&desde&hasta` → `text/csv; charset=utf-8` con BOM, columnas `Fecha, Persona, Acción, Resultado, IP`, cabecera `X-Total-Registros` (total con esos filtros) y `Content-Disposition: attachment; filename="actividad.csv"`.
  - `desde`/`hasta` fuera de `2000-01-01`–`2100-12-31` → 422 con `errores: [{campo, mensaje: "Use una fecha entre 2000-01-01 y 2100-12-31."}]`.

- [ ] **Step 1: Pruebas (fallan)**

`services/administracion/tests/test_textos.py`:

```python
import re
from pathlib import Path

from administracion.modelos import Actividad
from administracion.textos import TEXTOS, describir

WEB = Path(__file__).resolve().parents[3] / "web" / "src" / "actividad.ts"


def _actividad(tipo: str, **campos: object) -> Actividad:
    return Actividad(
        tipo=tipo,
        actor_nombre="admin1",
        objeto_nombre=campos.pop("objeto_nombre", "Ana López"),
        detalle=campos.pop("detalle", {}),
    )


def test_los_mismos_tipos_que_la_web() -> None:
    bloque = re.search(
        r"TIPOS_ACTIVIDAD = \[(.*?)\] as const", WEB.read_text(encoding="utf-8"), re.S
    )
    assert bloque is not None
    assert set(re.findall(r'"([a-z_.]+)"', bloque.group(1))) == set(TEXTOS)


def test_textos_en_lenguaje_llano() -> None:
    assert describir(_actividad("sesion.fallida", detalle={"error": "user_disabled"})) == (
        "Intento fallido de inicio de sesión: cuenta desactivada"
    )
    assert describir(
        _actividad(
            "usuario.roles_cambiados", detalle={"antes": ["comprador"], "despues": ["admin"]}
        )
    ) == ("Cambió los roles de Ana López: Compras → Administración")
    assert describir(
        _actividad("importacion.completada", objeto_nombre="contratos", detalle={"registros": 1250})
    ) == ("Importó 1,250 contratos")
    assert describir(
        _actividad("importacion.rechazada", objeto_nombre="proveedores", detalle={"errores": 3})
    ) == ("Intentó importar proveedores; el archivo tenía 3 errores")
    assert describir(_actividad("usuario.creado", detalle={"pendiente": "roles"})) == (
        "Dio de alta a Ana López; faltó asignar los roles"
    )
    assert describir(_actividad("servicio.desactivado", objeto_nombre="SOP-MESA-TK")) == (
        "Desactivó el servicio SOP-MESA-TK"
    )
    assert describir(_actividad("tipo.desconocido")) == "tipo.desconocido"
```

En `tests/test_actividad.py` agregue (importe `csv`, `io` y `pytest`):

```python
@pytest.mark.parametrize(
    ("params", "campo"),
    [({"hasta": "9999-12-31"}, "hasta"), ({"desde": "1999-12-31"}, "desde")],
)
async def test_fechas_fuera_de_rango(
    cliente: httpx.AsyncClient, admin: dict[str, str], params: dict[str, str], campo: str
) -> None:
    for ruta in ("/actividad", "/actividad/exportar"):
        respuesta = await cliente.get(ruta, params=params, headers=admin)
        assert respuesta.status_code == 422, ruta
        assert respuesta.json()["errores"] == [
            {"campo": campo, "mensaje": "Use una fecha entre 2000-01-01 y 2100-12-31."}
        ]


def _filas_csv(respuesta: httpx.Response) -> list[list[str]]:
    assert respuesta.content.startswith("﻿".encode())  # BOM: Excel lo abre como UTF-8
    return list(csv.reader(io.StringIO(respuesta.content.decode("utf-8-sig"))))


@pytest.mark.usefixtures("sembrada")
async def test_exportar_csv_en_hora_de_mexico(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    respuesta = await cliente.get("/actividad/exportar", headers=admin)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "text/csv; charset=utf-8"
    assert respuesta.headers["content-disposition"] == 'attachment; filename="actividad.csv"'
    assert respuesta.headers["x-total-registros"] == "2"
    assert _filas_csv(respuesta) == [
        ["Fecha", "Persona", "Acción", "Resultado", "IP"],
        ["2026-10-08 12:00", "admin1", "Desactivó a Ana López", "Éxito", ""],
        ["2026-10-07 23:30", "ana", "Inició sesión", "Éxito", ""],
    ]


@pytest.mark.usefixtures("sembrada")
async def test_exportar_respeta_los_filtros(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    respuesta = await cliente.get(
        "/actividad/exportar", params={"tipo": "sesiones"}, headers=admin
    )
    assert [fila[2] for fila in _filas_csv(respuesta)[1:]] == ["Inició sesión"]


async def test_exportar_neutraliza_formulas(
    cliente: httpx.AsyncClient, admin: dict[str, str], fabrica: async_sessionmaker[AsyncSession]
) -> None:
    async with fabrica() as sesion:
        await registrar(
            sesion,
            "sesion.fallida",
            Actor(None, '=HIPERVINCULO("http://x.example")'),
            detalle={"error": "user_not_found"},
            resultado="fallo",
            origen="keycloak",
            clave_origen="k:formula",
        )
        await sesion.commit()
    [_, fila] = _filas_csv(await cliente.get("/actividad/exportar", headers=admin))
    assert fila[1] == "'=HIPERVINCULO(\"http://x.example\")"
    assert fila[3] == "Falló"


@pytest.mark.usefixtures("sembrada")
async def test_exportar_hasta_el_limite_con_las_mas_recientes(
    cliente: httpx.AsyncClient, admin: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("administracion.api.rutas.MAX_FILAS_EXPORTACION", 1)
    respuesta = await cliente.get("/actividad/exportar", headers=admin)
    assert respuesta.headers["x-total-registros"] == "2"
    assert [fila[2] for fila in _filas_csv(respuesta)[1:]] == ["Desactivó a Ana López"]
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest services/administracion/tests/test_textos.py services/administracion/tests/test_actividad.py -q`
Expected: FAIL (`administracion.textos` no existe; `hasta=9999-12-31` da 500; `/actividad/exportar` da 404).

- [ ] **Step 3: Textos**

`services/administracion/src/administracion/textos.py`:

```python
"""La acción de cada registro de la bitácora en lenguaje llano.

Son los mismos textos que `web/src/actividad.ts`; una prueba verifica que ambos cubren los mismos
tipos.
"""

from collections.abc import Callable

from administracion.modelos import Actividad

NOMBRES_ROL = {"admin": "Administración", "comprador": "Compras", "aprobador": "Aprobación"}
ERRORES_SESION = {
    "invalid_user_credentials": "contraseña incorrecta",
    "user_not_found": "usuario inexistente",
    "user_disabled": "cuenta desactivada",
    "user_temporarily_disabled": "cuenta bloqueada temporalmente",
}
# Un alta que quedó a medias trae en el detalle qué faltó.
PENDIENTES = {"roles": "; faltó asignar los roles", "contrasena": "; faltó la contraseña"}


def _roles(valor: object) -> str:
    if not isinstance(valor, list):
        return ""
    return ", ".join(NOMBRES_ROL.get(str(r), str(r)) for r in valor)


def _numero(valor: object) -> str:
    """Como toLocaleString("es-MX"): separador de miles con coma."""
    return f"{int(valor):,}" if isinstance(valor, int | float) else "0"


def _sesion_fallida(a: Actividad) -> str:
    motivo = ERRORES_SESION.get(str(a.detalle.get("error", "")))
    return (
        f"Intento fallido de inicio de sesión: {motivo}"
        if motivo
        else "Intento fallido de inicio de sesión"
    )


TEXTOS: dict[str, Callable[[Actividad], str]] = {
    "sesion.iniciada": lambda a: "Inició sesión",
    "sesion.fallida": _sesion_fallida,
    "sesion.cerrada": lambda a: "Cerró sesión",
    "usuario.creado": lambda a: f"Dio de alta a {a.objeto_nombre}",
    "usuario.actualizado": lambda a: f"Editó los datos de {a.objeto_nombre}",
    "usuario.roles_cambiados": lambda a: (
        f"Cambió los roles de {a.objeto_nombre}: "
        f"{_roles(a.detalle.get('antes'))} → {_roles(a.detalle.get('despues'))}"
    ),
    "usuario.desactivado": lambda a: f"Desactivó a {a.objeto_nombre}",
    "usuario.activado": lambda a: f"Activó a {a.objeto_nombre}",
    "usuario.correo_contrasena": lambda a: (
        f"Envió a {a.objeto_nombre} un correo para definir su contraseña"
    ),
    "usuario.contrasena_temporal": lambda a: (
        f"Asignó una contraseña temporal a {a.objeto_nombre}"
    ),
    "usuario.sesiones_cerradas": lambda a: f"Cerró las sesiones de {a.objeto_nombre}",
    "importacion.completada": lambda a: (
        f"Importó {_numero(a.detalle.get('registros'))} {a.objeto_nombre}"
    ),
    "importacion.rechazada": lambda a: (
        f"Intentó importar {a.objeto_nombre}; el archivo tenía "
        f"{_numero(a.detalle.get('errores'))} errores"
    ),
    "servicio.creado": lambda a: f"Dio de alta el servicio {a.objeto_nombre}",
    "servicio.actualizado": lambda a: f"Editó el servicio {a.objeto_nombre}",
    "servicio.desactivado": lambda a: f"Desactivó el servicio {a.objeto_nombre}",
    "servicio.activado": lambda a: f"Activó el servicio {a.objeto_nombre}",
}


def describir(actividad: Actividad) -> str:
    """La acción en lenguaje llano; un tipo desconocido se muestra tal cual."""
    texto = TEXTOS.get(actividad.tipo)
    if texto is None:
        return actividad.tipo
    return texto(actividad) + PENDIENTES.get(str(actividad.detalle.get("pendiente")), "")
```

- [ ] **Step 4: Filtro compartido y exportación**

En `api/rutas.py` (importe `csv`, `io` y `from administracion.textos import describir`), reemplace el bloque desde `ZONA = ZoneInfo(...)` hasta el final por:

```python
ZONA = ZoneInfo("America/Mexico_City")
FECHA_MINIMA = date(2000, 1, 1)
FECHA_MAXIMA = date(2100, 12, 31)
MAX_FILAS_EXPORTACION = 10_000
# Excel ejecuta como fórmula una celda que empieza con estos caracteres (inyección CSV).
INICIOS_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _inicio_del_dia(dia: date) -> datetime:
    return datetime.combine(dia, time.min, tzinfo=ZONA)


def _invalida(campo: str, mensaje: str) -> ErrorDominio:
    return ErrorDominio(
        422,
        "Solicitud inválida",
        "Revise los campos indicados.",
        {"errores": [{"campo": campo, "mensaje": mensaje}]},
    )


def _filtro_actividad(
    persona: str | None, tipo: GrupoTipo | None, desde: date | None, hasta: date | None
) -> FiltroActividad:
    for campo, valor in (("desde", desde), ("hasta", hasta)):
        if valor is not None and not FECHA_MINIMA <= valor <= FECHA_MAXIMA:
            raise _invalida(
                campo, f"Use una fecha entre {FECHA_MINIMA:%Y-%m-%d} y {FECHA_MAXIMA:%Y-%m-%d}."
            )
    if desde and hasta and hasta < desde:
        raise _invalida("hasta", "Debe ser igual o posterior a la fecha inicial")
    return FiltroActividad(
        persona=persona,
        tipo=tipo,
        desde=_inicio_del_dia(desde) if desde else None,
        hasta=_inicio_del_dia(hasta + timedelta(days=1)) if hasta else None,
    )


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
    filtro = _filtro_actividad(persona, tipo, desde, hasta)
    total, filas = await consultar(sesion, filtro, (pagina - 1) * tamano, tamano)
    return esquemas.PaginaActividad(
        total=total, elementos=[esquemas.ActividadSalida.model_validate(f) for f in filas]
    )


def _celda(valor: str) -> str:
    return f"'{valor}" if valor.startswith(INICIOS_DE_FORMULA) else valor


@router.get("/actividad/exportar", tags=["actividad"])
async def exportar_actividad(
    sesion: Sesion,
    _: Admin,
    persona: Annotated[str | None, Query(max_length=64)] = None,
    tipo: GrupoTipo | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> Response:
    """Las más recientes primero, hasta 10,000 filas; X-Total-Registros dice cuántas hay."""
    filtro = _filtro_actividad(persona, tipo, desde, hasta)
    total, filas = await consultar(sesion, filtro, 0, MAX_FILAS_EXPORTACION)
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["Fecha", "Persona", "Acción", "Resultado", "IP"])
    for a in filas:
        escritor.writerow(
            [
                a.fecha.astimezone(ZONA).strftime("%Y-%m-%d %H:%M"),
                _celda(a.actor_nombre),
                _celda(describir(a)),
                "Éxito" if a.resultado == "exito" else "Falló",
                _celda(a.ip or ""),
            ]
        )
    return Response(
        ("﻿" + salida.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="actividad.csv"',
            "X-Total-Registros": str(total),
        },
    )
```

`Response` ya está importado de `fastapi` en este archivo.

- [ ] **Step 5: Correr las pruebas**

Run: `uv run pytest services/administracion -q`
Expected: PASS. `test_todas_las_rutas_exigen_el_rol_admin` ya recorre `/actividad/exportar`.

- [ ] **Step 6: Calidad y commit**

```bash
uv run ruff format services/administracion && uv run ruff check services/administracion && uv run mypy
git add services/administracion
git commit -m "feat(administracion): exportar la bitácora a CSV y validar el rango de fechas" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Estado del sistema y resumen del panel

**Files:**
- Create:
  - `services/administracion/src/administracion/estado.py`
  - `services/administracion/src/administracion/api/sistema.py`
  - `services/administracion/tests/test_sistema.py`
- Modify:
  - `services/administracion/src/administracion/config.py` (`proveedores_url`, `mailpit_url`, `rabbitmq_api_url`, `version_app`)
  - `services/administracion/src/administracion/api/esquemas.py` (`EstadoServicio`, `EstadoSistema`, `Resumen`)
  - `services/administracion/src/administracion/main.py` (cliente HTTP del estado, router `sistema`)
  - `infra/docker-compose.yml` (variables del servicio `administracion`)

**Interfaces:**
- Consumes: `ProveedorIdentidad.listar_usuarios()`, modelos `Actividad` y `CorreoEnviado`, `Sesion`, `Admin` e `Identidad` de `api/rutas.py`.
- Produces:
  - `GET /estado` → `EstadoSistema` = `{version: str, comprobado_en: datetime, servicios: [EstadoServicio]}`; `EstadoServicio` = `{clave, nombre, estado: "sano" | "con_problemas" | "caido", tiempo_ms: int | null, detalle}`. Claves en este orden: `base_de_datos`, `proveedores`, `identidad`, `mensajeria`, `correo`.
  - `GET /resumen` → `Resumen` = `{usuarios_activos: int | null, intentos_fallidos_24h: int, correos_7d: int}` (`usuarios_activos` es `null` si Keycloak no responde).
  - `crear_app(..., transporte_estado: httpx.AsyncBaseTransport | None = None)`.

- [ ] **Step 1: Pruebas (fallan)**

`services/administracion/tests/test_sistema.py`:

```python
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from administracion.bitacora import Actor, registrar
from administracion.config import Configuracion
from administracion.identidad_falsa import IdentidadFalsa
from administracion.main import crear_app
from administracion.modelos import CorreoEnviado
from comun.pruebas import ClavesPrueba
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Manejador = Callable[[httpx.Request], Awaitable[httpx.Response]]


async def _ok(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={})


async def _colas(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[{"name": "administracion.actividad", "messages_ready": 0}])


@pytest.fixture
def rutas() -> dict[str, Manejador]:
    """Respuestas de las dependencias por host; cada prueba cambia las que le interesan."""
    return {"prov": _ok, "kc": _ok, "rmq": _colas, "mail": _ok}


@pytest.fixture
async def cliente_sistema(
    urls_bd: tuple[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    claves: ClavesPrueba,
    identidad: IdentidadFalsa,
    rutas: dict[str, Manejador],
) -> AsyncIterator[httpx.AsyncClient]:
    async def manejar(peticion: httpx.Request) -> httpx.Response:
        return await rutas[peticion.url.host](peticion)

    app = crear_app(
        Configuracion(
            database_url=urls_bd[1],
            consumir_eventos=False,
            proveedores_url="http://prov",
            keycloak_url="http://kc/auth",
            rabbitmq_url="amqp://usuario:clave@rmq:5672/",
            rabbitmq_api_url="http://rmq/api",
            mailpit_url="http://mail",
            version_app="abc1234",
        ),
        claves.validador(),
        fabrica,
        identidad,
        transporte_estado=httpx.MockTransport(manejar),
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


async def _estados(cliente: httpx.AsyncClient, admin: dict[str, str]) -> dict[str, Any]:
    respuesta = await cliente.get("/estado", headers=admin)
    assert respuesta.status_code == 200
    return dict(respuesta.json())


async def _por_clave(cliente: httpx.AsyncClient, admin: dict[str, str]) -> dict[str, Any]:
    return {s["clave"]: s for s in (await _estados(cliente, admin))["servicios"]}


async def test_todo_sano(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    vistas: list[httpx.Request] = []

    async def colas(peticion: httpx.Request) -> httpx.Response:
        vistas.append(peticion)
        return await _colas(peticion)

    rutas["rmq"] = colas
    estado = await _estados(cliente_sistema, admin)
    assert estado["version"] == "abc1234"
    servicios = estado["servicios"]
    assert [s["clave"] for s in servicios] == [
        "base_de_datos",
        "proveedores",
        "identidad",
        "mensajeria",
        "correo",
    ]
    assert {s["estado"] for s in servicios} == {"sano"}
    [peticion] = vistas
    assert peticion.url.path == "/api/queues"
    assert peticion.headers["authorization"].startswith("Basic ")


async def test_un_servicio_caido_no_tumba_el_estado(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    async def sin_red(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=peticion)

    async def error(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    rutas["prov"] = sin_red
    rutas["kc"] = error
    servicios = await _por_clave(cliente_sistema, admin)
    assert servicios["proveedores"]["estado"] == "caido"
    assert servicios["proveedores"]["tiempo_ms"] is None
    assert servicios["identidad"]["estado"] == "caido"
    assert servicios["base_de_datos"]["estado"] == "sano"
    assert servicios["correo"]["estado"] == "sano"


async def test_una_cola_atrasada_es_un_problema(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    async def atrasada(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"name": "administracion.actividad", "messages_ready": 150},
                {"name": "otra", "messages_ready": 100},
            ],
        )

    rutas["rmq"] = atrasada
    servicios = await _por_clave(cliente_sistema, admin)
    assert servicios["mensajeria"]["estado"] == "con_problemas"
    assert servicios["mensajeria"]["detalle"] == (
        "Mensajes pendientes en: administracion.actividad (150)."
    )


async def test_lento_y_sin_respuesta(
    cliente_sistema: httpx.AsyncClient,
    admin: dict[str, str],
    rutas: dict[str, Manejador],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("administracion.estado.TIEMPO_LIMITE_S", 0.2)
    monkeypatch.setattr("administracion.estado.UMBRAL_LENTO_S", 0.05)

    async def lento(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.1)
        return httpx.Response(200)

    async def colgado(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200)

    rutas["mail"] = lento
    rutas["kc"] = colgado
    servicios = await _por_clave(cliente_sistema, admin)
    assert servicios["correo"]["estado"] == "con_problemas"
    assert servicios["correo"]["detalle"] == "Responde con lentitud."
    assert servicios["identidad"]["estado"] == "caido"
    assert servicios["identidad"]["detalle"] == "No respondió en 0.2 s."


async def test_resumen(
    cliente_sistema: httpx.AsyncClient,
    admin: dict[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    identidad: IdentidadFalsa,
) -> None:
    identidad.agregar("baja", ["comprador"], activo=False)
    ahora = datetime.now(UTC)
    async with fabrica() as sesion:
        for n, horas in enumerate((1, 5, 30)):
            await registrar(
                sesion,
                "sesion.fallida",
                Actor(None, "fantasma"),
                resultado="fallo",
                origen="keycloak",
                clave_origen=f"k:{n}",
                fecha=ahora - timedelta(hours=horas),
            )
        for dias in (1, 8):
            sesion.add(
                CorreoEnviado(
                    fecha=ahora - timedelta(days=dias),
                    tipo="invitacion",
                    destinatario="ana@x.mx",
                    usuario_id="ana",
                    solicitado_por="admin1",
                    estado="enviado",
                )
            )
        await sesion.commit()
    respuesta = await cliente_sistema.get("/resumen", headers=admin)
    assert respuesta.json() == {
        "usuarios_activos": 2,
        "intentos_fallidos_24h": 2,
        "correos_7d": 1,
    }


async def test_resumen_sin_identidad(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    identidad.caida = True
    respuesta = await cliente_sistema.get("/resumen", headers=admin)
    assert respuesta.status_code == 200
    assert respuesta.json()["usuarios_activos"] is None
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest services/administracion/tests/test_sistema.py -q`
Expected: FAIL (`crear_app` no acepta `transporte_estado`; `/estado` da 404).

- [ ] **Step 3: Configuración**

En `config.py`, agregue a `Configuracion`:

```python
    proveedores_url: str = "http://localhost:8000"
    mailpit_url: str = "http://localhost:8025"
    rabbitmq_api_url: str = "http://localhost:15672/api"
    version_app: str = "desarrollo"
```

- [ ] **Step 4: Comprobaciones**

`services/administracion/src/administracion/estado.py`:

```python
"""Estado de los servicios de la plataforma: cada comprobación con su propio límite de tiempo."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote, urlsplit

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from administracion.config import Configuracion

log = logging.getLogger(__name__)

UMBRAL_LENTO_S = 1.0
TIEMPO_LIMITE_S = 2.0
MAX_MENSAJES_EN_COLA = 100

Estado = Literal["sano", "con_problemas", "caido"]
Prueba = Callable[[], Awaitable[str | None]]  # devuelve un problema, o None si todo está bien


@dataclass(frozen=True)
class Comprobacion:
    clave: str
    nombre: str
    estado: Estado
    tiempo_ms: int | None
    detalle: str


async def medir(clave: str, nombre: str, prueba: Prueba) -> Comprobacion:
    inicio = time.perf_counter()
    try:
        problema = await asyncio.wait_for(prueba(), TIEMPO_LIMITE_S)
    except TimeoutError:
        return Comprobacion(clave, nombre, "caido", None, f"No respondió en {TIEMPO_LIMITE_S:g} s.")
    except Exception as exc:
        log.warning("La comprobación de %s falló: %s", clave, exc)
        return Comprobacion(clave, nombre, "caido", None, "No responde o respondió con un error.")
    ms = round((time.perf_counter() - inicio) * 1000)
    if problema:
        return Comprobacion(clave, nombre, "con_problemas", ms, problema)
    if ms >= UMBRAL_LENTO_S * 1000:
        return Comprobacion(clave, nombre, "con_problemas", ms, "Responde con lentitud.")
    return Comprobacion(clave, nombre, "sano", ms, "Funciona con normalidad.")


def _credenciales(url_amqp: str) -> tuple[str, str]:
    partes = urlsplit(url_amqp)
    return unquote(partes.username or "guest"), unquote(partes.password or "guest")


async def comprobar_todo(
    config: Configuracion, fabrica: async_sessionmaker[AsyncSession], http: httpx.AsyncClient
) -> list[Comprobacion]:
    async def obtener(url: str, auth: tuple[str, str] | None = None) -> httpx.Response:
        respuesta = await http.get(url, auth=auth)
        respuesta.raise_for_status()
        return respuesta

    async def base_de_datos() -> None:
        async with fabrica() as sesion:
            await sesion.execute(text("SELECT 1"))

    async def proveedores() -> None:
        await obtener(f"{config.proveedores_url}/salud/listo")

    async def identidad() -> None:
        await obtener(
            f"{config.keycloak_url}/realms/{config.keycloak_realm}/.well-known/openid-configuration"
        )

    async def mensajeria() -> str | None:
        colas = (
            await obtener(
                f"{config.rabbitmq_api_url}/queues", auth=_credenciales(config.rabbitmq_url)
            )
        ).json()
        atrasadas = [
            f"{c['name']} ({c.get('messages_ready', 0)})"
            for c in colas
            if c.get("messages_ready", 0) > MAX_MENSAJES_EN_COLA
        ]
        return f"Mensajes pendientes en: {', '.join(atrasadas)}." if atrasadas else None

    async def correo() -> None:
        await obtener(f"{config.mailpit_url}/readyz")

    pruebas: list[tuple[str, str, Prueba]] = [
        ("base_de_datos", "Base de datos de administración", base_de_datos),
        ("proveedores", "Servicio de proveedores", proveedores),
        ("identidad", "Identidad (Keycloak)", identidad),
        ("mensajeria", "Mensajería (RabbitMQ)", mensajeria),
        ("correo", "Buzón de correo (Mailpit)", correo),
    ]
    return list(await asyncio.gather(*(medir(c, n, p) for c, n, p in pruebas)))
```

- [ ] **Step 5: Esquemas y rutas**

En `api/esquemas.py`:

```python
class EstadoServicio(BaseModel):
    clave: str
    nombre: str
    estado: Literal["sano", "con_problemas", "caido"]
    tiempo_ms: int | None
    detalle: str


class EstadoSistema(BaseModel):
    version: str
    comprobado_en: datetime
    servicios: list[EstadoServicio]


class Resumen(BaseModel):
    usuarios_activos: int | None
    intentos_fallidos_24h: int
    correos_7d: int
```

`services/administracion/src/administracion/api/sistema.py`:

```python
"""Estado de la plataforma y conteos del panel de administración."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from administracion.api import esquemas
from administracion.api.rutas import Admin, Identidad, Sesion
from administracion.estado import comprobar_todo
from administracion.identidad import IdentidadNoDisponible
from administracion.modelos import Actividad, CorreoEnviado

router = APIRouter(tags=["sistema"])


@router.get("/estado")
async def estado_del_sistema(request: Request, _: Admin) -> esquemas.EstadoSistema:
    estado = request.app.state
    servicios = await comprobar_todo(estado.config, estado.fabrica, estado.http)
    return esquemas.EstadoSistema(
        version=estado.config.version_app,
        comprobado_en=datetime.now(UTC),
        servicios=[esquemas.EstadoServicio(**asdict(s)) for s in servicios],
    )


@router.get("/resumen")
async def resumen(sesion: Sesion, identidad: Identidad, _: Admin) -> esquemas.Resumen:
    ahora = datetime.now(UTC)
    try:
        usuarios_activos: int | None = sum(1 for u in await identidad.listar_usuarios() if u.activo)
    except IdentidadNoDisponible:
        usuarios_activos = None  # el panel lo muestra sin dato; el resto sí carga
    fallidos = await sesion.scalar(
        select(func.count())
        .select_from(Actividad)
        .where(Actividad.tipo == "sesion.fallida", Actividad.fecha >= ahora - timedelta(hours=24))
    )
    correos = await sesion.scalar(
        select(func.count())
        .select_from(CorreoEnviado)
        .where(CorreoEnviado.fecha >= ahora - timedelta(days=7))
    )
    return esquemas.Resumen(
        usuarios_activos=usuarios_activos,
        intentos_fallidos_24h=fallidos or 0,
        correos_7d=correos or 0,
    )
```

En `main.py`: importe `httpx`, `from administracion.api.sistema import router as router_sistema` y `from administracion import estado`; agregue el parámetro `transporte_estado: httpx.AsyncBaseTransport | None = None` a `crear_app`, cree el cliente antes del ciclo de vida

```python
    http = httpx.AsyncClient(timeout=estado.TIEMPO_LIMITE_S, transport=transporte_estado)
```

ciérrelo al final del ciclo de vida (`await http.aclose()`), guárdelo en `app.state.http = http` e incluya `app.include_router(router_sistema)` después de `router`.

- [ ] **Step 6: Infraestructura**

En `infra/docker-compose.yml`, servicio `administracion`, agregue a `environment`:

```yaml
      PROVEEDORES_URL: http://proveedores:8000
      MAILPIT_URL: http://mailpit:8025
      RABBITMQ_API_URL: http://rabbitmq:15672/api
      VERSION_APP: ${VERSION_APP:-desarrollo}
```

- [ ] **Step 7: Correr las pruebas**

Run: `uv run pytest services/administracion -q`
Expected: PASS (la prueba de rutas solo admin ya incluye `/estado` y `/resumen`).

- [ ] **Step 8: Calidad y commit**

```bash
uv run ruff format services/administracion && uv run ruff check services/administracion && uv run mypy
git add services/administracion infra/docker-compose.yml
git commit -m "feat(administracion): estado de los servicios de la plataforma y resumen para el panel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Web — pantalla Actividad con filtros y exportación

**Files:**
- Create:
  - `web/src/componentes/ListaActividad.tsx`
  - `web/src/paginas/Actividad.tsx`, `web/src/paginas/Actividad.test.tsx`
- Modify:
  - `web/src/api.ts` (`descargar`), `web/src/api.test.ts`
  - `web/src/paginas/UsuarioDetalle.tsx` (usa `ListaActividad`; enlace "Ver toda su actividad")
  - `web/src/componentes/navegacion.ts`, `web/src/componentes/navegacion.test.ts`
  - `web/src/rutas.tsx`

**Interfaces:**
- Consumes: `GET /administracion/actividad` y `GET /administracion/actividad/exportar` (Task 5), `GET /administracion/usuarios`, `describirActividad`, `formatoFechaHora`, `nombreCompleto`, `Filtro`, `Paginacion`, `RequiereRol`.
- Produces:
  - `descargar(ruta: string, token: string | undefined, nombre: string): Promise<void>` en `api.ts` (lanza `ErrorApi` como `pedir`).
  - `ListaActividad({ elementos: RegistroActividad[]; personaId?: string })`: la lista de la bitácora que también usan el Panel y el Estado del sistema (Task 9).
  - Página `Actividad` en `/sistema/actividad`; parámetros de URL `persona`, `tipo` (`sesiones` / `usuarios` / `importaciones` / `catalogo`), `desde`, `hasta`, `pagina`.
  - Menú: "Actividad" ("Quién hizo qué y cuándo"), después de "Usuarios".

- [ ] **Step 1: Pruebas (fallan)**

En `web/src/api.test.ts` agregue (importe `descargar`):

```ts
describe("descargar", () => {
  it("baja el archivo con el token y lo guarda con su nombre", async () => {
    const simulado = simular("a,b\n", 200, "text/csv")
    const crear = vi.fn(() => "blob:archivo")
    const revocar = vi.fn()
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: crear, revokeObjectURL: revocar }))
    const clic = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        expect(this.download).toBe("actividad.csv")
        expect(this.href).toBe("blob:archivo")
      })

    await descargar("/administracion/actividad/exportar?tipo=sesiones", "tk", "actividad.csv")

    const [url, init] = simulado.mock.calls[0]
    expect(url).toBe("/api/administracion/actividad/exportar?tipo=sesiones")
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tk")
    expect(clic).toHaveBeenCalledOnce()
    expect(revocar).toHaveBeenCalledWith("blob:archivo")
    clic.mockRestore()
  })

  it("convierte un error de la API en ErrorApi", async () => {
    simular(
      JSON.stringify({ title: "Solicitud inválida", detail: "Revise los campos indicados." }),
      422,
      "application/problem+json"
    )
    const error = await errorDe(descargar("/x", "tk", "x.csv"))
    expect(error.estado).toBe(422)
  })
})
```

`web/src/paginas/Actividad.test.tsx`:

```tsx
import { cleanup, fireEvent, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Actividad } from "@/paginas/Actividad"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const USUARIOS = {
  total: 1,
  elementos: [
    {
      id: "u-ana",
      usuario: "ana",
      nombre: "Ana",
      apellidos: "López",
      correo: "ana@plataforma.example",
      roles: ["comprador"],
      activo: true,
      creado_en: "2026-10-01T00:00:00Z",
      ultimo_acceso: null,
    },
  ],
}

const REGISTROS = {
  total: 2,
  elementos: [
    {
      id: "r2",
      fecha: "2026-10-09T18:00:00Z",
      actor_id: "admin-1",
      actor_nombre: "admin1",
      tipo: "importacion.completada",
      objeto_tipo: "importacion",
      objeto_id: "contratos",
      objeto_nombre: "contratos",
      detalle: { registros: 1250, filas: 1300, omitidos: 50 },
      resultado: "exito",
      ip: "10.0.0.7",
    },
    {
      id: "r1",
      fecha: "2026-10-09T17:00:00Z",
      actor_id: null,
      actor_nombre: "fantasma",
      tipo: "sesion.fallida",
      objeto_tipo: null,
      objeto_id: null,
      objeto_nombre: null,
      detalle: { error: "user_not_found" },
      resultado: "fallo",
      ip: null,
    },
  ],
}

function api(pagina = REGISTROS) {
  return simularApi((url) => {
    if (url.startsWith("/api/administracion/usuarios")) return respuestaJson(USUARIOS)
    if (url.startsWith("/api/administracion/actividad/exportar"))
      return new Response("Fecha\n", { status: 200, headers: { "Content-Type": "text/csv" } })
    return respuestaJson(pagina)
  })
}

const llamadasDeLista = (simulado: ReturnType<typeof api>) =>
  simulado.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.startsWith("/api/administracion/actividad?"))

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("Actividad", () => {
  it("muestra quién hizo qué, con el resultado en texto", async () => {
    api()
    const { container } = renderizarPagina(<Actividad />, { ruta: "/sistema/actividad" })
    expect(await screen.findByText("Importó 1,250 contratos")).toBeInTheDocument()
    const fallida = screen
      .getByText("Intento fallido de inicio de sesión: usuario inexistente")
      .closest("tr")!
    expect(within(fallida).getByText("fantasma")).toBeInTheDocument()
    expect(within(fallida).getByText("Falló")).toBeInTheDocument()
    expect(screen.getByText("Mostrando 1–2 de 2 registros")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("los filtros viajan en la URL y en la consulta", async () => {
    const simulado = api()
    renderizarPagina(<Actividad />, { ruta: "/sistema/actividad?persona=u-ana" })
    await screen.findByText("Importó 1,250 contratos")
    const primera = new URL(llamadasDeLista(simulado)[0], "http://localhost")
    expect(primera.searchParams.get("persona")).toBe("u-ana")
    expect(screen.getByRole("combobox", { name: "Persona" })).toHaveTextContent(
      "Ana López (ana)"
    )

    await userEvent.click(screen.getByRole("button", { name: "Importaciones" }))
    expect(ubicacionActual()).toBe("/sistema/actividad?persona=u-ana&tipo=importaciones")
    // jsdom no escribe tecla por tecla en un campo de fecha: se cambia el valor completo.
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-01" } })
    expect(ubicacionActual()).toContain("desde=2026-10-01")
    await screen.findByText("Importó 1,250 contratos")
    const ultima = new URL(llamadasDeLista(simulado).at(-1)!, "http://localhost")
    expect(ultima.searchParams.get("tipo")).toBe("importaciones")
    expect(ultima.searchParams.get("desde")).toBe("2026-10-01")
  })

  it("un rango invertido avisa junto a las fechas y no consulta", async () => {
    const simulado = api()
    renderizarPagina(<Actividad />, {
      ruta: "/sistema/actividad?desde=2026-10-09&hasta=2026-10-01",
    })
    expect(
      await screen.findByText("La fecha final debe ser igual o posterior a la inicial.")
    ).toBeInTheDocument()
    expect(screen.getByLabelText("Hasta")).toHaveAttribute("aria-invalid", "true")
    expect(llamadasDeLista(simulado)).toEqual([])
  })

  it("exporta con los mismos filtros y avisa del límite", async () => {
    const simulado = api({ ...REGISTROS, total: 12_000 })
    vi.stubGlobal(
      "URL",
      Object.assign(URL, { createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() })
    )
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
    renderizarPagina(<Actividad />, { ruta: "/sistema/actividad?tipo=sesiones" })
    expect(
      await screen.findByText(
        "Se exportarán los 10,000 registros más recientes; acote las fechas para obtener el resto."
      )
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: /Exportar CSV/ }))
    const exportacion = simulado.mock.calls
      .map(([url]) => String(url))
      .find((url) => url.startsWith("/api/administracion/actividad/exportar"))
    expect(exportacion).toBe("/api/administracion/actividad/exportar?tipo=sesiones")
    expect(screen.getByRole("button", { name: /Exportar CSV/ })).toHaveFocus()
  })

  it("sin resultados con filtros ofrece limpiarlos", async () => {
    api({ total: 0, elementos: [] })
    renderizarPagina(<Actividad />, { ruta: "/sistema/actividad?tipo=catalogo" })
    expect(await screen.findByText("Sin resultados")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Limpiar filtros" }))
    expect(ubicacionActual()).toBe("/sistema/actividad")
  })

  it("solo administración ve la bitácora", () => {
    sesionDePrueba.roles = ["comprador"]
    api()
    renderizarPagina(<Actividad />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })
})
```

En `navegacion.test.ts`:
- en `"descripciones del menú"`, agregue `Actividad: "Quién hizo qué y cuándo"` después de `Usuarios`;
- en `migasDe`, agregue el caso `["/sistema/actividad", [{ titulo: "Sistema" }, { titulo: "Actividad" }]]`.

- [ ] **Step 2: Correr y ver que fallan**

Run: `(cd web && npx vitest run src/api.test.ts src/paginas/Actividad.test.tsx src/componentes/navegacion.test.ts)`
Expected: FAIL (`descargar` y `@/paginas/Actividad` no existen).

- [ ] **Step 3: `descargar` en la capa de API**

En `web/src/api.ts`, extraiga la construcción del error y la petición para compartirlas:

```ts
/** Hace la petición con el token; sin red, lanza un ErrorApi en español. */
async function hacerPeticion(
  ruta: string,
  token: string | undefined,
  init: RequestInit
): Promise<Response> {
  const cabeceras = new Headers(init.headers)
  if (token) cabeceras.set("Authorization", `Bearer ${token}`)
  try {
    return await fetch(`/api${ruta}`, { ...init, headers: cabeceras })
  } catch (error) {
    // Una cancelación pedida por el llamador no es un fallo de red.
    if (init.signal?.aborted) throw error
    // fetch rechaza, con un mensaje en inglés, cuando no hay red o el gateway no responde.
    throw new ErrorApi(
      0,
      "Sin conexión",
      "No se pudo conectar con el servidor; revise su conexión e intente de nuevo."
    )
  }
}

/** ErrorApi a partir de una respuesta de error, con o sin Problem Details. */
async function errorDeRespuesta(respuesta: Response): Promise<ErrorApi> {
  const cuerpo: unknown = await respuesta.json().catch(() => null)
  const problema =
    typeof cuerpo === "object" && cuerpo !== null
      ? (cuerpo as {
          title?: string
          detail?: string
          errores?: ErrorFila[]
          codigo?: string
        })
      : {}
  const porDefecto = problemaPorEstado(respuesta.status)
  return new ErrorApi(
    respuesta.status,
    problema.title ?? porDefecto.titulo,
    problema.detail ?? porDefecto.detalle,
    problema.errores ?? [],
    problema.codigo ?? null
  )
}

export async function pedir<T>(
  ruta: string,
  token: string | undefined,
  init: RequestInit = {}
): Promise<T> {
  const respuesta = await hacerPeticion(ruta, token, init)
  if (!respuesta.ok) throw await errorDeRespuesta(respuesta)
  if (respuesta.status === 204) return undefined as T
  return (await respuesta.json()) as T
}

/** Descarga un archivo de la API con el token (un enlace normal no lo enviaría). */
export async function descargar(
  ruta: string,
  token: string | undefined,
  nombre: string
): Promise<void> {
  const respuesta = await hacerPeticion(ruta, token, {})
  if (!respuesta.ok) throw await errorDeRespuesta(respuesta)
  const url = URL.createObjectURL(await respuesta.blob())
  const enlace = document.createElement("a")
  enlace.href = url
  enlace.download = nombre
  document.body.append(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
}
```

(`pedir` reemplaza a la versión anterior; su comportamiento no cambia).

- [ ] **Step 4: `ListaActividad`**

`web/src/componentes/ListaActividad.tsx`:

```tsx
import { describirActividad } from "@/actividad"
import { Badge } from "@/components/ui/badge"
import { formatoFechaHora } from "@/fechas"
import type { RegistroActividad } from "@/tipos"

/** Registros de la bitácora; si `personaId` es quien actuó, no se repite su nombre. */
export function ListaActividad({
  elementos,
  personaId,
}: {
  elementos: RegistroActividad[]
  personaId?: string
}) {
  return (
    <ul className="divide-y">
      {elementos.map((a) => (
        <li
          key={a.id}
          className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-sm"
        >
          <time
            dateTime={a.fecha}
            className="w-44 shrink-0 text-muted-foreground"
          >
            {formatoFechaHora(a.fecha)}
          </time>
          <span className="min-w-0 flex-1">
            {a.actor_id !== personaId && (
              <span className="font-medium">{a.actor_nombre}: </span>
            )}
            {describirActividad(a)}
          </span>
          {a.resultado === "fallo" && <Badge variant="destructive">Falló</Badge>}
        </li>
      ))}
    </ul>
  )
}
```

En `UsuarioDetalle.tsx`, dentro de `ActividadReciente`:
- reemplace el `<ul>…</ul>` por `<ListaActividad elementos={consulta.data.elementos} personaId={usuarioId} />` (quite los imports que dejen de usarse);
- agregue a la `Seccion` la prop

```tsx
      acciones={
        <Link
          to={`/sistema/actividad?persona=${encodeURIComponent(usuarioId)}`}
          className="text-sm font-medium text-accent hover:underline"
        >
          Ver toda su actividad
        </Link>
      }
```

(importe `Link` de `react-router` si aún no está).

- [ ] **Step 5: Página Actividad**

`web/src/paginas/Actividad.tsx`:

```tsx
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { CircleCheck, CircleX, Download, History, X } from "lucide-react"
import { useId, useState } from "react"
import { descargar, pedir } from "@/api"
import { describirActividad } from "@/actividad"
import { useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Filtro } from "@/componentes/Filtro"
import { Paginacion } from "@/componentes/Paginacion"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora } from "@/fechas"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import type { PaginaActividad, PaginaUsuarios } from "@/tipos"
import { nombreCompleto } from "@/usuarios"

const POR_PAGINA = 25
const MAX_EXPORTACION = 10_000
// Radix Select no admite el valor vacío: "todas" representa "sin filtro".
const TODAS = "todas"
const GRUPOS = [
  ["sesiones", "Sesiones"],
  ["usuarios", "Usuarios"],
  ["importaciones", "Importaciones"],
  ["catalogo", "Catálogo"],
] as const
const CLAVES_GRUPO = GRUPOS.map(([clave]) => clave)
const FECHA_MINIMA = "2000-01-01"
const FECHA_MAXIMA = "2100-12-31"

/** AAAA-MM-DD dentro del rango que acepta la API; otro valor cuenta como "sin filtro". */
function fecha(valor: string | null): string | null {
  return valor &&
    /^\d{4}-\d{2}-\d{2}$/.test(valor) &&
    valor >= FECHA_MINIMA &&
    valor <= FECHA_MAXIMA
    ? valor
    : null
}

export function Actividad() {
  return (
    <RequiereRol rol="admin">
      <ContenidoActividad />
    </RequiereRol>
  )
}

function ContenidoActividad() {
  const token = useToken()
  const id = useId()
  const [parametros, actualizar] = useParametros()
  const persona = parametros.get("persona")?.slice(0, 64) || null
  const tipo = unoDe(parametros.get("tipo"), CLAVES_GRUPO)
  const desde = fecha(parametros.get("desde"))
  const hasta = fecha(parametros.get("hasta"))
  const pagina = enteroPositivo(parametros.get("pagina"), 1, 10_000)
  const rangoInvalido = Boolean(desde && hasta && hasta < desde)
  const hayFiltros = Boolean(persona || tipo || desde || hasta)
  const [exportando, setExportando] = useState(false)
  const [errorExportacion, setErrorExportacion] = useState<string | null>(null)

  const filtros = new URLSearchParams()
  if (persona) filtros.set("persona", persona)
  if (tipo) filtros.set("tipo", tipo)
  if (desde) filtros.set("desde", desde)
  if (hasta) filtros.set("hasta", hasta)

  // ponytail: la lista del filtro trae hasta 100 personas; con más, cambiar a búsqueda por texto.
  const personas = useQuery({
    queryKey: ["usuarios", "filtro-actividad"],
    queryFn: () =>
      pedir<PaginaUsuarios>("/administracion/usuarios?tamano=100", token),
    enabled: Boolean(token),
  })
  const consulta = useQuery({
    queryKey: ["actividad", "lista", { persona, tipo, desde, hasta, pagina }],
    queryFn: () => {
      const busqueda = new URLSearchParams(filtros)
      busqueda.set("pagina", String(pagina))
      busqueda.set("tamano", String(POR_PAGINA))
      return pedir<PaginaActividad>(
        `/administracion/actividad?${busqueda}`,
        token
      )
    },
    enabled: Boolean(token) && !rangoInvalido,
    placeholderData: keepPreviousData,
  })

  async function exportar() {
    if (exportando || rangoInvalido) return
    setExportando(true)
    setErrorExportacion(null)
    try {
      await descargar(
        `/administracion/actividad/exportar?${filtros}`,
        token,
        "actividad.csv"
      )
    } catch (error) {
      setErrorExportacion(
        error instanceof Error ? error.message : "No se pudo exportar."
      )
    } finally {
      setExportando(false)
    }
  }

  const limpiar = () =>
    actualizar({
      persona: null,
      tipo: null,
      desde: null,
      hasta: null,
      pagina: null,
    })
  const opcionesPersona = personas.data?.elementos ?? []
  const personaConocida = opcionesPersona.some((u) => u.id === persona)

  function contenido() {
    if (rangoInvalido) return null
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError)
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    const { total, elementos } = consulta.data
    if (elementos.length === 0)
      return hayFiltros ? (
        <EstadoVacio
          titulo="Sin resultados"
          descripcion="Ningún registro coincide con los filtros."
          accion={
            <Button type="button" variant="ghost" onClick={limpiar}>
              <X aria-hidden />
              Limpiar filtros
            </Button>
          }
        />
      ) : (
        <EstadoVacio
          icono={History}
          titulo="Aún no hay actividad registrada"
          descripcion="Aquí aparecerán los inicios de sesión, las acciones sobre usuarios, las importaciones y los cambios del catálogo."
        />
      )
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Persona</TableHead>
              <TableHead>Acción</TableHead>
              <TableHead>Resultado</TableHead>
              <TableHead>IP</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((a) => (
              <TableRow key={a.id}>
                <TableCell>
                  <time dateTime={a.fecha}>{formatoFechaHora(a.fecha)}</time>
                </TableCell>
                <TableCell>{a.actor_nombre}</TableCell>
                <TableCell className="whitespace-normal">
                  {describirActividad(a)}
                </TableCell>
                <TableCell>
                  {a.resultado === "exito" ? (
                    <Badge variant="success">
                      <CircleCheck aria-hidden />
                      Éxito
                    </Badge>
                  ) : (
                    <Badge variant="destructive">
                      <CircleX aria-hidden />
                      Falló
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {a.ip ?? (
                    <>
                      <span aria-hidden>—</span>
                      <span className="sr-only">Sin IP</span>
                    </>
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
          nombre="registros"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Actividad"
        descripcion="Quién hizo qué y cuándo: inicios de sesión, cambios de usuarios, importaciones y catálogo. Nada de esto se puede borrar."
        acciones={
          <Button
            variant="outline"
            aria-disabled={exportando || rangoInvalido}
            onClick={() => void exportar()}
          >
            <Download aria-hidden />
            {exportando ? "Exportando…" : "Exportar CSV"}
          </Button>
        }
      />
      {consulta.data && consulta.data.total > MAX_EXPORTACION && (
        <p className="text-sm text-muted-foreground">
          Se exportarán los 10,000 registros más recientes; acote las fechas para
          obtener el resto.
        </p>
      )}
      {errorExportacion && (
        <p role="alert" className="text-sm text-destructive">
          {errorExportacion}
        </p>
      )}
      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="grid gap-1.5">
              <span id={`${id}-persona`} className="text-sm font-medium">
                Persona
              </span>
              <Select
                value={persona ?? TODAS}
                onValueChange={(v) =>
                  actualizar({ persona: v === TODAS ? null : v, pagina: null })
                }
              >
                <SelectTrigger aria-labelledby={`${id}-persona`} className="w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={TODAS}>Todas las personas</SelectItem>
                  {persona && !personaConocida && (
                    <SelectItem value={persona}>{persona}</SelectItem>
                  )}
                  {opcionesPersona.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {nombreCompleto(u)} ({u.usuario})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}-desde`}>Desde</Label>
              <Input
                id={`${id}-desde`}
                type="date"
                min={FECHA_MINIMA}
                max={FECHA_MAXIMA}
                value={desde ?? ""}
                onChange={(e) =>
                  actualizar({ desde: e.target.value || null, pagina: null })
                }
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}-hasta`}>Hasta</Label>
              <Input
                id={`${id}-hasta`}
                type="date"
                min={FECHA_MINIMA}
                max={FECHA_MAXIMA}
                value={hasta ?? ""}
                aria-invalid={rangoInvalido || undefined}
                aria-describedby={rangoInvalido ? `${id}-rango` : undefined}
                onChange={(e) =>
                  actualizar({ hasta: e.target.value || null, pagina: null })
                }
              />
            </div>
            {hayFiltros && (
              <Button type="button" variant="ghost" onClick={limpiar}>
                <X aria-hidden />
                Limpiar filtros
              </Button>
            )}
          </div>
          {rangoInvalido && (
            <p id={`${id}-rango`} role="alert" className="text-sm text-destructive">
              La fecha final debe ser igual o posterior a la inicial.
            </p>
          )}
          <div
            role="group"
            aria-label="Filtrar por tipo"
            className="flex flex-wrap gap-2"
          >
            <Filtro
              activo={!tipo}
              onClick={() => actualizar({ tipo: null, pagina: null })}
            >
              Todos
            </Filtro>
            {GRUPOS.map(([clave, nombre]) => (
              <Filtro
                key={clave}
                activo={tipo === clave}
                onClick={() => actualizar({ tipo: clave, pagina: null })}
              >
                {nombre}
              </Filtro>
            ))}
          </div>
          {contenido()}
        </CardContent>
      </Card>
    </section>
  )
}
```

- [ ] **Step 6: Menú y ruta**

En `navegacion.ts`, importe `History` de `lucide-react` y agregue después de "Usuarios":

```ts
      {
        titulo: "Actividad",
        ruta: "/sistema/actividad",
        descripcion: "Quién hizo qué y cuándo",
        icono: History,
        soloAdmin: true,
      },
```

En `rutas.tsx`, importe `Actividad` y agregue `{ path: "sistema/actividad", Component: Actividad },` antes de `"*"`.

- [ ] **Step 7: Correr las pruebas**

Run: `(cd web && npx vitest run)`
Expected: PASS, sin advertencias.

- [ ] **Step 8: Calidad y commit**

```bash
(cd web && npx prettier --write src && npm run lint && npm run build)
git add web/src
git commit -m "feat(web): pantalla Actividad con filtros en la URL y exportación a CSV" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Web — Catálogo de servicios

**Files:**
- Create:
  - `web/src/componentes/FormularioServicio.tsx`
  - `web/src/paginas/Catalogo.tsx`, `web/src/paginas/Catalogo.test.tsx`
- Modify:
  - `web/src/tipos.ts` (`Servicio`, `Unidad`, `NOMBRES_UNIDAD`, `UNIDADES`, `MONEDAS`)
  - `web/src/componentes/navegacion.ts`, `web/src/componentes/navegacion.test.ts`
  - `web/src/rutas.tsx`

**Interfaces:**
- Consumes: `GET /proveedores/servicios?incluir_inactivos=true`, `POST /proveedores/servicios`, `PATCH /proveedores/servicios/{codigo}` (Task 1); `ConfirmarAccion`, `EtiquetaEstado`, `Filtro`, `enviarJson`, `erroresPorCampo`.
- Produces:
  - `Servicio` = `{id, codigo, nombre, categoria, unidad, moneda, activo, tiene_contratos}`.
  - `FormularioServicio({ abierto, alCambiarAbierto, servicio, devolverFoco, alGuardar })`: `servicio` `null` es alta.
  - Página `Catalogo` en `/sistema/catalogo`; parámetros de URL `categoria` y `estado` (`activos` / `inactivos`).
  - Menú: "Catálogo" ("Servicios de TI que se compran"), después de "Actividad".
  - Las consultas `["servicios", …]` se invalidan al guardar (Precios usa `["servicios"]`).

- [ ] **Step 1: Pruebas (fallan)**

`web/src/paginas/Catalogo.test.tsx`:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Catalogo } from "@/paginas/Catalogo"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const SAAS = {
  id: "s1",
  codigo: "SAAS-OFI-EMP",
  nombre: "Suite de productividad",
  categoria: "licencia_saas",
  unidad: "usuario_mes",
  moneda: "USD",
  activo: true,
  tiene_contratos: true,
}
const MESA = {
  id: "s2",
  codigo: "SOP-MESA-TK",
  nombre: "Mesa de ayuda",
  categoria: "soporte",
  unidad: "ticket",
  moneda: "MXN",
  activo: false,
  tiene_contratos: false,
}

/** API simulada del catálogo; un PATCH a SAAS-OFI-EMP alterna su estado. */
function catalogo(alta?: () => Response) {
  let saas = { ...SAAS }
  return simularApi((url) => {
    if (url === "/api/proveedores/servicios?incluir_inactivos=true")
      return respuestaJson([saas, MESA])
    if (url === "/api/proveedores/servicios")
      return alta ? alta() : respuestaJson({ ...MESA, codigo: "NUBE-VM-2" }, 201)
    if (url === "/api/proveedores/servicios/SAAS-OFI-EMP") {
      saas = { ...saas, activo: !saas.activo }
      return respuestaJson(saas)
    }
    return new Response("", { status: 404 })
  })
}

function cuerpos(simulado: ReturnType<typeof catalogo>, metodo: string) {
  return simulado.mock.calls
    .map((llamada) => llamada as unknown as [string, RequestInit | undefined])
    .filter(([, init]) => init?.method === metodo)
    .map(([url, init]) => [url, JSON.parse(String(init?.body))])
}

async function elegir(combo: string, opcion: string) {
  await userEvent.click(screen.getByRole("combobox", { name: combo }))
  await userEvent.click(await screen.findByRole("option", { name: opcion }))
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Catalogo", () => {
  it("lista los servicios con nombres legibles y su estado en texto", async () => {
    catalogo()
    const { container } = renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    const fila = (await screen.findByText("Suite de productividad")).closest("tr")!
    expect(within(fila).getByText("Licencias SaaS")).toBeInTheDocument()
    expect(within(fila).getByText("Usuario al mes")).toBeInTheDocument()
    expect(within(fila).getByText("Activo")).toBeInTheDocument()
    const inactiva = screen.getByText("Mesa de ayuda").closest("tr")!
    expect(within(inactiva).getByText("Inactivo")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("filtra por estado y categoría desde la URL", async () => {
    catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(screen.getByRole("button", { name: "Inactivos" }))
    expect(ubicacionActual()).toBe("/sistema/catalogo?estado=inactivos")
    expect(screen.queryByText("Suite de productividad")).not.toBeInTheDocument()
    expect(screen.getByText("Mesa de ayuda")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Nube" }))
    expect(await screen.findByText("Sin resultados")).toBeInTheDocument()
  })

  it("da de alta un servicio y devuelve el foco a «Nuevo servicio»", async () => {
    const simulado = catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(screen.getByRole("button", { name: "Nuevo servicio" }))
    await userEvent.type(screen.getByLabelText("Código"), "nube-vm-2")
    await userEvent.type(screen.getByLabelText("Nombre"), "Máquina virtual")
    await elegir("Categoría", "Nube")
    await elegir("Unidad", "vCPU al mes")
    await elegir("Moneda", "USD")
    await userEvent.click(screen.getByRole("button", { name: "Dar de alta" }))

    expect(
      await screen.findByText("Se dio de alta el servicio NUBE-VM-2.")
    ).toBeInTheDocument()
    expect(cuerpos(simulado, "POST")).toEqual([
      [
        "/api/proveedores/servicios",
        {
          codigo: "nube-vm-2",
          nombre: "Máquina virtual",
          categoria: "nube",
          unidad: "vcpu_mes",
          moneda: "USD",
        },
      ],
    ])
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Nuevo servicio" })).toHaveFocus()
    )
  })

  it("un código repetido se marca junto al campo", async () => {
    catalogo(() =>
      respuestaJson(
        {
          title: "Conflicto",
          detail: "Ya existe un servicio con ese código.",
          codigo: "servicio_duplicado",
          errores: [{ campo: "codigo", mensaje: "Ya existe un servicio con ese código." }],
        },
        409
      )
    )
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(screen.getByRole("button", { name: "Nuevo servicio" }))
    await userEvent.type(screen.getByLabelText("Código"), "SOP-MESA-TK")
    await userEvent.type(screen.getByLabelText("Nombre"), "Otra")
    await elegir("Categoría", "Soporte")
    await elegir("Unidad", "Ticket")
    await elegir("Moneda", "MXN")
    await userEvent.click(screen.getByRole("button", { name: "Dar de alta" }))
    expect(
      await screen.findByText("Ya existe un servicio con ese código.")
    ).toBeInTheDocument()
    expect(screen.getByLabelText("Código")).toHaveAttribute("aria-invalid", "true")
  })

  it("con contratos bloquea categoría y moneda y solo envía lo que cambió", async () => {
    const simulado = catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(screen.getByRole("button", { name: "Editar SAAS-OFI-EMP" }))
    expect(screen.getByLabelText("Código")).toHaveAttribute("readonly")
    for (const combo of ["Categoría", "Moneda"]) {
      const campo = screen.getByRole("combobox", { name: combo })
      expect(campo).toBeDisabled()
      expect(campo).toHaveAccessibleDescription(
        "La categoría y la moneda no se pueden cambiar: el servicio ya tiene contratos y sus precios dependen de ellas."
      )
    }
    const nombre = screen.getByLabelText("Nombre")
    await userEvent.clear(nombre)
    await userEvent.type(nombre, "Suite de oficina")
    await userEvent.click(screen.getByRole("button", { name: "Guardar cambios" }))
    await screen.findByText("Se guardaron los cambios de SAAS-OFI-EMP.")
    expect(cuerpos(simulado, "PATCH")).toEqual([
      ["/api/proveedores/servicios/SAAS-OFI-EMP", { nombre: "Suite de oficina" }],
    ])
  })

  it("desactiva con confirmación y deja el foco en «Activar»", async () => {
    const simulado = catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(screen.getByRole("button", { name: "Desactivar SAAS-OFI-EMP" }))
    await userEvent.click(await screen.findByRole("button", { name: "Desactivar" }))

    expect(
      await screen.findByText("Se desactivó el servicio SAAS-OFI-EMP.")
    ).toBeInTheDocument()
    expect(cuerpos(simulado, "PATCH")).toEqual([
      ["/api/proveedores/servicios/SAAS-OFI-EMP", { activo: false }],
    ])
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Activar SAAS-OFI-EMP" })).toHaveFocus()
    )
  })

  it("solo administración edita el catálogo", () => {
    sesionDePrueba.roles = ["comprador"]
    catalogo()
    renderizarPagina(<Catalogo />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })
})
```

En `navegacion.test.ts`:
- en `"descripciones del menú"`, agregue `Catálogo: "Servicios de TI que se compran"` después de `Actividad`;
- en `migasDe`, agregue `["/sistema/catalogo", [{ titulo: "Sistema" }, { titulo: "Catálogo" }]]`.

- [ ] **Step 2: Correr y ver que fallan**

Run: `(cd web && npx vitest run src/paginas/Catalogo.test.tsx src/componentes/navegacion.test.ts)`
Expected: FAIL (`@/paginas/Catalogo` no existe).

- [ ] **Step 3: Tipos**

En `web/src/tipos.ts`, reemplace `Servicio` y agregue las unidades y monedas:

```ts
export type Unidad =
  | "usuario_mes"
  | "vcpu_mes"
  | "gb_mes"
  | "mes"
  | "hora"
  | "ticket"

export const NOMBRES_UNIDAD: Record<Unidad, string> = {
  usuario_mes: "Usuario al mes",
  vcpu_mes: "vCPU al mes",
  gb_mes: "GB al mes",
  mes: "Mes",
  hora: "Hora",
  ticket: "Ticket",
}

export const UNIDADES = Object.keys(NOMBRES_UNIDAD) as Unidad[]
export const MONEDAS = ["MXN", "USD"] as const
export type Moneda = (typeof MONEDAS)[number]

export type Servicio = {
  id: string
  codigo: string
  nombre: string
  categoria: Categoria
  unidad: string
  moneda: Moneda
  activo: boolean
  tiene_contratos: boolean
}
```

- [ ] **Step 4: Formulario del servicio**

`web/src/componentes/FormularioServicio.tsx`:

```tsx
import { useMutation } from "@tanstack/react-query"
import { CircleAlert } from "lucide-react"
import { useId, useState, type FormEvent, type RefObject } from "react"
import { enviarJson, erroresPorCampo, ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  CATEGORIAS,
  MONEDAS,
  NOMBRES_CATEGORIA,
  NOMBRES_UNIDAD,
  UNIDADES,
  type Servicio,
} from "@/tipos"

type Valores = {
  codigo: string
  nombre: string
  categoria: string
  unidad: string
  moneda: string
}
const EDITABLES = ["nombre", "categoria", "unidad", "moneda"] as const
const AYUDA_CODIGO =
  "Letras, números y guiones (3 a 30). No cambia después de crearlo: las importaciones lo usan para identificar el servicio."
const AVISO_CONTRATOS =
  "La categoría y la moneda no se pueden cambiar: el servicio ya tiene contratos y sus precios dependen de ellas."

/** Alta (servicio null) o edición de un servicio del catálogo, en un panel lateral. */
export function FormularioServicio({
  abierto,
  alCambiarAbierto,
  servicio,
  devolverFoco,
  alGuardar,
}: {
  abierto: boolean
  alCambiarAbierto: (abierto: boolean) => void
  servicio: Servicio | null
  /** El panel se abre por estado, sin disparador: este elemento recibe el foco al cerrarlo. */
  devolverFoco: RefObject<HTMLElement | null>
  alGuardar: (guardado: Servicio, esAlta: boolean) => void
}) {
  const token = useToken()
  const id = useId()
  const esAlta = servicio === null
  const bloqueado = servicio?.tiene_contratos ?? false
  const [valores, setValores] = useState<Valores>({
    codigo: servicio?.codigo ?? "",
    nombre: servicio?.nombre ?? "",
    categoria: servicio?.categoria ?? "",
    unidad: servicio?.unidad ?? "",
    moneda: servicio?.moneda ?? "",
  })
  const mutacion = useMutation({
    mutationFn: (datos: object) =>
      esAlta
        ? pedir<Servicio>(
            "/proveedores/servicios",
            token,
            enviarJson("POST", datos)
          )
        : pedir<Servicio>(
            `/proveedores/servicios/${encodeURIComponent(servicio.codigo)}`,
            token,
            enviarJson("PATCH", datos)
          ),
    onSuccess: (guardado) => {
      alCambiarAbierto(false)
      alGuardar(guardado, esAlta)
    },
  })
  const errores = erroresPorCampo(mutacion.error)
  const errorGeneral =
    mutacion.error && Object.keys(errores).length === 0 ? mutacion.error : null

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (mutacion.isPending) return
    if (esAlta) {
      mutacion.mutate(valores)
      return
    }
    const cambios = Object.fromEntries(
      EDITABLES.filter((c) => valores[c] !== servicio[c]).map((c) => [
        c,
        valores[c],
      ])
    )
    if (Object.keys(cambios).length === 0) {
      alCambiarAbierto(false)
      return
    }
    mutacion.mutate(cambios)
  }

  function campoTexto(campo: "codigo" | "nombre", etiqueta: string) {
    const error = errores[campo]
    const ayuda = campo === "codigo" ? AYUDA_CODIGO : null
    const descritoPor =
      [ayuda && `${id}-${campo}-ayuda`, error && `${id}-${campo}-error`]
        .filter(Boolean)
        .join(" ") || undefined
    return (
      <div className="grid gap-1.5">
        <Label htmlFor={`${id}-${campo}`}>{etiqueta}</Label>
        <Input
          id={`${id}-${campo}`}
          value={valores[campo]}
          readOnly={campo === "codigo" && !esAlta}
          onChange={(e) =>
            setValores((v) => ({ ...v, [campo]: e.target.value }))
          }
          autoComplete="off"
          aria-invalid={error ? true : undefined}
          aria-describedby={descritoPor}
        />
        {ayuda && (
          <p id={`${id}-${campo}-ayuda`} className="text-xs text-muted-foreground">
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
  }

  function campoLista(
    campo: "categoria" | "unidad" | "moneda",
    etiqueta: string,
    opciones: [string, string][],
    soloSinContratos = false
  ) {
    const error = errores[campo]
    const deshabilitado = soloSinContratos && bloqueado
    const descritoPor =
      [deshabilitado && `${id}-contratos`, error && `${id}-${campo}-error`]
        .filter(Boolean)
        .join(" ") || undefined
    return (
      <div className="grid gap-1.5">
        <span id={`${id}-${campo}`} className="text-sm font-medium">
          {etiqueta}
        </span>
        <Select
          value={valores[campo] || undefined}
          disabled={deshabilitado}
          onValueChange={(v) => setValores((previos) => ({ ...previos, [campo]: v }))}
        >
          <SelectTrigger
            aria-labelledby={`${id}-${campo}`}
            aria-describedby={descritoPor}
            aria-invalid={error ? true : undefined}
            className="w-full"
          >
            <SelectValue placeholder="Elija una opción" />
          </SelectTrigger>
          <SelectContent>
            {opciones.map(([valor, nombre]) => (
              <SelectItem key={valor} value={valor}>
                {nombre}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {error && (
          <p id={`${id}-${campo}-error`} className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
    )
  }

  return (
    <Sheet
      open={abierto}
      onOpenChange={(siguiente) => {
        if (!siguiente) mutacion.reset()
        alCambiarAbierto(siguiente)
      }}
    >
      <SheetContent
        className="overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-md"
        onCloseAutoFocus={(evento) => {
          evento.preventDefault()
          devolverFoco.current?.focus()
        }}
      >
        <SheetHeader>
          <SheetTitle>
            {esAlta ? "Nuevo servicio" : `Editar ${servicio.codigo}`}
          </SheetTitle>
          <SheetDescription>
            Los servicios del catálogo son los que aparecen en los contratos y en
            Precios.
          </SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={enviar} className="space-y-5 px-4 pb-4">
          {errorGeneral && (
            <Alert variant="destructive">
              <CircleAlert aria-hidden />
              <AlertTitle>
                {errorGeneral instanceof ErrorApi
                  ? errorGeneral.titulo
                  : "No se pudo guardar"}
              </AlertTitle>
              <AlertDescription>{errorGeneral.message}</AlertDescription>
            </Alert>
          )}
          {campoTexto("codigo", "Código")}
          {campoTexto("nombre", "Nombre")}
          {bloqueado && (
            <p id={`${id}-contratos`} className="text-sm text-muted-foreground">
              {AVISO_CONTRATOS}
            </p>
          )}
          {campoLista(
            "categoria",
            "Categoría",
            CATEGORIAS.map((c) => [c, NOMBRES_CATEGORIA[c]]),
            true
          )}
          {campoLista(
            "unidad",
            "Unidad",
            UNIDADES.map((u) => [u, NOMBRES_UNIDAD[u]])
          )}
          {campoLista(
            "moneda",
            "Moneda",
            MONEDAS.map((m) => [m, m]),
            true
          )}
          <SheetFooter className="px-0">
            <Button type="submit" aria-disabled={mutacion.isPending}>
              {mutacion.isPending
                ? "Guardando…"
                : esAlta
                  ? "Dar de alta"
                  : "Guardar cambios"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
```

- [ ] **Step 5: Página Catálogo**

`web/src/paginas/Catalogo.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Package, Plus, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link } from "react-router"
import { enviarJson, pedir } from "@/api"
import { useToken } from "@/auth"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Filtro } from "@/componentes/Filtro"
import { FormularioServicio } from "@/componentes/FormularioServicio"
import { RequiereRol } from "@/componentes/RequiereRol"
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
import { unoDe, useParametros } from "@/parametros"
import {
  CATEGORIAS,
  NOMBRES_CATEGORIA,
  NOMBRES_UNIDAD,
  type Servicio,
  type Unidad,
} from "@/tipos"

const ESTADOS = ["activos", "inactivos"] as const

export function Catalogo() {
  return (
    <RequiereRol rol="admin">
      <ContenidoCatalogo />
    </RequiereRol>
  )
}

function ContenidoCatalogo() {
  const token = useToken()
  const cliente = useQueryClient()
  const [parametros, actualizar] = useParametros()
  const categoria = unoDe(parametros.get("categoria"), CATEGORIAS)
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const hayFiltros = Boolean(categoria || estado)
  const [abierto, setAbierto] = useState(false)
  const [editando, setEditando] = useState<Servicio | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [enfocar, setEnfocar] = useState<string | null>(null)
  const botonNuevo = useRef<HTMLButtonElement>(null)
  // El panel se abre por estado: recuerda qué botón lo abrió para devolverle el foco.
  const origen = useRef<HTMLElement | null>(null)

  const consulta = useQuery({
    queryKey: ["servicios", "con-inactivos"],
    queryFn: () =>
      pedir<Servicio[]>("/proveedores/servicios?incluir_inactivos=true", token),
    enabled: Boolean(token),
  })

  const cambioEstado = useMutation({
    mutationFn: (s: Servicio) =>
      pedir<Servicio>(
        `/proveedores/servicios/${encodeURIComponent(s.codigo)}`,
        token,
        enviarJson("PATCH", { activo: !s.activo })
      ),
    onSuccess: async (s) => {
      await cliente.invalidateQueries({ queryKey: ["servicios"] })
      setAviso(
        s.activo
          ? `Se activó el servicio ${s.codigo}.`
          : `Se desactivó el servicio ${s.codigo}.`
      )
      setEnfocar(s.codigo)
    },
    onError: (error) => setAviso(error.message),
  })

  // "Desactivar" y "Activar" se reemplazan entre sí: el foco pasa al botón nuevo de la fila o,
  // si la fila ya no se ve con el filtro actual, a "Nuevo servicio".
  useEffect(() => {
    if (!enfocar) return
    const boton = document.querySelector<HTMLElement>(
      `[data-estado-servicio="${enfocar}"]`
    )
    ;(boton ?? botonNuevo.current)?.focus()
    setEnfocar(null)
  }, [enfocar, consulta.data])

  function abrir(servicio: Servicio | null, desde: HTMLElement) {
    origen.current = desde
    setEditando(servicio)
    setAbierto(true)
  }

  function alternar(servicio: Servicio) {
    if (!cambioEstado.isPending) cambioEstado.mutate(servicio)
  }

  const limpiar = () => actualizar({ categoria: null, estado: null })

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError)
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    if (consulta.data.length === 0)
      return (
        <EstadoVacio
          icono={Package}
          titulo="Aún no hay servicios en el catálogo"
          descripcion="Impórtelos desde el ERP o dé de alta el primero."
          accion={
            <Button asChild variant="outline">
              <Link to="/importacion">Ir a Importación</Link>
            </Button>
          }
        />
      )
    const visibles = consulta.data.filter(
      (s) =>
        (!categoria || s.categoria === categoria) &&
        (!estado || s.activo === (estado === "activos"))
    )
    if (visibles.length === 0)
      return (
        <EstadoVacio
          titulo="Sin resultados"
          descripcion="Ningún servicio coincide con los filtros."
          accion={
            <Button type="button" variant="ghost" onClick={limpiar}>
              <X aria-hidden />
              Limpiar filtros
            </Button>
          }
        />
      )
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Código</TableHead>
            <TableHead>Nombre</TableHead>
            <TableHead>Categoría</TableHead>
            <TableHead>Unidad</TableHead>
            <TableHead>Moneda</TableHead>
            <TableHead>Estado</TableHead>
            <TableHead>
              <span className="sr-only">Acciones</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibles.map((s) => (
            <TableRow key={s.id}>
              <TableCell className="font-mono text-xs">{s.codigo}</TableCell>
              <TableCell className="whitespace-normal">{s.nombre}</TableCell>
              <TableCell>{NOMBRES_CATEGORIA[s.categoria] ?? s.categoria}</TableCell>
              <TableCell>
                {NOMBRES_UNIDAD[s.unidad as Unidad] ?? s.unidad}
              </TableCell>
              <TableCell>{s.moneda}</TableCell>
              <TableCell>
                <EtiquetaEstado activo={s.activo} />
              </TableCell>
              <TableCell>
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    aria-label={`Editar ${s.codigo}`}
                    onClick={(e) => abrir(s, e.currentTarget)}
                  >
                    Editar
                  </Button>
                  {s.activo ? (
                    <ConfirmarAccion
                      titulo={`¿Desactivar ${s.codigo}?`}
                      descripcion="Dejará de aparecer en Precios y en las listas para elegir servicios. Sus contratos y su historial se conservan; puede activarlo cuando quiera."
                      textoConfirmar="Desactivar"
                      alConfirmar={() => alternar(s)}
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        aria-label={`Desactivar ${s.codigo}`}
                        data-estado-servicio={s.codigo}
                        aria-disabled={cambioEstado.isPending}
                      >
                        Desactivar
                      </Button>
                    </ConfirmarAccion>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      aria-label={`Activar ${s.codigo}`}
                      data-estado-servicio={s.codigo}
                      aria-disabled={cambioEstado.isPending}
                      onClick={() => alternar(s)}
                    >
                      Activar
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Catálogo de servicios"
        descripcion="Los servicios de TI que se compran. Se desactivan, no se borran: sus contratos y su historial se conservan."
        acciones={
          <Button ref={botonNuevo} onClick={(e) => abrir(null, e.currentTarget)}>
            <Plus aria-hidden />
            Nuevo servicio
          </Button>
        }
      />
      <div aria-live="polite">
        {aviso && <p className="text-sm">{aviso}</p>}
      </div>
      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <div
              role="group"
              aria-label="Filtrar por categoría"
              className="flex flex-wrap gap-2"
            >
              <Filtro
                activo={!categoria}
                onClick={() => actualizar({ categoria: null })}
              >
                Todas
              </Filtro>
              {CATEGORIAS.map((c) => (
                <Filtro
                  key={c}
                  activo={categoria === c}
                  onClick={() => actualizar({ categoria: c })}
                >
                  {NOMBRES_CATEGORIA[c]}
                </Filtro>
              ))}
            </div>
            <div
              role="group"
              aria-label="Filtrar por estado"
              className="flex flex-wrap gap-2 md:ml-auto"
            >
              <Filtro activo={!estado} onClick={() => actualizar({ estado: null })}>
                Todos
              </Filtro>
              <Filtro
                activo={estado === "activos"}
                onClick={() => actualizar({ estado: "activos" })}
              >
                Activos
              </Filtro>
              <Filtro
                activo={estado === "inactivos"}
                onClick={() => actualizar({ estado: "inactivos" })}
              >
                Inactivos
              </Filtro>
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
      <FormularioServicio
        key={editando?.codigo ?? "nuevo"}
        abierto={abierto}
        alCambiarAbierto={setAbierto}
        servicio={editando}
        devolverFoco={origen}
        alGuardar={(guardado, esAlta) => {
          void cliente.invalidateQueries({ queryKey: ["servicios"] })
          setAviso(
            esAlta
              ? `Se dio de alta el servicio ${guardado.codigo}.`
              : `Se guardaron los cambios de ${guardado.codigo}.`
          )
        }}
      />
    </section>
  )
}
```

- [ ] **Step 6: Menú y ruta**

En `navegacion.ts`, importe `Package` y agregue después de "Actividad":

```ts
      {
        titulo: "Catálogo",
        ruta: "/sistema/catalogo",
        descripcion: "Servicios de TI que se compran",
        icono: Package,
        soloAdmin: true,
      },
```

En `rutas.tsx`, importe `Catalogo` y agregue `{ path: "sistema/catalogo", Component: Catalogo },` antes de `"*"`.

- [ ] **Step 7: Correr las pruebas**

Run: `(cd web && npx vitest run)`
Expected: PASS, sin advertencias (incluida `Precios.test.tsx`: la página sigue pidiendo `/proveedores/servicios` sin inactivos).

- [ ] **Step 8: Calidad y commit**

```bash
(cd web && npx prettier --write src && npm run lint && npm run build)
git add web/src
git commit -m "feat(web): catálogo de servicios con alta, edición y estado" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Web — Estado del sistema y Panel de administración

**Files:**
- Create:
  - `web/src/sistema.ts` (consultas compartidas)
  - `web/src/componentes/IndicadorEstado.tsx`
  - `web/src/paginas/EstadoSistema.tsx`, `web/src/paginas/EstadoSistema.test.tsx`
  - `web/src/paginas/Panel.tsx`, `web/src/paginas/Panel.test.tsx`
- Modify:
  - `web/src/tipos.ts` (`EstadoServicio`, `ComprobacionServicio`, `EstadoSistema`, `ResumenAdmin`)
  - `web/src/componentes/navegacion.ts` (`exacta`, Panel y Estado del sistema), `web/src/componentes/navegacion.test.ts`
  - `web/src/componentes/BarraLateral.tsx` (pasa `elemento.exacta`)
  - `web/src/rutas.tsx`

**Interfaces:**
- Consumes: `GET /administracion/estado` y `GET /administracion/resumen` (Task 6), `GET /administracion/actividad` (`ListaActividad`, Task 7), `TarjetaKpi`, `Seccion`, `ContenidoConsulta`.
- Produces:
  - `useEstadoSistema()` (clave `["estado-sistema"]`, se refresca cada 30 s) y `useRegistros(parametros: Record<string, string>)` (clave `["actividad", "ultimos", parametros]`) en `web/src/sistema.ts`.
  - `IndicadorEstado({ estado })`: icono y texto "Sano" / "Con problemas" / "Caído" (el color nunca va solo).
  - `estaActiva(ruta, pathname, exacta = false)` y `ElementoNavegacion.exacta?: boolean`.
  - Páginas `Panel` en `/sistema` y `EstadoSistema` en `/sistema/estado`.
  - Menú: "Panel" ("Lo importante de un vistazo") primero en Sistema; "Estado del sistema" ("Si cada servicio responde") después de "Catálogo".

- [ ] **Step 1: Pruebas (fallan)**

`web/src/paginas/EstadoSistema.test.tsx`:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { EstadoSistema } from "@/paginas/EstadoSistema"
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

const ESTADO = {
  version: "abc1234",
  comprobado_en: new Date().toISOString(),
  servicios: [
    {
      clave: "base_de_datos",
      nombre: "Base de datos de administración",
      estado: "sano",
      tiempo_ms: 4,
      detalle: "Funciona con normalidad.",
    },
    {
      clave: "proveedores",
      nombre: "Servicio de proveedores",
      estado: "caido",
      tiempo_ms: null,
      detalle: "No respondió en 2 s.",
    },
    {
      clave: "mensajeria",
      nombre: "Mensajería (RabbitMQ)",
      estado: "con_problemas",
      tiempo_ms: 30,
      detalle: "Mensajes pendientes en: administracion.actividad (150).",
    },
  ],
}

const IMPORTACIONES = {
  total: 1,
  elementos: [
    {
      id: "i1",
      fecha: "2026-10-09T18:00:00Z",
      actor_id: null,
      actor_nombre: "Sistema (línea de comandos)",
      tipo: "importacion.completada",
      objeto_tipo: "importacion",
      objeto_id: "proveedores",
      objeto_nombre: "proveedores",
      detalle: { registros: 60, filas: 60, omitidos: 0 },
      resultado: "exito",
      ip: null,
    },
  ],
}

function api(estado: () => Response = () => respuestaJson(ESTADO)) {
  return simularApi((url) =>
    url.startsWith("/api/administracion/estado")
      ? estado()
      : respuestaJson(IMPORTACIONES)
  )
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("EstadoSistema", () => {
  it("muestra cada servicio con su estado en texto y su tiempo", async () => {
    api()
    const { container } = renderizarPagina(<EstadoSistema />, {
      ruta: "/sistema/estado",
    })
    const caido = (await screen.findByText("Servicio de proveedores")).closest("li")!
    expect(within(caido).getByText("Caído")).toBeInTheDocument()
    expect(within(caido).getByText("Sin respuesta")).toBeInTheDocument()
    const lento = screen.getByText("Mensajería (RabbitMQ)").closest("li")!
    expect(within(lento).getByText("Con problemas")).toBeInTheDocument()
    expect(within(lento).getByText("Respondió en 30 ms")).toBeInTheDocument()
    expect(screen.getByText(/1 de 3 servicios sanos/)).toBeInTheDocument()
    expect(screen.getByText(/Versión abc1234/)).toBeInTheDocument()
    expect(screen.getByText("Importó 60 proveedores")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("«Volver a comprobar» pide el estado otra vez", async () => {
    const simulado = api()
    renderizarPagina(<EstadoSistema />, { ruta: "/sistema/estado" })
    await screen.findByText("Servicio de proveedores")
    const pedidos = () =>
      simulado.mock.calls.filter(([url]) =>
        String(url).startsWith("/api/administracion/estado")
      ).length
    expect(pedidos()).toBe(1)
    await userEvent.click(screen.getByRole("button", { name: /Volver a comprobar/ }))
    await waitFor(() => expect(pedidos()).toBe(2))
  })

  it("si la API falla, lo dice y permite reintentar", async () => {
    api(() =>
      respuestaJson({ title: "Servicio no disponible", detail: "Intente más tarde." }, 503)
    )
    renderizarPagina(<EstadoSistema />, { ruta: "/sistema/estado" })
    expect(await screen.findByText("Servicio no disponible")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument()
  })

  it("solo administración lo ve", () => {
    sesionDePrueba.roles = ["aprobador"]
    api()
    renderizarPagina(<EstadoSistema />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })
})
```

`web/src/paginas/Panel.test.tsx`:

```tsx
import { cleanup, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Panel } from "@/paginas/Panel"
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

const ESTADO = {
  version: "abc1234",
  comprobado_en: new Date().toISOString(),
  servicios: [
    {
      clave: "base_de_datos",
      nombre: "Base de datos de administración",
      estado: "sano",
      tiempo_ms: 4,
      detalle: "Funciona con normalidad.",
    },
    {
      clave: "correo",
      nombre: "Buzón de correo (Mailpit)",
      estado: "con_problemas",
      tiempo_ms: 1500,
      detalle: "Responde con lentitud.",
    },
  ],
}
const ACTIVIDAD = {
  total: 1,
  elementos: [
    {
      id: "a1",
      fecha: "2026-10-09T18:00:00Z",
      actor_id: "admin-1",
      actor_nombre: "admin1",
      tipo: "servicio.creado",
      objeto_tipo: "servicio",
      objeto_id: "NUBE-VM-2",
      objeto_nombre: "NUBE-VM-2",
      detalle: {},
      resultado: "exito",
      ip: null,
    },
  ],
}

function api(resumen: object) {
  return simularApi((url) => {
    if (url.startsWith("/api/administracion/resumen")) return respuestaJson(resumen)
    if (url.startsWith("/api/administracion/estado")) return respuestaJson(ESTADO)
    return respuestaJson(ACTIVIDAD)
  })
}

const tarjeta = (titulo: string) =>
  screen.getByText(titulo).closest<HTMLElement>("[data-slot=card]")!

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Panel", () => {
  it("resume usuarios, intentos fallidos, servicios y correos", async () => {
    api({ usuarios_activos: 12, intentos_fallidos_24h: 6, correos_7d: 3 })
    const { container } = renderizarPagina(<Panel />, { ruta: "/sistema" })
    await screen.findByText("Usuarios activos")
    expect(await within(tarjeta("Usuarios activos")).findByText("12")).toBeInTheDocument()
    const fallidos = tarjeta("Intentos fallidos (24 h)")
    expect(within(fallidos).getByText("6")).toBeInTheDocument()
    expect(fallidos.querySelector("[data-tono]")).toHaveAttribute("data-tono", "riesgo")
    const servicios = tarjeta("Servicios con problemas")
    expect(await within(servicios).findByText("1")).toBeInTheDocument()
    expect(within(servicios).getByText("Buzón de correo (Mailpit)")).toBeInTheDocument()
    expect(servicios.querySelector("[data-tono]")).toHaveAttribute("data-tono", "advertencia")
    expect(within(tarjeta("Correos (7 días)")).getByText("3")).toBeInTheDocument()
    expect(await screen.findAllByText("Dio de alta el servicio NUBE-VM-2")).not.toHaveLength(0)
    expect(screen.getByRole("link", { name: "Ver toda la actividad" })).toHaveAttribute(
      "href",
      "/sistema/actividad"
    )
    await esperarSinViolaciones(container)
  })

  it("con un intento fallido el tono es de advertencia; sin ninguno, de éxito", async () => {
    api({ usuarios_activos: 1, intentos_fallidos_24h: 1, correos_7d: 0 })
    renderizarPagina(<Panel />, { ruta: "/sistema" })
    await screen.findByText("Intentos fallidos (24 h)")
    const fallidos = tarjeta("Intentos fallidos (24 h)")
    expect(await within(fallidos).findByText("1")).toBeInTheDocument()
    expect(fallidos.querySelector("[data-tono]")).toHaveAttribute("data-tono", "advertencia")
  })

  it("sin el servicio de identidad, los usuarios activos quedan sin dato", async () => {
    api({ usuarios_activos: null, intentos_fallidos_24h: 0, correos_7d: 0 })
    renderizarPagina(<Panel />, { ruta: "/sistema" })
    expect(
      await screen.findByText("No se pudo consultar el servicio de identidad.")
    ).toBeInTheDocument()
    expect(within(tarjeta("Usuarios activos")).getByText("Sin datos")).toBeInTheDocument()
  })

  it("solo administración lo ve", () => {
    sesionDePrueba.roles = ["comprador"]
    api({ usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 })
    renderizarPagina(<Panel />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })
})
```

En `navegacion.test.ts`:
- en `estaActiva`, agregue `it("una ruta exacta no se activa en sus subrutas", () => { expect(estaActiva("/sistema", "/sistema", true)).toBe(true); expect(estaActiva("/sistema", "/sistema/usuarios", true)).toBe(false) })`;
- en `migasDe`, cambie el caso `["/sistema", [{ titulo: "Página no encontrada" }]]` por `["/sistema", [{ titulo: "Sistema" }, { titulo: "Panel" }]]` y agregue `["/sistema/estado", [{ titulo: "Sistema" }, { titulo: "Estado del sistema" }]]` y `["/sistema/no-existe", [{ titulo: "Página no encontrada" }]]`;
- en `"descripciones del menú"`, agregue `Panel: "Lo importante de un vistazo"` antes de `Usuarios` y `"Estado del sistema": "Si cada servicio responde"` después de `Catálogo`.

- [ ] **Step 2: Correr y ver que fallan**

Run: `(cd web && npx vitest run src/paginas/EstadoSistema.test.tsx src/paginas/Panel.test.tsx src/componentes/navegacion.test.ts)`
Expected: FAIL (las páginas no existen; `estaActiva` ignora el tercer argumento).

- [ ] **Step 3: Tipos y consultas compartidas**

En `web/src/tipos.ts`:

```ts
export type EstadoServicio = "sano" | "con_problemas" | "caido"
export type ComprobacionServicio = {
  clave: string
  nombre: string
  estado: EstadoServicio
  tiempo_ms: number | null
  detalle: string
}
export type EstadoSistema = {
  version: string
  comprobado_en: string
  servicios: ComprobacionServicio[]
}
export type ResumenAdmin = {
  usuarios_activos: number | null
  intentos_fallidos_24h: number
  correos_7d: number
}
```

`web/src/sistema.ts`:

```ts
import { useQuery } from "@tanstack/react-query"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import type { EstadoSistema, PaginaActividad } from "@/tipos"

/** Estado de los servicios, compartido por el Panel y la página de estado; se renueva cada 30 s. */
export function useEstadoSistema() {
  const token = useToken()
  return useQuery({
    queryKey: ["estado-sistema"],
    queryFn: () => pedir<EstadoSistema>("/administracion/estado", token),
    enabled: Boolean(token),
    refetchInterval: 30_000,
  })
}

/** Últimos registros de la bitácora con los parámetros dados (p. ej. tipo y tamaño). */
export function useRegistros(parametros: Record<string, string>) {
  const token = useToken()
  return useQuery({
    queryKey: ["actividad", "ultimos", parametros],
    queryFn: () =>
      pedir<PaginaActividad>(
        `/administracion/actividad?${new URLSearchParams(parametros)}`,
        token
      ),
    enabled: Boolean(token),
  })
}
```

`web/src/componentes/IndicadorEstado.tsx`:

```tsx
import { CircleCheck, CircleX, TriangleAlert, type LucideIcon } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import type { EstadoServicio } from "@/tipos"

const ESTILOS: Record<
  EstadoServicio,
  { texto: string; icono: LucideIcon; variante: "success" | "warning" | "destructive" }
> = {
  sano: { texto: "Sano", icono: CircleCheck, variante: "success" },
  con_problemas: { texto: "Con problemas", icono: TriangleAlert, variante: "warning" },
  caido: { texto: "Caído", icono: CircleX, variante: "destructive" },
}

/** Estado de un servicio con icono y texto: el color nunca va solo. */
export function IndicadorEstado({ estado }: { estado: EstadoServicio }) {
  const { texto, icono: Icono, variante } = ESTILOS[estado]
  return (
    <Badge variant={variante}>
      <Icono aria-hidden />
      {texto}
    </Badge>
  )
}
```

- [ ] **Step 4: Página Estado del sistema**

`web/src/paginas/EstadoSistema.tsx`:

```tsx
import { RefreshCw } from "lucide-react"
import { Link } from "react-router"
import { ContenidoConsulta } from "@/componentes/Estados"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { IndicadorEstado } from "@/componentes/IndicadorEstado"
import { ListaActividad } from "@/componentes/ListaActividad"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { haceCuanto } from "@/fechas"
import { useEstadoSistema, useRegistros } from "@/sistema"

export function EstadoSistema() {
  return (
    <RequiereRol rol="admin">
      <ContenidoEstado />
    </RequiereRol>
  )
}

function ContenidoEstado() {
  const estado = useEstadoSistema()
  const importaciones = useRegistros({ tipo: "importaciones", tamano: "5" })
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Estado del sistema"
        descripcion="Si cada servicio de la plataforma responde. Se vuelve a comprobar solo cada 30 segundos."
        acciones={
          <Button
            variant="outline"
            aria-disabled={estado.isFetching}
            onClick={() => {
              if (!estado.isFetching) void estado.refetch()
            }}
          >
            <RefreshCw aria-hidden />
            {estado.isFetching ? "Comprobando…" : "Volver a comprobar"}
          </Button>
        }
      />
      <ContenidoConsulta consulta={estado}>
        {(datos) => {
          const sanos = datos.servicios.filter((s) => s.estado === "sano").length
          return (
            <div className="space-y-4">
              <p aria-live="polite" className="text-sm text-muted-foreground">
                {sanos} de {datos.servicios.length} servicios sanos · Versión{" "}
                {datos.version} · Comprobado {haceCuanto(datos.comprobado_en)}
              </p>
              <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {datos.servicios.map((s) => (
                  <li key={s.clave}>
                    <Card size="sm" className="h-full">
                      <CardContent className="space-y-2">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <h2 className="font-medium">{s.nombre}</h2>
                          <IndicadorEstado estado={s.estado} />
                        </div>
                        <p className="text-sm text-muted-foreground">{s.detalle}</p>
                        <p className="text-xs text-muted-foreground">
                          {s.tiempo_ms === null
                            ? "Sin respuesta"
                            : `Respondió en ${s.tiempo_ms} ms`}
                        </p>
                      </CardContent>
                    </Card>
                  </li>
                ))}
              </ul>
            </div>
          )
        }}
      </ContenidoConsulta>
      <Seccion
        titulo="Últimas importaciones"
        acciones={
          <Link
            to="/sistema/actividad?tipo=importaciones"
            className="text-sm font-medium text-accent hover:underline"
          >
            Ver todas las importaciones
          </Link>
        }
      >
        <ContenidoConsulta consulta={importaciones}>
          {(datos) =>
            datos.elementos.length > 0 ? (
              <ListaActividad elementos={datos.elementos} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Aún no hay importaciones registradas.
              </p>
            )
          }
        </ContenidoConsulta>
      </Seccion>
    </section>
  )
}
```

- [ ] **Step 5: Panel de administración**

`web/src/paginas/Panel.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query"
import { Activity, Mail, ShieldAlert, UsersRound } from "lucide-react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { ContenidoConsulta, EstadoError } from "@/componentes/Estados"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { IndicadorEstado } from "@/componentes/IndicadorEstado"
import { ListaActividad } from "@/componentes/ListaActividad"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { TarjetaKpi, type Tono } from "@/componentes/TarjetaKpi"
import { useEstadoSistema, useRegistros } from "@/sistema"
import type { ResumenAdmin } from "@/tipos"

function numero(valor: number | null | undefined): string | null {
  return valor === null || valor === undefined ? null : valor.toLocaleString("es-MX")
}

function enlace(texto: string, ruta: string) {
  return (
    <Link to={ruta} className="text-sm font-medium text-accent hover:underline">
      {texto}
    </Link>
  )
}

export function Panel() {
  return (
    <RequiereRol rol="admin">
      <ContenidoPanel />
    </RequiereRol>
  )
}

function ContenidoPanel() {
  const token = useToken()
  const resumen = useQuery({
    queryKey: ["resumen-admin"],
    queryFn: () => pedir<ResumenAdmin>("/administracion/resumen", token),
    enabled: Boolean(token),
  })
  const estado = useEstadoSistema()
  const recientes = useRegistros({ tamano: "10" })
  const importaciones = useRegistros({ tipo: "importaciones", tamano: "5" })

  const fallidos = resumen.data?.intentos_fallidos_24h
  const tonoFallidos: Tono =
    fallidos === undefined
      ? "info"
      : fallidos >= 5
        ? "riesgo"
        : fallidos >= 1
          ? "advertencia"
          : "exito"
  const conProblemas = estado.data?.servicios.filter((s) => s.estado !== "sano") ?? []
  const tonoServicios: Tono = !estado.data
    ? "info"
    : conProblemas.some((s) => s.estado === "caido")
      ? "riesgo"
      : conProblemas.length > 0
        ? "advertencia"
        : "exito"

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Panel de administración"
        descripcion="Lo importante de la plataforma de un vistazo: quién entra, qué falla y qué se ha hecho."
      />
      {resumen.isError && (
        <EstadoError
          error={resumen.error}
          alReintentar={() => void resumen.refetch()}
        />
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <TarjetaKpi
          titulo="Usuarios activos"
          valor={numero(resumen.data?.usuarios_activos)}
          detalle={
            resumen.data && resumen.data.usuarios_activos === null
              ? "No se pudo consultar el servicio de identidad."
              : undefined
          }
          icono={UsersRound}
          enlace="/sistema/usuarios"
          textoEnlace="Ver usuarios"
        />
        <TarjetaKpi
          titulo="Intentos fallidos (24 h)"
          valor={numero(fallidos)}
          icono={ShieldAlert}
          enlace="/sistema/actividad?tipo=sesiones"
          textoEnlace="Ver inicios de sesión"
          tono={tonoFallidos}
        />
        <TarjetaKpi
          titulo="Servicios con problemas"
          valor={estado.data ? numero(conProblemas.length) : null}
          detalle={conProblemas.map((s) => s.nombre).join(", ") || undefined}
          icono={Activity}
          enlace="/sistema/estado"
          textoEnlace="Ver estado del sistema"
          tono={tonoServicios}
        />
        <TarjetaKpi
          titulo="Correos (7 días)"
          valor={numero(resumen.data?.correos_7d)}
          icono={Mail}
          enlace="/sistema/correos"
          textoEnlace="Ver correos"
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Seccion
          titulo="Actividad reciente"
          acciones={enlace("Ver toda la actividad", "/sistema/actividad")}
        >
          <ContenidoConsulta consulta={recientes}>
            {(datos) =>
              datos.elementos.length > 0 ? (
                <ListaActividad elementos={datos.elementos} />
              ) : (
                <p className="text-sm text-muted-foreground">
                  Aún no hay actividad registrada.
                </p>
              )
            }
          </ContenidoConsulta>
        </Seccion>
        <div className="space-y-4">
          <Seccion
            titulo="Estado del sistema"
            acciones={enlace("Ver detalle", "/sistema/estado")}
          >
            <ContenidoConsulta consulta={estado}>
              {(datos) => (
                <ul className="divide-y">
                  {datos.servicios.map((s) => (
                    <li
                      key={s.clave}
                      className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
                    >
                      <span>{s.nombre}</span>
                      <IndicadorEstado estado={s.estado} />
                    </li>
                  ))}
                </ul>
              )}
            </ContenidoConsulta>
          </Seccion>
          <Seccion
            titulo="Últimas importaciones"
            acciones={enlace("Ir a Importación", "/importacion")}
          >
            <ContenidoConsulta consulta={importaciones}>
              {(datos) =>
                datos.elementos.length > 0 ? (
                  <ListaActividad elementos={datos.elementos} />
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Aún no hay importaciones registradas.
                  </p>
                )
              }
            </ContenidoConsulta>
          </Seccion>
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 6: Ruta exacta en el menú, elementos y rutas**

En `navegacion.ts`:

```ts
export type ElementoNavegacion = {
  titulo: string
  ruta: string
  descripcion: string
  icono: LucideIcon
  soloAdmin?: boolean
  /** Solo cuenta como activa en su ruta exacta, no en sus subrutas (el Panel en /sistema). */
  exacta?: boolean
}
...
export function estaActiva(ruta: string, pathname: string, exacta = false): boolean {
  if (ruta === "/" || exacta) return pathname === ruta
  return pathname === ruta || pathname.startsWith(`${ruta}/`)
}
```

En `migasDe`, use `estaActiva(elemento.ruta, ruta, elemento.exacta)`. En `BarraLateral.tsx`, use `estaActiva(elemento.ruta, pathname, elemento.exacta)`.

Importe `Activity` y `Gauge` de `lucide-react` y agregue a la sección "Sistema": primero

```ts
      {
        titulo: "Panel",
        ruta: "/sistema",
        descripcion: "Lo importante de un vistazo",
        icono: Gauge,
        soloAdmin: true,
        exacta: true,
      },
```

y después de "Catálogo":

```ts
      {
        titulo: "Estado del sistema",
        ruta: "/sistema/estado",
        descripcion: "Si cada servicio responde",
        icono: Activity,
        soloAdmin: true,
      },
```

En `rutas.tsx`, importe `Panel` y `EstadoSistema` y agregue antes de `"*"`:

```tsx
      { path: "sistema", Component: Panel },
      { path: "sistema/estado", Component: EstadoSistema },
```

- [ ] **Step 7: Correr las pruebas**

Run: `(cd web && npx vitest run)`
Expected: PASS, sin advertencias.

- [ ] **Step 8: Calidad y commit**

```bash
(cd web && npx prettier --write src && npm run lint && npm run build)
git add web/src
git commit -m "feat(web): Estado del sistema y Panel de administración" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Web — Centro de ayuda y área Soporte

**Files:**
- Create:
  - `web/src/ayuda.ts`, `web/src/ayuda.test.ts`
  - `web/src/paginas/Ayuda.tsx`, `web/src/paginas/Ayuda.test.tsx`
  - `web/src/paginas/ArticuloAyuda.tsx`, `web/src/paginas/ArticuloAyuda.test.tsx`
- Modify:
  - `web/src/componentes/navegacion.ts`, `web/src/componentes/navegacion.test.ts` (sección "Soporte")
  - `web/src/componentes/BarraSuperior.tsx` (botón "?"), `web/src/componentes/Layout.test.tsx`
  - `web/src/componentes/GuiaUso.tsx`, `web/src/componentes/GuiaUso.test.tsx` (enlace al Centro de ayuda)
  - `web/src/rutas.tsx`

**Interfaces:**
- Consumes: `GLOSARIO` (`web/src/glosario.ts`), `normalizarTexto` (`web/src/tipos.ts`), `useRoles`, `RequiereRol`, `useParametros`.
- Produces:
  - `web/src/ayuda.ts`: `TEMAS`, `ARTICULOS`, `PREGUNTAS`, `esSoloAdmin(articulo)`, `articulosVisibles(esAdmin)`, `buscarArticulos(texto, esAdmin)` (sin acentos ni mayúsculas, todas las palabras) y `articuloPorSlug(slug)`.
  - Páginas `Ayuda` en `/ayuda` (parámetro `q`) y `ArticuloAyuda` en `/ayuda/:articulo`.
  - Menú: sección "Soporte" con "Centro de ayuda" ("Guías y preguntas frecuentes") para todos los roles.
  - Barra superior: enlace "Centro de ayuda" con icono "?".

- [ ] **Step 1: Pruebas (fallan)**

`web/src/ayuda.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import {
  ARTICULOS,
  articuloPorSlug,
  articulosVisibles,
  buscarArticulos,
  esSoloAdmin,
  PREGUNTAS,
  TEMAS,
} from "@/ayuda"

describe("contenido de la ayuda", () => {
  it("cada artículo tiene un slug único, un tema conocido y enlaces internos", () => {
    const slugs = ARTICULOS.map((a) => a.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
    const temas = new Set(TEMAS.map((t) => t.clave))
    for (const articulo of ARTICULOS) {
      expect(temas.has(articulo.tema)).toBe(true)
      expect(articulo.slug).toMatch(/^[a-z0-9-]+$/)
      expect(articulo.secciones.length).toBeGreaterThan(0)
      for (const enlace of articulo.enlaces ?? []) expect(enlace.ruta).toMatch(/^\//)
    }
    expect(PREGUNTAS.every((p) => p.pregunta && p.respuesta)).toBe(true)
  })

  it("los artículos de administración solo los ve administración", () => {
    const deAdmin = ARTICULOS.filter(esSoloAdmin)
    expect(deAdmin.length).toBeGreaterThan(0)
    expect(articulosVisibles(false)).not.toContain(deAdmin[0])
    expect(articulosVisibles(true)).toContain(deAdmin[0])
  })

  it("busca sin acentos ni mayúsculas y exige todas las palabras", () => {
    expect(buscarArticulos("CONTRASENA temporal", true).map((a) => a.slug)).toContain(
      "contrasenas-y-correos"
    )
    expect(buscarArticulos("contrasena temporal", false).map((a) => a.slug)).not.toContain(
      "contrasenas-y-correos"
    )
    expect(buscarArticulos("precio justo", false).map((a) => a.slug)).toEqual(["precio-justo"])
    expect(buscarArticulos("zzz inexistente", true)).toEqual([])
  })

  it("encuentra un artículo por su slug", () => {
    expect(articuloPorSlug("importar-datos")?.titulo).toBe("Importar los datos del ERP")
    expect(articuloPorSlug("no-existe")).toBeUndefined()
    expect(articuloPorSlug(undefined)).toBeUndefined()
  })
})
```

`web/src/paginas/Ayuda.test.tsx`:

```tsx
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { GLOSARIO } from "@/glosario"
import { Ayuda } from "@/paginas/Ayuda"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  ubicacionActual,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

afterEach(() => cleanup())

describe("Ayuda", () => {
  it("muestra los temas de su rol, las preguntas y el glosario", async () => {
    sesionDePrueba.roles = ["comprador"]
    const { container } = renderizarPagina(<Ayuda />, { ruta: "/ayuda" })
    for (const tema of ["Primeros pasos", "Proveedores y precios", "Datos e importación"])
      expect(screen.getByRole("heading", { name: tema })).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Administración" })).not.toBeInTheDocument()
    expect(screen.queryByText("La invitación no llegó")).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Cómo usar PluriOne/ })).toHaveAttribute(
      "href",
      "/ayuda/como-usar-pluri-one"
    )
    const glosario = screen.getByRole("heading", { name: "Glosario" }).closest("[data-slot=card]")!
    for (const { termino } of Object.values(GLOSARIO))
      expect(within(glosario as HTMLElement).getByText(termino)).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("administración ve también su tema y sus preguntas", () => {
    sesionDePrueba.roles = ["admin"]
    renderizarPagina(<Ayuda />, { ruta: "/ayuda" })
    expect(screen.getByRole("heading", { name: "Administración" })).toBeInTheDocument()
    expect(screen.getByText("La invitación no llegó")).toBeInTheDocument()
  })

  it("una pregunta frecuente se abre con clic", async () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Ayuda />, { ruta: "/ayuda" })
    const pregunta = screen.getByText("Mi sesión se cerró sola")
    expect(pregunta.closest("details")).not.toHaveAttribute("open")
    await userEvent.click(pregunta)
    expect(pregunta.closest("details")).toHaveAttribute("open")
  })

  it("la búsqueda va en la URL y muestra los resultados", async () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Ayuda />, { ruta: "/ayuda" })
    await userEvent.type(screen.getByRole("searchbox", { name: "Buscar en la ayuda" }), "importar")
    await userEvent.click(screen.getByRole("button", { name: "Buscar" }))
    expect(ubicacionActual()).toBe("/ayuda?q=importar")
    expect(screen.getByRole("heading", { name: "Resultados para «importar»" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Importar los datos del ERP/ })).toBeInTheDocument()
  })

  it("sin resultados lo dice", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Ayuda />, { ruta: "/ayuda?q=zzz" })
    expect(screen.getByText("Sin resultados")).toBeInTheDocument()
  })
})
```

`web/src/paginas/ArticuloAyuda.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ArticuloAyuda } from "@/paginas/ArticuloAyuda"
import { sesionDePrueba } from "@/pruebas/sesion"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const abrir = (slug: string) =>
  renderizarPagina(<ArticuloAyuda />, { ruta: `/ayuda/${slug}`, patron: "/ayuda/:articulo" })

afterEach(() => cleanup())

describe("ArticuloAyuda", () => {
  it("muestra el artículo con sus pasos y enlaces", async () => {
    sesionDePrueba.roles = ["comprador"]
    const { container } = abrir("importar-datos")
    expect(
      screen.getByRole("heading", { level: 1, name: "Importar los datos del ERP" })
    ).toBeInTheDocument()
    expect(screen.getAllByRole("listitem").length).toBeGreaterThan(2)
    expect(screen.getByRole("link", { name: "Ir a Importación" })).toHaveAttribute(
      "href",
      "/importacion"
    )
    expect(screen.getByRole("link", { name: /Centro de ayuda/ })).toHaveAttribute(
      "href",
      "/ayuda"
    )
    await esperarSinViolaciones(container)
  })

  it("un artículo que no existe lo dice", () => {
    sesionDePrueba.roles = ["comprador"]
    abrir("no-existe")
    expect(screen.getByText("No encontramos ese artículo")).toBeInTheDocument()
  })

  it("los artículos de administración son solo para administración", () => {
    sesionDePrueba.roles = ["comprador"]
    abrir("gestionar-usuarios")
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    cleanup()
    sesionDePrueba.roles = ["admin"]
    abrir("gestionar-usuarios")
    expect(
      screen.getByRole("heading", { level: 1, name: "Dar de alta y administrar usuarios" })
    ).toBeInTheDocument()
  })
})
```

En `navegacion.test.ts`:
- en `"oculta Importación y Configuración a quien no es admin"`, agregue `"Centro de ayuda"` al final de las dos listas esperadas;
- en `"muestra todo al admin, agrupado por sección"`, agregue `"Soporte"` al final;
- en `"descripciones del menú"`, agregue `"Centro de ayuda": "Guías y preguntas frecuentes"` al final;
- en `migasDe`, agregue `["/ayuda", [{ titulo: "Soporte" }, { titulo: "Centro de ayuda" }]]` y `["/ayuda/importar-datos", [{ titulo: "Soporte" }, { titulo: "Centro de ayuda", ruta: "/ayuda" }, { titulo: "Detalle" }]]`.

En `Layout.test.tsx`, agregue al `describe("Layout con sesión iniciada")`:

```tsx
  it("la barra superior enlaza al Centro de ayuda", () => {
    renderizar()
    const barra = document.querySelector("header")!
    expect(
      within(barra).getByRole("link", { name: "Centro de ayuda" })
    ).toHaveAttribute("href", "/ayuda")
  })
```

En `GuiaUso.test.tsx`, en `"con datos importados marca el paso 1 y cuenta el avance"`, agregue al final:

```tsx
    expect(screen.getByRole("link", { name: "Centro de ayuda" })).toHaveAttribute(
      "href",
      "/ayuda"
    )
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `(cd web && npx vitest run src/ayuda.test.ts src/paginas/Ayuda.test.tsx src/paginas/ArticuloAyuda.test.tsx src/componentes)`
Expected: FAIL (`@/ayuda` y las páginas no existen).

- [ ] **Step 3: Contenido de la ayuda**

`web/src/ayuda.ts`:

```ts
import { normalizarTexto } from "@/tipos"

export type TemaAyuda =
  | "primeros-pasos"
  | "proveedores-precios"
  | "datos"
  | "administracion"

export const TEMAS: {
  clave: TemaAyuda
  titulo: string
  descripcion: string
  soloAdmin?: boolean
}[] = [
  {
    clave: "primeros-pasos",
    titulo: "Primeros pasos",
    descripcion: "Entrar, moverse por la plataforma y el flujo de trabajo.",
  },
  {
    clave: "proveedores-precios",
    titulo: "Proveedores y precios",
    descripcion: "Consultar proveedores, su desempeño y el precio justo.",
  },
  {
    clave: "datos",
    titulo: "Datos e importación",
    descripcion: "Cargar los datos del ERP y corregir archivos con errores.",
  },
  {
    clave: "administracion",
    titulo: "Administración",
    descripcion: "Usuarios, contraseñas, catálogo, actividad y estado del sistema.",
    soloAdmin: true,
  },
]

export type SeccionArticulo = {
  titulo?: string
  parrafos?: string[]
  pasos?: string[]
}

export type Articulo = {
  slug: string
  tema: TemaAyuda
  titulo: string
  resumen: string
  secciones: SeccionArticulo[]
  enlaces?: { texto: string; ruta: string }[]
}

export const ARTICULOS: Articulo[] = [
  {
    slug: "como-usar-pluri-one",
    tema: "primeros-pasos",
    titulo: "Cómo usar PluriOne",
    resumen: "El flujo de trabajo en cuatro pasos, de los datos a la adjudicación.",
    secciones: [
      {
        pasos: [
          "Administración importa del ERP el catálogo, los proveedores, los contratos y el desempeño.",
          "Usted revisa en Proveedores quién le vende, sus contratos y cómo rinde.",
          "En Precios compara lo que paga con el precio de referencia del mercado.",
          "La negociación asistida por IA, dentro de los límites que usted fije, llegará en una próxima versión; usted aprobará cada cierre.",
        ],
      },
      {
        parrafos: [
          "La guía del Tablero muestra su avance en estos pasos. Puede ocultarla y volver a mostrarla desde el menú de su cuenta, abajo a la izquierda.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir al Tablero", ruta: "/" }],
  },
  {
    slug: "entrar-y-moverse",
    tema: "primeros-pasos",
    titulo: "Entrar y moverse por la plataforma",
    resumen: "El inicio de sesión, el menú por áreas, su cuenta y el tema.",
    secciones: [
      {
        titulo: "Inicio de sesión",
        parrafos: [
          "Entre con su usuario o correo y su contraseña. La primera vez, use el enlace del correo de invitación para definir su contraseña, o la contraseña temporal que le entregó administración: la plataforma le pedirá cambiarla.",
          "Por seguridad, la sesión se cierra sola después de un tiempo. Si eso pasa, vuelva a iniciar sesión y regresará a la página donde estaba.",
        ],
      },
      {
        titulo: "El menú",
        parrafos: [
          "El menú de la izquierda agrupa las pantallas por área: Resumen, Proveedores, Inteligencia, Sistema (solo administración) y Soporte. Cada opción dice para qué sirve. En pantallas pequeñas se abre con el botón de la esquina superior izquierda.",
        ],
      },
      {
        titulo: "Su cuenta y el tema",
        parrafos: [
          "Su nombre y su rol están abajo a la izquierda; desde ahí cierra sesión. El tema claro, el oscuro o el del sistema se elige con el botón de la barra superior.",
        ],
      },
    ],
  },
  {
    slug: "consultar-proveedores",
    tema: "proveedores-precios",
    titulo: "Consultar proveedores y su desempeño",
    resumen: "Buscar un proveedor y revisar sus contratos y su desempeño.",
    secciones: [
      {
        pasos: [
          "Abra Proveedores en el menú.",
          "Busque por nombre o RFC, o filtre por categoría y estado.",
          "Abra un proveedor para ver su contacto, sus contratos con cada línea y su desempeño mensual.",
        ],
      },
      {
        parrafos: [
          "El desempeño reúne el cumplimiento del SLA, el tiempo de resolución, los incidentes críticos, las entregas a tiempo y la satisfacción. Los términos técnicos tienen una ayuda: haga clic sobre ellos.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Proveedores", ruta: "/proveedores" }],
  },
  {
    slug: "precio-justo",
    tema: "proveedores-precios",
    titulo: "Entender el precio justo",
    resumen: "Qué significan el precio de referencia, los percentiles y el sobreprecio.",
    secciones: [
      {
        parrafos: [
          "El precio de referencia es lo que se paga normalmente en el mercado por un servicio, en una cantidad y un plazo dados. Se expresa con tres valores: P25 (precio bajo), P50 (típico) y P75 (alto).",
          "Hay sobreprecio cuando usted paga más que el P75. El ahorro potencial es lo que ahorraría al año si pagara el P50.",
          "Si hay pocos contratos comparables, el precio se marca con baja confianza: tómelo como una estimación.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Precios", ruta: "/precios" }],
  },
  {
    slug: "importar-datos",
    tema: "datos",
    titulo: "Importar los datos del ERP",
    resumen: "El orden de los archivos y el formato que se acepta.",
    secciones: [
      {
        pasos: [
          "Abra Importación en el menú (solo administración).",
          "Elija el tipo de archivo en este orden: catálogo de servicios, proveedores, tipo de cambio, contratos y desempeño.",
          "Arrastre el archivo CSV o haga clic para elegirlo, y pulse «Importar».",
          "Revise el resultado: filas leídas, registros guardados y omitidos.",
        ],
      },
      {
        titulo: "Formato",
        parrafos: [
          "Archivos CSV en UTF-8, separados por coma o punto y coma, de hasta 10 MB. Contratos y desempeño hacen referencia a proveedores y servicios que ya deben estar importados.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Importación", ruta: "/importacion" }],
  },
  {
    slug: "errores-de-importacion",
    tema: "datos",
    titulo: "Qué hacer si un archivo tiene errores",
    resumen: "Leer la lista de errores y volver a intentarlo.",
    secciones: [
      {
        parrafos: [
          "Si un archivo tiene errores no se guarda ninguna fila: la importación es todo o nada. Verá una tabla con la fila, la columna y el problema de cada error.",
          "Corrija el archivo en su origen (el ERP o la hoja de cálculo), guárdelo de nuevo como CSV en UTF-8 y vuelva a importarlo con «Elegir otro archivo».",
          "Cada intento, completo o rechazado, queda en la bitácora de Actividad con quién lo hizo.",
        ],
      },
    ],
  },
  {
    slug: "gestionar-usuarios",
    tema: "administracion",
    titulo: "Dar de alta y administrar usuarios",
    resumen: "Altas por invitación o con contraseña temporal, roles y desactivación.",
    secciones: [
      {
        titulo: "Alta",
        pasos: [
          "En Usuarios, pulse «Nuevo usuario».",
          "Escriba nombre, apellidos y correo; el usuario se sugiere a partir del correo.",
          "Elija uno o más roles: Administración, Compras o Aprobación.",
          "Elija cómo obtendrá su contraseña: por invitación (recomendada) o con una contraseña temporal que usted verá una sola vez.",
        ],
      },
      {
        titulo: "Roles y protección",
        parrafos: [
          "Puede cambiar los roles desde la ficha de cada persona. Para proteger la plataforma, nadie puede quitarse a sí mismo el rol de administración ni desactivarse, y siempre debe quedar al menos un administrador activo.",
        ],
      },
      {
        titulo: "Desactivar",
        parrafos: [
          "Las cuentas se desactivan, no se borran: la persona deja de entrar, sus sesiones se cierran y su historial se conserva. Puede activarla de nuevo cuando quiera.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Usuarios", ruta: "/sistema/usuarios" }],
  },
  {
    slug: "contrasenas-y-correos",
    tema: "administracion",
    titulo: "Contraseñas y correos del sistema",
    resumen: "Invitaciones, restablecimientos y contraseñas temporales.",
    secciones: [
      {
        parrafos: [
          "La invitación es un correo con un enlace para que la persona defina su contraseña; vence en 72 horas. A quien ya entró antes se le envía un correo de restablecimiento que vence en 24 horas.",
          "La contraseña temporal se muestra una sola vez: cópiela y entréguela por un medio seguro. La persona deberá cambiarla al entrar.",
          "En Correos ve cada correo enviado y si salió bien. Si uno no salió, reintente desde la ficha de la persona o asígnele una contraseña temporal. A una cuenta desactivada no se le puede enviar el correo: actívela primero.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Correos", ruta: "/sistema/correos" }],
  },
  {
    slug: "revisar-actividad",
    tema: "administracion",
    titulo: "Revisar la actividad y exportarla",
    resumen: "La bitácora: quién hizo qué, cuándo y con qué resultado.",
    secciones: [
      {
        parrafos: [
          "Actividad reúne los inicios de sesión (incluidos los intentos fallidos), las acciones sobre usuarios, las importaciones y los cambios del catálogo. Nada de esto se puede borrar ni modificar.",
          "Filtre por persona, tipo y fechas. Con «Exportar CSV» descarga los registros filtrados para abrirlos en Excel; se exportan como máximo los 10,000 más recientes, así que acote las fechas si necesita más.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Actividad", ruta: "/sistema/actividad" }],
  },
  {
    slug: "catalogo-de-servicios",
    tema: "administracion",
    titulo: "Mantener el catálogo de servicios",
    resumen: "Alta, edición y desactivación de los servicios de TI.",
    secciones: [
      {
        parrafos: [
          "El catálogo lista los servicios que aparecen en los contratos y en Precios. Puede darlos de alta, editarlos o desactivarlos; también se cargan con la importación del ERP.",
          "El código no cambia después de crearlo, porque las importaciones lo usan para identificar el servicio. Si un servicio ya tiene contratos, su categoría y su moneda tampoco cambian, porque los precios históricos dependen de ellas.",
          "Un servicio desactivado deja de aparecer en Precios, pero sus contratos y su historial se conservan.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir al Catálogo", ruta: "/sistema/catalogo" }],
  },
  {
    slug: "estado-del-sistema",
    tema: "administracion",
    titulo: "Saber si el sistema está sano",
    resumen: "Qué significa cada estado y qué hacer si algo falla.",
    secciones: [
      {
        parrafos: [
          "Estado del sistema comprueba cada 30 segundos la base de datos, el servicio de proveedores, la identidad (Keycloak), la mensajería (RabbitMQ) y el buzón de correo.",
          "Sano: responde en menos de un segundo. Con problemas: responde con lentitud o hay muchos mensajes pendientes. Caído: no responde en dos segundos o responde con un error.",
          "Si un servicio sigue caído, avise al equipo técnico con la hora y el detalle que muestra su tarjeta.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Estado del sistema", ruta: "/sistema/estado" }],
  },
]

export type Pregunta = { pregunta: string; respuesta: string; soloAdmin?: boolean }

export const PREGUNTAS: Pregunta[] = [
  {
    pregunta: "No puedo entrar a la plataforma",
    respuesta:
      "Revise que su usuario y su contraseña sean correctos. Después de varios intentos fallidos la cuenta se bloquea unos minutos. Si olvidó su contraseña o su cuenta está desactivada, pida ayuda a administración.",
  },
  {
    pregunta: "Mi sesión se cerró sola",
    respuesta:
      "Por seguridad, la sesión vence después de un tiempo. Vuelva a iniciar sesión y regresará a la página donde estaba.",
  },
  {
    pregunta: "¿Por qué no veo el área Sistema?",
    respuesta:
      "Sistema es solo para el rol de Administración. Si necesita acceso, pídalo a una persona con ese rol.",
  },
  {
    pregunta: "¿Dónde cambio entre el tema claro y el oscuro?",
    respuesta:
      "Con el botón de tema de la barra superior: claro, oscuro o el del sistema. La preferencia se guarda en este navegador.",
  },
  {
    pregunta: "La invitación no llegó",
    respuesta:
      "Revise en Correos si se envió. Si no salió, reintente desde la ficha de la persona o asígnele una contraseña temporal. Pida también que revise su carpeta de correo no deseado.",
    soloAdmin: true,
  },
  {
    pregunta: "¿Puedo borrar un usuario o un servicio?",
    respuesta:
      "No. Se desactivan para conservar su historial y la bitácora; puede activarlos de nuevo cuando quiera.",
    soloAdmin: true,
  },
]

const TEMAS_DE_ADMIN = new Set(
  TEMAS.filter((t) => t.soloAdmin).map((t) => t.clave)
)

export function esSoloAdmin(articulo: Articulo): boolean {
  return TEMAS_DE_ADMIN.has(articulo.tema)
}

export function articulosVisibles(esAdmin: boolean): Articulo[] {
  return ARTICULOS.filter((a) => esAdmin || !esSoloAdmin(a))
}

function textoDe(articulo: Articulo): string {
  return normalizarTexto(
    [
      articulo.titulo,
      articulo.resumen,
      ...articulo.secciones.flatMap((s) => [
        s.titulo ?? "",
        ...(s.parrafos ?? []),
        ...(s.pasos ?? []),
      ]),
    ].join(" ")
  )
}

/** Artículos visibles que contienen todas las palabras, sin acentos ni mayúsculas. */
export function buscarArticulos(texto: string, esAdmin: boolean): Articulo[] {
  const palabras = normalizarTexto(texto).split(/\s+/).filter(Boolean)
  return articulosVisibles(esAdmin).filter((a) => {
    const contenido = textoDe(a)
    return palabras.every((p) => contenido.includes(p))
  })
}

export function articuloPorSlug(slug: string | undefined): Articulo | undefined {
  return ARTICULOS.find((a) => a.slug === slug)
}
```

- [ ] **Step 4: Páginas**

`web/src/paginas/Ayuda.tsx`:

```tsx
import { Search, X } from "lucide-react"
import { useEffect, useRef, type FormEvent } from "react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import {
  ARTICULOS,
  buscarArticulos,
  PREGUNTAS,
  TEMAS,
  type Articulo,
} from "@/ayuda"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { GLOSARIO } from "@/glosario"
import { useParametros } from "@/parametros"

function ListaArticulos({ articulos }: { articulos: Articulo[] }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {articulos.map((a) => (
        <li key={a.slug}>
          <Link
            to={`/ayuda/${a.slug}`}
            className="block h-full rounded-xl border bg-card p-4 outline-hidden transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="block font-medium">{a.titulo}</span>
            <span className="block text-sm text-muted-foreground">{a.resumen}</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function Ayuda() {
  const esAdmin = useRoles().includes("admin")
  const [parametros, actualizar] = useParametros()
  const q = (parametros.get("q") ?? "").trim().slice(0, 100)
  const campo = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (campo.current && campo.current.value.trim() !== q) campo.current.value = q
  }, [q])

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = String(new FormData(evento.currentTarget).get("q") ?? "").trim()
    actualizar({ q: texto || null })
  }

  const temas = TEMAS.filter((t) => esAdmin || !t.soloAdmin)
  const preguntas = PREGUNTAS.filter((p) => esAdmin || !p.soloAdmin)
  const resultados = q ? buscarArticulos(q, esAdmin) : null

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Centro de ayuda"
        descripcion="Guías paso a paso, preguntas frecuentes y el significado de cada término."
      />
      <form role="search" onSubmit={buscar} className="flex flex-wrap items-center gap-2">
        <label htmlFor="busqueda-ayuda" className="sr-only">
          Buscar en la ayuda
        </label>
        <div className="relative w-full max-w-md">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            id="busqueda-ayuda"
            type="search"
            name="q"
            ref={campo}
            defaultValue={q}
            placeholder="¿Qué necesita hacer?"
            maxLength={100}
            className="pl-8"
          />
        </div>
        <Button type="submit">Buscar</Button>
        {q && (
          <Button type="button" variant="ghost" onClick={() => actualizar({ q: null })}>
            <X aria-hidden />
            Limpiar búsqueda
          </Button>
        )}
      </form>
      {resultados ? (
        <Seccion titulo={`Resultados para «${q}»`}>
          {resultados.length > 0 ? (
            <ListaArticulos articulos={resultados} />
          ) : (
            <EstadoVacio
              titulo="Sin resultados"
              descripcion="Pruebe con otras palabras o revise las preguntas frecuentes."
            />
          )}
        </Seccion>
      ) : (
        temas.map((t) => (
          <Seccion key={t.clave} titulo={t.titulo} descripcion={t.descripcion}>
            <ListaArticulos articulos={ARTICULOS.filter((a) => a.tema === t.clave)} />
          </Seccion>
        ))
      )}
      <Seccion titulo="Preguntas frecuentes">
        <div className="divide-y">
          {preguntas.map((p) => (
            <details key={p.pregunta} className="py-3">
              <summary className="cursor-pointer font-medium">{p.pregunta}</summary>
              <p className="mt-2 text-sm text-muted-foreground">{p.respuesta}</p>
            </details>
          ))}
        </div>
      </Seccion>
      <Seccion
        titulo="Glosario"
        descripcion="Los términos técnicos de la plataforma, en lenguaje llano."
      >
        <dl className="grid gap-4 sm:grid-cols-2">
          {Object.values(GLOSARIO).map((g) => (
            <div key={g.termino}>
              <dt className="font-medium">{g.termino}</dt>
              <dd className="text-sm text-muted-foreground">{g.definicion}</dd>
            </div>
          ))}
        </dl>
      </Seccion>
    </section>
  )
}
```

`web/src/paginas/ArticuloAyuda.tsx`:

```tsx
import { ArrowLeft, FileQuestion } from "lucide-react"
import { Link, useParams } from "react-router"
import { articuloPorSlug, esSoloAdmin } from "@/ayuda"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Button } from "@/components/ui/button"

export function ArticuloAyuda() {
  const articulo = articuloPorSlug(useParams().articulo)
  if (!articulo)
    return (
      <EstadoVacio
        icono={FileQuestion}
        titulo="No encontramos ese artículo"
        descripcion="Puede que el enlace esté incompleto o que el artículo haya cambiado de nombre."
        accion={
          <Button asChild variant="outline">
            <Link to="/ayuda">Volver al Centro de ayuda</Link>
          </Button>
        }
      />
    )
  const contenido = (
    <article className="max-w-3xl space-y-6">
      <Link
        to="/ayuda"
        className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
      >
        <ArrowLeft aria-hidden className="size-4" />
        Centro de ayuda
      </Link>
      <EncabezadoPagina titulo={articulo.titulo} descripcion={articulo.resumen} />
      {articulo.secciones.map((s, i) => (
        <section key={s.titulo ?? i} className="space-y-2">
          {s.titulo && <h2 className="text-base font-semibold">{s.titulo}</h2>}
          {s.parrafos?.map((p) => (
            <p key={p} className="text-sm leading-relaxed">
              {p}
            </p>
          ))}
          {s.pasos && (
            <ol className="list-decimal space-y-1 pl-5 text-sm leading-relaxed">
              {s.pasos.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ol>
          )}
        </section>
      ))}
      {articulo.enlaces && (
        <div className="flex flex-wrap gap-2">
          {articulo.enlaces.map((e) => (
            <Button key={e.ruta} asChild variant="outline">
              <Link to={e.ruta}>{e.texto}</Link>
            </Button>
          ))}
        </div>
      )}
    </article>
  )
  return esSoloAdmin(articulo) ? (
    <RequiereRol rol="admin">{contenido}</RequiereRol>
  ) : (
    contenido
  )
}
```

- [ ] **Step 5: Menú, barra superior, guía y rutas**

En `navegacion.ts`, importe `LifeBuoy` y agregue al final de `NAVEGACION`:

```ts
  {
    titulo: "Soporte",
    elementos: [
      {
        titulo: "Centro de ayuda",
        ruta: "/ayuda",
        descripcion: "Guías y preguntas frecuentes",
        icono: LifeBuoy,
      },
    ],
  },
```

En `BarraSuperior.tsx`, importe `CircleHelp` y agregue antes de `<MenuAlertas />`:

```tsx
        <Button asChild variant="ghost" size="icon-lg">
          <Link to="/ayuda" aria-label="Centro de ayuda">
            <CircleHelp aria-hidden />
          </Link>
        </Button>
```

En `GuiaUso.tsx`, después de la lista `<ol>…</ol>`:

```tsx
      <p className="text-sm text-muted-foreground">
        ¿Tiene dudas? Consulte el{" "}
        <Link to="/ayuda" className="font-medium text-accent hover:underline">
          Centro de ayuda
        </Link>
        .
      </p>
```

En `rutas.tsx`, importe `Ayuda` y `ArticuloAyuda` y agregue antes de `"*"`:

```tsx
      { path: "ayuda", Component: Ayuda },
      { path: "ayuda/:articulo", Component: ArticuloAyuda },
```

- [ ] **Step 6: Correr las pruebas**

Run: `(cd web && npx vitest run)`
Expected: PASS, sin advertencias.

- [ ] **Step 7: Calidad y commit**

```bash
(cd web && npx prettier --write src && npm run lint && npm run build)
git add web/src
git commit -m "feat(web): Centro de ayuda con guías, preguntas frecuentes y glosario, y área Soporte" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Foco en Importación, Dependabot, prueba de humo y documentación

**Files:**
- Modify:
  - `web/src/componentes/Seccion.tsx` (`refTitulo`)
  - `web/src/paginas/Importacion.tsx`, `web/src/paginas/Importacion.test.tsx`
  - `.github/dependabot.yml`
  - `infra/smoke_test.py`
  - `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md` (PRD)
  - `docs/superpowers/specs/2026-10-08-gestion-administracion-design.md` (estado, §3.3, §3.4, §3.7)
  - `README.md`

**Interfaces:**
- Consumes: todas las rutas nuevas (Tasks 1–6).
- Produces:
  - `Seccion({ …, refTitulo?: Ref<HTMLHeadingElement> })`: con `refTitulo`, el título se puede enfocar (`tabIndex={-1}`).
  - `smoke_test.verificar_operacion(cliente)`: estado sin servicios caídos, resumen, catálogo solo admin y cambios del catálogo que llegan a la bitácora en menos de 30 s.

- [ ] **Step 1: Pruebas de Importación (fallan)**

En `web/src/paginas/Importacion.test.tsx`, reemplace la prueba `"no permite volver atrás mientras la importación está en curso"` por:

```tsx
  it("mientras importa, el botón conserva el foco y «Atrás» no hace nada", async () => {
    simularApi({
      "/api/proveedores/importaciones/servicios": () =>
        new Promise<Response>(() => {}),
    })
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()
    await userEvent.upload(
      zonaDeArchivo(),
      new File(["x"], "servicios.csv", { type: "text/csv" })
    )
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    const importando = await screen.findByRole("button", { name: "Importando…" })
    expect(importando).toHaveAttribute("aria-disabled", "true")
    expect(importando).not.toBeDisabled()
    expect(importando).toHaveFocus()
    const atras = screen.getByRole("button", { name: "Atrás" })
    expect(atras).toHaveAttribute("aria-disabled", "true")
    await userEvent.click(atras)
    expect(
      screen.getByRole("heading", { name: /2\. Elija el archivo/ })
    ).toBeInTheDocument()
  })

  it("lleva el foco al título de cada paso nuevo", async () => {
    simularApi({
      "/api/proveedores/importaciones/servicios": () =>
        respuestaJson({
          entidad: "servicios",
          filas: 1,
          registros: 1,
          omitidos: 0,
          eventos: 0,
        }),
    })
    renderizarPagina(<Importacion />)
    expect(document.body).toHaveFocus() // al cargar la página no se mueve el foco
    await irAlPasoDeArchivo()
    expect(
      screen.getByRole("heading", { name: /2\. Elija el archivo/ })
    ).toHaveFocus()
    await userEvent.upload(
      zonaDeArchivo(),
      new File(["x"], "servicios.csv", { type: "text/csv" })
    )
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))
    expect(
      await screen.findByRole("heading", { name: "3. Resultado" })
    ).toHaveFocus()
  })
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `(cd web && npx vitest run src/paginas/Importacion.test.tsx)`
Expected: FAIL (el botón usa `disabled` y el foco no se mueve).

- [ ] **Step 3: Título enfocable y foco por paso**

En `Seccion.tsx`:

```tsx
import type { ReactNode, Ref } from "react"
...
export function Seccion({
  titulo,
  descripcion,
  acciones,
  children,
  className,
  refTitulo,
}: {
  titulo: string
  descripcion?: ReactNode
  acciones?: ReactNode
  children: ReactNode
  className?: string
  /** Para mover el foco al título (p. ej. al cambiar de paso); lo vuelve enfocable. */
  refTitulo?: Ref<HTMLHeadingElement>
}) {
  ...
          <h2
            ref={refTitulo}
            tabIndex={refTitulo ? -1 : undefined}
            className="text-base font-semibold"
          >
            {titulo}
          </h2>
```

En `Importacion.tsx` (importe `useEffect` y `useRef`):

```tsx
  // Cada paso reemplaza al anterior: el foco pasa a su título para no perderse (no al cargar).
  const tituloPaso = useRef<HTMLHeadingElement>(null)
  const primerPaso = useRef(true)
  useEffect(() => {
    if (primerPaso.current) {
      primerPaso.current = false
      return
    }
    tituloPaso.current?.focus()
  }, [paso])
```

Pase `refTitulo={tituloPaso}` a la `Seccion` de cada paso. Cambie `importar()`:

```tsx
  function importar() {
    if (importacion.isPending || !archivo || errorArchivo) return
    importacion.mutate({ entidad, archivo }, { onSettled: () => setPaso(3) })
  }
```

y los botones del paso 2:

```tsx
              <Button
                variant="outline"
                aria-disabled={importacion.isPending}
                onClick={() => {
                  if (!importacion.isPending) setPaso(1)
                }}
              >
                <ArrowLeft aria-hidden />
                Atrás
              </Button>
              <Button
                onClick={importar}
                disabled={!archivo || Boolean(errorArchivo)}
                aria-disabled={importacion.isPending}
              >
                {importacion.isPending ? "Importando…" : "Importar"}
              </Button>
```

(`disabled` se queda solo para "sin archivo válido": en ese caso el botón aún no tiene el foco).

- [ ] **Step 4: Correr las pruebas web**

Run: `(cd web && npx vitest run)`
Expected: PASS, sin advertencias.

- [ ] **Step 5: Dependabot**

En `.github/dependabot.yml`, cambie la línea de `directories` del ecosistema `docker` por:

```yaml
    directories: [/services/proveedores, /services/administracion, /web]
```

- [ ] **Step 6: Prueba de humo**

En `infra/smoke_test.py`, después de `verificar_administracion`:

```python
SERVICIO_HUMO = "HUMO-SERV"


def eventos_del_servicio_de_humo(cliente: httpx.Client, admin: dict[str, str]) -> set[str]:
    """IDs de los registros del catálogo sobre el servicio de humo (los 100 más recientes)."""
    respuesta = cliente.get(
        "/api/administracion/actividad",
        params={"tipo": "catalogo", "tamano": 100},
        headers=admin,
    )
    verificar(respuesta.status_code == 200, f"consultar la actividad falló: {respuesta.text}")
    return {e["id"] for e in respuesta.json()["elementos"] if e["objeto_id"] == SERVICIO_HUMO}


def verificar_operacion(cliente: httpx.Client) -> None:
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")

    estado = cliente.get("/api/administracion/estado", headers=admin)
    verificar(estado.status_code == 200, f"el estado del sistema falló: {estado.text}")
    caidos = [s["nombre"] for s in estado.json()["servicios"] if s["estado"] == "caido"]
    verificar(not caidos, f"servicios caídos según el estado del sistema: {caidos}")
    resumen = cliente.get("/api/administracion/resumen", headers=admin)
    verificar(
        resumen.status_code == 200 and resumen.json()["usuarios_activos"] is not None,
        f"el resumen del panel falló: {resumen.text}",
    )
    inactivos = cliente.get(
        "/api/proveedores/servicios", params={"incluir_inactivos": "true"}, headers=comprador
    )
    verificar(inactivos.status_code == 403, "un comprador no debe ver los servicios inactivos")

    # Servicio de humo reutilizable: se crea la primera vez; cada corrida lo desactiva y lo
    # reactiva. Solo cuentan los registros nuevos de esta corrida.
    antes = eventos_del_servicio_de_humo(cliente, admin)
    alta = cliente.post(
        "/api/proveedores/servicios",
        json={
            "codigo": SERVICIO_HUMO,
            "nombre": "Servicio de la prueba de humo",
            "categoria": "soporte",
            "unidad": "ticket",
            "moneda": "MXN",
        },
        headers=admin,
    )
    verificar(alta.status_code in (201, 409), f"el alta del servicio falló: {alta.text}")
    for activo in (False, True):
        cambio = cliente.patch(
            f"/api/proveedores/servicios/{SERVICIO_HUMO}", json={"activo": activo}, headers=admin
        )
        verificar(
            cambio.status_code == 200 and cambio.json()["activo"] is activo,
            f"cambiar el estado del servicio falló: {cambio.text}",
        )
    # Los cambios viajan por el outbox y RabbitMQ hasta la bitácora de administración.
    limite = time.monotonic() + 30
    while time.monotonic() < limite:
        if len(eventos_del_servicio_de_humo(cliente, admin) - antes) >= 2:
            return
        time.sleep(1)
    raise SystemExit("FALLA: los cambios del catálogo no llegaron a la bitácora en 30 s")
```

En `main()`, llame `verificar_operacion(cliente)` después de `verificar_administracion(cliente)` y cambie el mensaje final:

```python
    print(
        f"OK: SPA, Keycloak, proveedores, administración y operación responden "
        f"({lista.json()['total']} proveedores)."
    )
```

- [ ] **Step 7: Correr la prueba de humo contra el stack**

```bash
export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"; export MSYS_NO_PATHCONV=1
docker compose -f infra/docker-compose.yml up -d --build --wait
uv run python infra/smoke_test.py
```

Expected: `OK: SPA, Keycloak, proveedores, administración y operación responden (…)`. Si el stack ya existía antes de este plan, la migración 0003 de `proveedores` corre sola al arrancar el contenedor.

- [ ] **Step 8: Documentación**

**Spec de administración** (`docs/superpowers/specs/2026-10-08-gestion-administracion-design.md`):
- fila "Estado": `Aprobado por el residente; implementado en los planes "Usuarios y acceso" y "Operación del sistema"`;
- §3.3: borre la fila de `evento_procesado` y agregue debajo de la tabla: "- Los eventos de `proveedores` son idempotentes por `clave_origen` (`proveedores:{event_id}`), así que no hace falta una tabla de eventos procesados.";
- §3.4: reemplace el punto de los roles por "Los roles se leen **por usuario** (`/users/{id}/role-mappings/realm`), con hasta 20 consultas a la vez: los endpoints `/roles/*` piden `view-realm`, que la cuenta de servicio no tiene. Razonable hasta unos 1,000 usuarios.";
- §3.7: cambie `infra/postgres/crear-administracion.sh` por "`infra/postgres/administracion.sh` (el mismo script que corre al crear el volumen, montado como `20-administracion.sh`)";
- §9, en `IdentidadKeycloak`: "roles por rol" → "roles por usuario".

**PRD** (`docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md`):
- §2.1, en el diagrama, agregue `GW --> AD[administracion]`, `AD -- HTTP --> KC` y `MQ -- eventos --> AD`;
- §2.1, en la tabla de servicios, agregue después de `proveedores`:
  `| **administracion** | FastAPI | Usuarios y roles (vía la API de Keycloak), bitácora de actividad de solo inserción, correos del sistema, estado de los servicios y panel de administración. | `administracion_db` |`
- §2.2, en "Eventos iniciales", agregue:
  `| `servicio.actualizado` | proveedores | administracion, inteligencia | Cambios del catálogo (con quién los hizo) y copia local del servicio. |`
  `| `importacion.completada` · `importacion.rechazada` | proveedores | administracion | Bitácora de importaciones con quién las hizo. |`
- §4.1, agregue la fila `| administracion | Actividad (bitácora de solo inserción), CorreoEnviado, CursorEventos |`;
- §5.1, en la matriz de permisos, agregue `| Gestionar usuarios y ver actividad, correos y estado del sistema | ✔ | | | |` y `| Consultar el Centro de ayuda | ✔ | ✔ | ✔ | |`.

**README.md:**
- en "Arranque rápido", después de la línea de la prueba de humo, agregue: "También deja un servicio `HUMO-SERV` en el catálogo, que reactiva en cada corrida.";
- en "Interfaz", agregue:
  - "- Área **Sistema** (solo administración): Panel, Usuarios, Actividad (con exportación a CSV), Catálogo, Estado del sistema, Correos, Importación y Configuración."
  - "- Área **Soporte**: Centro de ayuda con guías, preguntas frecuentes y glosario (`web/src/ayuda.ts`); se abre también con el botón "?" de la barra superior."
- en "Estructura", la fila de `services/administracion` dice: "Microservicio de administración: usuarios, bitácora, correos, estado del sistema y panel (`/api/administracion/`)";
- en "Limitaciones conocidas", reemplace "Eventos sin cola enlazada" por: "**Eventos sin cola enlazada.** Un evento que se publica sin colas enlazadas al exchange se descarta; el outbox conserva el registro. `administracion` declara su cola (`administracion.actividad`) al arrancar, así que solo se pierden los eventos publicados antes de su primer arranque. El Plan B declarará toda la topología antes de publicar y agregará el reproceso.";
- en "Desarrollo", agregue la fila `| Versión que muestra el Estado del sistema | variable `VERSION_APP` de `infra/.env` (por defecto `desarrollo`) |`.

- [ ] **Step 9: Calidad y commit**

```bash
(cd web && npx prettier --write src && npm run lint && npm run build && npx vitest run)
uv run ruff format --check . && uv run ruff check . && uv run mypy
git add web/src .github/dependabot.yml infra/smoke_test.py docs/superpowers/specs README.md
git commit -m "feat: foco en Importación, Dependabot y prueba de humo de la operación; documentación del plan 2" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Revisión en el navegador y documento de QA

La hace el **controlador**, porque necesita el panel de navegador. Las correcciones se despachan a un implementador y pasan por revisión.

**Files:**
- Create: `docs/qa/revision-gestion-administracion.md`
- Modify: los archivos que requieran correcciones, cada una con su prueba cuando se pueda comprobar en jsdom o pytest.

- [ ] **Step 1: Stack y prueba de humo**

```bash
export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"; export MSYS_NO_PATHCONV=1
docker compose -f infra/docker-compose.yml up -d --build --wait
uv run python infra/smoke_test.py
```

Expected: `OK: …`.

- [ ] **Step 2: Flujos en el navegador (controlador)**

En `http://localhost:8080`, con `admin1`:
1. **Menú.** "Sistema" muestra Panel, Usuarios, Actividad, Catálogo, Estado del sistema, Correos, Importación y Configuración; "Soporte" muestra Centro de ayuda. El Panel solo se marca activo en `/sistema`.
2. **Catálogo.**
   - Dé de alta un servicio de prueba; edítelo.
   - En un servicio con contratos, categoría y moneda aparecen bloqueadas con su explicación.
   - Desactívelo y actívelo: el foco queda en el botón que reemplaza al pulsado.
3. **Actividad.**
   - Los cambios del paso 2 aparecen en menos de unos segundos ("Dio de alta el servicio …").
   - Importe un archivo con errores en Importación: aparece "Intentó importar …; el archivo tenía N errores".
   - Filtre por persona, tipo y fechas; los filtros quedan en la URL.
   - "Exportar CSV" descarga `actividad.csv`, que abre bien en Excel (acentos correctos).
4. **Estado del sistema.**
   - Todos "Sano" con su tiempo.
   - Detenga Mailpit (`docker compose -f infra/docker-compose.yml stop mailpit`): en el siguiente ciclo, o con "Volver a comprobar", el buzón aparece "Caído" y los demás siguen bien. Vuelva a levantarlo (`start mailpit`).
5. **Panel.** Las cuatro tarjetas muestran datos y enlazan a su pantalla; la actividad reciente y las últimas importaciones coinciden con Actividad.
6. **Centro de ayuda.**
   - Con `comprador1`: sin el tema Administración ni sus preguntas.
   - Con `admin1`: con ambos.
   - La búsqueda "contraseña temporal" encuentra los artículos; el botón "?" de la barra superior abre la ayuda.
7. **Importación.** Al pasar de paso, el foco va al título del paso nuevo.
8. **Accesibilidad.** Corra axe con contraste (en Vite, como en la revisión anterior) sobre Panel, Actividad, Catálogo (con el panel de alta abierto), Estado del sistema, Centro de ayuda y un artículo, a 375, 768, 1024 y 1440 px y en claro y oscuro: 0 violaciones y sin scroll horizontal.

- [ ] **Step 3: Corregir (implementador)**

Corrija cada hallazgo con su prueba cuando aplique, en un commit `fix(…)` por hallazgo. El controlador vuelve a verificar en el navegador.

- [ ] **Step 4: Documento de QA**

`docs/qa/revision-gestion-administracion.md`, con la estructura de `docs/qa/revision-claridad-y-acceso.md`:
- herramientas y método (gateway con CSP; Vite para axe; anchos y temas);
- tabla de flujos del Step 2 con su resultado;
- tabla de axe por pantalla, ancho y tema;
- hallazgos con su causa, su corrección y el commit;
- lo que queda fuera del alcance de la revisión.

```bash
git add docs/qa/revision-gestion-administracion.md
git commit -m "docs(qa): revisión en navegador de la gestión de administración" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
