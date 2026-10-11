# Servicio de inteligencia (Plan B1) — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un servicio `inteligencia` nuevo que, a partir de los eventos de `proveedores`, calcula el precio justo (línea base y modelo ML), la puntuación de proveedores, las alertas y los KPIs del Tablero, y los expone por API; la topología de RabbitMQ queda declarada antes de publicar y los cambios de configuración y los entrenamientos quedan en la bitácora de administración.

**Architecture:** La topología de RabbitMQ vive en `libs/comun/topologia.py` y en `infra/rabbitmq/definitions.json` (iguales, verificado por prueba); un contenedor de inicio la aplica con la API de administración y el relay del outbox publica con `mandatory=True`. El consumidor de eventos de `administracion` pasa a `libs/comun` y lo usan los dos servicios. `inteligencia` guarda una copia local de proveedores, servicios, tipo de cambio, contratos y desempeño (idempotente por `event_id`), calcula todo en funciones puras de `dominio/` y publica sus propios eventos (`configuracion.actualizada`, `modelo.entrenado`) con su outbox.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.1 async + asyncpg, Alembic, aio-pika 10, numpy, scikit-learn (`HistGradientBoostingRegressor`), joblib, Hypothesis, pytest + Testcontainers (PostgreSQL y RabbitMQ), Docker Compose, Nginx; en la web, React 19 + Vitest (solo el filtro y los textos de Actividad).

**Spec:** `docs/superpowers/specs/2026-10-10-servicio-inteligencia-design.md` (§2 B1, §3–§6, §8–§12). La especificación de origen `docs/superpowers/specs/2026-10-01-experiencia-e-inteligencia-design.md` (§4.4) detalla los cálculos que este documento resume.

## Global Constraints

**Rama y entorno**
- Rama `feat/servicio-inteligencia`, creada desde `main` en `42d7103`; la especificación está en `910768f`.
- Las pruebas de integración usan Testcontainers con `postgres:17-alpine` y `rabbitmq:4.1-alpine`; las que necesitan la API de administración de RabbitMQ usan `rabbitmq:4.1-management-alpine`.

**Topología (idéntica en `comun/topologia.py` y en `infra/rabbitmq/definitions.json`)**
- Exchange `eventos` (topic, ya existe) y exchange `eventos.dlx` (direct).
- Colas de consumo, *quorum*, con `ARGUMENTOS_COLA = {"x-queue-type": "quorum", "x-delivery-limit": 5}`:
  - `inteligencia.eventos`: `proveedor.*`, `servicio.*`, `contrato.*`, `desempeno.*`, `tipo_cambio.*`.
  - `administracion.actividad`: `importacion.*`, `servicio.*`, `configuracion.*`, `modelo.*`.
- Cola de fallidos por cola: `<cola>.dlq` (quorum), enlazada a `eventos.dlx` con la clave igual al nombre de la cola.
- La dead-letter se configura con la política `fallidos-<cola>` (`dead-letter-exchange: eventos.dlx`, `dead-letter-routing-key: <cola>`), nunca con argumentos de la cola.

**Eventos nuevos (payloads exactos)**
- `servicio.actualizado` (copia, al importar el catálogo y en el reproceso): `{id, codigo, nombre, categoria, unidad, moneda, activo}`, **sin** `cambio`, `campos` ni `actor`.
- `tipo_cambio.registrado`: `{periodo: "AAAA-MM-01", usd_mxn: "17.1234"}`.
- `configuracion.actualizada`: `{cambios: [{campo, anterior, nuevo}], actor}`.
- `modelo.entrenado`: `{version, mape, mape_linea_base, cobertura, promovido, origen: "manual" | "automatico", actor}`.
- `actor` es `{id, nombre}`; en un entrenamiento automático, `{"id": null, "nombre": "Sistema (automático)"}`.

**Cálculos de dominio**
- Línea base:
  - ventana de 24 meses hasta la fecha de referencia;
  - percentiles P25/P50/P75 por servicio y tercil de cantidad, con precios ajustados por inflación a la fecha de referencia;
  - con menos de 8 observaciones en el tercil (`MIN_OBSERVACIONES = 8`) se usa la línea base de la categoría, en forma relativa (precio entre la mediana de su servicio), con confianza `"baja"`;
  - un servicio sin observaciones en la ventana no tiene referencia.
- Inflación configurable, por defecto `4.50` % anual.
- Modelo ML:
  - tres `HistGradientBoostingRegressor(loss="quantile")` (0.25 / 0.5 / 0.75) sobre `log(precio deflactado)`;
  - variables: servicio, categoría, log(cantidad), plazo en meses, moneda, tamaño del proveedor y tipo;
  - validación temporal con los últimos 6 meses;
  - se promueve solo si su MAPE del P50 es menor que el de la línea base;
  - solo se usa para servicios que estaban en su entrenamiento.
- Reentrenamiento automático:
  - con 50 líneas de contrato nuevas desde el último entrenamiento (`MIN_LINEAS_NUEVAS = 50`);
  - y si la última llegó hace 30 s o más (`ESPERA_TRAS_ULTIMA_S = 30`);
  - lo revisa un bucle cada 60 s;
  - nunca dos entrenamientos a la vez.
- Puntuación (0–100):
  - KPIs de los últimos 12 meses con decaimiento de vida media 6 meses;
  - percentil de cada KPI (tiempo de resolución e incidentes invertidos) dentro de la categoría principal (la primera de sus categorías) cuando esa categoría tiene al menos 20 proveedores con desempeño (`MIN_PROVEEDORES_CATEGORIA = 20`); si tiene menos, contra todos los proveedores;
  - pesos por defecto: SLA 30, resolución 20, incidentes 20, entregas 15, satisfacción 15;
  - contracción bayesiana `(n·score + k·media_categoría) / (n + k)` con `k = 6`;
  - tendencia contra hace 3 meses;
  - "historial corto" con menos de 6 meses.
- Alertas:
  - vencimiento a 90 / 60 / 30 días, con severidad `informativa` / `media` / `alta`;
  - sobreprecio: precio > P75, severidad `media`;
  - riesgo: puntuación < umbral (por defecto 40), severidad `alta`, o caída > 10 puntos en 3 meses, severidad `media`.
- Unidades:
  - `usuario_mes`, `vcpu_mes`, `gb_mes` y `mes` son mensuales: la cantidad es por mes;
  - `hora` y `ticket` son por consumo: la cantidad es el total del contrato.
- Fórmulas:
  - `cantidad_mensual` = cantidad (mensual) o cantidad / meses del contrato (por consumo);
  - valor mensual = `cantidad_mensual × precio`;
  - ahorro potencial = `(precio − P50) × cantidad_mensual × meses restantes`, nunca negativo.
- "Hoy" es la fecha en `America/Mexico_City`.
- Los montos son `Decimal` en Python y texto decimal en JSON; los KPIs del Tablero van en MXN al último tipo de cambio.

**API (`/api/inteligencia/`)**
- Problem Details en español con `codigo`; errores de campo `{campo, mensaje}`.
- "Interno" son los roles `admin`, `comprador` y `aprobador`. Reentrenar, `PUT /configuracion` y `GET /datos` son solo `admin`.
- `/salud/listo` comprueba solo PostgreSQL.

**Dependencias nuevas**
- `inteligencia`: `numpy>=2.1`, `scikit-learn>=1.6`, `scipy>=1.14`, `tzdata>=2024.1` (además de las que comparte con `administracion`).
- Raíz (dev): `hypothesis>=6.120`.
- mypy: `sklearn.*`, `joblib` y `scipy.*` con `ignore_missing_imports`.

**Seguridad de credenciales**
- Nunca escriba contraseñas ni secretos en comandos, archivos versionados o reportes; `infra/.env` no se versiona.
- Las contraseñas de desarrollo están en `infra/keycloak/realm-plataforma.json`; no las repita.

**Calidad**
- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` y `uv run pytest` sin errores ni advertencias.
- Si la tarea toca `web/`: `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check "src/**/*.{ts,tsx}"` limpios.

**Commits**
- Conventional Commits en español.
- Mensaje: asunto, una línea en blanco y `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (dos `-m`).
- Verifique con `git log -1 --format=%B`.

## Review Focus

1. **Topología sin aplicar.** Con un RabbitMQ recién creado, o si el contenedor de inicio falló, los eventos quedan pendientes en el outbox: no se pierden, y un tipo sin cola no frena a los que sí la tienen. Prueba: Task 1 (`test_un_evento_sin_cola_queda_pendiente_y_no_frena_a_los_demas`).
2. **Eventos en desorden.** Un contrato llega antes que su proveedor, o una línea trae un servicio que la copia local aún no tiene: se guarda sin fallar y los cálculos lo usan cuando llega lo demás. Prueba: Task 7 (`test_un_contrato_de_un_proveedor_desconocido_se_guarda`).
3. **Servicio sin historia.** Un servicio sin contratos en 24 meses, o creado después del último entrenamiento: la referencia responde 404 `sin_observaciones` o usa la línea base, nunca un 500. Pruebas: Task 8 (`test_sin_observaciones_no_hay_referencia`), Task 11 (`test_un_servicio_que_el_modelo_no_conoce_usa_la_linea_base`) y Task 12 (`test_referencia_de_un_servicio_sin_contratos`).
4. **Reentrenamientos simultáneos o fallidos.** Un segundo pedido mientras otro corre responde 409 `entrenamiento_en_curso`; un entrenamiento que falla no deja el estado "entrenando" pegado. Pruebas: Task 11 (`test_un_entrenamiento_fallido_libera_el_candado`) y Task 13 (`test_un_segundo_entrenamiento_mientras_corre_el_primero`).
5. **Configuración inválida.** Pesos que no suman 100, pesos negativos o umbral fuera de rango responden 422 con el error junto al campo y no cambian nada; guardar sin cambios no publica evento. Prueba: Task 13 (`test_pesos_que_no_suman_100`, `test_guardar_sin_cambios_no_publica`).

## Tareas

Se ejecutan en orden; cada una deja el repositorio verde.

| # | Tarea | Archivos principales |
|---|---|---|
| 1 | El relay publica con `mandatory=True` | `libs/comun/src/comun/outbox.py` |
| 2 | Topología de RabbitMQ | `libs/comun/src/comun/topologia.py`, `infra/rabbitmq/definitions.json`, `infra/docker-compose.yml` |
| 3 | Consumidor de eventos común | `libs/comun/src/comun/consumidor.py`, `services/administracion/src/administracion/eventos.py` |
| 4 | `proveedores`: unidad bloqueada y eventos de copia | `services/proveedores/src/proveedores/api/catalogo.py`, `importacion/aplicar.py`, `web/src/componentes/FormularioServicio.tsx` |
| 5 | `proveedores`: reproceso | `services/proveedores/src/proveedores/reproceso.py` |
| 6 | Armazón de `inteligencia` | `services/inteligencia/`, `infra/postgres/inteligencia.sh`, compose, Nginx |
| 7 | Copia local por eventos | `services/inteligencia/src/inteligencia/eventos.py` |
| 8 | Línea base del precio justo | `dominio/precios.py` |
| 9 | Puntuación de proveedores | `dominio/puntuacion.py` |
| 10 | Alertas y KPIs del Tablero | `dominio/contratos.py`, `dominio/alertas.py`, `dominio/tablero.py` |
| 11 | Modelo de precios y reentrenamiento | `modelo.py`, `precio_justo.py`, `consultas.py`, `entrenamiento.py` |
| 12 | API: Tablero, alertas y precios | `contexto.py`, `api/tablero.py`, `api/precios.py` |
| 13 | API: proveedores, ranking, configuración, modelos y datos | `api/proveedores.py`, `api/ajustes.py` |
| 14 | Actividad de la inteligencia | `administracion/eventos.py`, `textos.py`, `bitacora.py`, `web/src/actividad.ts` |
| 15 | Estado del sistema | `administracion/estado.py` |
| 16 | Validación contra la verdad oculta | `inteligencia/validacion.py`, `docs/qa/validacion-inteligencia.md` |
| 17 | Prueba de humo y documentación | `infra/smoke_test.py`, `README.md`, PRD |

---

### Task 1: El relay del outbox publica con `mandatory=True`

Hoy el relay publica con `mandatory=False`: si ninguna cola recibe un tipo de evento, RabbitMQ lo descarta y el outbox lo marca como publicado. Con `mandatory=True` y `on_return_raises=True`, un evento sin cola vuelve como `PublishError`, queda pendiente y se reintenta en el siguiente ciclo, sin frenar a los demás.

**Files:**
- Modify: `libs/comun/src/comun/outbox.py` (`RelayOutbox.conectar`, `RelayOutbox.publicar_pendientes`)
- Test: `libs/comun/tests/test_outbox.py`

**Interfaces:**
- Produces: `RelayOutbox.publicar_pendientes() -> int` devuelve los eventos **publicados** (antes, los leídos). Un evento sin cola queda con `publicado_en = None` y se registra en el log con el texto `sin cola de destino`.

- [ ] **Step 1: Write the failing tests**

En `libs/comun/tests/test_outbox.py`:

1. Agregue este fixture después de `fabrica`:

```python
@pytest.fixture
async def cola_comodin(url_rabbitmq: str) -> AsyncIterator[None]:
    """Una cola que recibe todo: sin ella, con mandatory=True los eventos vuelven sin publicarse."""
    conexion = await aio_pika.connect_robust(url_rabbitmq)
    try:
        canal = await conexion.channel()
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        cola = await canal.declare_queue(exclusive=True)
        await cola.bind(exchange, routing_key="#")
        yield
    finally:
        await conexion.close()
```

2. Agregue `cola_comodin: None` como parámetro de `test_ejecutar_publica_en_segundo_plano`, `test_falla_de_publicacion_revierte_la_transaccion_y_se_reintenta` y `test_ejecutar_sobrevive_a_una_publicacion_fallida`; su cuerpo no cambia. Para que ruff no lo marque como argumento sin usar, decore cada una con `@pytest.mark.usefixtures("cola_comodin")` en vez del parámetro (elija una forma y úsela en las tres).

3. En `test_falla_de_publicacion_revierte_la_transaccion_y_se_reintenta`, cambie:

```python
        assert falla.opciones == {"mandatory": False, "timeout": TIMEOUT_PUBLICACION}
```

por:

```python
        assert falla.opciones == {"mandatory": True, "timeout": TIMEOUT_PUBLICACION}
```

4. Agregue al final del archivo:

```python
async def test_un_evento_sin_cola_queda_pendiente_y_no_frena_a_los_demas(
    fabrica: async_sessionmaker[AsyncSession],
    url_rabbitmq: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    relay = RelayOutbox(fabrica, OutboxPrueba, url_rabbitmq)
    await relay.conectar()
    conexion = await aio_pika.connect_robust(url_rabbitmq)
    try:
        canal = await conexion.channel()
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        cola = await canal.declare_queue(exclusive=True)
        await cola.bind(exchange, routing_key="contrato.*")
        async with fabrica() as sesion, sesion.begin():
            registrar_evento(sesion, OutboxPrueba, "huerfano.creado", {"n": 1})
            registrar_evento(sesion, OutboxPrueba, "contrato.registrado", {"n": 2})

        assert await relay.publicar_pendientes() == 1
        mensaje = await cola.get(timeout=5)
        await mensaje.ack()
        assert json.loads(mensaje.body)["type"] == "contrato.registrado"
        pendientes = [f.tipo for f in await _todas(fabrica) if f.publicado_en is None]
        assert pendientes == ["huerfano.creado"]
        assert "sin cola de destino" in caplog.text

        # Cuando aparece una cola para ese tipo, el siguiente ciclo lo publica.
        otra = await canal.declare_queue(exclusive=True)
        await otra.bind(exchange, routing_key="huerfano.*")
        assert await relay.publicar_pendientes() == 1
        assert all(f.publicado_en is not None for f in await _todas(fabrica))
    finally:
        await conexion.close()
        await relay.cerrar()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest libs/comun/tests/test_outbox.py -q`
Expected: FAIL. La prueba nueva publica 2 en vez de 1, y el diccionario de opciones trae `mandatory: False`.

- [ ] **Step 3: Implement**

En `libs/comun/src/comun/outbox.py`:

- importe `from aio_pika.exceptions import PublishError`;
- en `conectar`, abra el canal así:

```python
        # on_return_raises: un evento que ninguna cola recibe vuelve y publish lanza PublishError.
        canal = await self._conexion.channel(publisher_confirms=True, on_return_raises=True)
```

- reemplace el bucle de `publicar_pendientes` (desde `filas = …` hasta el `return`) por:

```python
            filas = (await sesion.scalars(consulta)).all()
            publicados = 0
            for fila in filas:
                mensaje = aio_pika.Message(
                    json.dumps(sobre_evento(fila)).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    message_id=str(fila.id),
                    correlation_id=fila.correlation_id,
                    type=fila.tipo,
                )
                # mandatory=True: si ninguna cola recibe este tipo (topología sin aplicar), RabbitMQ
                # lo devuelve; queda pendiente y se reintenta, sin frenar a los demás.
                # timeout: un broker detenido no debe retener la transacción ni los bloqueos de
                # fila (FOR UPDATE) indefinidamente.
                try:
                    await self._exchange.publish(
                        mensaje,
                        routing_key=fila.tipo,
                        mandatory=True,
                        timeout=TIMEOUT_PUBLICACION,
                    )
                except PublishError:
                    # ponytail: si hay más de `lote` eventos sin cola delante, los que sí tienen
                    # cola esperan detrás de ellos; solo pasa con la topología sin aplicar.
                    log.warning(
                        "Evento %s (%s) sin cola de destino; queda pendiente", fila.id, fila.tipo
                    )
                    continue
                fila.publicado_en = datetime.now(UTC)
                publicados += 1
        return publicados
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest libs/comun -q`
Expected: PASS, sin advertencias.

Run: `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: limpios.

- [ ] **Step 5: Commit**

```bash
git add libs/comun/src/comun/outbox.py libs/comun/tests/test_outbox.py
git commit -m "feat(comun): el relay deja pendiente un evento sin cola en lugar de perderlo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Topología de RabbitMQ declarada antes de publicar

**Files:**
- Create: `libs/comun/src/comun/topologia.py`
- Create: `infra/rabbitmq/definitions.json`
- Create: `libs/comun/tests/test_topologia.py`
- Modify: `infra/docker-compose.yml` (servicio `rabbitmq-topologia`; `proveedores` y `administracion` dependen de él)

**Interfaces:**
- Produces (`comun.topologia`):
  - `EXCHANGE_FALLIDOS = "eventos.dlx"`.
  - `ARGUMENTOS_COLA: dict[str, Any] = {"x-queue-type": "quorum", "x-delivery-limit": 5}`.
  - `Cola(nombre: str, claves: tuple[str, ...])` con la propiedad `fallidos -> str` (`f"{nombre}.dlq"`).
  - `COLA_INTELIGENCIA`, `COLA_ADMINISTRACION`, `COLAS` y `TIPOS_EVENTO: frozenset[str]`.
  - `coincide(clave: str, tipo: str) -> bool`, `colas_de(tipo: str) -> list[str]` y `definiciones() -> dict[str, list[dict[str, Any]]]`.

- [ ] **Step 1: Write the failing tests**

Cree `libs/comun/tests/test_topologia.py`:

```python
"""La topología de infra/rabbitmq/definitions.json: coincide con comun.topologia, cubre todo evento
que se publica y RabbitMQ la acepta."""

import asyncio
import json
import re
from collections.abc import Iterator
from pathlib import Path

import aio_pika
import httpx
import pytest
from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import (
    ARGUMENTOS_COLA,
    COLA_ADMINISTRACION,
    COLA_INTELIGENCIA,
    TIPOS_EVENTO,
    coincide,
    colas_de,
    definiciones,
)
from testcontainers.community.rabbitmq import RabbitMqContainer

RAIZ = Path(__file__).resolve().parents[3]
ARCHIVO = RAIZ / "infra" / "rabbitmq" / "definitions.json"
# registrar_evento(sesion, Modelo, "tipo.evento", …): el tipo siempre se escribe como literal.
PUBLICACION = re.compile(r'registrar_evento\(\s*\w+,\s*\w+,\s*"([a-z_]+\.[a-z_]+)"')


def test_el_archivo_coincide_con_el_modulo() -> None:
    assert json.loads(ARCHIVO.read_text(encoding="utf-8")) == definiciones()


def test_las_claves_comparan_palabra_por_palabra() -> None:
    assert coincide("servicio.*", "servicio.actualizado")
    assert not coincide("servicio.*", "contrato.registrado")
    assert not coincide("servicio.*", "servicio.actualizado.extra")
    assert colas_de("servicio.actualizado") == [
        COLA_INTELIGENCIA.nombre,
        COLA_ADMINISTRACION.nombre,
    ]
    assert colas_de("importacion.completada") == [COLA_ADMINISTRACION.nombre]
    assert colas_de("modelo.entrenado") == [COLA_ADMINISTRACION.nombre]


def _tipos_publicados() -> set[str]:
    tipos: set[str] = set()
    for ruta in RAIZ.glob("services/*/src/**/*.py"):
        tipos.update(PUBLICACION.findall(ruta.read_text(encoding="utf-8")))
    return tipos


def test_cada_evento_publicado_esta_declarado_y_tiene_cola() -> None:
    publicados = _tipos_publicados()
    assert "contrato.registrado" in publicados  # que la búsqueda no quede vacía
    assert publicados <= TIPOS_EVENTO, sorted(publicados - TIPOS_EVENTO)
    assert sorted(t for t in TIPOS_EVENTO if not colas_de(t)) == []


@pytest.fixture(scope="module")
def rabbitmq() -> Iterator[tuple[str, str]]:
    """(URL AMQP, URL de la API de administración) de un RabbitMQ con el plugin de administración."""
    contenedor = RabbitMqContainer(
        "rabbitmq:4.1-management-alpine", username="prueba", password="prueba"
    ).with_exposed_ports(15672)
    with contenedor as rmq:
        host = rmq.get_container_host_ip()
        yield (
            f"amqp://prueba:prueba@{host}:{rmq.get_exposed_port(5672)}/",
            f"http://{host}:{rmq.get_exposed_port(15672)}/api",
        )


async def _aplicar(api: str) -> None:
    contenido = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    async with httpx.AsyncClient(auth=("prueba", "prueba"), timeout=5) as http:
        for _ in range(120):  # la API de administración arranca unos segundos después que AMQP
            try:
                respuesta = await http.post(f"{api}/definitions", json=contenido)
                if respuesta.is_success:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.5)
    pytest.fail("RabbitMQ no aceptó las definiciones")


@pytest.mark.integracion
async def test_rabbitmq_acepta_la_topologia_y_manda_a_fallidos_tras_5_entregas(
    rabbitmq: tuple[str, str],
) -> None:
    amqp, api = rabbitmq
    conexion = await aio_pika.connect_robust(amqp)
    async with conexion:
        canal = await conexion.channel()
        # Un entorno existente: la cola de administración ya la había declarado su consumidor.
        await canal.declare_queue(
            COLA_ADMINISTRACION.nombre, durable=True, arguments=ARGUMENTOS_COLA
        )
        await _aplicar(api)
        await _aplicar(api)  # aplicarla de nuevo no cambia nada

        exchange = await canal.get_exchange(EXCHANGE_EVENTOS)
        await exchange.publish(
            aio_pika.Message(b'{"prueba": 1}'), routing_key="contrato.registrado"
        )
        cola = await canal.get_queue(COLA_INTELIGENCIA.nombre)
        for _ in range(10):  # se rechaza cada entrega hasta que RabbitMQ la manda a fallidos
            mensaje = await cola.get(timeout=5, fail=False)
            if mensaje is None:
                break
            await mensaje.reject(requeue=True)

        fallidos = await canal.get_queue(COLA_INTELIGENCIA.fallidos)
        muerto = None
        for _ in range(50):
            muerto = await fallidos.get(timeout=5, fail=False)
            if muerto is not None:
                break
            await asyncio.sleep(0.1)
        assert muerto is not None
        await muerto.ack()
        assert muerto.body == b'{"prueba": 1}'
        # contrato.* no va a administración.
        administracion = await canal.get_queue(COLA_ADMINISTRACION.nombre)
        assert await administracion.get(timeout=5, fail=False) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest libs/comun/tests/test_topologia.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'comun.topologia'`.

- [ ] **Step 3: Implement the module**

Cree `libs/comun/src/comun/topologia.py`:

```python
"""Topología de RabbitMQ que comparten los servicios: qué colas reciben qué eventos.

`infra/rabbitmq/definitions.json` la declara antes de que alguien publique (el contenedor
`rabbitmq-topologia` la aplica con la API de administración). Una prueba verifica que el archivo y
este módulo coinciden, y que todo evento que se publica llega a alguna cola.
"""

import re
from dataclasses import dataclass
from typing import Any

from comun.outbox import EXCHANGE_EVENTOS

EXCHANGE_FALLIDOS = "eventos.dlx"
VHOST = "/"
# Quorum: sobrevive a los reinicios. Tras 5 entregas fallidas, RabbitMQ manda el mensaje a la cola
# de fallidos de esa cola (la política se aplica en definitions.json, no con argumentos: cambiar
# los argumentos de una cola que ya existe falla con PRECONDITION_FAILED).
ARGUMENTOS_COLA: dict[str, Any] = {"x-queue-type": "quorum", "x-delivery-limit": 5}


@dataclass(frozen=True)
class Cola:
    nombre: str
    claves: tuple[str, ...]

    @property
    def fallidos(self) -> str:
        return f"{self.nombre}.dlq"


COLA_INTELIGENCIA = Cola(
    "inteligencia.eventos",
    ("proveedor.*", "servicio.*", "contrato.*", "desempeno.*", "tipo_cambio.*"),
)
COLA_ADMINISTRACION = Cola(
    "administracion.actividad",
    ("importacion.*", "servicio.*", "configuracion.*", "modelo.*"),
)
COLAS = (COLA_INTELIGENCIA, COLA_ADMINISTRACION)

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
    }
)


def coincide(clave: str, tipo: str) -> bool:
    """Si la clave de enlace de un exchange topic ("servicio.*") recibe ese tipo de evento."""
    partes_clave, partes_tipo = clave.split("."), tipo.split(".")
    return len(partes_clave) == len(partes_tipo) and all(
        parte in ("*", palabra) for parte, palabra in zip(partes_clave, partes_tipo, strict=True)
    )


def colas_de(tipo: str) -> list[str]:
    return [cola.nombre for cola in COLAS if any(coincide(c, tipo) for c in cola.claves)]


def _exchange(nombre: str, tipo: str) -> dict[str, Any]:
    return {
        "name": nombre,
        "vhost": VHOST,
        "type": tipo,
        "durable": True,
        "auto_delete": False,
        "internal": False,
        "arguments": {},
    }


def _cola(nombre: str, argumentos: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": nombre,
        "vhost": VHOST,
        "durable": True,
        "auto_delete": False,
        "arguments": argumentos,
    }


def _enlace(origen: str, destino: str, clave: str) -> dict[str, Any]:
    return {
        "source": origen,
        "vhost": VHOST,
        "destination": destino,
        "destination_type": "queue",
        "routing_key": clave,
        "arguments": {},
    }


def definiciones() -> dict[str, list[dict[str, Any]]]:
    """El contenido que debe tener infra/rabbitmq/definitions.json."""
    colas: list[dict[str, Any]] = []
    enlaces: list[dict[str, Any]] = []
    politicas: list[dict[str, Any]] = []
    for cola in COLAS:
        colas.append(_cola(cola.nombre, ARGUMENTOS_COLA))
        colas.append(_cola(cola.fallidos, {"x-queue-type": "quorum"}))
        enlaces.extend(_enlace(EXCHANGE_EVENTOS, cola.nombre, clave) for clave in cola.claves)
        enlaces.append(_enlace(EXCHANGE_FALLIDOS, cola.fallidos, cola.nombre))
        politicas.append(
            {
                "vhost": VHOST,
                "name": f"fallidos-{cola.nombre}",
                "pattern": f"^{re.escape(cola.nombre)}$",
                "apply-to": "queues",
                "priority": 0,
                "definition": {
                    "dead-letter-exchange": EXCHANGE_FALLIDOS,
                    "dead-letter-routing-key": cola.nombre,
                },
            }
        )
    return {
        "exchanges": [_exchange(EXCHANGE_EVENTOS, "topic"), _exchange(EXCHANGE_FALLIDOS, "direct")],
        "queues": colas,
        "bindings": enlaces,
        "policies": politicas,
    }
```

- [ ] **Step 4: Generate the definitions file**

Genérelo desde el módulo (así coinciden byte a byte con lo que la prueba compara):

```bash
uv run python -c "import json; from comun.topologia import definiciones; print(json.dumps(definiciones(), indent=2, ensure_ascii=False))" > infra/rabbitmq/definitions.json
```

Revise que `infra/rabbitmq/definitions.json` empiece así y que termine en salto de línea:

```json
{
  "exchanges": [
    {
      "name": "eventos",
      "vhost": "/",
      "type": "topic",
      "durable": true,
      "auto_delete": false,
      "internal": false,
      "arguments": {}
    },
```

Debe tener 4 colas (`inteligencia.eventos`, `inteligencia.eventos.dlq`, `administracion.actividad` y `administracion.actividad.dlq`), 11 enlaces y 2 políticas (`fallidos-inteligencia.eventos` y `fallidos-administracion.actividad`, con `"pattern": "^inteligencia\\.eventos$"` y `"pattern": "^administracion\\.actividad$"`). En Windows, si la redirección escribe con CRLF, conviértalo a LF (el repositorio guarda LF).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest libs/comun/tests/test_topologia.py -q`
Expected: PASS (4 pruebas; la de integración tarda unos segundos en levantar RabbitMQ con su API de administración).

- [ ] **Step 6: Apply the topology in Docker Compose**

En `infra/docker-compose.yml`, agregue después del servicio `rabbitmq`:

```yaml
  rabbitmq-topologia:
    image: curlimages/curl:8.11.1
    # Declara colas, enlaces y colas de fallidos antes de que alguien publique. La API de
    # administración fusiona: no borra nada ni toca los usuarios. Aplicarla de nuevo no cambia nada.
    environment:
      RABBITMQ_PASSWORD: ${RABBITMQ_PASSWORD}
    volumes:
      - ./rabbitmq/definitions.json:/definitions.json:ro
    entrypoint: ["sh", "-c"]
    command:
      - >-
        curl -fsS --retry 20 --retry-delay 3 --retry-all-errors
        -u "plataforma:$${RABBITMQ_PASSWORD}" -H "content-type: application/json"
        -X POST --data-binary @/definitions.json http://rabbitmq:15672/api/definitions
    depends_on:
      rabbitmq:
        condition: service_healthy
```

y en `depends_on` de `proveedores` y de `administracion`:

```yaml
      rabbitmq-topologia:
        condition: service_completed_successfully
```

`$$` evita que Compose sustituya la variable: la expande el shell del contenedor, así que la contraseña no queda en el comando.

- [ ] **Step 7: Verify in the running stack**

Con las variables de `entorno.md`:

```bash
docker compose -f infra/docker-compose.yml up -d --build --wait
docker compose -f infra/docker-compose.yml exec -T rabbitmq rabbitmqctl list_queues -q name type
docker compose -f infra/docker-compose.yml exec -T rabbitmq rabbitmqctl list_policies -q
```

Expected:
- `up` termina con código 0 (`rabbitmq-topologia` aparece como `Exited (0)`);
- las cuatro colas aparecen como `quorum`;
- las dos políticas `fallidos-…` aparecen.

No imprima ni copie la contraseña.

- [ ] **Step 8: Commit**

```bash
git add libs/comun/src/comun/topologia.py libs/comun/tests/test_topologia.py infra/rabbitmq/definitions.json infra/docker-compose.yml
git commit -m "feat(infra): topología de RabbitMQ con colas de fallidos, declarada antes de publicar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Consumidor de eventos común en `libs/comun`

**Files:**
- Create: `libs/comun/src/comun/consumidor.py`
- Create: `libs/comun/tests/test_consumidor.py`
- Modify: `services/administracion/src/administracion/eventos.py` (usa el consumidor común; quedan `traducir`, `guardar` y `atendedor`)
- Modify: `services/administracion/src/administracion/main.py`
- Modify: `services/administracion/tests/test_eventos.py`

**Interfaces:**
- Consumes: `comun.topologia.Cola`, `ARGUMENTOS_COLA` y `COLA_ADMINISTRACION` (Task 2).
- Produces (`comun.consumidor`):
  - `REINTENTO_S = 5`.
  - `Atender = Callable[[dict[str, Any]], Awaitable[None]]`.
  - `EventoInvalido(ValueError)`.
  - `atender_mensaje(mensaje: AbstractIncomingMessage, atender: Atender) -> None`.
  - `ConsumidorEventos(url_rabbitmq: str, cola: Cola, atender: Atender, prefetch: int = 10)` con `ejecutar()`, `conectado() -> bool` y `cerrar()`.
- Produces (`administracion.eventos`): `atendedor(fabrica) -> Atender`. Se quitan `COLA`, `CLAVES`, `ARGUMENTOS_COLA`, `REINTENTO_CONEXION_S`, `atender` y la clase `ConsumidorEventos`; `EventoInvalido` se importa de `comun.consumidor`.

- [ ] **Step 1: Write the failing tests**

Cree `libs/comun/tests/test_consumidor.py`:

```python
import asyncio
import contextlib
import json
import socket
from collections.abc import AsyncIterator, Iterator
from typing import Any, cast

import aio_pika
import pytest
from aio_pika.abc import AbstractIncomingMessage
from comun.consumidor import (
    REINTENTO_S,
    ConsumidorEventos,
    EventoInvalido,
    atender_mensaje,
)
from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import ARGUMENTOS_COLA, Cola
from sqlalchemy.exc import SQLAlchemyError
from testcontainers.community.rabbitmq import RabbitMqContainer

SOBRE = {"event_id": "e-1", "type": "prueba.creada", "payload": {"n": 1}}


class _MensajeFalso:
    """Lo mínimo de un mensaje entrante: anota ack y reject en la lista compartida."""

    message_id = "m-1"

    def __init__(self, cuerpo: bytes, anotaciones: list[tuple[Any, ...]]) -> None:
        self.body = cuerpo
        self._anotaciones = anotaciones

    async def ack(self) -> None:
        self._anotaciones.append(("ack",))

    async def reject(self, requeue: bool = False) -> None:
        self._anotaciones.append(("reject", requeue))


def _mensaje(cuerpo: bytes, anotaciones: list[tuple[Any, ...]]) -> AbstractIncomingMessage:
    return cast(AbstractIncomingMessage, _MensajeFalso(cuerpo, anotaciones))


async def test_un_evento_atendido_se_confirma() -> None:
    anotaciones: list[tuple[Any, ...]] = []
    recibidos: list[dict[str, Any]] = []

    async def atender(sobre: dict[str, Any]) -> None:
        recibidos.append(sobre)

    await atender_mensaje(_mensaje(json.dumps(SOBRE).encode(), anotaciones), atender)
    assert recibidos == [SOBRE]
    assert anotaciones == [("ack",)]


@pytest.mark.parametrize(
    "cuerpo", [b"no es json", b"[1, 2]", b"\xff\xfe"], ids=["texto", "lista", "binario"]
)
async def test_un_mensaje_mal_formado_se_descarta(cuerpo: bytes) -> None:
    anotaciones: list[tuple[Any, ...]] = []

    async def atender(_sobre: dict[str, Any]) -> None:
        pytest.fail("no debe llegar al manejador")

    await atender_mensaje(_mensaje(cuerpo, anotaciones), atender)
    assert anotaciones == [("reject", False)]


async def test_un_evento_invalido_se_descarta() -> None:
    anotaciones: list[tuple[Any, ...]] = []

    async def atender(_sobre: dict[str, Any]) -> None:
        raise EventoInvalido("falta el payload")

    await atender_mensaje(_mensaje(json.dumps(SOBRE).encode(), anotaciones), atender)
    assert anotaciones == [("reject", False)]


@pytest.mark.parametrize(
    "error",
    [
        SQLAlchemyError("la base de datos no responde"),
        # Con PostgreSQL detenido o inalcanzable, asyncpg relanza el error de red tal cual.
        ConnectionRefusedError("conexión rechazada"),
        socket.gaierror("no se resuelve el nombre"),
        TimeoutError("se agotó la espera"),
    ],
    ids=["sqlalchemy", "conexion_rechazada", "dns", "tiempo_agotado"],
)
async def test_si_falla_la_base_espera_y_devuelve_el_mensaje_a_la_cola(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    anotaciones: list[tuple[Any, ...]] = []

    async def dormir(segundos: float) -> None:
        anotaciones.append(("sleep", segundos))

    async def atender(_sobre: dict[str, Any]) -> None:
        raise error

    monkeypatch.setattr(asyncio, "sleep", dormir)
    await atender_mensaje(_mensaje(json.dumps(SOBRE).encode(), anotaciones), atender)
    # Sin la espera, el mensaje volvería de inmediato y agotaría las 5 entregas en milisegundos.
    assert anotaciones == [("sleep", REINTENTO_S), ("reject", True)]


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


COLA_PRUEBA = Cola("prueba.eventos", ("prueba.*",))


@contextlib.asynccontextmanager
async def _consumidor(
    url: str, recibidos: list[dict[str, Any]]
) -> AsyncIterator[ConsumidorEventos]:
    async def atender(sobre: dict[str, Any]) -> None:
        recibidos.append(sobre)

    consumidor = ConsumidorEventos(url, COLA_PRUEBA, atender)
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


async def _publicar(url: str, cuerpo: bytes, clave: str) -> None:
    conexion = await aio_pika.connect_robust(url)
    async with conexion:
        canal = await conexion.channel()
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        await exchange.publish(aio_pika.Message(cuerpo), routing_key=clave)


@pytest.mark.integracion
async def test_consume_su_cola_y_un_mensaje_mal_formado_no_la_detiene(url_rabbitmq: str) -> None:
    recibidos: list[dict[str, Any]] = []
    async with _consumidor(url_rabbitmq, recibidos):
        await _publicar(url_rabbitmq, b"no es json", "prueba.creada")
        await _publicar(url_rabbitmq, json.dumps(SOBRE).encode(), "prueba.creada")
        await _publicar(url_rabbitmq, json.dumps(SOBRE).encode(), "otra.cosa")  # sin enlace
        for _ in range(100):
            if recibidos:
                break
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.3)
    assert recibidos == [SOBRE]


@pytest.mark.integracion
async def test_la_cola_es_durable_de_tipo_quorum(url_rabbitmq: str) -> None:
    async with _consumidor(url_rabbitmq, []):
        conexion = await aio_pika.connect_robust(url_rabbitmq)
        async with conexion:
            canal = await conexion.channel()
            # Redeclarar con argumentos distintos falla (PRECONDITION_FAILED): si pasa, coinciden.
            cola = await canal.declare_queue(
                COLA_PRUEBA.nombre, durable=True, arguments=ARGUMENTOS_COLA
            )
            assert cola.name == COLA_PRUEBA.nombre
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest libs/comun/tests/test_consumidor.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'comun.consumidor'`.

- [ ] **Step 3: Implement the common consumer**

Cree `libs/comun/src/comun/consumidor.py`:

```python
"""Consumidor de eventos de RabbitMQ con reconexión.

Cada mensaje se entrega como sobre (un dict) a la función `atender` del servicio:
- Un mensaje mal formado (`ValueError`, incluido `EventoInvalido`) se descarta: reintentarlo no lo
  arregla.
- Una falla de la base de datos (`SQLAlchemyError`, u `OSError`: asyncpg relanza los errores de red
  sin envolverlos) espera `REINTENTO_S` y devuelve el mensaje a la cola. Tras 5 entregas fallidas,
  RabbitMQ lo manda a la cola de fallidos (ver comun.topologia).
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection
from sqlalchemy.exc import SQLAlchemyError

from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import ARGUMENTOS_COLA, Cola

log = logging.getLogger(__name__)

REINTENTO_S = 5
Atender = Callable[[dict[str, Any]], Awaitable[None]]


class EventoInvalido(ValueError):
    """El mensaje no tiene la forma esperada: reintentarlo no lo arregla."""


async def atender_mensaje(mensaje: AbstractIncomingMessage, atender: Atender) -> None:
    try:
        sobre = json.loads(mensaje.body)
        if not isinstance(sobre, dict):
            raise EventoInvalido("El sobre no es un objeto JSON")
        await atender(sobre)
    except ValueError as exc:  # JSON inválido o EventoInvalido
        log.warning(
            "Evento con forma inesperada; se descarta (mensaje %s): %r", mensaje.message_id, exc
        )
        await mensaje.reject(requeue=False)
        return
    except (SQLAlchemyError, OSError):
        log.exception("No se pudo procesar el evento %s; se reintentará", mensaje.message_id)
        # Sin esta espera el mensaje vuelve de inmediato y agota sus entregas en milisegundos.
        await asyncio.sleep(REINTENTO_S)
        await mensaje.reject(requeue=True)
        return
    await mensaje.ack()


class ConsumidorEventos:
    def __init__(self, url_rabbitmq: str, cola: Cola, atender: Atender, prefetch: int = 10) -> None:
        self._url = url_rabbitmq
        self._cola = cola
        self._atender = atender
        self._prefetch = prefetch
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
        await canal.set_qos(prefetch_count=self._prefetch)
        exchange = await canal.declare_exchange(
            EXCHANGE_EVENTOS, aio_pika.ExchangeType.TOPIC, durable=True
        )
        cola = await canal.declare_queue(self._cola.nombre, durable=True, arguments=ARGUMENTOS_COLA)
        for clave in self._cola.claves:
            await cola.bind(exchange, clave)
        self._enlazada = True
        async with cola.iterator() as mensajes:
            async for mensaje in mensajes:
                await atender_mensaje(mensaje, self._atender)

    async def ejecutar(self) -> None:
        """Consume sin fin; si la conexión se cae, reintenta cada REINTENTO_S segundos."""
        while True:
            try:
                await self._consumir()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception(
                    "Se interrumpió el consumo de eventos; se reintentará en %s s", REINTENTO_S
                )
                await self.cerrar()
                await asyncio.sleep(REINTENTO_S)
```

- [ ] **Step 4: Move `administracion` to the common consumer**

En `services/administracion/src/administracion/eventos.py`:
- borre `COLA`, `CLAVES`, `ARGUMENTOS_COLA`, `REINTENTO_CONEXION_S`, la clase `EventoInvalido`, la función `atender` y la clase `ConsumidorEventos`, y los imports que queden sin uso (`asyncio`, `json`, `logging`, `aio_pika`, `AbstractIncomingMessage`, `AbstractRobustConnection`, `EXCHANGE_EVENTOS`, `SQLAlchemyError`);
- importe `from comun.consumidor import Atender, EventoInvalido`;
- cambie el docstring del módulo a `"""Copia a la bitácora los eventos que publican los otros servicios."""`;
- agregue al final:

```python
def atendedor(fabrica: async_sessionmaker[AsyncSession]) -> Atender:
    """La función que el consumidor común llama con cada sobre de evento."""

    async def atender(sobre: dict[str, Any]) -> None:
        registro = traducir(sobre)
        if registro is not None:
            await guardar(fabrica, registro)

    return atender
```

En `services/administracion/src/administracion/main.py`:
- reemplace `from administracion.eventos import ConsumidorEventos` por:

```python
from administracion.eventos import atendedor
from comun.consumidor import ConsumidorEventos
from comun.topologia import COLA_ADMINISTRACION
```

  (respetando el orden de imports de ruff);
- cree el consumidor así:

```python
    consumidor = ConsumidorEventos(config.rabbitmq_url, COLA_ADMINISTRACION, atendedor(sesiones))
```

En `services/administracion/tests/test_eventos.py`:
- borre `_MensajeFalso`, `_FabricaRota`, `test_si_falla_la_base_espera_y_devuelve_el_mensaje_a_la_cola` y `test_la_cola_es_durable_de_tipo_quorum` (pasaron a `libs/comun/tests/test_consumidor.py`);
- cambie los imports de `administracion.eventos` a `Registro, atendedor, traducir`;
- importe `from comun.consumidor import ConsumidorEventos, EventoInvalido` y `from comun.topologia import COLA_ADMINISTRACION`;
- quite los imports que queden sin uso (`socket`, `cast`, `AbstractIncomingMessage`, `SQLAlchemyError`, `AsyncSession` si ya no se usa como tipo);
- en `_consumidor`, cree el consumidor así:

```python
    consumidor = ConsumidorEventos(url, COLA_ADMINISTRACION, atendedor(fabrica))
```

  `test_un_evento_repetido_deja_un_solo_registro` y `test_un_mensaje_mal_formado_no_detiene_la_cola` quedan iguales.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest libs/comun services/administracion -q`
Expected: PASS, sin advertencias.

Run: `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: limpios.

- [ ] **Step 6: Commit**

```bash
git add libs/comun/src/comun/consumidor.py libs/comun/tests/test_consumidor.py services/administracion/src/administracion/eventos.py services/administracion/src/administracion/main.py services/administracion/tests/test_eventos.py
git commit -m "refactor(comun): consumidor de eventos común; administración lo usa con su cola de la topología" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `proveedores`: unidad bloqueada con contratos, copias del catálogo y tipo de cambio

**Files:**
- Modify: `services/proveedores/src/proveedores/api/catalogo.py` (`CAMPOS_CON_CONTRATOS` y el detalle del 409)
- Modify: `services/proveedores/src/proveedores/importacion/aplicar.py` (`copia_servicio`, `copia_tipo_cambio`, `_servicios` y `_tipo_cambio`)
- Modify: `web/src/componentes/FormularioServicio.tsx` (la unidad también se bloquea; aviso nuevo)
- Modify: `web/src/ayuda.ts` (artículo del catálogo)
- Test:
  - `services/proveedores/tests/test_aplicar.py`
  - `services/proveedores/tests/test_catalogo.py`
  - `services/proveedores/tests/test_api.py`
  - `services/proveedores/tests/test_cli.py`
  - `web/src/paginas/Catalogo.test.tsx`

**Interfaces:**
- Produces (`proveedores.importacion.aplicar`):
  - `copia_servicio(servicio: ServicioCatalogo) -> dict[str, Any]`: `{id, codigo, nombre, categoria, unidad, moneda, activo}`.
  - `copia_tipo_cambio(periodo: date, usd_mxn: Decimal) -> dict[str, Any]`: `{periodo, usd_mxn}`.
  - Ambas las usa también el reproceso (Task 5).
- Eventos: `servicio.actualizado` (copia) por cada servicio importado y `tipo_cambio.registrado` por cada periodo importado. `ResumenImportacion.eventos` de servicios y de tipo de cambio deja de ser 0.
- API: `PATCH /servicios/{codigo}` responde 409 `servicio_con_contratos` también por `unidad`.

- [ ] **Step 1: Write the failing backend tests**

En `services/proveedores/tests/test_aplicar.py`:

- reemplace `test_tipo_cambio_se_actualiza_sin_eventos` por:

```python
async def test_tipo_cambio_se_actualiza_y_publica_cada_periodo(fabrica: Fabrica) -> None:
    await _importar(fabrica, Entidad.TIPO_CAMBIO, "periodo,usd_mxn\n2025-01-01,20.4512\n")
    resumen = await _importar(
        fabrica, Entidad.TIPO_CAMBIO, "periodo,usd_mxn\n2025-01-01,20.1000\n"
    )
    assert resumen == ResumenImportacion("tipo_cambio", 1, 1, 0, 1)
    async with fabrica() as sesion:
        [valor] = (await sesion.scalars(select(TipoCambio.usd_mxn))).all()
    assert valor == Decimal("20.1000")
    eventos = sorted(
        await _eventos(fabrica, "tipo_cambio.registrado"), key=lambda e: e.ocurrido_en
    )
    assert [e.payload for e in eventos] == [
        {"periodo": "2025-01-01", "usd_mxn": "20.4512"},
        {"periodo": "2025-01-01", "usd_mxn": "20.1000"},
    ]
```

- agregue:

```python
async def test_importar_servicios_publica_una_copia_por_servicio(fabrica: Fabrica) -> None:
    resumen = await _importar(fabrica, Entidad.SERVICIOS, SERVICIOS)
    assert resumen == ResumenImportacion("servicios", 2, 2, 0, 2)
    eventos = await _eventos(fabrica, "servicio.actualizado")
    [copia] = [e.payload for e in eventos if e.payload["codigo"] == "CONS-DEV-SR"]
    # Una copia es el estado del servicio, no una acción: no lleva cambio, campos ni actor.
    assert set(copia) == {"id", "codigo", "nombre", "categoria", "unidad", "moneda", "activo"}
    assert (copia["categoria"], copia["unidad"], copia["moneda"], copia["activo"]) == (
        "consultoria",
        "hora",
        "MXN",
        True,
    )


async def test_con_contratos_no_cambia_categoria_unidad_ni_moneda(fabrica: Fabrica) -> None:
    await _catalogo_y_proveedores(fabrica)
    await _importar(fabrica, Entidad.CONTRATOS, CONTRATOS)
    cambiado = SERVICIOS.replace("consultoria,hora,MXN", "soporte,ticket,USD")
    with pytest.raises(ErrorImportacion) as error:
        await _importar(fabrica, Entidad.SERVICIOS, cambiado)
    assert [(e.fila, e.campo, e.mensaje) for e in error.value.errores] == [
        (3, "categoria", "El servicio tiene contratos: no se puede cambiar la categoría"),
        (3, "moneda", "El servicio tiene contratos: no se puede cambiar la moneda"),
        (3, "unidad", "El servicio tiene contratos: no se puede cambiar la unidad"),
    ]
    # El nombre sí se puede cambiar aunque haya contratos.
    renombrado = SERVICIOS.replace("Desarrollador(a) senior - hora", "Desarrollo senior")
    await _importar(fabrica, Entidad.SERVICIOS, renombrado)
    async with fabrica() as sesion:
        nombre = await sesion.scalar(
            select(ServicioCatalogo.nombre).where(ServicioCatalogo.codigo == "CONS-DEV-SR")
        )
    assert nombre == "Desarrollo senior"
```

  (importe `ServicioCatalogo` de `proveedores.modelos`).

En `services/proveedores/tests/test_catalogo.py`:

- en `_eventos_servicio`, deje fuera las copias de la importación (las acciones del catálogo son las que traen `cambio`):

```python
        return [f.payload for f in filas if "cambio" in f.payload]
```

- reemplace `test_categoria_y_moneda_bloqueadas_con_contratos` por:

```python
async def test_categoria_unidad_y_moneda_bloqueadas_con_contratos(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    admin = _auth(claves, "admin")
    bloqueado = await con_catalogo.patch(
        "/servicios/SAAS-OFI-EMP",
        json={"categoria": "nube", "unidad": "vcpu_mes", "moneda": "MXN"},
        headers=admin,
    )
    assert bloqueado.status_code == 409
    assert bloqueado.json()["codigo"] == "servicio_con_contratos"
    assert bloqueado.json()["detail"] == (
        "El servicio ya tiene contratos: su categoría, su unidad y su moneda no se pueden cambiar."
    )
    assert [e["campo"] for e in bloqueado.json()["errores"]] == ["categoria", "unidad", "moneda"]
    libre = await con_catalogo.patch(
        "/servicios/SOP-MESA-TK", json={"categoria": "consultoria", "unidad": "hora"}, headers=admin
    )
    assert libre.status_code == 200
    assert (libre.json()["categoria"], libre.json()["unidad"]) == ("consultoria", "hora")
```

En `services/proveedores/tests/test_api.py`, en `test_importar_devuelve_resumen` y en `test_importar_registra_resumen_y_usuario_sin_contenido_ni_token`, los servicios importados ahora publican sus copias: cambie `"eventos": 0` por `"eventos": 2` y `0 eventos` por `2 eventos` en el mensaje esperado.

En `services/proveedores/tests/test_cli.py`, en `test_la_cli_imprime_un_resumen_por_entidad`, cambie las líneas esperadas de servicios y tipo de cambio por:

```python
        "servicios: 40 registros, 0 omitidos, 40 eventos",
        "proveedores: 3 registros, 0 omitidos, 3 eventos",
        f"tipo_cambio: {len(datos.tipo_cambio)} registros, 0 omitidos, "
        f"{len(datos.tipo_cambio)} eventos",
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest services/proveedores -q`
Expected: FAIL. Las importaciones de servicios y tipo de cambio no publican eventos, el bloqueo no considera la unidad y la importación no bloquea nada.

- [ ] **Step 3: Implement in `proveedores`**

En `services/proveedores/src/proveedores/api/catalogo.py`:

```python
CAMPOS_CON_CONTRATOS = ("categoria", "unidad", "moneda")  # los precios históricos dependen de ellos
```

y en el `ErrorDominio` del 409:

```python
                "El servicio ya tiene contratos: su categoría, su unidad y su moneda no se pueden "
                "cambiar.",
```

En `services/proveedores/src/proveedores/importacion/aplicar.py`:

- agregue los imports `from datetime import date` y `from decimal import Decimal`;
- agregue después de `registrar_rechazo`:

```python
# El catálogo de un servicio con contratos no cambia en lo que define sus precios.
CAMPOS_BLOQUEADOS_CON_CONTRATOS = {"categoria": "categoría", "unidad": "unidad", "moneda": "moneda"}


def copia_servicio(servicio: ServicioCatalogo) -> dict[str, Any]:
    """Payload de servicio.actualizado sin cambio ni actor: el estado del servicio, no una acción."""
    return {
        "id": servicio.id,
        "codigo": servicio.codigo,
        "nombre": servicio.nombre,
        "categoria": servicio.categoria,
        "unidad": servicio.unidad,
        "moneda": servicio.moneda,
        "activo": servicio.activo,
    }


def copia_tipo_cambio(periodo: date, usd_mxn: Decimal) -> dict[str, Any]:
    return {"periodo": periodo, "usd_mxn": usd_mxn}
```

- reemplace `_servicios` por:

```python
async def _servicios(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaServicio)
    errores = resultado.errores + duplicados(resultado, lambda f: f.codigo, "codigo")
    codigos = [fila.codigo for _, fila in resultado.filas]
    existentes = {
        s.codigo: s
        for s in await sesion.scalars(
            select(ServicioCatalogo).where(ServicioCatalogo.codigo.in_(codigos))
        )
    }
    con_contratos = set(
        await sesion.scalars(
            select(LineaContrato.servicio_id)
            .where(LineaContrato.servicio_id.in_([s.id for s in existentes.values()]))
            .distinct()
        )
    )
    for numero, fila in resultado.filas:
        actual = existentes.get(fila.codigo)
        if actual is None or actual.id not in con_contratos:
            continue
        errores += [
            ErrorFila(numero, campo, f"El servicio tiene contratos: no se puede cambiar la {nombre}")
            for campo, nombre in CAMPOS_BLOQUEADOS_CON_CONTRATOS.items()
            if getattr(fila, campo) != getattr(actual, campo)
        ]
    _exigir_sin_errores(errores)
    datos = [fila.model_dump() for _, fila in resultado.filas]
    if not datos:
        return ResumenImportacion(Entidad.SERVICIOS, 0, 0, 0, 0)
    insercion = insert(ServicioCatalogo)
    consulta = insercion.on_conflict_do_update(
        index_elements=[ServicioCatalogo.codigo],
        set_={c: insercion.excluded[c] for c in ("nombre", "categoria", "unidad", "moneda")},
    ).returning(ServicioCatalogo)
    servicios = (
        await sesion.scalars(consulta, datos, execution_options={"populate_existing": True})
    ).all()
    for servicio in servicios:
        registrar_evento(sesion, Outbox, "servicio.actualizado", copia_servicio(servicio))
    return ResumenImportacion(Entidad.SERVICIOS, len(datos), len(servicios), 0, len(servicios))
```

- en `_tipo_cambio`, después del `if datos:` (que no cambia), agregue la publicación y cambie el resumen:

```python
    for fila in datos:
        registrar_evento(
            sesion,
            Outbox,
            "tipo_cambio.registrado",
            copia_tipo_cambio(fila["periodo"], fila["usd_mxn"]),
        )
    return ResumenImportacion(Entidad.TIPO_CAMBIO, len(datos), len(datos), 0, len(datos))
```

- [ ] **Step 4: Run the backend tests to verify they pass**

Run: `uv run pytest services/proveedores libs/comun/tests/test_topologia.py -q`
Expected: PASS. `test_cada_evento_publicado_esta_declarado_y_tiene_cola` ahora también encuentra `tipo_cambio.registrado`. Si alguna otra prueba de `proveedores` contaba los eventos del outbox sin filtrar por tipo, ajuste solo ese número y anótelo en el reporte.

- [ ] **Step 5: Write the failing web test**

En `web/src/paginas/Catalogo.test.tsx`, en `"con contratos bloquea categoría y moneda y solo envía lo que cambió"`:

- cambie el título por `"con contratos bloquea categoría, unidad y moneda y solo envía lo que cambió"`;
- recorra los tres campos: `for (const combo of ["Categoría", "Unidad", "Moneda"])`;
- cambie la descripción esperada por `"La categoría, la unidad y la moneda no se pueden cambiar: el servicio ya tiene contratos y sus precios dependen de ellas."`.

Run: `cd web && npx vitest run src/paginas/Catalogo.test.tsx`
Expected: FAIL (la unidad no está deshabilitada y el aviso es el anterior).

- [ ] **Step 6: Implement in the web**

En `web/src/componentes/FormularioServicio.tsx`:

```tsx
const AVISO_CONTRATOS =
  "La categoría, la unidad y la moneda no se pueden cambiar: el servicio ya tiene contratos y sus precios dependen de ellas."
```

y pase `true` como cuarto argumento de `campoLista("unidad", "Unidad", …)`, igual que en categoría y moneda.

En `web/src/ayuda.ts`, en el artículo `catalogo-de-servicios`, cambie `tampoco puede cambiar su categoría ni su moneda, porque los precios históricos dependen de ellas.` por `tampoco puede cambiar su categoría, su unidad ni su moneda, porque los precios históricos dependen de ellas.`

- [ ] **Step 7: Run the web checks**

Desde `web/`: `npx vitest run`, `npm run lint`, `npm run build` y `npx prettier --check "src/**/*.{ts,tsx}"`.
Expected: todo limpio, sin advertencias.

- [ ] **Step 8: Commit**

```bash
git add services/proveedores web/src/componentes/FormularioServicio.tsx web/src/ayuda.ts web/src/paginas/Catalogo.test.tsx
git commit -m "feat(proveedores): la unidad se bloquea con contratos y las importaciones publican el catálogo y el tipo de cambio" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `proveedores`: reproceso para reconstruir las copias de otros servicios

**Files:**
- Create: `services/proveedores/src/proveedores/reproceso.py`
- Test: `services/proveedores/tests/test_reproceso.py`

**Interfaces:**
- Consumes: `copia_servicio` y `copia_tipo_cambio` (Task 4).
- Produces:
  - `republicar_todo(fabrica) -> int`: marca como pendientes todos los eventos ya publicados del outbox y devuelve cuántos marcó.
  - `emitir_instantanea(fabrica) -> tuple[int, int]`: `(servicios, tipos_de_cambio)` emitidos.
  - CLI `python -m proveedores.reproceso --todo | --instantanea`.

- [ ] **Step 1: Write the failing tests**

Cree `services/proveedores/tests/test_reproceso.py`:

```python
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from proveedores.modelos import Outbox, ServicioCatalogo, TipoCambio
from proveedores.reproceso import _principal, emitir_instantanea, republicar_todo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]


async def _outbox(fabrica: Fabrica) -> list[Outbox]:
    async with fabrica() as sesion:
        return list((await sesion.scalars(select(Outbox).order_by(Outbox.ocurrido_en))).all())


async def test_republicar_todo_marca_los_publicados_como_pendientes(fabrica: Fabrica) -> None:
    async with fabrica() as sesion, sesion.begin():
        for n, publicado in enumerate((True, True, False)):
            sesion.add(
                Outbox(
                    tipo="proveedor.actualizado",
                    payload={"n": n},
                    correlation_id="c",
                    publicado_en=datetime.now(UTC) if publicado else None,
                )
            )
    assert await republicar_todo(fabrica) == 2
    assert [f.publicado_en for f in await _outbox(fabrica)] == [None, None, None]


async def test_la_instantanea_emite_el_catalogo_y_el_tipo_de_cambio(fabrica: Fabrica) -> None:
    async with fabrica() as sesion, sesion.begin():
        sesion.add(
            ServicioCatalogo(
                codigo="SOP-MESA-TK",
                nombre="Mesa de ayuda - ticket",
                categoria="soporte",
                unidad="ticket",
                moneda="MXN",
                activo=False,
            )
        )
        sesion.add(TipoCambio(periodo=date(2026, 9, 1), usd_mxn=Decimal("18.2500")))
    assert await emitir_instantanea(fabrica) == (1, 1)
    eventos = {f.tipo: f.payload for f in await _outbox(fabrica)}
    servicio = eventos["servicio.actualizado"]
    assert (servicio["codigo"], servicio["activo"]) == ("SOP-MESA-TK", False)
    assert "cambio" not in servicio
    assert eventos["tipo_cambio.registrado"] == {"periodo": "2026-09-01", "usd_mxn": "18.2500"}


@pytest.mark.usefixtures("fabrica")
async def test_la_cli_exige_una_sola_opcion(capsys: pytest.CaptureFixture[str]) -> None:
    assert await _principal(["--instantanea"]) == 0
    assert capsys.readouterr().out.strip() == (
        "Se emitieron 0 copias de servicios y 0 tipos de cambio; el relay los publicará."
    )
    with pytest.raises(SystemExit):
        await _principal([])
    with pytest.raises(SystemExit):
        await _principal(["--todo", "--instantanea"])
```

El fixture `url_bd` de `conftest.py` (del que depende `fabrica`) exporta `DATABASE_URL`, que es la URL que usa `_principal` por medio de `Configuracion()`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest services/proveedores/tests/test_reproceso.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'proveedores.reproceso'`.

- [ ] **Step 3: Implement**

Cree `services/proveedores/src/proveedores/reproceso.py`:

```python
"""Vuelve a publicar eventos para (re)construir las copias de los otros servicios.

Uso (dentro del contenedor de proveedores, con el servicio corriendo: su relay los publica):
  python -m proveedores.reproceso --todo         # todos los eventos del outbox, otra vez
  python -m proveedores.reproceso --instantanea  # el catálogo y el tipo de cambio actuales

Los consumidores ignoran los eventos repetidos, así que repetirlo es seguro.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from comun.outbox import registrar_evento
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from proveedores.config import Configuracion
from proveedores.importacion.aplicar import copia_servicio, copia_tipo_cambio
from proveedores.modelos import Outbox, ServicioCatalogo, TipoCambio


async def republicar_todo(fabrica: async_sessionmaker[AsyncSession]) -> int:
    async with fabrica() as sesion, sesion.begin():
        resultado = await sesion.execute(
            update(Outbox).where(Outbox.publicado_en.is_not(None)).values(publicado_en=None)
        )
    return int(resultado.rowcount)  # type: ignore[attr-defined]


async def emitir_instantanea(fabrica: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    async with fabrica() as sesion, sesion.begin():
        servicios = (await sesion.scalars(select(ServicioCatalogo))).all()
        for servicio in servicios:
            registrar_evento(sesion, Outbox, "servicio.actualizado", copia_servicio(servicio))
        tipos = (await sesion.scalars(select(TipoCambio))).all()
        for tipo in tipos:
            registrar_evento(
                sesion,
                Outbox,
                "tipo_cambio.registrado",
                copia_tipo_cambio(tipo.periodo, tipo.usd_mxn),
            )
    return len(servicios), len(tipos)


async def _principal(argumentos: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m proveedores.reproceso")
    opcion = parser.add_mutually_exclusive_group(required=True)
    opcion.add_argument("--todo", action="store_true", help="vuelve a publicar todo el outbox")
    opcion.add_argument(
        "--instantanea", action="store_true", help="publica el catálogo y el tipo de cambio actuales"
    )
    elegido = parser.parse_args(argumentos)
    motor = create_async_engine(
        Configuracion().database_url, pool_pre_ping=True, hide_parameters=True
    )
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    try:
        if elegido.todo:
            marcados = await republicar_todo(fabrica)
            print(f"Se marcaron {marcados} eventos para volver a publicarse.")
        else:
            servicios, tipos = await emitir_instantanea(fabrica)
            print(
                f"Se emitieron {servicios} copias de servicios y {tipos} tipos de cambio; "
                "el relay los publicará."
            )
    finally:
        await motor.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_principal(sys.argv[1:])))
```

Si mypy acepta `resultado.rowcount` sin el `type: ignore`, quítelo (mypy estricto avisa de los `ignore` que sobran).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest services/proveedores -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio.

- [ ] **Step 5: Commit**

```bash
git add services/proveedores/src/proveedores/reproceso.py services/proveedores/tests/test_reproceso.py
git commit -m "feat(proveedores): reproceso para volver a publicar el outbox o el estado del catálogo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Servicio `inteligencia`: armazón, base de datos e infraestructura

**Files:**
- Create:
  - `services/inteligencia/pyproject.toml`, `services/inteligencia/Dockerfile`, `services/inteligencia/alembic.ini`
  - `services/inteligencia/alembic/env.py`, `services/inteligencia/alembic/script.py.mako`
  - `services/inteligencia/alembic/versions/0001_esquema_inicial.py`
  - `services/inteligencia/src/inteligencia/__init__.py` (vacío), `config.py`, `db.py`, `modelos.py`, `main.py`
  - `services/inteligencia/tests/conftest.py`, `test_migraciones.py`, `test_salud.py`
  - `infra/postgres/inteligencia.sh`
- Modify:
  - `pyproject.toml` raíz (miembro del workspace, `hypothesis`, cobertura, mypy) y `uv.lock`
  - `infra/docker-compose.yml`, `infra/nginx/nginx.conf`, `infra/.env.example`, `.github/dependabot.yml`

**Interfaces:**
- Produces:
  - `inteligencia.config.Configuracion`, con `usar_rabbitmq: bool = True`, `entrenamiento_automatico: bool = True` y `directorio_modelos: Path = Path("modelos")`.
  - `inteligencia.db.Base` y `obtener_sesion`.
  - `inteligencia.modelos`: `Proveedor`, `Servicio`, `TipoCambio`, `Contrato`, `LineaContrato`, `Desempeno`, `EventoProcesado`, `Configuracion`, `ModeloBenchmark` y `Outbox`.
  - `inteligencia.main.crear_app(configuracion=None, validador=None, fabrica=None) -> FastAPI`, con `app.state.fabrica`, `app.state.config` y el relay del outbox en el ciclo de vida cuando `usar_rabbitmq`.
  - En las pruebas, los fixtures `urls_bd`, `fabrica`, `claves`, `app` y `cliente` (igual que en `administracion`).

- [ ] **Step 1: Package and workspace**

Cree `services/inteligencia/pyproject.toml`:

```toml
[project]
name = "inteligencia"
version = "0.1.0"
description = "Precio justo, puntuación de proveedores, alertas y KPIs a partir de los eventos de proveedores"
requires-python = ">=3.13"
dependencies = [
    "comun",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "aio-pika>=9.5",
    "numpy>=2.1",
    "scikit-learn>=1.6",
    "scipy>=1.14",  # Spearman en la validación contra la verdad oculta
    "tzdata>=2024.1",  # base IANA para ZoneInfo en Windows e imágenes slim
]

[tool.uv.sources]
comun = { workspace = true }

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

En el `pyproject.toml` raíz:
- agregue `"inteligencia"` y `"hypothesis>=6.120"` al grupo `dev`, e `inteligencia = { workspace = true }` en `[tool.uv.sources]`;
- agregue `"inteligencia"` a `[tool.coverage.run] source` y a `[tool.mypy] packages`;
- agregue después de `[tool.mypy]`:

```toml
[[tool.mypy.overrides]]
module = ["sklearn.*", "joblib", "scipy.*"]
ignore_missing_imports = true
```

Run: `uv sync --all-packages` (actualiza `uv.lock`).

- [ ] **Step 2: Write the failing tests**

Cree `services/inteligencia/tests/conftest.py`:

```python
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI
from inteligencia.config import Configuracion
from inteligencia.main import crear_app
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
CLAVE_APLICACION = "clave-aplicacion-prueba"
TABLAS = (
    "proveedor, servicio, tipo_cambio, contrato, linea_contrato, desempeno, "
    "evento_procesado, modelo_benchmark, outbox"
)
CONFIGURACION_INICIAL = (
    "UPDATE configuracion SET peso_sla = 30, peso_resolucion = 20, peso_incidentes = 20, "
    "peso_entregas = 15, peso_satisfaccion = 15, umbral_riesgo = 40, inflacion_anual = 4.50, "
    "actualizado_en = NULL, actualizado_por = NULL"
)


@pytest.fixture(scope="session")
def urls_bd() -> Iterator[tuple[str, str]]:
    """(URL del dueño, que migra; URL del usuario de la aplicación, con permisos reducidos)."""
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as contenedor:
        # El rol de la aplicación existe antes de migrar, como en infra/postgres/inteligencia.sh.
        resultado = contenedor.exec(
            [
                "psql",
                "-U",
                contenedor.username,
                "-d",
                contenedor.dbname,
                "-c",
                f"CREATE ROLE inteligencia LOGIN PASSWORD '{CLAVE_APLICACION}'",
            ]
        )
        assert resultado.exit_code == 0, resultado.output
        url_dueno = contenedor.get_connection_url()
        os.environ["DATABASE_URL_MIGRACIONES"] = url_dueno
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        url_app = (
            make_url(url_dueno)
            .set(username="inteligencia", password=CLAVE_APLICACION)
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
    # La aplicación no puede borrar: limpia el dueño.
    limpieza = create_async_engine(url_dueno, poolclass=NullPool)
    async with limpieza.begin() as conexion:
        await conexion.execute(text(f"TRUNCATE {TABLAS} CASCADE"))
        await conexion.execute(text(CONFIGURACION_INICIAL))
    await limpieza.dispose()


@pytest.fixture(scope="session")
def claves() -> ClavesPrueba:
    return ClavesPrueba()


@pytest.fixture
def app(
    urls_bd: tuple[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    claves: ClavesPrueba,
    tmp_path: Path,
) -> FastAPI:
    return crear_app(
        Configuracion(
            database_url=urls_bd[1],
            usar_rabbitmq=False,
            entrenamiento_automatico=False,
            directorio_modelos=tmp_path,
        ),
        claves.validador(),
        fabrica,
    )


@pytest.fixture
async def cliente(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente
```

Cree `services/inteligencia/tests/test_migraciones.py`:

```python
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
            text("INSERT INTO evento_procesado (event_id, tipo, procesado_en) VALUES ('e', 't', now())")
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
```

Cree `services/inteligencia/tests/test_salud.py`:

```python
import httpx
import pytest

pytestmark = pytest.mark.integracion


async def test_listo_con_postgres(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/salud/listo")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "dependencias": {"postgres": "ok"}}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest services/inteligencia -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'inteligencia.config'`.

- [ ] **Step 4: Implement the package**

`services/inteligencia/src/inteligencia/config.py`:

```python
from pathlib import Path

from comun.config import ConfiguracionBase


class Configuracion(ConfiguracionBase):
    nombre_servicio: str = "inteligencia"
    # Usuario de la aplicación: sin DELETE en ninguna tabla.
    database_url: str = (
        "postgresql+asyncpg://inteligencia:inteligencia@localhost:5432/inteligencia_db"
    )
    # Dueño del esquema: solo para correr las migraciones.
    database_url_migraciones: str = (
        "postgresql+asyncpg://inteligencia_dueno:inteligencia_dueno@localhost:5432/inteligencia_db"
    )
    # Las pruebas lo apagan: no hay RabbitMQ en ellas.
    usar_rabbitmq: bool = True
    entrenamiento_automatico: bool = True
    directorio_modelos: Path = Path("modelos")
```

`services/inteligencia/src/inteligencia/db.py`: el mismo contenido que `services/administracion/src/administracion/db.py` (convención de nombres, `Base` y `obtener_sesion`).

`services/inteligencia/src/inteligencia/modelos.py`:

```python
"""Copia local de los datos de proveedores (alimentada por eventos) y estado propio del servicio."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from comun.outbox import ColumnasOutbox
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from inteligencia.db import Base

DINERO = Numeric(14, 4)
PORCENTAJE = Numeric(5, 2)
METRICA = Numeric(8, 6)


def _ahora() -> datetime:
    return datetime.now(UTC)


class Proveedor(Base):
    __tablename__ = "proveedor"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    rfc: Mapped[str] = mapped_column(String(13))
    nombre: Mapped[str] = mapped_column(String(200))
    tamano: Mapped[str] = mapped_column(String(10))
    categorias: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    activo: Mapped[bool]


class Servicio(Base):
    __tablename__ = "servicio"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(20))
    unidad: Mapped[str] = mapped_column(String(20))
    moneda: Mapped[str] = mapped_column(String(3))
    activo: Mapped[bool]


class TipoCambio(Base):
    __tablename__ = "tipo_cambio"

    periodo: Mapped[date] = mapped_column(Date, primary_key=True)
    usd_mxn: Mapped[Decimal] = mapped_column(Numeric(10, 4))


class Contrato(Base):
    """Sin llave foránea al proveedor: los eventos pueden llegar en desorden."""

    __tablename__ = "contrato"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    folio: Mapped[str] = mapped_column(String(30))
    proveedor_id: Mapped[uuid.UUID] = mapped_column(index=True)
    tipo: Mapped[str] = mapped_column(String(10))
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    moneda: Mapped[str] = mapped_column(String(3))
    recibido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)

    lineas: Mapped[list["LineaContrato"]] = relationship(lazy="selectin")


class LineaContrato(Base):
    """Categoría y unidad tal como estaban al firmarse el contrato (vienen en el evento)."""

    __tablename__ = "linea_contrato"

    contrato_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contrato.id", ondelete="CASCADE"), primary_key=True
    )
    codigo_servicio: Mapped[str] = mapped_column(String(30), primary_key=True)
    categoria: Mapped[str] = mapped_column(String(20))
    unidad: Mapped[str] = mapped_column(String(20))
    cantidad: Mapped[Decimal] = mapped_column(DINERO)
    precio_unitario: Mapped[Decimal] = mapped_column(DINERO)


class Desempeno(Base):
    __tablename__ = "desempeno"

    proveedor_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    periodo: Mapped[date] = mapped_column(Date, primary_key=True)
    sla_cumplimiento_pct: Mapped[Decimal] = mapped_column(PORCENTAJE)
    tiempo_resolucion_h: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    incidentes_criticos: Mapped[int]
    entregas_a_tiempo_pct: Mapped[Decimal] = mapped_column(PORCENTAJE)
    satisfaccion: Mapped[Decimal] = mapped_column(Numeric(3, 2))


class EventoProcesado(Base):
    """Idempotencia: un evento repetido choca con su event_id y no se aplica dos veces."""

    __tablename__ = "evento_procesado"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100))
    procesado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Configuracion(Base):
    """Una sola fila (id = 1), creada por la migración."""

    __tablename__ = "configuracion"
    __table_args__ = (CheckConstraint("id = 1", name="unica"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    peso_sla: Mapped[int]
    peso_resolucion: Mapped[int]
    peso_incidentes: Mapped[int]
    peso_entregas: Mapped[int]
    peso_satisfaccion: Mapped[int]
    umbral_riesgo: Mapped[int]
    inflacion_anual: Mapped[Decimal] = mapped_column(PORCENTAJE)
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actualizado_por: Mapped[str | None] = mapped_column(String(200))


class ModeloBenchmark(Base):
    """Registro de entrenamientos del modelo de precios; el activo es el último promovido."""

    __tablename__ = "modelo_benchmark"
    __table_args__ = (CheckConstraint("origen IN ('manual', 'automatico')", name="origen"),)

    version: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    entrenado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    origen: Mapped[str] = mapped_column(String(10))
    actor_nombre: Mapped[str] = mapped_column(String(200))
    observaciones: Mapped[int]
    datos_hasta: Mapped[date] = mapped_column(Date)
    mape: Mapped[Decimal] = mapped_column(METRICA)
    mape_linea_base: Mapped[Decimal] = mapped_column(METRICA)
    cobertura: Mapped[Decimal] = mapped_column(METRICA)
    pinball: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    promovido: Mapped[bool]
    artefacto: Mapped[str | None] = mapped_column(String(300))


class Outbox(ColumnasOutbox, Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_pendientes", "ocurrido_en", postgresql_where=text("publicado_en IS NULL")),
    )
```

`services/inteligencia/alembic.ini`, `alembic/script.py.mako` y `alembic/env.py`: copie los de `administracion`, cambiando en `env.py` los imports a `from inteligencia import modelos`, `from inteligencia.config import Configuracion` y `from inteligencia.db import Base`.

`services/inteligencia/alembic/versions/0001_esquema_inicial.py`:

```python
"""Esquema inicial de inteligencia: copia local, idempotencia, configuración, modelos y outbox.

Revision ID: 0001
Revises:
Create Date: 2026-10-10
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
        "proveedor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rfc", sa.String(13), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("tamano", sa.String(10), nullable=False),
        sa.Column("categorias", postgresql.ARRAY(sa.String(20)), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
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
        "tipo_cambio",
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("usd_mxn", sa.Numeric(10, 4), nullable=False),
        sa.PrimaryKeyConstraint("periodo", name=op.f("pk_tipo_cambio")),
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
        sa.Column("recibido_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contrato")),
    )
    op.create_index(op.f("ix_contrato_proveedor_id"), "contrato", ["proveedor_id"])
    op.create_table(
        "linea_contrato",
        sa.Column("contrato_id", sa.Uuid(), nullable=False),
        sa.Column("codigo_servicio", sa.String(30), nullable=False),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(14, 4), nullable=False),
        sa.ForeignKeyConstraint(
            ["contrato_id"],
            ["contrato.id"],
            name=op.f("fk_linea_contrato_contrato_id_contrato"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "contrato_id", "codigo_servicio", name=op.f("pk_linea_contrato")
        ),
    )
    op.create_table(
        "desempeno",
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("sla_cumplimiento_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("tiempo_resolucion_h", sa.Numeric(8, 2), nullable=False),
        sa.Column("incidentes_criticos", sa.Integer(), nullable=False),
        sa.Column("entregas_a_tiempo_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("satisfaccion", sa.Numeric(3, 2), nullable=False),
        sa.PrimaryKeyConstraint("proveedor_id", "periodo", name=op.f("pk_desempeno")),
    )
    op.create_table(
        "evento_procesado",
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_evento_procesado")),
    )
    op.create_table(
        "configuracion",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("peso_sla", sa.Integer(), nullable=False),
        sa.Column("peso_resolucion", sa.Integer(), nullable=False),
        sa.Column("peso_incidentes", sa.Integer(), nullable=False),
        sa.Column("peso_entregas", sa.Integer(), nullable=False),
        sa.Column("peso_satisfaccion", sa.Integer(), nullable=False),
        sa.Column("umbral_riesgo", sa.Integer(), nullable=False),
        sa.Column("inflacion_anual", sa.Numeric(5, 2), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actualizado_por", sa.String(200), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_configuracion_unica")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuracion")),
    )
    op.create_table(
        "modelo_benchmark",
        sa.Column("version", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("entrenado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("origen", sa.String(10), nullable=False),
        sa.Column("actor_nombre", sa.String(200), nullable=False),
        sa.Column("observaciones", sa.Integer(), nullable=False),
        sa.Column("datos_hasta", sa.Date(), nullable=False),
        sa.Column("mape", sa.Numeric(8, 6), nullable=False),
        sa.Column("mape_linea_base", sa.Numeric(8, 6), nullable=False),
        sa.Column("cobertura", sa.Numeric(8, 6), nullable=False),
        sa.Column("pinball", sa.Numeric(10, 6), nullable=False),
        sa.Column("promovido", sa.Boolean(), nullable=False),
        sa.Column("artefacto", sa.String(300), nullable=True),
        sa.CheckConstraint(
            "origen IN ('manual', 'automatico')", name=op.f("ck_modelo_benchmark_origen")
        ),
        sa.PrimaryKeyConstraint("version", name=op.f("pk_modelo_benchmark")),
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

    op.execute(
        "INSERT INTO configuracion (id, peso_sla, peso_resolucion, peso_incidentes, "
        "peso_entregas, peso_satisfaccion, umbral_riesgo, inflacion_anual) "
        "VALUES (1, 30, 20, 20, 15, 15, 40, 4.50)"
    )
    # El rol "inteligencia" (usuario de la aplicación) lo crea infra/postgres/inteligencia.sh.
    # La aplicación nunca borra: la copia local solo se inserta o se actualiza.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON proveedor, servicio, tipo_cambio, contrato, "
        "linea_contrato, desempeno, modelo_benchmark, outbox TO inteligencia"
    )
    op.execute("GRANT SELECT, UPDATE ON configuracion TO inteligencia")
    op.execute("GRANT SELECT, INSERT ON evento_procesado TO inteligencia")


def downgrade() -> None:
    op.drop_index("ix_outbox_pendientes", table_name="outbox")
    op.drop_table("outbox")
    op.drop_table("modelo_benchmark")
    op.drop_table("configuracion")
    op.drop_table("evento_procesado")
    op.drop_table("desempeno")
    op.drop_table("linea_contrato")
    op.drop_index(op.f("ix_contrato_proveedor_id"), table_name="contrato")
    op.drop_table("contrato")
    op.drop_table("tipo_cambio")
    op.drop_table("servicio")
    op.drop_table("proveedor")
```

Si `test_modelos_y_migraciones_coinciden` reporta una diferencia de nombre de restricción, siga la convención de `db.py` (la prueba manda) y anótelo en el reporte.

`services/inteligencia/src/inteligencia/main.py`:

```python
"""Aplicación FastAPI del servicio de inteligencia."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.outbox import RelayOutbox
from comun.salud import crear_router_salud
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from inteligencia.config import Configuracion
from inteligencia.modelos import Outbox


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

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        tareas: list[asyncio.Task[None]] = []
        if config.usar_rabbitmq:
            await relay.conectar()
            tareas.append(asyncio.create_task(relay.ejecutar()))
        yield
        for tarea in tareas:
            tarea.cancel()
        for tarea in tareas:
            with contextlib.suppress(asyncio.CancelledError):
                await tarea
        if config.usar_rabbitmq:
            await relay.cerrar()

    app = FastAPI(
        title="Servicio de inteligencia",
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
        async with sesiones() as sesion:
            await sesion.execute(text("SELECT 1"))

    app.include_router(crear_router_salud({"postgres": verificar_postgres}))
    return app
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest services/inteligencia -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio.

- [ ] **Step 6: Infrastructure**

`services/inteligencia/Dockerfile`:

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
    uv sync --locked --no-dev --package inteligencia

ENV PATH="/app/.venv/bin:$PATH"
# /modelos: volumen de los artefactos del modelo de precios; el usuario del servicio debe poder
# escribir en él (Docker copia el dueño de este directorio al crear el volumen).
RUN useradd --create-home --uid 10001 servicio \
    && mkdir -p /modelos && chown servicio /modelos
USER servicio
EXPOSE 8000

# ponytail: migra al arrancar; con varias réplicas, mover a un job de migración previo al despliegue.
CMD ["sh", "-c", "alembic -c services/inteligencia/alembic.ini upgrade head && exec env -u DATABASE_URL_MIGRACIONES uvicorn inteligencia.main:crear_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
```

`infra/postgres/inteligencia.sh`: copie `infra/postgres/administracion.sh` cambiando `administracion` por `inteligencia` (roles `inteligencia_dueno` e `inteligencia`, base `inteligencia_db`, variables `INTELIGENCIA_DUENO_DB_PASSWORD` e `INTELIGENCIA_DB_PASSWORD`, y el comando para volúmenes existentes con `30-inteligencia.sh`). Debe quedar ejecutable igual que el otro (`git update-index --chmod=+x` si hace falta).

`infra/docker-compose.yml`:
- en `postgres`, agregue al `environment`:

```yaml
      INTELIGENCIA_DB_PASSWORD: ${INTELIGENCIA_DB_PASSWORD:?Defina INTELIGENCIA_DB_PASSWORD en infra/.env}
      INTELIGENCIA_DUENO_DB_PASSWORD: ${INTELIGENCIA_DUENO_DB_PASSWORD:?Defina INTELIGENCIA_DUENO_DB_PASSWORD en infra/.env}
```

  y a `volumes`: `- ./postgres/inteligencia.sh:/docker-entrypoint-initdb.d/30-inteligencia.sh:ro`;
- agregue el servicio después de `administracion`:

```yaml
  inteligencia:
    build:
      context: ..
      dockerfile: services/inteligencia/Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://inteligencia:${INTELIGENCIA_DB_PASSWORD}@postgres:5432/inteligencia_db
      DATABASE_URL_MIGRACIONES: postgresql+asyncpg://inteligencia_dueno:${INTELIGENCIA_DUENO_DB_PASSWORD}@postgres:5432/inteligencia_db
      RABBITMQ_URL: amqp://plataforma:${RABBITMQ_PASSWORD}@rabbitmq:5672/
      OIDC_ISSUER: http://localhost:8080/auth/realms/plataforma
      OIDC_JWKS_URL: http://keycloak:8080/auth/realms/plataforma/protocol/openid-connect/certs
      ROOT_PATH: /api/inteligencia
      DIRECTORIO_MODELOS: /modelos
    volumes:
      - modelos:/modelos
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      rabbitmq-topologia:
        condition: service_completed_successfully
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

- en `gateway.depends_on`, agregue `inteligencia` con `condition: service_healthy` y `restart: true`;
- en `volumes:`, agregue `modelos:`.

`infra/nginx/nginx.conf`: agregue después de `location /api/administracion/` el mismo bloque para `/api/inteligencia/` con `proxy_pass http://inteligencia:8000/;`.

`infra/.env.example`: agregue después de `ADMINISTRACION_DUENO_DB_PASSWORD`:

```
INTELIGENCIA_DB_PASSWORD=cambiar-inteligencia
INTELIGENCIA_DUENO_DB_PASSWORD=cambiar-inteligencia-dueno
```

`.github/dependabot.yml`: agregue `/services/inteligencia` a `directories` del ecosistema `docker`.

- [ ] **Step 7: Verify in the running stack**

`infra/.env` no se versiona y aún no tiene las dos variables nuevas. Agréguelas al final con los mismos valores de desarrollo de `.env.example`, sin imprimir el archivo. El volumen de PostgreSQL ya existe, así que el script de inicio no correrá solo: créelo a mano.

```bash
docker compose -f infra/docker-compose.yml up -d --build --wait postgres
docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/30-inteligencia.sh
docker compose -f infra/docker-compose.yml up -d --build --wait
curl -s http://localhost:8080/api/inteligencia/salud/listo
```

Expected:
- `up` termina con código 0;
- `/api/inteligencia/salud/listo` responde `{"estado":"ok","dependencias":{"postgres":"ok"}}`.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock services/inteligencia infra/postgres/inteligencia.sh infra/docker-compose.yml infra/nginx/nginx.conf infra/.env.example .github/dependabot.yml
git commit -m "feat(inteligencia): servicio nuevo con su base de datos, outbox e infraestructura" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `inteligencia`: copia local alimentada por eventos

**Files:**
- Create: `services/inteligencia/src/inteligencia/eventos.py`
- Create: `services/inteligencia/tests/test_eventos.py`
- Modify: `services/inteligencia/src/inteligencia/main.py` (consumidor en el ciclo de vida)

**Interfaces:**
- Consumes: `comun.consumidor.ConsumidorEventos`, `Atender` y `EventoInvalido` (Task 3); `comun.topologia.COLA_INTELIGENCIA` (Task 2); los modelos de la Task 6; los payloads de `proveedores` (Task 4 y los existentes).
- Produces:
  - `inteligencia.eventos.aplicar(sesion: AsyncSession, sobre: dict[str, Any]) -> bool`: aplica el evento dentro de la transacción en curso; `False` si ese `event_id` ya se había aplicado.
  - `inteligencia.eventos.atendedor(fabrica) -> Atender`.
  - Cada contrato guarda `recibido_en` (lo usa el reentrenamiento automático, Task 11).

Payloads que llegan (los publica `proveedores`):
- `proveedor.actualizado`: `{id, rfc, nombre, tamano, categorias, contacto_nombre, contacto_email, activo}`.
- `servicio.actualizado`: la copia `{id, codigo, nombre, categoria, unidad, moneda, activo}`, o la edición del catálogo con además `cambio`, `campos` y `actor`.
- `tipo_cambio.registrado`: `{periodo, usd_mxn}`.
- `contrato.registrado`: `{id, proveedor_id, folio, rfc_proveedor, tipo, fecha_inicio, fecha_fin, moneda, plazo_pago_dias, sla_disponibilidad, tope_aumento_pct, cuota_implementacion, lineas: [{codigo_servicio, nombre_servicio, categoria, unidad, cantidad, precio_unitario}]}`.
- `desempeno.registrado`: `{proveedor_id, periodo, sla_cumplimiento_pct, tiempo_resolucion_h, incidentes_criticos, entregas_a_tiempo_pct, satisfaccion}`.

Fechas como `"AAAA-MM-DD"`, decimales como texto.

- [ ] **Step 1: Write the failing tests**

Cree `services/inteligencia/tests/test_eventos.py`:

```python
import asyncio
import json
import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import aio_pika
import pytest
from comun.consumidor import ConsumidorEventos
from comun.outbox import EXCHANGE_EVENTOS
from comun.topologia import COLA_INTELIGENCIA
from inteligencia.eventos import atendedor
from inteligencia.modelos import (
    Contrato,
    Desempeno,
    EventoProcesado,
    Proveedor,
    Servicio,
    TipoCambio,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.rabbitmq import RabbitMqContainer

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
ID_PROVEEDOR = "6f1c2c1e-0000-4000-8000-000000000001"
ID_SERVICIO = "6f1c2c1e-0000-4000-8000-000000000002"
ID_CONTRATO = "6f1c2c1e-0000-4000-8000-000000000003"
PROVEEDOR = {
    "id": ID_PROVEEDOR,
    "rfc": "NAZ210315AB1",
    "nombre": "Nube Azteca S.A. de C.V.",
    "tamano": "mediana",
    "categorias": ["licencia_saas"],
    "contacto_nombre": "Laura Méndez",
    "contacto_email": "ventas01@proveedor01.example",
    "activo": True,
}
SERVICIO = {
    "id": ID_SERVICIO,
    "codigo": "SAAS-OFI-EMP",
    "nombre": "Suite de productividad",
    "categoria": "licencia_saas",
    "unidad": "usuario_mes",
    "moneda": "USD",
    "activo": True,
}
CONTRATO = {
    "id": ID_CONTRATO,
    "proveedor_id": ID_PROVEEDOR,
    "folio": "C-0001",
    "rfc_proveedor": "NAZ210315AB1",
    "tipo": "nuevo",
    "fecha_inicio": "2025-01-01",
    "fecha_fin": "2025-12-31",
    "moneda": "USD",
    "plazo_pago_dias": 30,
    "sla_disponibilidad": "99.90",
    "tope_aumento_pct": "5.00",
    "cuota_implementacion": "0",
    "lineas": [
        {
            "codigo_servicio": "SAAS-OFI-EMP",
            "nombre_servicio": "Suite de productividad",
            "categoria": "licencia_saas",
            "unidad": "usuario_mes",
            "cantidad": "250",
            "precio_unitario": "21.5",
        }
    ],
}
DESEMPENO = {
    "proveedor_id": ID_PROVEEDOR,
    "periodo": "2025-01-01",
    "sla_cumplimiento_pct": "99.50",
    "tiempo_resolucion_h": "4.25",
    "incidentes_criticos": 0,
    "entregas_a_tiempo_pct": "97.00",
    "satisfaccion": "4.60",
}


def _sobre(tipo: str, payload: Any, event_id: str | None = None) -> dict[str, Any]:
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "type": tipo,
        "version": 1,
        "occurred_at": "2026-10-10T15:00:00+00:00",
        "correlation_id": "c-1",
        "payload": payload,
    }


async def _contar(fabrica: Fabrica, modelo: type[object]) -> int:
    async with fabrica() as sesion:
        return int(await sesion.scalar(select(func.count()).select_from(modelo)) or 0)


async def test_cada_evento_actualiza_la_copia(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    for tipo, payload in (
        ("proveedor.actualizado", PROVEEDOR),
        ("servicio.actualizado", SERVICIO),
        ("tipo_cambio.registrado", {"periodo": "2025-01-01", "usd_mxn": "20.4512"}),
        ("contrato.registrado", CONTRATO),
        ("desempeno.registrado", DESEMPENO),
    ):
        await atender(_sobre(tipo, payload))
    async with fabrica() as sesion:
        proveedor = await sesion.get(Proveedor, uuid.UUID(ID_PROVEEDOR))
        servicio = await sesion.get(Servicio, uuid.UUID(ID_SERVICIO))
        contrato = await sesion.get(Contrato, uuid.UUID(ID_CONTRATO))
        tipo_cambio = await sesion.scalar(select(TipoCambio.usd_mxn))
        satisfaccion = await sesion.scalar(select(Desempeno.satisfaccion))
    assert proveedor is not None and proveedor.categorias == ["licencia_saas"]
    assert servicio is not None and servicio.unidad == "usuario_mes"
    assert contrato is not None and contrato.folio == "C-0001"
    [linea] = contrato.lineas
    assert (linea.codigo_servicio, linea.cantidad, linea.precio_unitario) == (
        "SAAS-OFI-EMP",
        Decimal("250"),
        Decimal("21.5"),
    )
    assert tipo_cambio == Decimal("20.4512")
    assert satisfaccion == Decimal("4.60")
    assert await _contar(fabrica, EventoProcesado) == 5


async def test_un_evento_repetido_no_se_aplica_dos_veces(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    await atender(_sobre("desempeno.registrado", DESEMPENO, "repetido"))
    # Mismo event_id con otro contenido: es el mismo evento entregado otra vez, se ignora.
    await atender(_sobre("desempeno.registrado", DESEMPENO | {"satisfaccion": "4.90"}, "repetido"))
    async with fabrica() as sesion:
        assert await sesion.scalar(select(Desempeno.satisfaccion)) == Decimal("4.60")
    # Un evento nuevo del mismo periodo sí actualiza.
    await atender(_sobre("desempeno.registrado", DESEMPENO | {"satisfaccion": "4.90"}))
    async with fabrica() as sesion:
        assert await sesion.scalar(select(Desempeno.satisfaccion)) == Decimal("4.90")
    await atender(_sobre("contrato.registrado", CONTRATO))
    await atender(_sobre("contrato.registrado", CONTRATO))  # reproceso: otro event_id
    assert await _contar(fabrica, Contrato) == 1


async def test_un_contrato_de_un_proveedor_desconocido_se_guarda(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    await atender(_sobre("contrato.registrado", CONTRATO))
    assert await _contar(fabrica, Contrato) == 1
    await atender(_sobre("proveedor.actualizado", PROVEEDOR))
    assert await _contar(fabrica, Proveedor) == 1


async def test_la_edicion_del_catalogo_actualiza_el_servicio(fabrica: Fabrica) -> None:
    atender = atendedor(fabrica)
    await atender(_sobre("servicio.actualizado", SERVICIO))
    edicion = SERVICIO | {
        "nombre": "Suite de oficina",
        "activo": False,
        "cambio": "desactivado",
        "campos": [],
        "actor": {"id": "admin-1", "nombre": "admin1"},
    }
    await atender(_sobre("servicio.actualizado", edicion))
    async with fabrica() as sesion:
        servicio = await sesion.get(Servicio, uuid.UUID(ID_SERVICIO))
    assert servicio is not None
    assert (servicio.nombre, servicio.activo) == ("Suite de oficina", False)


async def test_un_tipo_que_no_le_importa_solo_se_anota(fabrica: Fabrica) -> None:
    await atendedor(fabrica)(_sobre("importacion.completada", {"entidad": "contratos"}))
    assert await _contar(fabrica, EventoProcesado) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        "no es un objeto",
        CONTRATO | {"fecha_inicio": "no es fecha"},
        CONTRATO | {"lineas": [{"codigo_servicio": "SAAS-OFI-EMP"}]},
        CONTRATO | {"lineas": [CONTRATO["lineas"][0] | {"cantidad": "mucho"}]},  # type: ignore[index]
    ],
    ids=["vacio", "texto", "fecha", "linea_incompleta", "cantidad"],
)
async def test_un_evento_mal_formado_es_invalido_y_no_deja_rastro(
    fabrica: Fabrica, payload: Any
) -> None:
    with pytest.raises(ValueError):  # EventoInvalido también es ValueError
        await atendedor(fabrica)(_sobre("contrato.registrado", payload))
    assert await _contar(fabrica, Contrato) == 0
    assert await _contar(fabrica, EventoProcesado) == 0


@pytest.fixture(scope="module")
def url_rabbitmq() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:4.1-alpine", username="prueba", password="prueba") as rmq:
        host, puerto = rmq.get_container_host_ip(), rmq.get_exposed_port(5672)
        yield f"amqp://prueba:prueba@{host}:{puerto}/"


async def test_consume_los_eventos_de_su_cola(fabrica: Fabrica, url_rabbitmq: str) -> None:
    consumidor = ConsumidorEventos(url_rabbitmq, COLA_INTELIGENCIA, atendedor(fabrica))
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
            await exchange.publish(
                aio_pika.Message(json.dumps(_sobre("proveedor.actualizado", PROVEEDOR)).encode()),
                routing_key="proveedor.actualizado",
            )
        for _ in range(200):
            if await _contar(fabrica, Proveedor):
                break
            await asyncio.sleep(0.05)
        assert await _contar(fabrica, Proveedor) == 1
    finally:
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea
        await consumidor.cerrar()
```

Si mypy marca el `type: ignore[index]` como innecesario, quítelo. Si en cambio no acepta indexar `CONTRATO["lineas"]`, extraiga la línea a una constante `LINEA` y construya `CONTRATO` con ella.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest services/inteligencia/tests/test_eventos.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'inteligencia.eventos'`.

- [ ] **Step 3: Implement**

Cree `services/inteligencia/src/inteligencia/eventos.py`:

```python
"""Copia local de los datos de proveedores, alimentada por sus eventos.

Cada evento se aplica en una transacción que también registra su event_id: un evento repetido choca
con esa clave y no se aplica dos veces. Los eventos pueden llegar en desorden (un contrato antes que
su proveedor), por eso la copia no tiene llaves foráneas entre entidades.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from typing import Any

from comun.consumidor import Atender, EventoInvalido
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inteligencia.modelos import (
    Contrato,
    Desempeno,
    EventoProcesado,
    LineaContrato,
    Proveedor,
    Servicio,
    TipoCambio,
)


def _uuid(valor: Any) -> uuid.UUID:
    return uuid.UUID(str(valor))


def _fecha(valor: Any) -> date:
    return date.fromisoformat(str(valor))


def _decimal(valor: Any) -> Decimal:
    return Decimal(str(valor))


async def _proveedor(sesion: AsyncSession, p: dict[str, Any]) -> None:
    consulta = insert(Proveedor).values(
        id=_uuid(p["id"]),
        rfc=str(p["rfc"]),
        nombre=str(p["nombre"]),
        tamano=str(p["tamano"]),
        categorias=[str(c) for c in p["categorias"]],
        activo=bool(p["activo"]),
    )
    columnas = ("rfc", "nombre", "tamano", "categorias", "activo")
    await sesion.execute(
        consulta.on_conflict_do_update(
            index_elements=[Proveedor.id], set_={c: consulta.excluded[c] for c in columnas}
        )
    )


async def _servicio(sesion: AsyncSession, p: dict[str, Any]) -> None:
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
    await sesion.execute(
        consulta.on_conflict_do_update(
            index_elements=[Servicio.id], set_={c: consulta.excluded[c] for c in columnas}
        )
    )


async def _tipo_cambio(sesion: AsyncSession, p: dict[str, Any]) -> None:
    consulta = insert(TipoCambio).values(
        periodo=_fecha(p["periodo"]), usd_mxn=_decimal(p["usd_mxn"])
    )
    await sesion.execute(
        consulta.on_conflict_do_update(
            index_elements=[TipoCambio.periodo], set_={"usd_mxn": consulta.excluded.usd_mxn}
        )
    )


async def _contrato(sesion: AsyncSession, p: dict[str, Any]) -> None:
    """Los contratos no cambian después de importarse: uno repetido (reproceso) no hace nada."""
    contrato_id = _uuid(p["id"])
    lineas = [
        {
            "contrato_id": contrato_id,
            "codigo_servicio": str(linea["codigo_servicio"]),
            "categoria": str(linea["categoria"]),
            "unidad": str(linea["unidad"]),
            "cantidad": _decimal(linea["cantidad"]),
            "precio_unitario": _decimal(linea["precio_unitario"]),
        }
        for linea in p["lineas"]
    ]
    await sesion.execute(
        insert(Contrato)
        .values(
            id=contrato_id,
            folio=str(p["folio"]),
            proveedor_id=_uuid(p["proveedor_id"]),
            tipo=str(p["tipo"]),
            fecha_inicio=_fecha(p["fecha_inicio"]),
            fecha_fin=_fecha(p["fecha_fin"]),
            moneda=str(p["moneda"]),
        )
        .on_conflict_do_nothing(index_elements=[Contrato.id])
    )
    if lineas:
        await sesion.execute(insert(LineaContrato).on_conflict_do_nothing(), lineas)


async def _desempeno(sesion: AsyncSession, p: dict[str, Any]) -> None:
    metricas = {
        "sla_cumplimiento_pct": _decimal(p["sla_cumplimiento_pct"]),
        "tiempo_resolucion_h": _decimal(p["tiempo_resolucion_h"]),
        "incidentes_criticos": int(p["incidentes_criticos"]),
        "entregas_a_tiempo_pct": _decimal(p["entregas_a_tiempo_pct"]),
        "satisfaccion": _decimal(p["satisfaccion"]),
    }
    consulta = insert(Desempeno).values(
        proveedor_id=_uuid(p["proveedor_id"]), periodo=_fecha(p["periodo"]), **metricas
    )
    await sesion.execute(
        consulta.on_conflict_do_update(
            index_elements=[Desempeno.proveedor_id, Desempeno.periodo],
            set_={c: consulta.excluded[c] for c in metricas},
        )
    )


APLICADORES: dict[str, Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]] = {
    "proveedor.actualizado": _proveedor,
    "servicio.actualizado": _servicio,
    "tipo_cambio.registrado": _tipo_cambio,
    "contrato.registrado": _contrato,
    "desempeno.registrado": _desempeno,
}


async def aplicar(sesion: AsyncSession, sobre: dict[str, Any]) -> bool:
    """Aplica el evento en la transacción en curso; False si ese event_id ya se había aplicado."""
    tipo = str(sobre["type"])
    nuevo = await sesion.scalar(
        insert(EventoProcesado)
        .values(event_id=str(sobre["event_id"]), tipo=tipo)
        .on_conflict_do_nothing(index_elements=[EventoProcesado.event_id])
        .returning(EventoProcesado.event_id)
    )
    if nuevo is None:
        return False
    aplicador = APLICADORES.get(tipo)
    if aplicador is not None:
        await aplicador(sesion, sobre["payload"])
    return True


def atendedor(fabrica: async_sessionmaker[AsyncSession]) -> Atender:
    """La función que el consumidor común llama con cada sobre de evento."""

    async def atender(sobre: dict[str, Any]) -> None:
        try:
            async with fabrica() as sesion, sesion.begin():
                await aplicar(sesion, sobre)
        # Un ValueError (fecha o UUID inválidos) ya lo trata el consumidor como evento inválido.
        except (KeyError, TypeError, AttributeError, ArithmeticError) as exc:
            raise EventoInvalido(repr(exc)) from exc

    return atender
```

En `services/inteligencia/src/inteligencia/main.py`:

- importe `from comun.consumidor import ConsumidorEventos`, `from comun.topologia import COLA_INTELIGENCIA` y `from inteligencia.eventos import atendedor`;
- después de crear el `relay`, cree `consumidor = ConsumidorEventos(config.rabbitmq_url, COLA_INTELIGENCIA, atendedor(sesiones))`;
- en el ciclo de vida, dentro de `if config.usar_rabbitmq:`, agregue `tareas.append(asyncio.create_task(consumidor.ejecutar()))`;
- al cerrar, dentro de `if config.usar_rabbitmq:`, llame `await consumidor.cerrar()` antes de `await relay.cerrar()`;
- guarde `app.state.consumidor = consumidor`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest services/inteligencia -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio.

- [ ] **Step 5: Commit**

```bash
git add services/inteligencia/src/inteligencia/eventos.py services/inteligencia/src/inteligencia/main.py services/inteligencia/tests/test_eventos.py
git commit -m "feat(inteligencia): copia local de proveedores alimentada por eventos, idempotente" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Dominio: línea base del precio justo

Funciones puras, sin E/S. Se usan desde la API (Task 12), desde el entrenamiento (Task 11) y desde la validación (Task 16).

**Files:**
- Create: `services/inteligencia/src/inteligencia/dominio/__init__.py` (vacío)
- Create: `services/inteligencia/src/inteligencia/dominio/precios.py`
- Test: `services/inteligencia/tests/test_precios.py`

**Interfaces:**
- Produces (`inteligencia.dominio.precios`):
  - Constantes: `MIN_OBSERVACIONES = 8`, `VENTANA_MESES = 24` y `UNIDADES_MENSUALES = frozenset({"usuario_mes", "vcpu_mes", "gb_mes", "mes"})`.
  - `Observacion(servicio, categoria, moneda, fecha: date, cantidad: float, precio: float, plazo_meses: int, tamano: str | None, tipo: str)`, frozen. `precio` está en la moneda del servicio y `fecha` es el inicio del contrato.
  - `Banda(p25: float, p50: float, p75: float)` y `Referencia(banda, confianza: Literal["normal", "baja"], observaciones: int, metodo: Literal["linea_base", "modelo"] = "linea_base", version: int | None = None)`, frozen.
  - Fechas:
    - `meses_entre(inicio: date, fin: date) -> int`;
    - `sumar_meses(fecha: date, meses: int) -> date` (primer día del mes);
    - `plazo_en_meses(inicio: date, fin: date) -> int` (2025-01-01 → 2025-12-31 son 12);
    - `meses_restantes(hoy: date, fin: date) -> int`.
  - `ajustar_por_inflacion(precio: float, desde: date, hasta: date, tasa_anual: float) -> float` y `cuartiles(valores: Sequence[float]) -> Banda`.
  - `linea_base(observaciones: Iterable[Observacion], servicio: str, categoria: str, cantidad: float, fecha: date, tasa_inflacion: float) -> Referencia | None`.
  - `cantidad_mensual(cantidad: Decimal, unidad: str, plazo_meses: int) -> Decimal`.
  - `posicion(precio: float, banda: Banda) -> Literal["bajo_p25", "justo", "sobre_p75"]`.
  - `ahorro_potencial(precio: Decimal, p50: Decimal, cantidad_mes: Decimal, meses: int) -> Decimal` (2 decimales, nunca negativo).

- [ ] **Step 1: Write the failing tests**

Cree `services/inteligencia/tests/test_precios.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from inteligencia.dominio.precios import (
    Banda,
    Observacion,
    ahorro_potencial,
    ajustar_por_inflacion,
    cantidad_mensual,
    cuartiles,
    linea_base,
    meses_restantes,
    plazo_en_meses,
    posicion,
    sumar_meses,
)

HOY = date(2026, 9, 1)
INFLACION = 0.045


def _obs(
    precio: float,
    cantidad: float = 100.0,
    fecha: date = HOY,
    servicio: str = "SAAS-OFI-EMP",
    categoria: str = "licencia_saas",
) -> Observacion:
    return Observacion(
        servicio=servicio,
        categoria=categoria,
        moneda="USD",
        fecha=fecha,
        cantidad=cantidad,
        precio=precio,
        plazo_meses=12,
        tamano="mediana",
        tipo="nuevo",
    )


def test_sin_observaciones_no_hay_referencia() -> None:
    assert linea_base([], "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION) is None
    vieja = _obs(20.0, fecha=date(2024, 8, 1))  # fuera de la ventana de 24 meses
    assert linea_base([vieja], "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION) is None
    otro = _obs(20.0, servicio="SAAS-CRM-PRO")  # la categoría tiene datos, el servicio no
    assert linea_base([otro], "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION) is None


def test_cuartiles_del_tercil_con_suficientes_observaciones() -> None:
    observaciones = [_obs(p) for p in (10.0, 11, 12, 13, 14, 15, 16, 17, 18)]
    referencia = linea_base(observaciones, "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION)
    assert referencia is not None
    assert (referencia.confianza, referencia.observaciones) == ("normal", 9)
    assert referencia.banda == Banda(12.0, 14.0, 16.0)
    assert (referencia.metodo, referencia.version) == ("linea_base", None)


def test_compara_con_contratos_de_cantidad_parecida() -> None:
    chicos = [_obs(20.0 + i * 0.1, cantidad=10) for i in range(9)]
    grandes = [_obs(15.0 + i * 0.1, cantidad=1_000) for i in range(9)]
    medianos = [_obs(17.0 + i * 0.1, cantidad=100) for i in range(9)]
    todas = chicos + medianos + grandes
    grande = linea_base(todas, "SAAS-OFI-EMP", "licencia_saas", 900, HOY, INFLACION)
    chico = linea_base(todas, "SAAS-OFI-EMP", "licencia_saas", 12, HOY, INFLACION)
    assert grande is not None and chico is not None
    assert grande.banda.p50 == pytest.approx(15.4)
    assert chico.banda.p50 == pytest.approx(20.4)


def test_con_pocas_observaciones_usa_la_categoria_con_baja_confianza() -> None:
    propios = [_obs(p) for p in (19.0, 20.0, 21.0)]
    otros = [
        _obs(p, servicio="SAAS-CRM-PRO") for p in (90.0, 95, 100, 100, 100, 100, 105, 110, 100)
    ]
    referencia = linea_base(
        propios + otros, "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION
    )
    assert referencia is not None
    assert (referencia.confianza, referencia.observaciones) == ("baja", 3)
    # La mediana del servicio (20) con la dispersión relativa de la categoría.
    assert referencia.banda.p50 == pytest.approx(20.0)
    assert referencia.banda.p25 < 20.0 < referencia.banda.p75


def test_lleva_los_precios_viejos_a_la_fecha_por_inflacion() -> None:
    assert ajustar_por_inflacion(100.0, date(2025, 9, 1), HOY, INFLACION) == pytest.approx(104.5)
    hace_un_anio = [_obs(100.0, fecha=date(2025, 9, 1)) for _ in range(8)]
    referencia = linea_base(hace_un_anio, "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION)
    assert referencia is not None
    assert referencia.banda.p50 == pytest.approx(104.5)


def test_fechas_y_cantidades() -> None:
    assert plazo_en_meses(date(2025, 1, 1), date(2025, 12, 31)) == 12
    assert plazo_en_meses(date(2025, 3, 1), date(2025, 8, 31)) == 6
    assert sumar_meses(date(2026, 9, 15), -24) == date(2024, 9, 1)
    assert meses_restantes(date(2026, 10, 10), date(2026, 12, 31)) == 3
    assert meses_restantes(date(2026, 10, 10), date(2026, 9, 30)) == 0
    assert cantidad_mensual(Decimal("250"), "usuario_mes", 12) == Decimal("250")
    # Por consumo, la cantidad es del contrato completo.
    assert cantidad_mensual(Decimal("120"), "hora", 6) == Decimal("20")


def test_posicion_frente_al_mercado() -> None:
    banda = Banda(10.0, 12.0, 14.0)
    assert posicion(9.5, banda) == "bajo_p25"
    assert posicion(12.0, banda) == "justo"
    assert posicion(14.0, banda) == "justo"
    assert posicion(14.5, banda) == "sobre_p75"


def test_ahorro_potencial() -> None:
    # (25 − 20) × 100 al mes × 6 meses.
    assert ahorro_potencial(Decimal("25"), Decimal("20"), Decimal("100"), 6) == Decimal("3000.00")
    assert ahorro_potencial(Decimal("18"), Decimal("20"), Decimal("100"), 6) == Decimal("0.00")


PRECIOS = st.lists(
    st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=40,
)


@given(PRECIOS)
def test_los_cuartiles_siempre_estan_ordenados(valores: list[float]) -> None:
    banda = cuartiles(valores)
    assert banda.p25 <= banda.p50 <= banda.p75


@given(PRECIOS, st.floats(min_value=1, max_value=10_000))
def test_la_referencia_siempre_esta_ordenada(valores: list[float], cantidad: float) -> None:
    observaciones = [_obs(p, cantidad=float(i % 7 + 1) * 10) for i, p in enumerate(valores)]
    referencia = linea_base(
        observaciones, "SAAS-OFI-EMP", "licencia_saas", cantidad, HOY, INFLACION
    )
    assert referencia is not None
    assert referencia.banda.p25 <= referencia.banda.p50 <= referencia.banda.p75


DECIMALES = st.decimals(
    min_value=Decimal("0.0001"), max_value=Decimal("100000"), places=4, allow_nan=False
)


@given(DECIMALES, DECIMALES, DECIMALES, st.integers(min_value=0, max_value=60))
def test_el_ahorro_nunca_es_negativo(
    precio: Decimal, p50: Decimal, cantidad: Decimal, meses: int
) -> None:
    assert ahorro_potencial(precio, p50, cantidad, meses) >= 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest services/inteligencia/tests/test_precios.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'inteligencia.dominio'`.

- [ ] **Step 3: Implement**

Cree `services/inteligencia/src/inteligencia/dominio/__init__.py` vacío y `services/inteligencia/src/inteligencia/dominio/precios.py`:

```python
"""Precio justo por línea base: percentiles de los contratos recientes del mismo servicio.

Funciones puras: reciben las observaciones ya cargadas y no hacen E/S.
"""

import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

MIN_OBSERVACIONES = 8
VENTANA_MESES = 24
UNIDADES_MENSUALES = frozenset({"usuario_mes", "vcpu_mes", "gb_mes", "mes"})

Confianza = Literal["normal", "baja"]
Posicion = Literal["bajo_p25", "justo", "sobre_p75"]


@dataclass(frozen=True)
class Observacion:
    """Una línea de contrato vista como precio observado, en la moneda del servicio."""

    servicio: str
    categoria: str
    moneda: str
    fecha: date  # inicio del contrato
    cantidad: float
    precio: float
    plazo_meses: int
    tamano: str | None
    tipo: str


@dataclass(frozen=True)
class Banda:
    p25: float
    p50: float
    p75: float


@dataclass(frozen=True)
class Referencia:
    banda: Banda
    confianza: Confianza
    observaciones: int
    metodo: Literal["linea_base", "modelo"] = "linea_base"
    version: int | None = None


def meses_entre(inicio: date, fin: date) -> int:
    """Meses de calendario de `inicio` a `fin` (del 15 de enero al 1 de marzo son 2)."""
    return (fin.year - inicio.year) * 12 + fin.month - inicio.month


def sumar_meses(fecha: date, meses: int) -> date:
    """El primer día del mes que queda `meses` después (o antes) del mes de `fecha`."""
    indice = fecha.year * 12 + fecha.month - 1 + meses
    return date(indice // 12, indice % 12 + 1, 1)


def plazo_en_meses(inicio: date, fin: date) -> int:
    """Duración del contrato en meses: del 2025-01-01 al 2025-12-31 son 12."""
    return max(1, meses_entre(inicio, fin) + 1)


def meses_restantes(hoy: date, fin: date) -> int:
    """Meses que le quedan al contrato, contando el actual; 0 si ya terminó."""
    return 0 if fin < hoy else meses_entre(hoy, fin) + 1


def ajustar_por_inflacion(precio: float, desde: date, hasta: date, tasa_anual: float) -> float:
    return precio * (1 + tasa_anual) ** (meses_entre(desde, hasta) / 12)


def cuartiles(valores: Sequence[float]) -> Banda:
    if len(valores) == 1:
        return Banda(valores[0], valores[0], valores[0])
    # sorted: el redondeo de punto flotante no debe dejar P25 > P50 con valores casi iguales.
    p25, p50, p75 = sorted(statistics.quantiles(valores, n=4, method="inclusive"))
    return Banda(p25, p50, p75)


def _cortes(cantidades: Sequence[float]) -> tuple[float, float]:
    if len(cantidades) < 3:
        medio = statistics.median(cantidades)
        return medio, medio
    primero, segundo = statistics.quantiles(cantidades, n=3, method="inclusive")
    return primero, segundo


def _tercil(cantidad: float, cortes: tuple[float, float]) -> int:
    return 0 if cantidad <= cortes[0] else 1 if cantidad <= cortes[1] else 2


def linea_base(
    observaciones: Iterable[Observacion],
    servicio: str,
    categoria: str,
    cantidad: float,
    fecha: date,
    tasa_inflacion: float,
) -> Referencia | None:
    """P25/P50/P75 del servicio para esa cantidad a la `fecha`; None sin contratos recientes.

    Usa los contratos de los últimos 24 meses del mismo tercil de cantidad, con los precios llevados
    a la `fecha` por inflación. Con menos de MIN_OBSERVACIONES en el tercil, aplica a la mediana del
    servicio la dispersión relativa de toda su categoría y marca la referencia como de baja
    confianza.
    """
    desde = sumar_meses(fecha, -VENTANA_MESES)
    ventana = [o for o in observaciones if o.categoria == categoria and desde < o.fecha <= fecha]
    propios = [o for o in ventana if o.servicio == servicio]
    if not propios:
        return None

    def ajustado(o: Observacion) -> float:
        return ajustar_por_inflacion(o.precio, o.fecha, fecha, tasa_inflacion)

    cortes = _cortes([o.cantidad for o in propios])
    tercil = _tercil(cantidad, cortes)
    mismos = [ajustado(o) for o in propios if _tercil(o.cantidad, cortes) == tercil]
    if len(mismos) >= MIN_OBSERVACIONES:
        return Referencia(cuartiles(mismos), "normal", len(mismos))
    por_servicio: dict[str, list[float]] = defaultdict(list)
    for o in ventana:
        por_servicio[o.servicio].append(ajustado(o))
    razones = [p / statistics.median(precios) for precios in por_servicio.values() for p in precios]
    base = statistics.median(ajustado(o) for o in propios)
    relativa = cuartiles(razones)
    banda = Banda(relativa.p25 * base, relativa.p50 * base, relativa.p75 * base)
    return Referencia(banda, "baja", len(propios))


def cantidad_mensual(cantidad: Decimal, unidad: str, plazo_meses: int) -> Decimal:
    """Por mes: las unidades mensuales ya lo son; las de consumo (hora, ticket) son del contrato."""
    return cantidad if unidad in UNIDADES_MENSUALES else cantidad / plazo_meses


def posicion(precio: float, banda: Banda) -> Posicion:
    if precio < banda.p25:
        return "bajo_p25"
    return "sobre_p75" if precio > banda.p75 else "justo"


def ahorro_potencial(precio: Decimal, p50: Decimal, cantidad_mes: Decimal, meses: int) -> Decimal:
    """Lo que se ahorraría en `meses` pagando el P50 en vez del precio actual; nunca negativo."""
    ahorro = max(Decimal(0), (precio - p50) * cantidad_mes * meses)
    return ahorro.quantize(Decimal("0.01"))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest services/inteligencia/tests/test_precios.py -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio. Si Hypothesis encuentra un contraejemplo, corrija el código, no la prueba, y anote el caso en el reporte.

- [ ] **Step 5: Commit**

```bash
git add services/inteligencia/src/inteligencia/dominio services/inteligencia/tests/test_precios.py
git commit -m "feat(inteligencia): línea base del precio justo por servicio y tercil de cantidad" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Dominio: puntuación de proveedores

**Files:**
- Create: `services/inteligencia/src/inteligencia/dominio/puntuacion.py`
- Test: `services/inteligencia/tests/test_puntuacion.py`

**Interfaces:**
- Consumes: `meses_entre` y `sumar_meses` (Task 8).
- Produces (`inteligencia.dominio.puntuacion`):
  - Constantes:
    - `KPIS = ("sla", "resolucion", "incidentes", "entregas", "satisfaccion")`;
    - `INVERSOS = frozenset({"resolucion", "incidentes"})`;
    - `VENTANA_MESES = 12`, `VIDA_MEDIA_MESES = 6`, `K_CONTRACCION = 6`;
    - `MIN_PROVEEDORES_CATEGORIA = 20`, `MESES_HISTORIAL_CORTO = 6`, `MESES_TENDENCIA = 3`.
  - `Mes(periodo: date, sla: float, resolucion: float, incidentes: float, entregas: float, satisfaccion: float)`, frozen.
  - `Pesos(sla=30, resolucion=20, incidentes=20, entregas=15, satisfaccion=15)`, frozen, con `como_dict() -> dict[str, int]`.
  - `validar_pesos(pesos: Mapping[str, int]) -> str | None`: el mensaje de error, o `None`.
  - `Puntuacion(puntuacion: float, sin_ajuste: float, meses: int, componentes: dict[str, float], valores: dict[str, float])`, frozen, con la propiedad `historial_corto -> bool`.
  - `promedio_ponderado(meses: Sequence[Mes], hasta: date) -> tuple[dict[str, float], int] | None`.
  - `percentil(valor: float, todos: Sequence[float]) -> float`.
  - `contraer(puntuacion: float, media: float, meses: int) -> float`.
  - `puntuar(desempeno: Mapping[str, Sequence[Mes]], categorias: Mapping[str, str], pesos: Pesos, hasta: date) -> dict[str, Puntuacion]`. Las llaves son los ids de proveedor como texto; `categorias` es la categoría principal de cada uno (la primera de su lista).
  - `historial(desempeno, categorias, pesos, hasta, meses: int = 12) -> dict[str, list[tuple[date, float]]]`: la puntuación al cierre de cada uno de los últimos `meses` meses, del más viejo al más nuevo.

- [ ] **Step 1: Write the failing tests**

Cree `services/inteligencia/tests/test_puntuacion.py`:

```python
from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st
from inteligencia.dominio.precios import sumar_meses
from inteligencia.dominio.puntuacion import (
    Mes,
    Pesos,
    contraer,
    historial,
    percentil,
    promedio_ponderado,
    puntuar,
    validar_pesos,
)

HOY = date(2026, 9, 1)


def _mes(periodo: date, nivel: float) -> Mes:
    """Un mes de desempeño de un proveedor con calidad `nivel` (0 malo, 1 excelente)."""
    return Mes(
        periodo=periodo,
        sla=95 + 5 * nivel,
        resolucion=24 - 18 * nivel,
        incidentes=3 * (1 - nivel),
        entregas=80 + 20 * nivel,
        satisfaccion=1.5 + 3.5 * nivel,
    )


def _historia(nivel: float, meses: int = 12, hasta: date = HOY) -> list[Mes]:
    return [_mes(sumar_meses(hasta, -i), nivel) for i in range(meses)]


def test_mejor_desempeno_mejor_puntuacion() -> None:
    desempeno = {"bueno": _historia(0.9), "medio": _historia(0.5), "malo": _historia(0.1)}
    categorias = dict.fromkeys(desempeno, "nube")
    puntuaciones = puntuar(desempeno, categorias, Pesos(), HOY)
    assert (
        puntuaciones["bueno"].puntuacion
        > puntuaciones["medio"].puntuacion
        > puntuaciones["malo"].puntuacion
    )
    # Resolución e incidentes: menos es mejor, así que el bueno queda arriba también ahí.
    assert puntuaciones["bueno"].componentes["resolucion"] == 100
    assert puntuaciones["bueno"].componentes["incidentes"] == 100
    assert puntuaciones["bueno"].meses == 12


def test_percentil_con_empates() -> None:
    assert percentil(5, [1, 5, 5, 9]) == pytest.approx(50.0)
    assert percentil(9, [1, 5, 5, 9]) == pytest.approx(100.0)
    assert percentil(7, [7]) == 50.0


def test_el_desempeno_reciente_pesa_mas() -> None:
    reciente = Mes(HOY, sla=100, resolucion=1, incidentes=0, entregas=100, satisfaccion=5)
    viejo = Mes(sumar_meses(HOY, -6), sla=90, resolucion=1, incidentes=0, entregas=100, satisfaccion=5)
    resultado = promedio_ponderado([reciente, viejo], HOY)
    assert resultado is not None
    valores, meses = resultado
    # Vida media de 6 meses: el mes de hace 6 pesa la mitad.
    assert valores["sla"] == pytest.approx((100 * 1 + 90 * 0.5) / 1.5)
    assert meses == 2


def test_fuera_de_los_12_meses_no_cuenta() -> None:
    assert promedio_ponderado([_mes(sumar_meses(HOY, -12), 0.5)], HOY) is None


def test_un_historial_corto_se_acerca_a_la_media() -> None:
    desempeno = {f"p{i}": _historia(0.2 + i * 0.05) for i in range(10)}
    desempeno["nuevo"] = _historia(1.0, meses=1)
    categorias = dict.fromkeys(desempeno, "nube")
    puntuaciones = puntuar(desempeno, categorias, Pesos(), HOY)
    nuevo = puntuaciones["nuevo"]
    media = sum(p.sin_ajuste for p in puntuaciones.values()) / len(puntuaciones)
    assert nuevo.historial_corto
    assert media < nuevo.puntuacion < nuevo.sin_ajuste
    assert not puntuaciones["p0"].historial_corto


def test_con_20_proveedores_compara_dentro_de_la_categoria_y_con_menos_contra_todos() -> None:
    nube = {f"n{i}": _historia(0.8 + i * 0.005) for i in range(20)}
    soporte = {f"s{i}": _historia(0.1 + i * 0.005) for i in range(20)}
    categorias = dict.fromkeys(nube, "nube") | dict.fromkeys(soporte, "soporte")
    muchos = puntuar(nube | soporte, categorias, Pesos(), HOY)
    # El mejor de soporte es el mejor de su categoría aunque sea peor que todos los de nube.
    assert muchos["s19"].sin_ajuste == pytest.approx(100.0)
    pocos = {k: v for k, v in (nube | soporte).items() if int(k[1:]) < 10}
    menos = puntuar(pocos, categorias, Pesos(), HOY)
    assert menos["s9"].sin_ajuste < menos["n0"].sin_ajuste


def test_los_pesos_cambian_la_puntuacion() -> None:
    bueno_en_sla = [
        Mes(sumar_meses(HOY, -i), sla=100, resolucion=24, incidentes=3, entregas=80, satisfaccion=1.5)
        for i in range(12)
    ]
    bueno_en_lo_demas = [
        Mes(sumar_meses(HOY, -i), sla=95, resolucion=6, incidentes=0, entregas=100, satisfaccion=5)
        for i in range(12)
    ]
    desempeno = {"a": bueno_en_sla, "b": bueno_en_lo_demas}
    categorias = dict.fromkeys(desempeno, "nube")
    solo_sla = Pesos(sla=100, resolucion=0, incidentes=0, entregas=0, satisfaccion=0)
    assert puntuar(desempeno, categorias, solo_sla, HOY)["a"].sin_ajuste == 100
    assert puntuar(desempeno, categorias, Pesos(), HOY)["b"].sin_ajuste == 70


def test_validar_pesos() -> None:
    assert validar_pesos(Pesos().como_dict()) is None
    assert validar_pesos(Pesos(sla=25).como_dict()) == "Los pesos deben sumar 100 (suman 95)."
    assert (
        validar_pesos(Pesos(sla=-10, resolucion=60).como_dict())
        == "Los pesos no pueden ser negativos."
    )


def test_historial_de_12_meses() -> None:
    mejora = [_mes(sumar_meses(HOY, -i), 0.9 - i * 0.05) for i in range(24)]
    desempeno = {"mejora": mejora} | {f"p{i}": _historia(0.5, meses=24) for i in range(5)}
    categorias = dict.fromkeys(desempeno, "nube")
    serie = historial(desempeno, categorias, Pesos(), HOY)["mejora"]
    assert [fecha for fecha, _ in serie] == [sumar_meses(HOY, -i) for i in range(11, -1, -1)]
    assert serie[-1][1] > serie[0][1]


@given(
    st.lists(st.floats(min_value=0, max_value=1), min_size=1, max_size=15),
    st.integers(min_value=1, max_value=12),
)
def test_la_puntuacion_esta_entre_0_y_100(niveles: list[float], meses: int) -> None:
    desempeno = {f"p{i}": _historia(nivel, meses) for i, nivel in enumerate(niveles)}
    categorias = dict.fromkeys(desempeno, "nube")
    for p in puntuar(desempeno, categorias, Pesos(), HOY).values():
        assert 0 <= p.sin_ajuste <= 100
        assert 0 <= p.puntuacion <= 100


@given(
    st.floats(min_value=0, max_value=100),
    st.floats(min_value=0, max_value=100),
    st.integers(min_value=1, max_value=12),
)
def test_la_contraccion_acerca_a_la_media_sin_cruzarla(
    puntuacion: float, media: float, meses: int
) -> None:
    ajustada = contraer(puntuacion, media, meses)
    assert min(puntuacion, media) - 1e-9 <= ajustada <= max(puntuacion, media) + 1e-9


@given(st.lists(st.integers(min_value=0, max_value=25), min_size=4, max_size=4))
def test_pesos_no_negativos_que_suman_100_son_validos(cuatro: list[int]) -> None:
    pesos = dict(zip(KPIS, [*cuatro, 100 - sum(cuatro)], strict=True))
    assert validar_pesos(pesos) is None
```

(agregue `KPIS` al import de `inteligencia.dominio.puntuacion`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest services/inteligencia/tests/test_puntuacion.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'inteligencia.dominio.puntuacion'`.

- [ ] **Step 3: Implement**

Cree `services/inteligencia/src/inteligencia/dominio/puntuacion.py`:

```python
"""Puntuación de proveedores (0 a 100) a partir de su desempeño mensual.

1. Cada KPI se promedia en los últimos 12 meses con decaimiento exponencial (vida media 6 meses).
2. Se convierte en percentil (0 a 100, más es mejor; resolución e incidentes se invierten) frente a
   los proveedores de su categoría principal si esa categoría tiene al menos
   MIN_PROVEEDORES_CATEGORIA proveedores con desempeño; si tiene menos, frente a todos (con pocos
   proveedores, los percentiles quedan muy gruesos y la puntuación pierde orden).
3. Los percentiles se combinan con los pesos (que suman 100).
4. Contracción bayesiana hacia la media de la categoría: con pocos meses de historia, la puntuación
   se acerca a la media en vez de quedar en un extremo.
"""

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import date

from inteligencia.dominio.precios import meses_entre, sumar_meses

KPIS = ("sla", "resolucion", "incidentes", "entregas", "satisfaccion")
INVERSOS = frozenset({"resolucion", "incidentes"})  # menos es mejor
VENTANA_MESES = 12
VIDA_MEDIA_MESES = 6
K_CONTRACCION = 6
MIN_PROVEEDORES_CATEGORIA = 20
MESES_HISTORIAL_CORTO = 6
MESES_TENDENCIA = 3


@dataclass(frozen=True)
class Mes:
    periodo: date
    sla: float
    resolucion: float
    incidentes: float
    entregas: float
    satisfaccion: float


@dataclass(frozen=True)
class Pesos:
    sla: int = 30
    resolucion: int = 20
    incidentes: int = 20
    entregas: int = 15
    satisfaccion: int = 15

    def como_dict(self) -> dict[str, int]:
        return {campo.name: getattr(self, campo.name) for campo in fields(self)}


def validar_pesos(pesos: Mapping[str, int]) -> str | None:
    if any(valor < 0 for valor in pesos.values()):
        return "Los pesos no pueden ser negativos."
    total = sum(pesos.values())
    return None if total == 100 else f"Los pesos deben sumar 100 (suman {total})."


@dataclass(frozen=True)
class Puntuacion:
    puntuacion: float  # ajustada por la contracción; la que se muestra
    sin_ajuste: float
    meses: int  # meses con desempeño dentro de la ventana
    componentes: dict[str, float]  # percentil de cada KPI, más es mejor
    valores: dict[str, float]  # promedio ponderado de cada KPI

    @property
    def historial_corto(self) -> bool:
        return self.meses < MESES_HISTORIAL_CORTO


def promedio_ponderado(
    meses: Sequence[Mes], hasta: date
) -> tuple[dict[str, float], int] | None:
    sumas = dict.fromkeys(KPIS, 0.0)
    peso_total = 0.0
    contados = 0
    for mes in meses:
        antiguedad = meses_entre(mes.periodo, hasta)
        if 0 <= antiguedad < VENTANA_MESES:
            peso = 0.5 ** (antiguedad / VIDA_MEDIA_MESES)
            peso_total += peso
            contados += 1
            for kpi in KPIS:
                sumas[kpi] += peso * getattr(mes, kpi)
    if contados == 0:
        return None
    return {kpi: suma / peso_total for kpi, suma in sumas.items()}, contados


def percentil(valor: float, todos: Sequence[float]) -> float:
    """Rango percentil de 0 a 100; los empates comparten el promedio de sus posiciones."""
    if len(todos) <= 1:
        return 50.0
    menores = sum(1 for v in todos if v < valor)
    iguales = sum(1 for v in todos if v == valor)
    return 100 * (menores + (iguales - 1) / 2) / (len(todos) - 1)


def contraer(puntuacion: float, media: float, meses: int) -> float:
    return (meses * puntuacion + K_CONTRACCION * media) / (meses + K_CONTRACCION)


def puntuar(
    desempeno: Mapping[str, Sequence[Mes]],
    categorias: Mapping[str, str],
    pesos: Pesos,
    hasta: date,
) -> dict[str, Puntuacion]:
    resumen: dict[str, tuple[dict[str, float], int]] = {}
    for proveedor, meses in desempeno.items():
        promedio = promedio_ponderado(meses, hasta)
        if promedio is not None:
            resumen[proveedor] = promedio
    por_categoria: dict[str, list[str]] = defaultdict(list)
    for proveedor in resumen:
        por_categoria[categorias[proveedor]].append(proveedor)
    pesos_kpi = pesos.como_dict()
    componentes: dict[str, dict[str, float]] = {}
    crudas: dict[str, float] = {}
    for proveedor, (valores, _) in resumen.items():
        de_su_categoria = por_categoria[categorias[proveedor]]
        pares = (
            de_su_categoria
            if len(de_su_categoria) >= MIN_PROVEEDORES_CATEGORIA
            else list(resumen)
        )
        propios: dict[str, float] = {}
        for kpi in KPIS:
            valor = percentil(valores[kpi], [resumen[otro][0][kpi] for otro in pares])
            propios[kpi] = 100 - valor if kpi in INVERSOS else valor
        componentes[proveedor] = propios
        crudas[proveedor] = sum(pesos_kpi[kpi] * propios[kpi] for kpi in KPIS) / 100
    medias = {
        categoria: statistics.mean(crudas[p] for p in proveedores)
        for categoria, proveedores in por_categoria.items()
    }
    return {
        proveedor: Puntuacion(
            puntuacion=contraer(crudas[proveedor], medias[categorias[proveedor]], meses),
            sin_ajuste=crudas[proveedor],
            meses=meses,
            componentes=componentes[proveedor],
            valores=valores,
        )
        for proveedor, (valores, meses) in resumen.items()
    }


def historial(
    desempeno: Mapping[str, Sequence[Mes]],
    categorias: Mapping[str, str],
    pesos: Pesos,
    hasta: date,
    meses: int = 12,
) -> dict[str, list[tuple[date, float]]]:
    """La puntuación de cada proveedor al inicio de cada uno de los últimos `meses` meses."""
    serie: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for atras in range(meses - 1, -1, -1):
        fecha = sumar_meses(hasta, -atras)
        for proveedor, p in puntuar(desempeno, categorias, pesos, fecha).items():
            serie[proveedor].append((fecha, p.puntuacion))
    return dict(serie)
```

`test_historial_de_12_meses` espera fechas `sumar_meses(HOY, -i)`: como `HOY` es día 1, `sumar_meses(HOY, 0)` es `HOY`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest services/inteligencia/tests/test_puntuacion.py -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio.

- [ ] **Step 5: Commit**

```bash
git add services/inteligencia/src/inteligencia/dominio/puntuacion.py services/inteligencia/tests/test_puntuacion.py
git commit -m "feat(inteligencia): puntuación de proveedores con decaimiento, percentiles y contracción bayesiana" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Dominio: alertas y KPIs del Tablero

**Files:**
- Create: `services/inteligencia/src/inteligencia/dominio/contratos.py`
- Create: `services/inteligencia/src/inteligencia/dominio/alertas.py`
- Create: `services/inteligencia/src/inteligencia/dominio/tablero.py`
- Test: `services/inteligencia/tests/test_alertas.py`
- Test: `services/inteligencia/tests/test_tablero.py`

**Interfaces:**
- Consumes (Task 8): `Banda`, `cantidad_mensual`, `plazo_en_meses`, `meses_restantes`, `ahorro_potencial` y `sumar_meses`.
- Produces:
  - `dominio.contratos`:
    - `Linea(codigo, servicio, categoria, unidad, cantidad: Decimal, precio: Decimal)`; `servicio` es el nombre legible.
    - `ContratoInfo(id, folio, proveedor_id, proveedor, tipo, fecha_inicio, fecha_fin, moneda, lineas: tuple[Linea, ...])`, con `plazo_meses`, `vigente(fecha) -> bool` y `valor_mensual() -> Decimal` (en la moneda del contrato).
    - Todos los ids van como texto.
  - `dominio.alertas`:
    - `Alerta(id, tipo, severidad, titulo, explicacion, entidad_tipo, entidad_id, entidad_nombre, proveedor_id, proveedor_nombre, fecha, ahorro_potencial: Decimal | None = None, moneda: str | None = None)`;
    - `vencimiento(contrato, hoy)`, `sobreprecio(contrato, linea, banda, hoy)` y `riesgo(proveedor_id, nombre, actual, anterior, umbral, hoy)`, cada una `-> Alerta | None`;
    - `ordenar(alertas) -> list[Alerta]`;
    - `NOMBRES_UNIDAD`, `ORDEN_SEVERIDAD`, `CAIDA_RIESGO = 10.0`.
  - `dominio.tablero`:
    - `tipo_cambio_en(tipos, fecha) -> Decimal | None` y `a_mxn(monto, moneda, usd_mxn) -> Decimal`;
    - `Vencimiento(contrato, dias, monto_mensual)`, `Destacado(proveedor_id, nombre, puntuacion)` y `Tablero(...)`;
    - `calcular(contratos, tipos_cambio, puntuaciones, nombres, activos: int, alertas, hoy) -> Tablero`.

- [ ] **Step 1: Write the failing tests**

Cree `services/inteligencia/tests/test_alertas.py`:

```python
from datetime import date, timedelta
from decimal import Decimal

import pytest
from inteligencia.dominio.alertas import ordenar, riesgo, sobreprecio, vencimiento
from inteligencia.dominio.contratos import ContratoInfo, Linea
from inteligencia.dominio.precios import Banda

HOY = date(2026, 10, 10)
LINEA = Linea(
    codigo="SAAS-OFI-EMP",
    servicio="Suite de productividad",
    categoria="licencia_saas",
    unidad="usuario_mes",
    cantidad=Decimal("100"),
    precio=Decimal("25"),
)


def _contrato(fin: date, lineas: tuple[Linea, ...] = (LINEA,)) -> ContratoInfo:
    return ContratoInfo(
        id="c-1",
        folio="C-0001",
        proveedor_id="p-1",
        proveedor="Nube Azteca S.A. de C.V.",
        tipo="nuevo",
        fecha_inicio=date(2026, 1, 1),
        fecha_fin=fin,
        moneda="USD",
        lineas=lineas,
    )


@pytest.mark.parametrize(
    ("dias", "severidad", "titulo"),
    [
        (0, "alta", "Vence hoy: C-0001"),
        (1, "alta", "Vence mañana: C-0001"),
        (21, "alta", "Vence en 21 días: C-0001"),
        (45, "media", "Vence en 45 días: C-0001"),
        (80, "informativa", "Vence en 80 días: C-0001"),
    ],
)
def test_vencimiento_por_dias(dias: int, severidad: str, titulo: str) -> None:
    alerta = vencimiento(_contrato(HOY + timedelta(days=dias)), HOY)
    assert alerta is not None
    assert (alerta.tipo, alerta.severidad, alerta.titulo) == ("vencimiento", severidad, titulo)
    assert alerta.entidad_tipo == "contrato"
    fin = HOY + timedelta(days=dias)
    assert alerta.explicacion == (
        "El contrato con Nube Azteca S.A. de C.V. (Suite de productividad) termina el "
        f"{fin:%d/%m/%Y}."
    )


def test_sin_alerta_de_vencimiento_lejos_o_ya_terminado() -> None:
    assert vencimiento(_contrato(HOY + timedelta(days=91)), HOY) is None
    assert vencimiento(_contrato(HOY - timedelta(days=1)), HOY) is None


def test_sobreprecio_con_su_ahorro() -> None:
    contrato = _contrato(date(2026, 12, 31))
    alerta = sobreprecio(contrato, LINEA, Banda(18.0, 20.0, 22.0), HOY)
    assert alerta is not None
    # (25 − 20) × 100 al mes × 3 meses (octubre, noviembre y diciembre).
    assert (alerta.ahorro_potencial, alerta.moneda) == (Decimal("1500.00"), "USD")
    assert alerta.titulo == "Sobreprecio en C-0001: Suite de productividad"
    assert alerta.explicacion == (
        "Paga 25.00 USD por usuario al mes; el mercado paga hasta 22.00 (P75). Pagando el precio "
        "típico (20.00) ahorraría 1,500.00 USD en lo que resta del contrato."
    )
    assert sobreprecio(contrato, LINEA, Banda(18.0, 20.0, 25.0), HOY) is None


def test_riesgo_por_puntuacion_baja_o_en_caida() -> None:
    baja = riesgo("p-1", "Nube Azteca", 35.0, 38.0, 40, HOY)
    assert baja is not None
    assert (baja.severidad, baja.titulo) == ("alta", "Puntuación baja: Nube Azteca")
    assert baja.explicacion == "Su puntuación es 35 de 100, por debajo del umbral de 40."
    caida = riesgo("p-1", "Nube Azteca", 60.0, 75.0, 40, HOY)
    assert caida is not None
    assert (caida.severidad, caida.titulo) == ("media", "Puntuación en caída: Nube Azteca")
    assert caida.explicacion == "Bajó 15 puntos en 3 meses (de 75 a 60)."
    assert riesgo("p-1", "Nube Azteca", 60.0, 65.0, 40, HOY) is None
    assert riesgo("p-1", "Nube Azteca", 60.0, None, 40, HOY) is None


def test_ordenar_por_severidad_y_fecha() -> None:
    informativa = vencimiento(_contrato(HOY + timedelta(days=80)), HOY)
    alta = riesgo("p-2", "Datos del Norte", 20.0, None, 40, HOY)
    media = vencimiento(_contrato(HOY + timedelta(days=45)), HOY)
    assert informativa is not None and alta is not None and media is not None
    assert [a.severidad for a in ordenar([informativa, media, alta])] == [
        "alta",
        "media",
        "informativa",
    ]
```

Cree `services/inteligencia/tests/test_tablero.py`:

```python
from datetime import date
from decimal import Decimal

from inteligencia.dominio.alertas import Alerta
from inteligencia.dominio.contratos import ContratoInfo, Linea
from inteligencia.dominio.tablero import a_mxn, calcular, tipo_cambio_en

HOY = date(2026, 10, 10)
TIPOS_CAMBIO = {date(2026, 9, 1): Decimal("18.0000")}
USD = ContratoInfo(
    id="c-usd",
    folio="C-0001",
    proveedor_id="p-1",
    proveedor="Nube Azteca",
    tipo="nuevo",
    fecha_inicio=date(2025, 11, 1),
    fecha_fin=date(2026, 10, 31),
    moneda="USD",
    lineas=(
        Linea("SAAS-OFI-EMP", "Suite", "licencia_saas", "usuario_mes", Decimal("100"), Decimal("20")),
    ),
)
MXN = ContratoInfo(
    id="c-mxn",
    folio="C-0002",
    proveedor_id="p-2",
    proveedor="Datos del Norte",
    tipo="nuevo",
    fecha_inicio=date(2025, 1, 1),
    fecha_fin=date(2026, 12, 31),
    moneda="MXN",
    lineas=(
        Linea("SOP-ADM-SRV", "Administración", "soporte", "mes", Decimal("2"), Decimal("5000")),
        # Por consumo: 240 horas en los 24 meses del contrato, 10 al mes.
        Linea("SOP-APP-HR", "Soporte a aplicaciones", "soporte", "hora", Decimal("240"), Decimal("650")),
    ),
)


def _alerta(tipo: str, proveedor_id: str, ahorro: str | None = None, moneda: str | None = None) -> Alerta:
    return Alerta(
        id=f"{tipo}:{proveedor_id}",
        tipo=tipo,  # type: ignore[arg-type]
        severidad="media",
        titulo="t",
        explicacion="e",
        entidad_tipo="proveedor",
        entidad_id=proveedor_id,
        entidad_nombre="n",
        proveedor_id=proveedor_id,
        proveedor_nombre="n",
        fecha=HOY,
        ahorro_potencial=Decimal(ahorro) if ahorro else None,
        moneda=moneda,
    )


def test_tipo_de_cambio_y_conversion() -> None:
    assert tipo_cambio_en(TIPOS_CAMBIO, HOY) == Decimal("18.0000")
    assert tipo_cambio_en(TIPOS_CAMBIO, date(2020, 1, 1)) == Decimal("18.0000")  # el más viejo
    assert tipo_cambio_en({}, HOY) is None
    assert a_mxn(Decimal("10"), "USD", Decimal("18")) == Decimal("180")
    assert a_mxn(Decimal("10"), "MXN", None) == Decimal("10")
    assert a_mxn(Decimal("10"), "USD", None) == Decimal("0")


def test_gasto_anual_por_categoria_y_variacion() -> None:
    tablero = calcular([USD, MXN], TIPOS_CAMBIO, {}, {}, 2, [], HOY)
    # USD: 100 × 20 × 18 = 36,000 al mes. MXN: 2 × 5,000 + 10 × 650 = 16,500 al mes.
    assert tablero.gasto_anual == Decimal("630000.00")
    assert tablero.gasto_por_categoria == {
        "licencia_saas": Decimal("432000.00"),
        "soporte": Decimal("198000.00"),
    }
    # Hace un año solo estaba vigente el contrato en MXN (198,000 al año).
    assert tablero.variacion_pct is not None
    assert round(tablero.variacion_pct, 1) == 218.2


def test_serie_de_24_meses() -> None:
    serie = calcular([USD, MXN], TIPOS_CAMBIO, {}, {}, 2, [], HOY).gasto_por_mes
    assert len(serie) == 24
    assert serie[-1] == (date(2026, 10, 1), Decimal("52500.00"))
    assert serie[0] == (date(2024, 11, 1), Decimal("0.00"))
    assert dict(serie)[date(2025, 10, 1)] == Decimal("16500.00")


def test_proximos_vencimientos() -> None:
    tablero = calcular([USD, MXN], TIPOS_CAMBIO, {}, {}, 2, [], HOY)
    assert tablero.por_vencer == 2
    [primero, segundo] = tablero.proximos_vencimientos
    assert (primero.contrato.folio, primero.dias, primero.monto_mensual) == (
        "C-0001",
        21,
        Decimal("36000.00"),
    )
    assert (segundo.contrato.folio, segundo.dias) == ("C-0002", 82)


def test_ahorro_en_riesgo_y_destacados() -> None:
    alertas = [
        _alerta("sobreprecio", "p-1", "100.00", "USD"),
        _alerta("sobreprecio", "p-2", "500.00", "MXN"),
        _alerta("riesgo", "p-3"),
    ]
    puntuaciones = {"p-1": 90.0, "p-2": 50.0, "p-3": 10.0}
    nombres = {"p-1": "Nube Azteca", "p-2": "Datos del Norte", "p-3": "Red Maya"}
    tablero = calcular([USD, MXN], TIPOS_CAMBIO, puntuaciones, nombres, 3, alertas, HOY)
    assert tablero.ahorro_potencial == Decimal("2300.00")
    assert (tablero.en_riesgo, tablero.total_proveedores) == (1, 3)
    assert [d.nombre for d in tablero.mejores] == ["Nube Azteca", "Datos del Norte", "Red Maya"]
    assert [d.nombre for d in tablero.peores] == ["Red Maya", "Datos del Norte", "Nube Azteca"]
    assert tablero.distribucion == [
        ("0-19", 1),
        ("20-39", 0),
        ("40-59", 1),
        ("60-79", 0),
        ("80-100", 1),
    ]
    assert len(tablero.alertas_principales) == 3


def test_sin_tipo_de_cambio_los_montos_en_usd_no_cuentan() -> None:
    assert calcular([USD, MXN], {}, {}, {}, 2, [], HOY).gasto_anual == Decimal("198000.00")
```

Comprobación de `test_gasto_anual_por_categoria_y_variacion`: el gasto actual es 630,000 y el de hace un año es 198,000, así que la variación es (630,000 / 198,000 − 1) × 100 = 218.18 %.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest services/inteligencia/tests/test_alertas.py services/inteligencia/tests/test_tablero.py -q`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Cree `services/inteligencia/src/inteligencia/dominio/contratos.py`:

```python
"""Contratos tal como los usan las alertas y el Tablero (ids como texto)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from inteligencia.dominio.precios import cantidad_mensual, plazo_en_meses


@dataclass(frozen=True)
class Linea:
    codigo: str
    servicio: str  # nombre legible
    categoria: str
    unidad: str
    cantidad: Decimal
    precio: Decimal


@dataclass(frozen=True)
class ContratoInfo:
    id: str
    folio: str
    proveedor_id: str
    proveedor: str  # nombre legible
    tipo: str
    fecha_inicio: date
    fecha_fin: date
    moneda: str
    lineas: tuple[Linea, ...]

    @property
    def plazo_meses(self) -> int:
        return plazo_en_meses(self.fecha_inicio, self.fecha_fin)

    def vigente(self, fecha: date) -> bool:
        return self.fecha_inicio <= fecha <= self.fecha_fin

    def valor_mensual(self) -> Decimal:
        """Lo que cuesta al mes, en la moneda del contrato."""
        return sum(
            (
                cantidad_mensual(linea.cantidad, linea.unidad, self.plazo_meses) * linea.precio
                for linea in self.lineas
            ),
            Decimal(0),
        )
```

Cree `services/inteligencia/src/inteligencia/dominio/alertas.py`:

```python
"""Alertas: contratos por vencer, precios sobre el mercado y proveedores en riesgo.

Se calculan al consultar; no tienen estado ("atendida") en este sub-proyecto.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from inteligencia.dominio.contratos import ContratoInfo, Linea
from inteligencia.dominio.precios import (
    Banda,
    ahorro_potencial,
    cantidad_mensual,
    meses_restantes,
)

Severidad = Literal["alta", "media", "informativa"]
TipoAlerta = Literal["vencimiento", "sobreprecio", "riesgo"]
ORDEN_SEVERIDAD: dict[str, int] = {"alta": 0, "media": 1, "informativa": 2}
DIAS_VENCIMIENTO: tuple[tuple[int, Severidad], ...] = (
    (30, "alta"),
    (60, "media"),
    (90, "informativa"),
)
CAIDA_RIESGO = 10.0  # puntos en 3 meses
NOMBRES_UNIDAD = {
    "usuario_mes": "usuario al mes",
    "vcpu_mes": "vCPU al mes",
    "gb_mes": "GB al mes",
    "mes": "mes",
    "hora": "hora",
    "ticket": "ticket",
}


@dataclass(frozen=True)
class Alerta:
    id: str
    tipo: TipoAlerta
    severidad: Severidad
    titulo: str
    explicacion: str
    entidad_tipo: Literal["contrato", "proveedor"]
    entidad_id: str
    entidad_nombre: str
    proveedor_id: str
    proveedor_nombre: str
    fecha: date
    ahorro_potencial: Decimal | None = None
    moneda: str | None = None


def _dinero(valor: Decimal | float) -> str:
    return f"{valor:,.2f}"


def vencimiento(contrato: ContratoInfo, hoy: date) -> Alerta | None:
    if not contrato.vigente(hoy):
        return None
    dias = (contrato.fecha_fin - hoy).days
    severidad = next((s for limite, s in DIAS_VENCIMIENTO if dias <= limite), None)
    if severidad is None:
        return None
    cuando = "hoy" if dias == 0 else "mañana" if dias == 1 else f"en {dias} días"
    servicios = ", ".join(linea.servicio for linea in contrato.lineas)
    return Alerta(
        id=f"vencimiento:{contrato.id}",
        tipo="vencimiento",
        severidad=severidad,
        titulo=f"Vence {cuando}: {contrato.folio}",
        explicacion=(
            f"El contrato con {contrato.proveedor} ({servicios}) termina el "
            f"{contrato.fecha_fin:%d/%m/%Y}."
        ),
        entidad_tipo="contrato",
        entidad_id=contrato.id,
        entidad_nombre=contrato.folio,
        proveedor_id=contrato.proveedor_id,
        proveedor_nombre=contrato.proveedor,
        fecha=contrato.fecha_fin,
    )


def sobreprecio(contrato: ContratoInfo, linea: Linea, banda: Banda, hoy: date) -> Alerta | None:
    if float(linea.precio) <= banda.p75:
        return None
    p50 = Decimal(str(round(banda.p50, 4)))
    ahorro = ahorro_potencial(
        linea.precio,
        p50,
        cantidad_mensual(linea.cantidad, linea.unidad, contrato.plazo_meses),
        meses_restantes(hoy, contrato.fecha_fin),
    )
    unidad = NOMBRES_UNIDAD.get(linea.unidad, linea.unidad)
    return Alerta(
        id=f"sobreprecio:{contrato.id}:{linea.codigo}",
        tipo="sobreprecio",
        severidad="media",
        titulo=f"Sobreprecio en {contrato.folio}: {linea.servicio}",
        explicacion=(
            f"Paga {_dinero(linea.precio)} {contrato.moneda} por {unidad}; el mercado paga hasta "
            f"{_dinero(banda.p75)} (P75). Pagando el precio típico ({_dinero(p50)}) ahorraría "
            f"{_dinero(ahorro)} {contrato.moneda} en lo que resta del contrato."
        ),
        entidad_tipo="contrato",
        entidad_id=contrato.id,
        entidad_nombre=contrato.folio,
        proveedor_id=contrato.proveedor_id,
        proveedor_nombre=contrato.proveedor,
        fecha=hoy,
        ahorro_potencial=ahorro,
        moneda=contrato.moneda,
    )


def riesgo(
    proveedor_id: str,
    nombre: str,
    actual: float,
    anterior: float | None,
    umbral: int,
    hoy: date,
) -> Alerta | None:
    if actual < umbral:
        severidad: Severidad = "alta"
        titulo = f"Puntuación baja: {nombre}"
        explicacion = f"Su puntuación es {actual:.0f} de 100, por debajo del umbral de {umbral}."
    elif anterior is not None and anterior - actual > CAIDA_RIESGO:
        severidad = "media"
        titulo = f"Puntuación en caída: {nombre}"
        explicacion = (
            f"Bajó {anterior - actual:.0f} puntos en 3 meses (de {anterior:.0f} a {actual:.0f})."
        )
    else:
        return None
    return Alerta(
        id=f"riesgo:{proveedor_id}",
        tipo="riesgo",
        severidad=severidad,
        titulo=titulo,
        explicacion=explicacion,
        entidad_tipo="proveedor",
        entidad_id=proveedor_id,
        entidad_nombre=nombre,
        proveedor_id=proveedor_id,
        proveedor_nombre=nombre,
        fecha=hoy,
    )


def ordenar(alertas: Iterable[Alerta]) -> list[Alerta]:
    return sorted(alertas, key=lambda a: (ORDEN_SEVERIDAD[a.severidad], a.fecha, a.id))
```

Cree `services/inteligencia/src/inteligencia/dominio/tablero.py`:

```python
"""KPIs del Tablero, en MXN: al último tipo de cambio, y al de cada mes en la serie mensual."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from inteligencia.dominio.alertas import Alerta, ordenar
from inteligencia.dominio.contratos import ContratoInfo
from inteligencia.dominio.precios import cantidad_mensual, sumar_meses

MESES_SERIE = 24
DIAS_POR_VENCER = 90
MAX_VENCIMIENTOS = 10
CUANTOS_DESTACADOS = 5
CUANTAS_ALERTAS = 5
RANGOS_PUNTUACION = (
    ("0-19", 0, 20),
    ("20-39", 20, 40),
    ("40-59", 40, 60),
    ("60-79", 60, 80),
    ("80-100", 80, 101),
)
CENTAVOS = Decimal("0.01")


@dataclass(frozen=True)
class Vencimiento:
    contrato: ContratoInfo
    dias: int
    monto_mensual: Decimal  # MXN


@dataclass(frozen=True)
class Destacado:
    proveedor_id: str
    nombre: str
    puntuacion: float


@dataclass(frozen=True)
class Tablero:
    gasto_anual: Decimal
    variacion_pct: float | None
    por_vencer: int
    en_riesgo: int
    total_proveedores: int
    ahorro_potencial: Decimal
    gasto_por_categoria: dict[str, Decimal]
    gasto_por_mes: list[tuple[date, Decimal]]
    proximos_vencimientos: list[Vencimiento]
    alertas_principales: list[Alerta]
    mejores: list[Destacado]
    peores: list[Destacado]
    distribucion: list[tuple[str, int]]


def tipo_cambio_en(tipos: Mapping[date, Decimal], fecha: date) -> Decimal | None:
    """El tipo de cambio vigente en `fecha` (o el más viejo si `fecha` es anterior a todos)."""
    if not tipos:
        return None
    anteriores = [periodo for periodo in tipos if periodo <= fecha]
    return tipos[max(anteriores)] if anteriores else tipos[min(tipos)]


def a_mxn(monto: Decimal, moneda: str, usd_mxn: Decimal | None) -> Decimal:
    if moneda == "MXN":
        return monto
    # ponytail: sin tipo de cambio registrado, los montos en USD no se pueden convertir y no
    # cuentan; con el ERP de verdad siempre hay al menos un periodo.
    return monto * usd_mxn if usd_mxn is not None else Decimal(0)


def _gasto_anual(contratos: Sequence[ContratoInfo], fecha: date, usd_mxn: Decimal | None) -> Decimal:
    mensual = sum(
        (a_mxn(c.valor_mensual(), c.moneda, usd_mxn) for c in contratos if c.vigente(fecha)),
        Decimal(0),
    )
    return mensual * 12


def _vigente_en_mes(contrato: ContratoInfo, mes: date) -> bool:
    fin_de_mes = sumar_meses(mes, 1) - timedelta(days=1)
    return contrato.fecha_inicio <= fin_de_mes and contrato.fecha_fin >= mes


def calcular(
    contratos: Sequence[ContratoInfo],
    tipos_cambio: Mapping[date, Decimal],
    puntuaciones: Mapping[str, float],
    nombres: Mapping[str, str],
    activos: int,
    alertas: Sequence[Alerta],
    hoy: date,
) -> Tablero:
    ultimo = tipo_cambio_en(tipos_cambio, hoy)
    actual = _gasto_anual(contratos, hoy, ultimo)
    anterior = _gasto_anual(contratos, date(hoy.year - 1, hoy.month, min(hoy.day, 28)), ultimo)
    variacion = float((actual / anterior - 1) * 100) if anterior > 0 else None

    vigentes = [c for c in contratos if c.vigente(hoy)]
    por_categoria: dict[str, Decimal] = defaultdict(Decimal)
    for contrato in vigentes:
        for linea in contrato.lineas:
            mensual = cantidad_mensual(linea.cantidad, linea.unidad, contrato.plazo_meses)
            por_categoria[linea.categoria] += a_mxn(mensual * linea.precio, contrato.moneda, ultimo)
    serie = []
    for atras in range(MESES_SERIE - 1, -1, -1):
        mes = sumar_meses(hoy, -atras)
        cambio = tipo_cambio_en(tipos_cambio, mes)
        total = sum(
            (
                a_mxn(c.valor_mensual(), c.moneda, cambio)
                for c in contratos
                if _vigente_en_mes(c, mes)
            ),
            Decimal(0),
        )
        serie.append((mes, total.quantize(CENTAVOS)))

    proximos = sorted(
        (
            Vencimiento(
                c,
                (c.fecha_fin - hoy).days,
                a_mxn(c.valor_mensual(), c.moneda, ultimo).quantize(CENTAVOS),
            )
            for c in vigentes
            if (c.fecha_fin - hoy).days <= DIAS_POR_VENCER
        ),
        key=lambda v: (v.dias, v.contrato.folio),
    )
    ahorro = sum(
        (
            a_mxn(a.ahorro_potencial, a.moneda or "MXN", ultimo)
            for a in alertas
            if a.tipo == "sobreprecio" and a.ahorro_potencial is not None
        ),
        Decimal(0),
    )
    ranking = sorted(puntuaciones.items(), key=lambda par: (-par[1], nombres.get(par[0], par[0])))
    destacados = [Destacado(pid, nombres.get(pid, pid), valor) for pid, valor in ranking]
    return Tablero(
        gasto_anual=actual.quantize(CENTAVOS),
        variacion_pct=variacion,
        por_vencer=len(proximos),
        en_riesgo=len({a.proveedor_id for a in alertas if a.tipo == "riesgo"}),
        total_proveedores=activos,
        ahorro_potencial=ahorro.quantize(CENTAVOS),
        gasto_por_categoria={
            categoria: (mensual * 12).quantize(CENTAVOS)
            for categoria, mensual in sorted(por_categoria.items())
        },
        gasto_por_mes=serie,
        proximos_vencimientos=proximos[:MAX_VENCIMIENTOS],
        alertas_principales=ordenar(alertas)[:CUANTAS_ALERTAS],
        mejores=destacados[:CUANTOS_DESTACADOS],
        peores=destacados[::-1][:CUANTOS_DESTACADOS],
        distribucion=[
            (rango, sum(1 for _, valor in ranking if bajo <= valor < alto))
            for rango, bajo, alto in RANGOS_PUNTUACION
        ],
    )
```

Comprobación de la serie en `test_serie_de_24_meses`:
- en octubre de 2026 están vigentes los dos contratos: 36,000 + 16,500 = 52,500;
- en noviembre de 2024 ninguno;
- en octubre de 2025 solo el de MXN (16,500).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest services/inteligencia/tests/test_alertas.py services/inteligencia/tests/test_tablero.py -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio.

- [ ] **Step 5: Commit**

```bash
git add services/inteligencia/src/inteligencia/dominio services/inteligencia/tests/test_alertas.py services/inteligencia/tests/test_tablero.py
git commit -m "feat(inteligencia): alertas de vencimiento, sobreprecio y riesgo, y KPIs del Tablero" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Modelo de precios, registro de entrenamientos y reentrenamiento

**Files:**
- Create:
  - `services/inteligencia/src/inteligencia/modelo.py` (regresores, validación temporal y promoción)
  - `services/inteligencia/src/inteligencia/precio_justo.py` (modelo si conoce el servicio; si no, línea base)
  - `services/inteligencia/src/inteligencia/consultas.py` (lectura de la copia local; la Task 12 lo amplía)
  - `services/inteligencia/src/inteligencia/entrenamiento.py` (`Entrenador`)
  - `services/inteligencia/tests/test_modelo.py`, `services/inteligencia/tests/test_entrenamiento.py`
- Modify:
  - `services/inteligencia/tests/conftest.py` (datos del generador como observaciones y como eventos)
  - `services/inteligencia/src/inteligencia/main.py` (el entrenador y su bucle automático)

**Interfaces:**
- Consumes:
  - `Observacion`, `Banda`, `Referencia`, `linea_base`, `meses_entre`, `sumar_meses` y `plazo_en_meses` (Task 8);
  - `eventos.aplicar` (Task 7);
  - los modelos `Contrato`, `LineaContrato`, `Proveedor`, `Configuracion`, `ModeloBenchmark` y `Outbox` (Task 6);
  - `comun.outbox.registrar_evento`.
- Produces:
  - `inteligencia.modelo`:
    - constantes `CUANTILES`, `MESES_VALIDACION = 6`, `MIN_OBSERVACIONES_ENTRENAMIENTO = 50` y `ORIGEN`;
    - `DatosInsuficientes(ValueError)`;
    - `Consulta(servicio, categoria, moneda, cantidad: float, plazo_meses: int, fecha: date, tamano: str | None = None, tipo: str = "nuevo")`, frozen;
    - `consulta_de(observacion) -> Consulta`;
    - `ModeloPrecios(version, tasa_inflacion, categorias, regresores)`, con `conoce(servicio) -> bool` y `predecir(consultas) -> list[Banda]`;
    - `ajustar_modelo(observaciones, tasa_inflacion, version) -> ModeloPrecios`;
    - `Resultado(modelo, observaciones, datos_hasta, mape, mape_linea_base, cobertura, cobertura_linea_base, pinball)`, con `promovido -> bool` (las métricas son de la validación temporal; `cobertura` es la del modelo);
    - `entrenar(observaciones, tasa_inflacion, version) -> Resultado`;
    - `guardar_modelo(modelo, ruta)` y `cargar_modelo(ruta) -> ModeloPrecios`.
  - `inteligencia.precio_justo.referencias(consultas, por_categoria: Mapping[str, Sequence[Observacion]], modelo: ModeloPrecios | None, tasa_inflacion: float) -> list[Referencia | None]`.
  - `inteligencia.consultas`:
    - `observaciones(sesion) -> list[Observacion]`;
    - `configuracion(sesion) -> modelos.Configuracion`;
    - `modelo_activo(sesion) -> ModeloBenchmark | None` (el último promovido).
  - `inteligencia.entrenamiento`:
    - constantes `ACTOR_AUTOMATICO`, `MIN_LINEAS_NUEVAS = 50`, `ESPERA_TRAS_ULTIMA_S = 30` e `INTERVALO_REVISION_S = 60`;
    - `Entrenador(fabrica, directorio: Path, ahora: Callable[[], datetime] | None = None)`, con:
      - `entrenando: bool`;
      - `iniciar(origen: str, actor: dict[str, str | None]) -> bool` (`False` si ya hay uno en curso);
      - `esperar()`;
      - `revisar_automatico() -> bool`;
      - `ejecutar_periodicamente(intervalo)`.
  - `app.state.entrenador`.
  - Evento `modelo.entrenado`: `{version, mape, mape_linea_base, cobertura, promovido, origen, actor}`.
  - En las pruebas (`conftest.py`):
    - las funciones `id_de(clave) -> str`, `observaciones(datos) -> list[Observacion]` y `sobres(datos) -> list[dict]`;
    - el fixture de sesión `generadas` (las observaciones de `generar(42, n_proveedores=30)`);
    - el fixture `cargar`, una función `async (datos: DatosSinteticos) -> None` que aplica todos sus eventos a la base de la prueba.

- [ ] **Step 1: Test helpers with generated data**

Los módulos de prueba no se pueden importar entre sí (pytest corre con `--import-mode=importlib`), así que los ayudantes van en `services/inteligencia/tests/conftest.py`. Agregue a sus imports:

```python
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from generador.modelo import DatosSinteticos, generar
from inteligencia.dominio.precios import Observacion, plazo_en_meses
from inteligencia.eventos import aplicar
```

y al final del archivo:

```python
# Datos del generador como observaciones (para el dominio) y como eventos (para la copia local).
ESPACIO = uuid.UUID("0b8f4c1e-7c55-4c5f-9a43-2f6f0a1d3b10")
Cargar = Callable[[DatosSinteticos], Awaitable[None]]


def id_de(clave: str) -> str:
    """Un id estable por RFC, código o folio: el mismo dato da el mismo id en cada prueba."""
    return str(uuid.uuid5(ESPACIO, clave))


def observaciones(datos: DatosSinteticos) -> list[Observacion]:
    servicios = {s.codigo: s for s in datos.servicios}
    tamanos = {p.rfc: p.tamano for p in datos.proveedores}
    resultado = []
    for fila in datos.contratos:
        servicio = servicios[fila["codigo_servicio"]]
        inicio = date.fromisoformat(fila["fecha_inicio"])
        fin = date.fromisoformat(fila["fecha_fin"])
        resultado.append(
            Observacion(
                servicio=servicio.codigo,
                categoria=servicio.categoria,
                moneda=servicio.moneda,
                fecha=inicio,
                cantidad=float(fila["cantidad"]),
                precio=float(fila["precio_unitario"]),
                plazo_meses=plazo_en_meses(inicio, fin),
                tamano=tamanos[fila["rfc_proveedor"]],
                tipo=fila["tipo"],
            )
        )
    return resultado


def sobres(datos: DatosSinteticos) -> list[dict[str, Any]]:
    """Los eventos que publicaría proveedores al importar esos datos, en el orden de carga."""
    eventos: list[tuple[str, dict[str, Any]]] = []
    for s in datos.servicios:
        eventos.append(
            (
                "servicio.actualizado",
                {
                    "id": id_de(s.codigo),
                    "codigo": s.codigo,
                    "nombre": s.nombre,
                    "categoria": s.categoria,
                    "unidad": s.unidad,
                    "moneda": s.moneda,
                    "activo": True,
                },
            )
        )
    for p in datos.proveedores:
        eventos.append(
            (
                "proveedor.actualizado",
                {
                    "id": id_de(p.rfc),
                    "rfc": p.rfc,
                    "nombre": p.nombre,
                    "tamano": p.tamano,
                    "categorias": list(p.categorias),
                    "activo": p.activo,
                },
            )
        )
    eventos += [("tipo_cambio.registrado", dict(fila)) for fila in datos.tipo_cambio]
    servicios = {s.codigo: s for s in datos.servicios}
    por_folio: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fila in datos.contratos:
        por_folio[fila["folio"]].append(fila)
    for folio, lineas in por_folio.items():
        cabecera = lineas[0]
        eventos.append(
            (
                "contrato.registrado",
                {
                    "id": id_de(folio),
                    "proveedor_id": id_de(cabecera["rfc_proveedor"]),
                    "folio": folio,
                    "tipo": cabecera["tipo"],
                    "fecha_inicio": cabecera["fecha_inicio"],
                    "fecha_fin": cabecera["fecha_fin"],
                    "moneda": cabecera["moneda"],
                    "lineas": [
                        {
                            "codigo_servicio": linea["codigo_servicio"],
                            "categoria": servicios[linea["codigo_servicio"]].categoria,
                            "unidad": servicios[linea["codigo_servicio"]].unidad,
                            "cantidad": linea["cantidad"],
                            "precio_unitario": linea["precio_unitario"],
                        }
                        for linea in lineas
                    ],
                },
            )
        )
    for fila in datos.desempeno:
        eventos.append(
            (
                "desempeno.registrado",
                {"proveedor_id": id_de(fila["rfc_proveedor"])}
                | {k: v for k, v in fila.items() if k != "rfc_proveedor"},
            )
        )
    return [
        {"event_id": str(uuid.uuid4()), "type": tipo, "payload": payload}
        for tipo, payload in eventos
    ]


@pytest.fixture(scope="session")
def generadas() -> list[Observacion]:
    """Las líneas de contrato de 30 proveedores generados, como precios observados."""
    return observaciones(generar(42, n_proveedores=30))


@pytest.fixture
def cargar(fabrica: async_sessionmaker[AsyncSession]) -> Cargar:
    """Aplica todos los eventos de los datos en una sola transacción (rápido para las pruebas)."""

    async def _cargar(datos: DatosSinteticos) -> None:
        async with fabrica() as sesion, sesion.begin():
            for sobre in sobres(datos):
                await aplicar(sesion, sobre)

    return _cargar
```

- [ ] **Step 2: Write the failing model tests**

Cree `services/inteligencia/tests/test_modelo.py`:

```python
from collections import defaultdict
from pathlib import Path

import pytest
from inteligencia.dominio.precios import Observacion
from inteligencia.modelo import (
    Consulta,
    DatosInsuficientes,
    ajustar_modelo,
    cargar_modelo,
    consulta_de,
    entrenar,
    guardar_modelo,
)
from inteligencia.precio_justo import referencias

INFLACION = 0.045


def _por_categoria(datos: list[Observacion]) -> dict[str, list[Observacion]]:
    grupos: dict[str, list[Observacion]] = defaultdict(list)
    for o in datos:
        grupos[o.categoria].append(o)
    return grupos


def test_entrena_valida_y_solo_promueve_si_mejora_la_linea_base(
    generadas: list[Observacion],
) -> None:
    resultado = entrenar(generadas, INFLACION, version=1)
    assert resultado.mape < 0.15
    assert resultado.mape_linea_base < 0.15
    assert 0.3 <= resultado.cobertura <= 0.7
    assert 0.3 <= resultado.cobertura_linea_base <= 0.7
    assert resultado.pinball > 0
    assert resultado.promovido == (resultado.mape < resultado.mape_linea_base)
    assert resultado.observaciones == len(generadas)
    assert resultado.datos_hasta == max(o.fecha for o in generadas)
    if resultado.modelo is not None:
        assert resultado.modelo.version == 1


def test_las_predicciones_estan_ordenadas_y_son_positivas(generadas: list[Observacion]) -> None:
    modelo = ajustar_modelo(generadas, INFLACION, version=3)
    bandas = modelo.predecir([consulta_de(o) for o in generadas[:50]])
    assert len(bandas) == 50
    assert all(0 < b.p25 <= b.p50 <= b.p75 for b in bandas)
    assert modelo.predecir([]) == []


def test_un_servicio_que_el_modelo_no_conoce_usa_la_linea_base(
    generadas: list[Observacion],
) -> None:
    servicio = generadas[0].servicio
    modelo = ajustar_modelo([o for o in generadas if o.servicio != servicio], INFLACION, 2)
    fecha = max(o.fecha for o in generadas)
    desconocida = Consulta(
        servicio, generadas[0].categoria, generadas[0].moneda, 100.0, 12, fecha
    )
    conocida_obs = next(o for o in generadas if o.servicio != servicio)
    conocida = Consulta(
        conocida_obs.servicio, conocida_obs.categoria, conocida_obs.moneda, 100.0, 12, fecha
    )
    [primera, segunda] = referencias(
        [desconocida, conocida], _por_categoria(generadas), modelo, INFLACION
    )
    assert primera is not None and primera.metodo == "linea_base"
    assert segunda is not None and (segunda.metodo, segunda.version) == ("modelo", 2)


def test_sin_modelo_usa_la_linea_base(generadas: list[Observacion]) -> None:
    o = generadas[0]
    [referencia] = referencias(
        [Consulta(o.servicio, o.categoria, o.moneda, 100.0, 12, o.fecha)],
        _por_categoria(generadas),
        None,
        INFLACION,
    )
    assert referencia is not None and referencia.metodo == "linea_base"


def test_sin_datos_suficientes_no_entrena(generadas: list[Observacion]) -> None:
    with pytest.raises(DatosInsuficientes):
        entrenar(generadas[:10], INFLACION, version=1)


def test_guardar_y_cargar(generadas: list[Observacion], tmp_path: Path) -> None:
    modelo = ajustar_modelo(generadas, INFLACION, version=5)
    ruta = tmp_path / "modelo-v5.joblib"
    guardar_modelo(modelo, ruta)
    cargado = cargar_modelo(ruta)
    consulta = consulta_de(generadas[0])
    assert cargado.version == 5
    assert cargado.predecir([consulta]) == modelo.predecir([consulta])
```

- [ ] **Step 3: Run the model tests to verify they fail**

Run: `uv run pytest services/inteligencia/tests/test_modelo.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'inteligencia.modelo'`.

- [ ] **Step 4: Implement the model and the fair-price rule**

Cree `services/inteligencia/src/inteligencia/modelo.py`:

```python
"""Modelo de precio justo: tres regresores por cuantiles (P25, P50 y P75) sobre el logaritmo del
precio deflactado.

Antes de entrenar, cada precio se lleva a pesos de una fecha fija (ORIGEN) con la tasa de inflación
configurada; al predecir, se lleva de vuelta a la fecha de la consulta. Un árbol no extrapola una
tendencia a fechas que no vio, por eso el modelo no usa los meses transcurridos como variable.
"""

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import HistGradientBoostingRegressor

from inteligencia.dominio.precios import (
    Banda,
    Observacion,
    Referencia,
    linea_base,
    meses_entre,
    sumar_meses,
)

CUANTILES = (0.25, 0.5, 0.75)
MESES_VALIDACION = 6
MIN_OBSERVACIONES_ENTRENAMIENTO = 50
ORIGEN = date(2000, 1, 1)
CATEGORICAS = ("servicio", "categoria", "moneda", "tamano", "tipo")
MASCARA_CATEGORICAS = [True] * len(CATEGORICAS) + [False, False]  # + log(cantidad) y plazo


class DatosInsuficientes(ValueError):
    """No hay suficientes contratos para entrenar y validar."""


@dataclass(frozen=True)
class Consulta:
    servicio: str
    categoria: str
    moneda: str
    cantidad: float
    plazo_meses: int
    fecha: date
    tamano: str | None = None
    tipo: str = "nuevo"


def consulta_de(o: Observacion) -> Consulta:
    return Consulta(
        o.servicio, o.categoria, o.moneda, o.cantidad, o.plazo_meses, o.fecha, o.tamano, o.tipo
    )


def _deflactor(fecha: date, tasa: float) -> float:
    return float((1 + tasa) ** (meses_entre(ORIGEN, fecha) / 12))


def _codigo(valor: str | None, conocidos: list[str]) -> float:
    """El índice del valor entre los conocidos; NaN si el modelo no lo vio (HGB lo admite)."""
    return float(conocidos.index(valor)) if valor in conocidos else math.nan


def _matriz(consultas: Sequence[Consulta], categorias: dict[str, list[str]]) -> NDArray[np.float64]:
    return np.array(
        [
            [_codigo(getattr(c, nombre), categorias[nombre]) for nombre in CATEGORICAS]
            + [math.log(c.cantidad), float(c.plazo_meses)]
            for c in consultas
        ],
        dtype=np.float64,
    )


@dataclass
class ModeloPrecios:
    version: int
    tasa_inflacion: float
    categorias: dict[str, list[str]]
    regresores: list[HistGradientBoostingRegressor]

    def conoce(self, servicio: str) -> bool:
        return servicio in self.categorias["servicio"]

    def predecir(self, consultas: Sequence[Consulta]) -> list[Banda]:
        if not consultas:
            return []
        x = _matriz(consultas, self.categorias)
        logaritmos = np.sort(np.vstack([r.predict(x) for r in self.regresores]), axis=0)
        factores = np.array([_deflactor(c.fecha, self.tasa_inflacion) for c in consultas])
        precios = np.exp(logaritmos) * factores
        return [Banda(float(a), float(b), float(c)) for a, b, c in precios.T]


def _categorias(observaciones: Sequence[Observacion]) -> dict[str, list[str]]:
    return {
        nombre: sorted({str(v) for o in observaciones if (v := getattr(o, nombre)) is not None})
        for nombre in CATEGORICAS
    }


def ajustar_modelo(
    observaciones: Sequence[Observacion], tasa_inflacion: float, version: int
) -> ModeloPrecios:
    categorias = _categorias(observaciones)
    x = _matriz([consulta_de(o) for o in observaciones], categorias)
    y = np.array(
        [math.log(o.precio / _deflactor(o.fecha, tasa_inflacion)) for o in observaciones]
    )
    regresores = []
    for cuantil in CUANTILES:
        regresor = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=cuantil,
            categorical_features=MASCARA_CATEGORICAS,
            random_state=0,
        )
        regresor.fit(x, y)
        regresores.append(regresor)
    return ModeloPrecios(version, tasa_inflacion, categorias, regresores)


@dataclass(frozen=True)
class Resultado:
    modelo: ModeloPrecios | None  # solo si se promovió; reentrenado con todos los datos
    observaciones: int
    datos_hasta: date
    mape: float
    mape_linea_base: float
    cobertura: float  # del modelo
    cobertura_linea_base: float
    pinball: float

    @property
    def promovido(self) -> bool:
        return self.modelo is not None


def _pinball(reales: NDArray[np.float64], bandas: Sequence[Banda]) -> float:
    """Pérdida pinball promedio de los tres cuantiles, sobre el logaritmo del precio."""
    perdidas = []
    for cuantil, predichos in zip(
        CUANTILES,
        ([b.p25 for b in bandas], [b.p50 for b in bandas], [b.p75 for b in bandas]),
        strict=True,
    ):
        diferencia = np.log(reales) - np.log(np.array(predichos))
        perdidas.append(np.mean(np.maximum(cuantil * diferencia, (cuantil - 1) * diferencia)))
    return float(np.mean(perdidas))


def entrenar(
    observaciones: Sequence[Observacion], tasa_inflacion: float, version: int
) -> Resultado:
    """Valida con los últimos 6 meses y promueve el modelo solo si su MAPE mejora la línea base."""
    if len(observaciones) < MIN_OBSERVACIONES_ENTRENAMIENTO:
        raise DatosInsuficientes(f"Solo hay {len(observaciones)} líneas de contrato.")
    datos_hasta = max(o.fecha for o in observaciones)
    corte = sumar_meses(datos_hasta, -MESES_VALIDACION)
    entrenamiento = [o for o in observaciones if o.fecha <= corte]
    prueba = [o for o in observaciones if o.fecha > corte]
    if len(entrenamiento) < MIN_OBSERVACIONES_ENTRENAMIENTO or not prueba:
        raise DatosInsuficientes("Faltan contratos anteriores o posteriores al corte de validación.")
    por_categoria: dict[str, list[Observacion]] = defaultdict(list)
    for o in entrenamiento:
        por_categoria[o.categoria].append(o)
    pares: list[tuple[Observacion, Referencia]] = []
    for o in prueba:
        referencia = linea_base(
            por_categoria[o.categoria], o.servicio, o.categoria, o.cantidad, o.fecha, tasa_inflacion
        )
        if referencia is not None:
            pares.append((o, referencia))
    if not pares:
        raise DatosInsuficientes("Ningún contrato reciente tiene con qué compararse.")

    candidato = ajustar_modelo(entrenamiento, tasa_inflacion, version)
    bandas = candidato.predecir([consulta_de(o) for o, _ in pares])
    reales = np.array([o.precio for o, _ in pares], dtype=np.float64)
    del_modelo = np.array([b.p50 for b in bandas])
    de_la_base = np.array([r.banda.p50 for _, r in pares])
    mape = float(np.mean(np.abs(del_modelo - reales) / reales))
    mape_linea_base = float(np.mean(np.abs(de_la_base - reales) / reales))
    cobertura = float(
        np.mean([b.p25 <= o.precio <= b.p75 for (o, _), b in zip(pares, bandas, strict=True)])
    )
    cobertura_linea_base = float(
        np.mean([r.banda.p25 <= o.precio <= r.banda.p75 for o, r in pares])
    )
    modelo = (
        ajustar_modelo(observaciones, tasa_inflacion, version)
        if mape < mape_linea_base
        else None
    )
    return Resultado(
        modelo=modelo,
        observaciones=len(observaciones),
        datos_hasta=datos_hasta,
        mape=mape,
        mape_linea_base=mape_linea_base,
        cobertura=cobertura,
        cobertura_linea_base=cobertura_linea_base,
        pinball=_pinball(reales, bandas),
    )


def guardar_modelo(modelo: ModeloPrecios, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, ruta)


def cargar_modelo(ruta: Path) -> ModeloPrecios:
    modelo = joblib.load(ruta)
    if not isinstance(modelo, ModeloPrecios):
        raise TypeError(f"{ruta} no contiene un modelo de precios")
    return modelo
```

Cree `services/inteligencia/src/inteligencia/precio_justo.py`:

```python
"""Precio justo: el modelo promovido si conoce el servicio; si no, la línea base.

Sin contratos del servicio en los últimos 24 meses no hay referencia, aunque haya modelo.
"""

from collections.abc import Mapping, Sequence

from inteligencia.dominio.precios import Observacion, Referencia, linea_base
from inteligencia.modelo import Consulta, ModeloPrecios


def referencias(
    consultas: Sequence[Consulta],
    por_categoria: Mapping[str, Sequence[Observacion]],
    modelo: ModeloPrecios | None,
    tasa_inflacion: float,
) -> list[Referencia | None]:
    bases = [
        linea_base(
            por_categoria.get(c.categoria, ()),
            c.servicio,
            c.categoria,
            c.cantidad,
            c.fecha,
            tasa_inflacion,
        )
        for c in consultas
    ]
    if modelo is None:
        return bases
    # Una sola predicción para todas las consultas que el modelo puede responder.
    indices = [
        i
        for i, (consulta, base) in enumerate(zip(consultas, bases, strict=True))
        if base is not None and modelo.conoce(consulta.servicio)
    ]
    resultado = list(bases)
    for i, banda in zip(indices, modelo.predecir([consultas[i] for i in indices]), strict=True):
        base = bases[i]
        if base is not None:
            resultado[i] = Referencia(
                banda, base.confianza, base.observaciones, "modelo", modelo.version
            )
    return resultado
```

- [ ] **Step 5: Run the model tests to verify they pass**

Run: `uv run pytest services/inteligencia/tests/test_modelo.py -q`
Expected: PASS. El entrenamiento con 30 proveedores tarda unos segundos.

Si `MAPE < 0.15` o la cobertura entre 0.3 y 0.7 no se cumplen, **no** cambie las metas: reporte los números (BLOCKED) para que el controlador decida. El prototipo del plan, con 60 proveedores, dio:
- línea base: MAPE 0.093, cobertura 0.435;
- modelo deflactado: MAPE 0.083, cobertura 0.462.

- [ ] **Step 6: Write the failing trainer tests**

Cree `services/inteligencia/tests/test_entrenamiento.py`:

```python
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from generador.modelo import DatosSinteticos, generar
from inteligencia import entrenamiento
from inteligencia.entrenamiento import Entrenador
from inteligencia.modelo import cargar_modelo
from inteligencia.modelos import ModeloBenchmark, Outbox
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
Cargar = Callable[[DatosSinteticos], Awaitable[None]]
ADMIN: dict[str, str | None] = {"id": "admin-1", "nombre": "admin1"}


async def _registros(fabrica: Fabrica) -> list[ModeloBenchmark]:
    async with fabrica() as sesion:
        return list((await sesion.scalars(select(ModeloBenchmark))).all())


async def test_entrenar_registra_el_modelo_y_publica_el_evento(
    fabrica: Fabrica, cargar: Cargar, tmp_path: Path
) -> None:
    await cargar(generar(42, n_proveedores=15))
    entrenador = Entrenador(fabrica, tmp_path)
    assert entrenador.iniciar("manual", ADMIN)
    assert entrenador.entrenando
    assert not entrenador.iniciar("manual", ADMIN)  # un segundo pedido mientras corre
    await entrenador.esperar()
    assert not entrenador.entrenando

    [registro] = await _registros(fabrica)
    assert (registro.version, registro.origen, registro.actor_nombre) == (1, "manual", "admin1")
    if registro.promovido:
        assert registro.artefacto is not None
        assert cargar_modelo(Path(registro.artefacto)).version == 1
    else:
        assert registro.artefacto is None
    async with fabrica() as sesion:
        [evento] = (
            await sesion.scalars(select(Outbox).where(Outbox.tipo == "modelo.entrenado"))
        ).all()
    assert set(evento.payload) == {
        "version",
        "mape",
        "mape_linea_base",
        "cobertura",
        "promovido",
        "origen",
        "actor",
    }
    assert (evento.payload["version"], evento.payload["actor"]) == (1, ADMIN)


async def test_un_entrenamiento_fallido_libera_el_candado(
    fabrica: Fabrica, cargar: Cargar, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await cargar(generar(42, n_proveedores=15))

    def fallar(*_argumentos: object) -> None:
        raise RuntimeError("se acabó la memoria")

    monkeypatch.setattr(entrenamiento, "entrenar", fallar)
    entrenador = Entrenador(fabrica, tmp_path)
    assert entrenador.iniciar("manual", ADMIN)
    await entrenador.esperar()
    assert not entrenador.entrenando
    assert await _registros(fabrica) == []
    assert entrenador.iniciar("manual", ADMIN)  # se puede volver a intentar
    await entrenador.esperar()


async def test_sin_datos_no_registra_nada(
    fabrica: Fabrica, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    entrenador = Entrenador(fabrica, tmp_path)
    assert entrenador.iniciar("manual", ADMIN)
    await entrenador.esperar()
    assert await _registros(fabrica) == []
    assert "No se entrenó el modelo de precios" in caplog.text


async def test_el_automatico_espera_a_que_termine_la_importacion(
    fabrica: Fabrica, cargar: Cargar, tmp_path: Path
) -> None:
    await cargar(generar(42, n_proveedores=15))
    reloj = [datetime.now(UTC)]
    entrenador = Entrenador(fabrica, tmp_path, ahora=lambda: reloj[0])
    assert not await entrenador.revisar_automatico()  # la última línea llegó hace menos de 30 s
    reloj[0] += timedelta(seconds=31)
    assert await entrenador.revisar_automatico()
    await entrenador.esperar()
    [registro] = await _registros(fabrica)
    assert (registro.origen, registro.actor_nombre) == ("automatico", "Sistema (automático)")
    reloj[0] = datetime.now(UTC) + timedelta(minutes=5)
    assert not await entrenador.revisar_automatico()  # no hay líneas nuevas desde entonces
```

- [ ] **Step 7: Run the trainer tests to verify they fail**

Run: `uv run pytest services/inteligencia/tests/test_entrenamiento.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'inteligencia.entrenamiento'`.

- [ ] **Step 8: Implement the queries and the trainer**

Cree `services/inteligencia/src/inteligencia/consultas.py`:

```python
"""Lectura de la copia local para los cálculos de dominio."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inteligencia.dominio.precios import Observacion, plazo_en_meses
from inteligencia.modelos import Configuracion, Contrato, LineaContrato, ModeloBenchmark, Proveedor


async def observaciones(sesion: AsyncSession) -> list[Observacion]:
    """Cada línea de contrato como precio observado (el contrato va en la moneda del servicio)."""
    filas = await sesion.execute(
        select(
            LineaContrato.codigo_servicio,
            LineaContrato.categoria,
            Contrato.moneda,
            Contrato.fecha_inicio,
            Contrato.fecha_fin,
            LineaContrato.cantidad,
            LineaContrato.precio_unitario,
            Proveedor.tamano,
            Contrato.tipo,
        )
        .join(Contrato, LineaContrato.contrato_id == Contrato.id)
        .outerjoin(Proveedor, Proveedor.id == Contrato.proveedor_id)
    )
    return [
        Observacion(
            servicio=servicio,
            categoria=categoria,
            moneda=moneda,
            fecha=inicio,
            cantidad=float(cantidad),
            precio=float(precio),
            plazo_meses=plazo_en_meses(inicio, fin),
            tamano=tamano,
            tipo=tipo,
        )
        for servicio, categoria, moneda, inicio, fin, cantidad, precio, tamano, tipo in filas
    ]


async def configuracion(sesion: AsyncSession) -> Configuracion:
    fila = await sesion.get(Configuracion, 1)
    if fila is None:
        raise LookupError("Falta la fila de configuración (la crea la migración 0001)")
    return fila


async def modelo_activo(sesion: AsyncSession) -> ModeloBenchmark | None:
    return await sesion.scalar(
        select(ModeloBenchmark)
        .where(ModeloBenchmark.promovido)
        .order_by(ModeloBenchmark.version.desc())
        .limit(1)
    )
```

Cree `services/inteligencia/src/inteligencia/entrenamiento.py`:

```python
"""Entrenamiento del modelo de precios: a pedido del administrador o automático.

Nunca corre más de uno a la vez. El automático espera a acumular MIN_LINEAS_NUEVAS líneas de
contrato desde el último entrenamiento y a que la última haya llegado hace ESPERA_TRAS_ULTIMA_S o
más, para no entrenar a la mitad de una importación.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from comun.outbox import registrar_evento
from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inteligencia import consultas
from inteligencia.modelo import DatosInsuficientes, entrenar, guardar_modelo
from inteligencia.modelos import Contrato, LineaContrato, ModeloBenchmark, Outbox

log = logging.getLogger(__name__)

ACTOR_AUTOMATICO: dict[str, str | None] = {"id": None, "nombre": "Sistema (automático)"}
MIN_LINEAS_NUEVAS = 50
ESPERA_TRAS_ULTIMA_S = 30
INTERVALO_REVISION_S = 60


def _metrica(valor: float, decimales: int = 6) -> Decimal:
    return Decimal(f"{valor:.{decimales}f}")


class Entrenador:
    def __init__(
        self,
        fabrica: async_sessionmaker[AsyncSession],
        directorio: Path,
        ahora: Callable[[], datetime] | None = None,
    ) -> None:
        self._fabrica = fabrica
        self._directorio = directorio
        self._ahora = ahora or (lambda: datetime.now(UTC))
        self._en_curso = False
        self._tarea: asyncio.Task[None] | None = None

    @property
    def entrenando(self) -> bool:
        return self._en_curso

    def iniciar(self, origen: str, actor: dict[str, str | None]) -> bool:
        """Lanza un entrenamiento en segundo plano; False si ya hay uno en curso."""
        if self._en_curso:
            return False
        self._en_curso = True  # antes de crear la tarea: dos pedidos seguidos no lanzan dos
        self._tarea = asyncio.create_task(self._entrenar(origen, actor))
        return True

    async def esperar(self) -> None:
        if self._tarea is not None:
            await self._tarea

    async def _entrenar(self, origen: str, actor: dict[str, str | None]) -> None:
        try:
            async with self._fabrica() as sesion:
                observaciones = await consultas.observaciones(sesion)
                tasa = float((await consultas.configuracion(sesion)).inflacion_anual) / 100
                ultima = await sesion.scalar(select(func.max(ModeloBenchmark.version)))
            version = (ultima or 0) + 1
            resultado = await asyncio.to_thread(entrenar, observaciones, tasa, version)
            artefacto = None
            if resultado.modelo is not None:
                ruta = self._directorio / f"modelo-v{version}.joblib"
                await asyncio.to_thread(guardar_modelo, resultado.modelo, ruta)
                artefacto = str(ruta)
            async with self._fabrica() as sesion, sesion.begin():
                sesion.add(
                    ModeloBenchmark(
                        version=version,
                        entrenado_en=self._ahora(),
                        origen=origen,
                        actor_nombre=str(actor["nombre"]),
                        observaciones=resultado.observaciones,
                        datos_hasta=resultado.datos_hasta,
                        mape=_metrica(resultado.mape),
                        mape_linea_base=_metrica(resultado.mape_linea_base),
                        cobertura=_metrica(resultado.cobertura),
                        pinball=_metrica(resultado.pinball),
                        promovido=resultado.promovido,
                        artefacto=artefacto,
                    )
                )
                registrar_evento(
                    sesion,
                    Outbox,
                    "modelo.entrenado",
                    {
                        "version": version,
                        "mape": round(resultado.mape, 6),
                        "mape_linea_base": round(resultado.mape_linea_base, 6),
                        "cobertura": round(resultado.cobertura, 6),
                        "promovido": resultado.promovido,
                        "origen": origen,
                        "actor": actor,
                    },
                )
            log.info(
                "Modelo de precios v%s: MAPE %.4f (línea base %.4f), promovido: %s",
                version,
                resultado.mape,
                resultado.mape_linea_base,
                resultado.promovido,
            )
        except DatosInsuficientes as exc:
            log.warning("No se entrenó el modelo de precios: %s", exc)
        except Exception:
            log.exception("Falló el entrenamiento del modelo de precios")
        finally:
            self._en_curso = False

    async def revisar_automatico(self) -> bool:
        """Lanza un entrenamiento automático si toca; True si lo lanzó."""
        if self._en_curso:
            return False
        async with self._fabrica() as sesion:
            ultimo = await sesion.scalar(select(func.max(ModeloBenchmark.entrenado_en)))
            nuevas, mas_reciente = (
                await sesion.execute(
                    select(func.count(), func.max(Contrato.recibido_en))
                    .select_from(LineaContrato)
                    .join(Contrato, LineaContrato.contrato_id == Contrato.id)
                    .where(Contrato.recibido_en > ultimo if ultimo is not None else true())
                )
            ).one()
        if nuevas < MIN_LINEAS_NUEVAS or mas_reciente is None:
            return False
        if (self._ahora() - mas_reciente).total_seconds() < ESPERA_TRAS_ULTIMA_S:
            return False
        return self.iniciar("automatico", ACTOR_AUTOMATICO)

    async def ejecutar_periodicamente(self, intervalo: float = INTERVALO_REVISION_S) -> None:
        # ponytail: si el entrenamiento falla siempre (p. ej. pocos datos), se reintenta cada
        # `intervalo` y solo deja un aviso en el log; un estado de "último error" si molesta.
        while True:
            try:
                await self.revisar_automatico()
            except Exception:
                log.exception("No se pudo revisar si hay que reentrenar el modelo")
            await asyncio.sleep(intervalo)
```

`test_el_automatico_espera_a_que_termine_la_importacion` guarda `entrenado_en` con el reloj inyectado (`self._ahora()`, 31 s después). Las líneas cargadas antes quedan así como anteriores al entrenamiento, y la última revisión no encuentra líneas nuevas.

En `services/inteligencia/src/inteligencia/main.py`:

- importe `from inteligencia.entrenamiento import Entrenador`;
- después de `consumidor`, cree `entrenador = Entrenador(sesiones, config.directorio_modelos)`;
- en el ciclo de vida, agregue (fuera del `if config.usar_rabbitmq`):

```python
        if config.entrenamiento_automatico:
            tareas.append(asyncio.create_task(entrenador.ejecutar_periodicamente()))
```

- guarde `app.state.entrenador = entrenador`.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `uv run pytest services/inteligencia -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio. Si scikit-learn emite advertencias en las pruebas, corríjalas en el código, sin filtrarlas.

- [ ] **Step 10: Commit**

```bash
git add services/inteligencia
git commit -m "feat(inteligencia): modelo de precios por cuantiles con validación temporal y reentrenamiento manual o automático" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: API — contexto calculado, Tablero, alertas y precios

**Files:**
- Create:
  - `services/inteligencia/src/inteligencia/contexto.py` (`Contexto`, `LineaMercado`, `construir`, `armar` y `CacheContexto`)
  - `services/inteligencia/src/inteligencia/api/__init__.py` (vacío)
  - `services/inteligencia/src/inteligencia/api/dependencias.py`, `api/esquemas.py`, `api/tablero.py` y `api/precios.py`
  - `services/inteligencia/tests/test_api_tablero.py`, `test_api_precios.py` y `test_rendimiento.py`
- Modify:
  - `services/inteligencia/src/inteligencia/consultas.py` (cargadores de la copia local y `clave_datos`)
  - `services/inteligencia/src/inteligencia/main.py` (`hoy`, el caché y las rutas)
  - `services/inteligencia/tests/conftest.py` (`HOY`, `hoy`, `comprador`, `admin` y `aplicar_evento`)

**Interfaces:**
- Consumes:
  - Task 8: `Observacion`, `Referencia`, `Posicion`, `VENTANA_MESES`, `linea_base`, `posicion` y `sumar_meses`.
  - Task 9: `Mes`, `Pesos`, `Puntuacion`, `MESES_TENDENCIA`, `puntuar` e `historial`.
  - Task 10: `ContratoInfo`, `Linea`, `Alerta`, `vencimiento`, `sobreprecio`, `riesgo`, `ordenar`, `Tablero`, `Destacado`, `calcular`, `tipo_cambio_en`, `a_mxn` y `CENTAVOS`.
  - Task 11:
    - `Consulta`, `ModeloPrecios` y `cargar_modelo`;
    - `precio_justo.referencias`;
    - `consultas.observaciones`, `consultas.configuracion` y `consultas.modelo_activo`;
    - los fixtures `cargar` y `generadas`.
- Produces:
  - `inteligencia.consultas`:
    - `proveedores`, `servicios`, `contratos` (con sus líneas), `tipos_cambio -> dict[date, Decimal]` y `desempeno`;
    - `clave_datos(sesion) -> tuple[object, ...]`.
  - `inteligencia.contexto`:
    - `LineaMercado(contrato, linea, referencia: Referencia | None, posicion: Posicion | None, ahorro: Decimal)`;
    - `Contexto(hoy, pesos, umbral, tasa_inflacion, modelo, proveedores: dict[str, Proveedor], servicios: dict[str, Servicio], contratos, tipos_cambio, por_categoria, puntuaciones, historial, mercado, alertas, tablero)`, con `anterior(proveedor_id) -> float | None` y `tendencia(proveedor_id) -> float | None`;
    - `puntuacion_en(serie, fecha) -> float | None`;
    - `CacheContexto().obtener(sesion, hoy) -> Contexto`.
  - `inteligencia.api.dependencias`:
    - `Sesion`, `Interno`, `Admin`;
    - `Ctx` (el contexto del día; exige un rol interno antes de tocar la base);
    - `CodigoServicio` (código en la ruta, patrón del catálogo).
  - `inteligencia.api.esquemas`:
    - `unitario(valor: float) -> Decimal` (4 decimales);
    - `AlertaSalida`, `PaginaAlertas` y `TableroSalida`;
    - `ServicioPrecios`, `ReferenciaSalida`, `HistorialPrecios` y `Sobreprecio`.
  - `crear_app(configuracion=None, validador=None, fabrica=None, hoy: Callable[[], date] | None = None)`, con `app.state.hoy` y `app.state.contexto`.
  - En las pruebas:
    - `HOY = date(2026, 9, 15)` y el fixture `hoy`;
    - las cabeceras `comprador` y `admin` (`sub="admin-1"`);
    - el fixture `aplicar_evento(tipo, payload)`.
  - Errores: 404 `servicio_no_encontrado` y 404 `sin_observaciones`.

Decisiones que esta tarea fija:
- **Contexto calculado una vez.** La puntuación de cada proveedor depende de las de los demás (percentiles) y las alertas recorren todos los contratos vigentes. Por eso todo se calcula junto y se guarda hasta que:
  - se aplique un evento;
  - se guarde la configuración;
  - se promueva un modelo;
  - o cambie el día.
- **Precio vs. mercado de una línea.** Se compara con el precio justo **a la fecha de inicio del contrato**, con su cantidad, su plazo, el tamaño del proveedor y su tipo: lo que el mercado cobraba cuando se firmó.
- **Proveedores inactivos.** No reciben alertas de riesgo y no cuentan en mejores y peores ni en la distribución. Sus contratos vigentes sí cuentan en el gasto, los vencimientos y los sobreprecios.
- **Alertas paginadas.** `GET /alertas` acepta `pagina` además de `tipo`, `severidad` y `limite` (la campana usa `limite=5`): con ~1,600 contratos hay cientos de sobreprecios.
- **Historial de precios.** Lo que devuelve:
  - los puntos son las líneas del servicio con inicio en los últimos 24 meses;
  - las bandas son la línea base al cierre de cada mes, para la cantidad pedida (por defecto, la mediana de los puntos).

- [ ] **Step 1: Test fixtures**

En `services/inteligencia/tests/conftest.py`:
- agregue después de las constantes:

```python
HOY = date(2026, 9, 15)  # dos semanas después del último mes de los datos generados
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
```

- en el fixture `app`, pase `hoy=lambda: HOY` a `crear_app`;
- agregue al final:

```python
@pytest.fixture
def hoy() -> date:
    return HOY


@pytest.fixture
def comprador(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('comprador')}"}


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


@pytest.fixture
def aplicar_evento(fabrica: async_sessionmaker[AsyncSession]) -> AplicarEvento:
    """Aplica un evento suelto, como si hubiera llegado por la cola."""

    async def _aplicar(tipo: str, payload: dict[str, Any]) -> None:
        async with fabrica() as sesion, sesion.begin():
            await aplicar(sesion, {"event_id": str(uuid.uuid4()), "type": tipo, "payload": payload})

    return _aplicar
```

- [ ] **Step 2: Write the failing tests**

Cree `services/inteligencia/tests/test_api_tablero.py`:

```python
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from generador.modelo import DatosSinteticos, generar

pytestmark = pytest.mark.integracion

Cargar = Callable[[DatosSinteticos], Awaitable[None]]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
Cabeceras = dict[str, str]
SEVERIDADES = {"alta": 0, "media": 1, "informativa": 2}


def _por_vencer(datos: DatosSinteticos, hoy: date) -> set[str]:
    """Folios vigentes que terminan en 90 días o menos, directo de los datos generados."""
    return {
        fila["folio"]
        for fila in datos.contratos
        if date.fromisoformat(fila["fecha_inicio"]) <= hoy <= date.fromisoformat(fila["fecha_fin"])
        and (date.fromisoformat(fila["fecha_fin"]) - hoy).days <= 90
    }


async def test_tablero_sin_datos(cliente: httpx.AsyncClient, comprador: Cabeceras) -> None:
    respuesta = await cliente.get("/tablero", headers=comprador)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["fecha"], cuerpo["moneda"]) == ("2026-09-15", "MXN")
    assert (cuerpo["gasto_anual"], cuerpo["ahorro_potencial"]) == ("0.00", "0.00")
    assert cuerpo["variacion_pct"] is None
    assert (cuerpo["por_vencer"], cuerpo["en_riesgo"], cuerpo["total_proveedores"]) == (0, 0, 0)
    assert len(cuerpo["gasto_por_mes"]) == 24
    assert {mes["monto"] for mes in cuerpo["gasto_por_mes"]} == {"0.00"}
    for lista in (
        "gasto_por_categoria",
        "proximos_vencimientos",
        "alertas_principales",
        "mejores",
        "peores",
    ):
        assert cuerpo[lista] == [], lista


async def test_tablero_con_los_datos_generados(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar, hoy: date
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    cuerpo = (await cliente.get("/tablero", headers=comprador)).json()
    activos = sum(p.activo for p in datos.proveedores)
    assert cuerpo["total_proveedores"] == activos
    assert cuerpo["por_vencer"] == len(_por_vencer(datos, hoy))
    assert Decimal(cuerpo["gasto_anual"]) > 0
    assert Decimal(cuerpo["ahorro_potencial"]) >= 0
    assert cuerpo["gasto_por_mes"][-1]["mes"] == "2026-09-01"
    assert len(cuerpo["mejores"]) == len(cuerpo["peores"]) == 5
    mejores = [d["puntuacion"] for d in cuerpo["mejores"]]
    assert mejores == sorted(mejores, reverse=True)
    # Todos los proveedores generados tienen desempeño en los últimos 12 meses.
    assert sum(rango["proveedores"] for rango in cuerpo["distribucion"]) == activos
    assert len(cuerpo["alertas_principales"]) == 5
    dias = [v["dias"] for v in cuerpo["proximos_vencimientos"]]
    assert dias == sorted(dias)
    assert all(v["servicios"] and Decimal(v["monto_mensual"]) > 0 for v in cuerpo["proximos_vencimientos"])


async def test_el_tablero_se_actualiza_al_llegar_un_evento(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    aplicar_evento: AplicarEvento,
    hoy: date,
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    antes = (await cliente.get("/tablero", headers=comprador)).json()
    servicio = datos.servicios[0]
    contrato_id = str(uuid.uuid4())
    await aplicar_evento(
        "contrato.registrado",
        {
            "id": contrato_id,
            "proveedor_id": antes["mejores"][0]["proveedor_id"],
            "folio": "C-PRUEBA",
            "tipo": "nuevo",
            "fecha_inicio": "2026-01-01",
            "fecha_fin": (hoy + timedelta(days=10)).isoformat(),
            "moneda": servicio.moneda,
            "lineas": [
                {
                    "codigo_servicio": servicio.codigo,
                    "categoria": servicio.categoria,
                    "unidad": servicio.unidad,
                    "cantidad": "10",
                    "precio_unitario": "1.0000",
                }
            ],
        },
    )
    despues = (await cliente.get("/tablero", headers=comprador)).json()
    assert despues["por_vencer"] == antes["por_vencer"] + 1
    vencimientos = (
        await cliente.get(
            "/alertas", params={"tipo": "vencimiento", "limite": 200}, headers=comprador
        )
    ).json()
    [alerta] = [a for a in vencimientos["elementos"] if a["entidad_id"] == contrato_id]
    assert (alerta["severidad"], alerta["titulo"]) == ("alta", "Vence en 10 días: C-PRUEBA")


async def test_alertas_filtra_pagina_y_ordena(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=10))
    todas = (await cliente.get("/alertas", params={"limite": 200}, headers=comprador)).json()
    assert 5 < todas["total"] == len(todas["elementos"])
    orden = [(SEVERIDADES[a["severidad"]], a["fecha"]) for a in todas["elementos"]]
    assert orden == sorted(orden)
    for filtro, valor in (("tipo", "vencimiento"), ("tipo", "sobreprecio"), ("severidad", "alta")):
        parcial = (
            await cliente.get(
                "/alertas", params={filtro: valor, "limite": 200}, headers=comprador
            )
        ).json()
        assert parcial["elementos"] == [a for a in todas["elementos"] if a[filtro] == valor]
    campana = (await cliente.get("/alertas", params={"limite": 5}, headers=comprador)).json()
    assert campana == {"total": todas["total"], "elementos": todas["elementos"][:5]}
    segunda = (
        await cliente.get("/alertas", params={"limite": 5, "pagina": 2}, headers=comprador)
    ).json()
    assert segunda["elementos"] == todas["elementos"][5:10]


@pytest.mark.parametrize(
    "params", [{"tipo": "otro"}, {"severidad": "baja"}, {"limite": "0"}, {"pagina": "0"}]
)
async def test_alertas_valida_los_filtros(
    cliente: httpx.AsyncClient, comprador: Cabeceras, params: dict[str, str]
) -> None:
    respuesta = await cliente.get("/alertas", params=params, headers=comprador)
    assert respuesta.status_code == 422
```

Cree `services/inteligencia/tests/test_api_precios.py`:

```python
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from generador.modelo import DatosSinteticos, generar
from inteligencia.dominio.precios import Observacion
from inteligencia.modelo import ajustar_modelo, guardar_modelo
from inteligencia.modelos import ModeloBenchmark
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
Cargar = Callable[[DatosSinteticos], Awaitable[None]]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
Cabeceras = dict[str, str]
INICIO_VENTANA = date(2024, 9, 1)  # 24 meses antes de HOY: la ventana empieza después


def _servicio(codigo: str, activo: bool = True) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "codigo": codigo,
        "nombre": f"Servicio {codigo}",
        "categoria": "nube",
        "unidad": "vcpu_mes",
        "moneda": "USD",
        "activo": activo,
    }


async def _mas_visto(cliente: httpx.AsyncClient, comprador: Cabeceras) -> dict[str, Any]:
    servicios = (await cliente.get("/precios/servicios", headers=comprador)).json()
    return max(servicios, key=lambda s: (s["observaciones"], s["codigo"]))


async def _registrar_modelo(fabrica: Fabrica, artefacto: str) -> None:
    async with fabrica() as sesion, sesion.begin():
        sesion.add(
            ModeloBenchmark(
                version=1,
                entrenado_en=datetime.now(UTC),
                origen="manual",
                actor_nombre="admin-1",
                observaciones=100,
                datos_hasta=date(2026, 9, 1),
                mape=Decimal("0.08"),
                mape_linea_base=Decimal("0.09"),
                cobertura=Decimal("0.5"),
                pinball=Decimal("0.02"),
                promovido=True,
                artefacto=artefacto,
            )
        )


async def test_servicios_activos_con_sus_observaciones(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    aplicar_evento: AplicarEvento,
    hoy: date,
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    await aplicar_evento("servicio.actualizado", _servicio("NUEVO-SERV"))
    await aplicar_evento("servicio.actualizado", _servicio("VIEJO-SERV", activo=False))
    lista = (await cliente.get("/precios/servicios", headers=comprador)).json()
    assert [s["nombre"] for s in lista] == sorted(s["nombre"] for s in lista)
    servicios = {s["codigo"]: s for s in lista}
    assert "VIEJO-SERV" not in servicios
    assert servicios["NUEVO-SERV"]["observaciones"] == 0
    assert len(servicios) == len(datos.servicios) + 1
    for codigo in (s.codigo for s in datos.servicios):
        esperadas = sum(
            1
            for fila in datos.contratos
            if fila["codigo_servicio"] == codigo
            and INICIO_VENTANA < date.fromisoformat(fila["fecha_inicio"]) <= hoy
        )
        assert servicios[codigo]["observaciones"] == esperadas, codigo


async def test_referencia_de_un_servicio_sin_contratos(
    cliente: httpx.AsyncClient, comprador: Cabeceras, aplicar_evento: AplicarEvento
) -> None:
    await aplicar_evento("servicio.actualizado", _servicio("NUEVO-SERV"))
    sin_datos = await cliente.get(
        "/precios/servicios/nuevo-serv/referencia", params={"cantidad": "10"}, headers=comprador
    )
    assert (sin_datos.status_code, sin_datos.json()["codigo"]) == (404, "sin_observaciones")
    inexistente = await cliente.get(
        "/precios/servicios/NO-EXISTE/referencia", params={"cantidad": "10"}, headers=comprador
    )
    assert (inexistente.status_code, inexistente.json()["codigo"]) == (
        404,
        "servicio_no_encontrado",
    )


@pytest.mark.parametrize(
    ("ruta", "params"),
    [
        ("/precios/servicios/NUBE-VM/referencia", {"cantidad": "0"}),
        ("/precios/servicios/NUBE-VM/referencia", {"cantidad": "-5"}),
        ("/precios/servicios/NUBE-VM/referencia", {}),
        ("/precios/servicios/NUBE-VM/referencia", {"cantidad": "10", "plazo": "0"}),
        ("/precios/servicios/NUBE-VM/referencia", {"cantidad": "10", "plazo": "121"}),
        ("/precios/servicios/a$/referencia", {"cantidad": "10"}),
        ("/precios/servicios/NUBE-VM/historial", {"cantidad": "0"}),
        ("/precios/sobreprecios", {"codigo": "a$"}),
    ],
)
async def test_los_parametros_se_validan(
    cliente: httpx.AsyncClient, comprador: Cabeceras, ruta: str, params: dict[str, str]
) -> None:
    respuesta = await cliente.get(ruta, params=params, headers=comprador)
    assert respuesta.status_code == 422


async def test_referencia_con_la_linea_base(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=15))
    servicio = await _mas_visto(cliente, comprador)
    respuesta = await cliente.get(
        f"/precios/servicios/{servicio['codigo']}/referencia",
        params={"cantidad": "50", "plazo": "12"},
        headers=comprador,
    )
    assert respuesta.status_code == 200
    ref = respuesta.json()
    assert Decimal(ref["p25"]) <= Decimal(ref["p50"]) <= Decimal(ref["p75"])
    assert (ref["metodo"], ref["version"]) == ("linea_base", None)
    assert (ref["moneda"], ref["unidad"]) == (servicio["moneda"], servicio["unidad"])
    assert (ref["cantidad"], ref["plazo"], ref["fecha"]) == ("50", 12, "2026-09-15")
    assert ref["confianza"] in {"normal", "baja"}
    assert 0 < ref["observaciones"] <= servicio["observaciones"]


async def test_la_referencia_usa_el_modelo_activo(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    fabrica: Fabrica,
    generadas: list[Observacion],
    tmp_path: Path,
) -> None:
    await cargar(generar(42, n_proveedores=15))
    ruta = tmp_path / "modelo-v1.joblib"
    guardar_modelo(ajustar_modelo(generadas, 0.045, version=1), ruta)
    await _registrar_modelo(fabrica, str(ruta))
    servicio = await _mas_visto(cliente, comprador)
    ref = (
        await cliente.get(
            f"/precios/servicios/{servicio['codigo']}/referencia",
            params={"cantidad": "50"},
            headers=comprador,
        )
    ).json()
    assert (ref["metodo"], ref["version"]) == ("modelo", 1)
    assert Decimal(ref["p25"]) <= Decimal(ref["p50"]) <= Decimal(ref["p75"])


async def test_un_modelo_sin_artefacto_usa_la_linea_base(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    fabrica: Fabrica,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await cargar(generar(42, n_proveedores=15))
    await _registrar_modelo(fabrica, str(tmp_path / "no-existe.joblib"))
    servicio = await _mas_visto(cliente, comprador)
    respuesta = await cliente.get(
        f"/precios/servicios/{servicio['codigo']}/referencia",
        params={"cantidad": "50"},
        headers=comprador,
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["metodo"] == "linea_base"
    assert "No se pudo cargar el modelo de precios v1" in caplog.text


async def test_historial_de_precios(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=15))
    servicio = await _mas_visto(cliente, comprador)
    ruta = f"/precios/servicios/{servicio['codigo']}/historial"
    cuerpo = (await cliente.get(ruta, headers=comprador)).json()
    assert cuerpo["moneda"] == servicio["moneda"]
    fechas = [p["fecha"] for p in cuerpo["puntos"]]
    assert len(fechas) == servicio["observaciones"]
    assert fechas == sorted(fechas)
    assert "2024-09-01" < fechas[0] and fechas[-1] <= "2026-09-15"
    meses = [b["mes"] for b in cuerpo["bandas"]]
    assert meses == sorted(meses)
    assert 0 < len(meses) <= 24 and meses[-1] == "2026-09-01"
    assert all(
        Decimal(b["p25"]) <= Decimal(b["p50"]) <= Decimal(b["p75"]) for b in cuerpo["bandas"]
    )
    con_cantidad = (await cliente.get(ruta, params={"cantidad": "5"}, headers=comprador)).json()
    assert con_cantidad["cantidad"] == "5"


async def test_sobreprecios(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=15))
    todos = (await cliente.get("/precios/sobreprecios", headers=comprador)).json()
    assert todos
    for fila in todos:
        assert Decimal(fila["precio"]) >= Decimal(fila["p75"])
        assert Decimal(fila["ahorro_potencial"]) >= 0
        assert Decimal(fila["ahorro_potencial_mxn"]) >= 0
    ahorros = [Decimal(fila["ahorro_potencial_mxn"]) for fila in todos]
    assert ahorros == sorted(ahorros, reverse=True)
    codigo = todos[0]["codigo_servicio"]
    del_servicio = (
        await cliente.get(
            "/precios/sobreprecios", params={"codigo": codigo.lower()}, headers=comprador
        )
    ).json()
    assert del_servicio == [fila for fila in todos if fila["codigo_servicio"] == codigo]
    alertas = (
        await cliente.get(
            "/alertas", params={"tipo": "sobreprecio", "limite": 1}, headers=comprador
        )
    ).json()
    assert alertas["total"] == len(todos)
```

Cree `services/inteligencia/tests/test_rendimiento.py`:

```python
import time
from collections.abc import Awaitable, Callable

import httpx
import pytest
from generador.modelo import DatosSinteticos, generar

pytestmark = pytest.mark.integracion

Cargar = Callable[[DatosSinteticos], Awaitable[None]]
REPETICIONES = 20


async def test_el_tablero_responde_en_300_ms_con_el_dataset_por_defecto(
    cliente: httpx.AsyncClient, comprador: dict[str, str], cargar: Cargar
) -> None:
    await cargar(generar(42))  # el dataset por defecto: 60 proveedores, ~1,600 contratos
    inicio = time.perf_counter()
    primera = await cliente.get("/tablero", headers=comprador)
    en_frio = time.perf_counter() - inicio
    assert primera.status_code == 200
    tiempos = []
    for _ in range(REPETICIONES):
        inicio = time.perf_counter()
        respuesta = await cliente.get("/tablero", headers=comprador)
        tiempos.append(time.perf_counter() - inicio)
        assert respuesta.status_code == 200
    p95 = sorted(tiempos)[int(0.95 * REPETICIONES) - 1]
    assert p95 <= 0.3, f"p95 de {p95:.3f} s"
    # El cálculo completo se hace una vez por versión de los datos; este límite solo detecta un
    # cálculo cuadrático accidental.
    assert en_frio <= 10, f"la primera consulta tardó {en_frio:.1f} s"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest services/inteligencia/tests/test_api_tablero.py services/inteligencia/tests/test_api_precios.py -q`
Expected: FAIL; las rutas aún no existen (404 en lugar de 200 o 422).

- [ ] **Step 4: Implement the loaders and the context**

Agregue a `services/inteligencia/src/inteligencia/consultas.py` (amplíe los imports con `date`, `Decimal`, `func`, `Desempeno`, `EventoProcesado`, `Servicio` y `TipoCambio`):

```python
async def proveedores(sesion: AsyncSession) -> list[Proveedor]:
    return list((await sesion.scalars(select(Proveedor))).all())


async def servicios(sesion: AsyncSession) -> list[Servicio]:
    return list((await sesion.scalars(select(Servicio))).all())


async def contratos(sesion: AsyncSession) -> list[Contrato]:
    """Con sus líneas (las carga la relación `selectin`)."""
    return list((await sesion.scalars(select(Contrato))).all())


async def tipos_cambio(sesion: AsyncSession) -> dict[date, Decimal]:
    filas = await sesion.execute(select(TipoCambio.periodo, TipoCambio.usd_mxn))
    return {periodo: usd_mxn for periodo, usd_mxn in filas}


async def desempeno(sesion: AsyncSession) -> list[Desempeno]:
    return list((await sesion.scalars(select(Desempeno))).all())


async def clave_datos(sesion: AsyncSession) -> tuple[object, ...]:
    """Cambia cuando se aplica un evento, se guarda la configuración o se promueve un modelo.

    El conteo, además del máximo, detecta un evento que confirmó tarde con una hora anterior.
    """
    # ponytail: cuenta evento_procesado completo en cada consulta (~1 ms con 10,000 eventos); un
    # contador propio si la tabla llega a millones.
    fila = (
        await sesion.execute(
            select(
                select(func.count()).select_from(EventoProcesado).scalar_subquery(),
                select(func.max(EventoProcesado.procesado_en)).scalar_subquery(),
                select(Configuracion.actualizado_en).scalar_subquery(),
                select(func.max(ModeloBenchmark.version))
                .where(ModeloBenchmark.promovido)
                .scalar_subquery(),
            )
        )
    ).one()
    return tuple(fila)
```

Cree `services/inteligencia/src/inteligencia/contexto.py`:

```python
"""Lo que consultan las rutas, calculado una vez por versión de los datos.

La puntuación de un proveedor depende de todos los demás (percentiles) y las alertas recorren todos
los contratos vigentes: el cálculo se hace completo y se guarda hasta que se aplique un evento, se
guarde la configuración, se promueva un modelo o cambie el día.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from inteligencia import consultas
from inteligencia.dominio.alertas import Alerta, ordenar, riesgo, sobreprecio, vencimiento
from inteligencia.dominio.contratos import ContratoInfo, Linea
from inteligencia.dominio.precios import (
    Observacion,
    Posicion,
    Referencia,
    posicion,
    sumar_meses,
)
from inteligencia.dominio.puntuacion import (
    MESES_TENDENCIA,
    Mes,
    Pesos,
    Puntuacion,
    historial,
    puntuar,
)
from inteligencia.dominio.tablero import Tablero, calcular
from inteligencia.modelo import Consulta, ModeloPrecios, cargar_modelo
from inteligencia.modelos import (
    Configuracion,
    Contrato,
    Desempeno,
    ModeloBenchmark,
    Proveedor,
    Servicio,
)
from inteligencia.precio_justo import referencias

log = logging.getLogger(__name__)

SIN_NOMBRE = "Proveedor sin datos"  # el contrato llegó antes que su proveedor
CERO = Decimal("0.00")


@dataclass(frozen=True)
class LineaMercado:
    """Una línea de un contrato vigente frente al precio justo de su servicio."""

    contrato: ContratoInfo
    linea: Linea
    referencia: Referencia | None  # None: su servicio no tiene contratos recientes
    posicion: Posicion | None
    ahorro: Decimal  # en la moneda del contrato; 0.00 si no está sobre P75


@dataclass(frozen=True)
class Datos:
    """La copia local tal como se leyó de la base."""

    configuracion: Configuracion
    proveedores: list[Proveedor]
    servicios: list[Servicio]
    contratos: list[Contrato]
    tipos_cambio: dict[date, Decimal]
    desempeno: list[Desempeno]
    observaciones: list[Observacion]


def puntuacion_en(serie: Sequence[tuple[date, float]], fecha: date) -> float | None:
    return next((valor for mes, valor in serie if mes == fecha), None)


@dataclass(frozen=True)
class Contexto:
    hoy: date
    pesos: Pesos
    umbral: int
    tasa_inflacion: float
    modelo: ModeloPrecios | None
    proveedores: dict[str, Proveedor]  # por id, como texto
    servicios: dict[str, Servicio]  # por código
    contratos: list[ContratoInfo]
    tipos_cambio: dict[date, Decimal]
    por_categoria: dict[str, list[Observacion]]
    puntuaciones: dict[str, Puntuacion]
    historial: dict[str, list[tuple[date, float]]]
    mercado: list[LineaMercado]
    alertas: list[Alerta]  # ordenadas por severidad y fecha
    tablero: Tablero

    def anterior(self, proveedor_id: str) -> float | None:
        """La puntuación de hace MESES_TENDENCIA meses; None si aún no tenía historia."""
        return puntuacion_en(
            self.historial.get(proveedor_id, []), sumar_meses(self.hoy, -MESES_TENDENCIA)
        )

    def tendencia(self, proveedor_id: str) -> float | None:
        actual = self.puntuaciones.get(proveedor_id)
        anterior = self.anterior(proveedor_id)
        return None if actual is None or anterior is None else actual.puntuacion - anterior


def _contrato(
    contrato: Contrato, proveedores: dict[str, Proveedor], servicios: dict[str, Servicio]
) -> ContratoInfo:
    proveedor = proveedores.get(str(contrato.proveedor_id))
    return ContratoInfo(
        id=str(contrato.id),
        folio=contrato.folio,
        proveedor_id=str(contrato.proveedor_id),
        proveedor=proveedor.nombre if proveedor is not None else SIN_NOMBRE,
        tipo=contrato.tipo,
        fecha_inicio=contrato.fecha_inicio,
        fecha_fin=contrato.fecha_fin,
        moneda=contrato.moneda,
        lineas=tuple(
            Linea(
                codigo=linea.codigo_servicio,
                servicio=(
                    servicios[linea.codigo_servicio].nombre
                    if linea.codigo_servicio in servicios
                    else linea.codigo_servicio
                ),
                categoria=linea.categoria,
                unidad=linea.unidad,
                cantidad=linea.cantidad,
                precio=linea.precio_unitario,
            )
            for linea in sorted(contrato.lineas, key=lambda linea: linea.codigo_servicio)
        ),
    )


def _meses(registros: Sequence[Desempeno]) -> dict[str, list[Mes]]:
    meses: dict[str, list[Mes]] = defaultdict(list)
    for r in registros:
        meses[str(r.proveedor_id)].append(
            Mes(
                r.periodo,
                sla=float(r.sla_cumplimiento_pct),
                resolucion=float(r.tiempo_resolucion_h),
                incidentes=float(r.incidentes_criticos),
                entregas=float(r.entregas_a_tiempo_pct),
                satisfaccion=float(r.satisfaccion),
            )
        )
    return meses


def construir(datos: Datos, modelo: ModeloPrecios | None, hoy: date) -> Contexto:
    config = datos.configuracion
    pesos = Pesos(
        config.peso_sla,
        config.peso_resolucion,
        config.peso_incidentes,
        config.peso_entregas,
        config.peso_satisfaccion,
    )
    tasa = float(config.inflacion_anual) / 100
    proveedores = {str(p.id): p for p in datos.proveedores}
    servicios = {s.codigo: s for s in datos.servicios}
    contratos = [_contrato(c, proveedores, servicios) for c in datos.contratos]
    por_categoria: dict[str, list[Observacion]] = defaultdict(list)
    for observacion in datos.observaciones:
        por_categoria[observacion.categoria].append(observacion)

    # Solo se puntúa a los proveedores de la copia: su categoría principal decide contra quién se
    # comparan, y su desempeño pudo llegar antes que ellos.
    desempeno = {
        pid: meses
        for pid, meses in _meses(datos.desempeno).items()
        if pid in proveedores and proveedores[pid].categorias
    }
    categorias = {pid: proveedores[pid].categorias[0] for pid in desempeno}
    puntuaciones = puntuar(desempeno, categorias, pesos, hoy)
    series = historial(desempeno, categorias, pesos, hoy)
    hace_tres = sumar_meses(hoy, -MESES_TENDENCIA)

    vigentes = [c for c in contratos if c.vigente(hoy)]
    pares = [(c, linea) for c in vigentes for linea in c.lineas]
    consultas_mercado = []
    for c, linea in pares:
        proveedor = proveedores.get(c.proveedor_id)
        consultas_mercado.append(
            Consulta(
                linea.codigo,
                linea.categoria,
                c.moneda,
                float(linea.cantidad),
                c.plazo_meses,
                c.fecha_inicio,
                proveedor.tamano if proveedor is not None else None,
                c.tipo,
            )
        )
    avisos = [a for c in vigentes if (a := vencimiento(c, hoy)) is not None]
    mercado = []
    for (c, linea), referencia in zip(
        pares, referencias(consultas_mercado, por_categoria, modelo, tasa), strict=True
    ):
        alerta = sobreprecio(c, linea, referencia.banda, hoy) if referencia is not None else None
        if alerta is not None:
            avisos.append(alerta)
        mercado.append(
            LineaMercado(
                c,
                linea,
                referencia,
                posicion(float(linea.precio), referencia.banda) if referencia is not None else None,
                alerta.ahorro_potencial
                if alerta is not None and alerta.ahorro_potencial is not None
                else CERO,
            )
        )
    for pid, puntuacion in puntuaciones.items():
        proveedor = proveedores[pid]
        if not proveedor.activo:
            continue
        alerta = riesgo(
            pid,
            proveedor.nombre,
            puntuacion.puntuacion,
            puntuacion_en(series.get(pid, []), hace_tres),
            config.umbral_riesgo,
            hoy,
        )
        if alerta is not None:
            avisos.append(alerta)
    alertas = ordenar(avisos)
    activos = {pid for pid, p in proveedores.items() if p.activo}
    tablero = calcular(
        contratos,
        datos.tipos_cambio,
        {pid: p.puntuacion for pid, p in puntuaciones.items() if pid in activos},
        {pid: p.nombre for pid, p in proveedores.items()},
        len(activos),
        alertas,
        hoy,
    )
    return Contexto(
        hoy=hoy,
        pesos=pesos,
        umbral=config.umbral_riesgo,
        tasa_inflacion=tasa,
        modelo=modelo,
        proveedores=proveedores,
        servicios=servicios,
        contratos=contratos,
        tipos_cambio=datos.tipos_cambio,
        por_categoria=dict(por_categoria),
        puntuaciones=puntuaciones,
        historial=series,
        mercado=mercado,
        alertas=alertas,
        tablero=tablero,
    )


def _cargar_modelo(registro: ModeloBenchmark | None) -> ModeloPrecios | None:
    if registro is None or registro.artefacto is None:
        return None
    try:
        return cargar_modelo(Path(registro.artefacto))
    except Exception:
        # El volumen de modelos se perdió o el archivo está dañado: la línea base sigue sirviendo.
        log.exception(
            "No se pudo cargar el modelo de precios v%s; se usa la línea base", registro.version
        )
        return None


async def armar(sesion: AsyncSession, hoy: date) -> Contexto:
    registro = await consultas.modelo_activo(sesion)
    datos = Datos(
        configuracion=await consultas.configuracion(sesion),
        proveedores=await consultas.proveedores(sesion),
        servicios=await consultas.servicios(sesion),
        contratos=await consultas.contratos(sesion),
        tipos_cambio=await consultas.tipos_cambio(sesion),
        desempeno=await consultas.desempeno(sesion),
        observaciones=await consultas.observaciones(sesion),
    )
    modelo = await asyncio.to_thread(_cargar_modelo, registro)
    # Fuera del bucle de eventos: con el dataset por defecto el cálculo tarda alrededor de un
    # segundo, y mientras tanto el servicio debe seguir atendiendo la salud y la cola.
    return await asyncio.to_thread(construir, datos, modelo, hoy)


class CacheContexto:
    """El último Contexto; se rehace cuando cambian el día o `consultas.clave_datos`."""

    def __init__(self) -> None:
        self._candado = asyncio.Lock()
        self._clave: tuple[object, ...] | None = None
        self._contexto: Contexto | None = None

    async def obtener(self, sesion: AsyncSession, hoy: date) -> Contexto:
        version = await consultas.clave_datos(sesion)
        clave = (hoy, *version)
        # Varias consultas a la vez esperan un solo cálculo en lugar de repetirlo.
        async with self._candado:
            if self._contexto is None or clave != self._clave:
                self._contexto = await armar(sesion, hoy)
                self._clave = clave
            return self._contexto
```

Los datos se leen después de la clave: si llega un evento entre las dos lecturas, el contexto ya lo incluye y la siguiente consulta solo lo recalcula una vez más. Nunca queda un contexto más viejo que su clave.

- [ ] **Step 5: Implement the routes**

Cree `services/inteligencia/src/inteligencia/api/dependencias.py`:

```python
"""Sesión, roles y el contexto del día para las rutas."""

from datetime import date
from typing import Annotated

from comun.auth import ROLES_INTERNOS, Usuario, requiere_rol
from fastapi import Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from inteligencia.contexto import CacheContexto, Contexto
from inteligencia.db import obtener_sesion

Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]
Interno = Annotated[Usuario, Depends(requiere_rol(*ROLES_INTERNOS))]
Admin = Annotated[Usuario, Depends(requiere_rol("admin"))]
CodigoServicio = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{3,30}$")]


async def _contexto(request: Request, sesion: Sesion, _: Interno) -> Contexto:
    """Exige el rol antes de leer la base: sin una sesión válida no se calcula nada."""
    cache: CacheContexto = request.app.state.contexto
    hoy: date = request.app.state.hoy()
    return await cache.obtener(sesion, hoy)


Ctx = Annotated[Contexto, Depends(_contexto)]
```

Cree `services/inteligencia/src/inteligencia/api/esquemas.py`:

```python
"""Respuestas de la API: montos como texto decimal y puntuaciones con un decimal."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


def unitario(valor: float) -> Decimal:
    """Un precio unitario calculado, con 4 decimales como los de la base."""
    return Decimal(f"{valor:.4f}")


class AlertaSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tipo: str
    severidad: str
    titulo: str
    explicacion: str
    entidad_tipo: str
    entidad_id: str
    entidad_nombre: str
    proveedor_id: str
    proveedor_nombre: str
    fecha: date
    ahorro_potencial: Decimal | None
    moneda: str | None


class PaginaAlertas(BaseModel):
    total: int
    elementos: list[AlertaSalida]


class MontoCategoria(BaseModel):
    categoria: str
    monto: Decimal


class MontoMes(BaseModel):
    mes: date
    monto: Decimal


class VencimientoSalida(BaseModel):
    contrato_id: str
    folio: str
    proveedor_id: str
    proveedor: str
    servicios: list[str]
    fecha_fin: date
    dias: int
    monto_mensual: Decimal


class Destacado(BaseModel):
    proveedor_id: str
    nombre: str
    puntuacion: float


class RangoPuntuacion(BaseModel):
    rango: str
    proveedores: int


class TableroSalida(BaseModel):
    fecha: date
    moneda: Literal["MXN"] = "MXN"
    gasto_anual: Decimal
    variacion_pct: float | None
    por_vencer: int
    en_riesgo: int
    total_proveedores: int
    ahorro_potencial: Decimal
    gasto_por_categoria: list[MontoCategoria]
    gasto_por_mes: list[MontoMes]
    proximos_vencimientos: list[VencimientoSalida]
    alertas_principales: list[AlertaSalida]
    mejores: list[Destacado]
    peores: list[Destacado]
    distribucion: list[RangoPuntuacion]


class ServicioPrecios(BaseModel):
    codigo: str
    nombre: str
    categoria: str
    unidad: str
    moneda: str
    observaciones: int  # contratos de los últimos 24 meses


class ReferenciaSalida(BaseModel):
    codigo: str
    moneda: str
    unidad: str
    cantidad: Decimal
    plazo: int
    fecha: date
    p25: Decimal
    p50: Decimal
    p75: Decimal
    metodo: Literal["linea_base", "modelo"]
    version: int | None
    confianza: Literal["normal", "baja"]
    observaciones: int


class PuntoPrecio(BaseModel):
    fecha: date
    precio: Decimal
    cantidad: Decimal
    folio: str
    proveedor: str


class BandaMes(BaseModel):
    mes: date
    p25: Decimal
    p50: Decimal
    p75: Decimal


class HistorialPrecios(BaseModel):
    codigo: str
    moneda: str
    cantidad: Decimal  # la de las bandas
    puntos: list[PuntoPrecio]
    bandas: list[BandaMes]


class Sobreprecio(BaseModel):
    contrato_id: str
    folio: str
    proveedor_id: str
    proveedor: str
    codigo_servicio: str
    servicio: str
    moneda: str
    precio: Decimal
    p25: Decimal
    p50: Decimal
    p75: Decimal
    fecha_fin: date
    ahorro_potencial: Decimal  # en la moneda del contrato, por lo que le resta
    ahorro_potencial_mxn: Decimal
```

Cree `services/inteligencia/src/inteligencia/api/tablero.py`:

```python
"""Tablero y alertas: lo que cada persona ve al iniciar sesión."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from inteligencia.api import esquemas
from inteligencia.api.dependencias import Ctx
from inteligencia.dominio.tablero import Destacado

router = APIRouter(tags=["tablero"])


def _destacado(destacado: Destacado) -> esquemas.Destacado:
    return esquemas.Destacado(
        proveedor_id=destacado.proveedor_id,
        nombre=destacado.nombre,
        puntuacion=round(destacado.puntuacion, 1),
    )


@router.get("/tablero")
async def tablero(contexto: Ctx) -> esquemas.TableroSalida:
    t = contexto.tablero
    return esquemas.TableroSalida(
        fecha=contexto.hoy,
        gasto_anual=t.gasto_anual,
        variacion_pct=None if t.variacion_pct is None else round(t.variacion_pct, 1),
        por_vencer=t.por_vencer,
        en_riesgo=t.en_riesgo,
        total_proveedores=t.total_proveedores,
        ahorro_potencial=t.ahorro_potencial,
        gasto_por_categoria=[
            esquemas.MontoCategoria(categoria=categoria, monto=monto)
            for categoria, monto in t.gasto_por_categoria.items()
        ],
        gasto_por_mes=[esquemas.MontoMes(mes=mes, monto=monto) for mes, monto in t.gasto_por_mes],
        proximos_vencimientos=[
            esquemas.VencimientoSalida(
                contrato_id=v.contrato.id,
                folio=v.contrato.folio,
                proveedor_id=v.contrato.proveedor_id,
                proveedor=v.contrato.proveedor,
                servicios=[linea.servicio for linea in v.contrato.lineas],
                fecha_fin=v.contrato.fecha_fin,
                dias=v.dias,
                monto_mensual=v.monto_mensual,
            )
            for v in t.proximos_vencimientos
        ],
        alertas_principales=[
            esquemas.AlertaSalida.model_validate(a) for a in t.alertas_principales
        ],
        mejores=[_destacado(d) for d in t.mejores],
        peores=[_destacado(d) for d in t.peores],
        distribucion=[
            esquemas.RangoPuntuacion(rango=rango, proveedores=cuantos)
            for rango, cuantos in t.distribucion
        ],
    )


@router.get("/alertas")
async def alertas(
    contexto: Ctx,
    tipo: Literal["vencimiento", "sobreprecio", "riesgo"] | None = None,
    severidad: Literal["alta", "media", "informativa"] | None = None,
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> esquemas.PaginaAlertas:
    filtradas = [
        a
        for a in contexto.alertas
        if (tipo is None or a.tipo == tipo) and (severidad is None or a.severidad == severidad)
    ]
    visibles = filtradas[(pagina - 1) * limite : pagina * limite]
    return esquemas.PaginaAlertas(
        total=len(filtradas),
        elementos=[esquemas.AlertaSalida.model_validate(a) for a in visibles],
    )
```

Cree `services/inteligencia/src/inteligencia/api/precios.py`:

```python
"""Precio justo por servicio, su historia y los contratos que pagan de más."""

import statistics
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from comun.errores import ErrorDominio
from fastapi import APIRouter, Query

from inteligencia.api import esquemas
from inteligencia.api.dependencias import CodigoServicio, Ctx
from inteligencia.api.esquemas import unitario
from inteligencia.contexto import Contexto
from inteligencia.dominio.precios import VENTANA_MESES, linea_base, sumar_meses
from inteligencia.dominio.tablero import CENTAVOS, a_mxn, tipo_cambio_en
from inteligencia.modelo import Consulta
from inteligencia.modelos import Servicio
from inteligencia.precio_justo import referencias

router = APIRouter(prefix="/precios", tags=["precios"])

Cantidad = Annotated[Decimal, Query(gt=0, le=10_000_000)]


def _servicio(contexto: Contexto, codigo: str) -> Servicio:
    servicio = contexto.servicios.get(codigo.upper())
    if servicio is None:
        raise ErrorDominio(
            404, "No encontrado", "El servicio no existe.", {"codigo": "servicio_no_encontrado"}
        )
    return servicio


@router.get("/servicios")
async def servicios(contexto: Ctx) -> list[esquemas.ServicioPrecios]:
    """Los servicios activos; un servicio inactivo no se cotiza, aunque sus contratos sigan."""
    desde = sumar_meses(contexto.hoy, -VENTANA_MESES)
    recientes = Counter(
        o.servicio
        for observaciones in contexto.por_categoria.values()
        for o in observaciones
        if desde < o.fecha <= contexto.hoy
    )
    return [
        esquemas.ServicioPrecios(
            codigo=s.codigo,
            nombre=s.nombre,
            categoria=s.categoria,
            unidad=s.unidad,
            moneda=s.moneda,
            observaciones=recientes[s.codigo],
        )
        for s in sorted(contexto.servicios.values(), key=lambda s: (s.nombre, s.codigo))
        if s.activo
    ]


@router.get("/servicios/{codigo}/referencia")
async def referencia(
    codigo: CodigoServicio,
    contexto: Ctx,
    cantidad: Cantidad,
    plazo: Annotated[int, Query(ge=1, le=120)] = 12,
) -> esquemas.ReferenciaSalida:
    servicio = _servicio(contexto, codigo)
    consulta = Consulta(
        servicio.codigo,
        servicio.categoria,
        servicio.moneda,
        float(cantidad),
        plazo,
        contexto.hoy,
    )
    [resultado] = referencias(
        [consulta], contexto.por_categoria, contexto.modelo, contexto.tasa_inflacion
    )
    if resultado is None:
        raise ErrorDominio(
            404,
            "No encontrado",
            "No hay contratos de este servicio en los últimos 24 meses: no se puede calcular su "
            "precio justo.",
            {"codigo": "sin_observaciones"},
        )
    return esquemas.ReferenciaSalida(
        codigo=servicio.codigo,
        moneda=servicio.moneda,
        unidad=servicio.unidad,
        cantidad=cantidad,
        plazo=plazo,
        fecha=contexto.hoy,
        p25=unitario(resultado.banda.p25),
        p50=unitario(resultado.banda.p50),
        p75=unitario(resultado.banda.p75),
        metodo=resultado.metodo,
        version=resultado.version,
        confianza=resultado.confianza,
        observaciones=resultado.observaciones,
    )


@router.get("/servicios/{codigo}/historial")
async def historial(
    codigo: CodigoServicio,
    contexto: Ctx,
    cantidad: Annotated[Decimal | None, Query(gt=0, le=10_000_000)] = None,
) -> esquemas.HistorialPrecios:
    servicio = _servicio(contexto, codigo)
    hoy = contexto.hoy
    desde = sumar_meses(hoy, -VENTANA_MESES)
    puntos = sorted(
        (
            (c, linea)
            for c in contexto.contratos
            for linea in c.lineas
            if linea.codigo == servicio.codigo and desde < c.fecha_inicio <= hoy
        ),
        key=lambda par: (par[0].fecha_inicio, par[0].folio),
    )
    if cantidad is None:
        cantidad = statistics.median(linea.cantidad for _, linea in puntos) if puntos else Decimal(1)
    observaciones = contexto.por_categoria.get(servicio.categoria, [])
    bandas = []
    for atras in range(VENTANA_MESES - 1, -1, -1):
        mes = sumar_meses(hoy, -atras)
        cierre = min(sumar_meses(mes, 1) - timedelta(days=1), hoy)
        base = linea_base(
            observaciones,
            servicio.codigo,
            servicio.categoria,
            float(cantidad),
            cierre,
            contexto.tasa_inflacion,
        )
        if base is not None:
            bandas.append(
                esquemas.BandaMes(
                    mes=mes,
                    p25=unitario(base.banda.p25),
                    p50=unitario(base.banda.p50),
                    p75=unitario(base.banda.p75),
                )
            )
    return esquemas.HistorialPrecios(
        codigo=servicio.codigo,
        moneda=servicio.moneda,
        cantidad=cantidad,
        puntos=[
            esquemas.PuntoPrecio(
                fecha=c.fecha_inicio,
                precio=linea.precio,
                cantidad=linea.cantidad,
                folio=c.folio,
                proveedor=c.proveedor,
            )
            for c, linea in puntos
        ],
        bandas=bandas,
    )


@router.get("/sobreprecios")
async def sobreprecios(
    contexto: Ctx,
    codigo: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9-]{3,30}$")] = None,
) -> list[esquemas.Sobreprecio]:
    """Líneas de contratos vigentes sobre P75, de mayor a menor ahorro potencial en MXN."""
    ultimo = tipo_cambio_en(contexto.tipos_cambio, contexto.hoy)
    filas = [
        esquemas.Sobreprecio(
            contrato_id=m.contrato.id,
            folio=m.contrato.folio,
            proveedor_id=m.contrato.proveedor_id,
            proveedor=m.contrato.proveedor,
            codigo_servicio=m.linea.codigo,
            servicio=m.linea.servicio,
            moneda=m.contrato.moneda,
            precio=m.linea.precio,
            p25=unitario(m.referencia.banda.p25),
            p50=unitario(m.referencia.banda.p50),
            p75=unitario(m.referencia.banda.p75),
            fecha_fin=m.contrato.fecha_fin,
            ahorro_potencial=m.ahorro,
            ahorro_potencial_mxn=a_mxn(m.ahorro, m.contrato.moneda, ultimo).quantize(CENTAVOS),
        )
        for m in contexto.mercado
        if m.referencia is not None
        and m.posicion == "sobre_p75"
        and (codigo is None or m.linea.codigo == codigo.upper())
    ]
    return sorted(filas, key=lambda s: (-s.ahorro_potencial_mxn, s.folio, s.codigo_servicio))
```

En `services/inteligencia/src/inteligencia/main.py`:
- importe `from collections.abc import Callable`, `from datetime import date, datetime`, `from zoneinfo import ZoneInfo`, `from inteligencia.api import precios, tablero` y `from inteligencia.contexto import CacheContexto`;
- agregue la constante `ZONA_NEGOCIO = ZoneInfo("America/Mexico_City")  # el "hoy" del negocio`;
- agregue el parámetro `hoy: Callable[[], date] | None = None` al final de `crear_app`;
- después de `app.state.config = config`:

```python
    app.state.hoy = hoy or (lambda: datetime.now(ZONA_NEGOCIO).date())
    app.state.contexto = CacheContexto()
```

- después del router de salud:

```python
    app.include_router(tablero.router)
    app.include_router(precios.router)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest services/inteligencia -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio. `test_rendimiento.py` carga el dataset completo y tarda alrededor de un minuto.

Si el p95 del Tablero supera 300 ms, **no** suba el límite. Mida con el contexto ya calculado: la consulta normal solo lee `clave_datos` y serializa. Reporte qué tarda.

- [ ] **Step 7: Commit**

```bash
git add services/inteligencia
git commit -m "feat(inteligencia): API del Tablero, alertas y precio justo sobre un contexto calculado por versión de los datos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: API — proveedores, ranking, configuración, modelos y datos

**Files:**
- Create:
  - `services/inteligencia/src/inteligencia/api/proveedores.py` (lista, puntuación, mercado y ranking)
  - `services/inteligencia/src/inteligencia/api/ajustes.py` (configuración, registro y entrenamiento del modelo, datos)
  - `services/inteligencia/tests/test_api_proveedores.py`, `test_api_ajustes.py` y `test_api_permisos.py`
- Modify:
  - `services/inteligencia/src/inteligencia/api/esquemas.py` (esquemas nuevos)
  - `services/inteligencia/src/inteligencia/main.py` (las rutas nuevas)

**Interfaces:**
- Consumes:
  - Task 12: `Ctx`, `Sesion`, `Interno`, `Admin`, `unitario`, `Contexto`, `LineaMercado` y los fixtures `cargar`, `aplicar_evento`, `hoy`, `comprador` y `admin`.
  - Task 9: `KPIS` y `validar_pesos`.
  - Task 11: `Entrenador` (`app.state.entrenador`), `consultas.configuracion` y `consultas.modelo_activo`.
- Produces:
  - Rutas: `GET /proveedores`, `GET /proveedores/{id}/puntuacion`, `GET /proveedores/{id}/mercado`, `GET /ranking`, `GET` y `PUT /configuracion`, `GET /modelos`, `POST /modelos/entrenar` y `GET /datos`.
  - Errores: 404 `proveedor_no_encontrado`, 422 `pesos_invalidos` (campo `body.pesos`) y 409 `entrenamiento_en_curso`.
  - Evento `configuracion.actualizada`:
    - forma: `{cambios: [{campo, anterior, nuevo}], actor: {id, nombre}}`;
    - campos: `peso_sla`, `peso_resolucion`, `peso_incidentes`, `peso_entregas`, `peso_satisfaccion`, `umbral_riesgo` e `inflacion_anual`;
    - `inflacion_anual` va como texto con 2 decimales;
    - sin cambios no hay evento.

Decisiones que esta tarea fija:
- **Parámetros de `GET /proveedores`.** Son los de la §4.3 de la especificación y siguen la convención de las listas de `administracion`:
  - `busqueda`, sin acentos, por nombre o RFC;
  - `categoria`;
  - `estado`: `activos` | `inactivos`;
  - `en_riesgo`;
  - `orden`: `nombre` | `puntuacion` | `gasto_anual` | `contratos_vigentes` | `alertas`;
  - `direccion`: `asc` | `desc`;
  - `pagina` y `tamano`.

  Un proveedor sin puntuación va al final en cualquier dirección.
- **Ranking.** Incluye a los proveedores activos con puntuación. `categoria` filtra a los que ofrecen esa categoría (entre cualquiera de las suyas); la puntuación es la misma de la lista.
- **Registro de modelos.** `GET /modelos` devuelve:
  - `entrenando`;
  - `activo`: la versión en uso, o `null` si se usa la línea base;
  - los últimos 50 entrenamientos, del más nuevo al más viejo.

  No expone la ruta del artefacto.

- [ ] **Step 1: Write the failing tests**

Cree `services/inteligencia/tests/test_api_proveedores.py`:

```python
import unicodedata
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from generador.modelo import DatosSinteticos, generar

pytestmark = pytest.mark.integracion

Cargar = Callable[[DatosSinteticos], Awaitable[None]]
Cabeceras = dict[str, str]
KPIS = ["sla", "resolucion", "incidentes", "entregas", "satisfaccion"]


def _sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


async def _lista(
    cliente: httpx.AsyncClient, comprador: Cabeceras, **params: Any
) -> list[dict[str, Any]]:
    cuerpo = (
        await cliente.get("/proveedores", params={"tamano": 100, **params}, headers=comprador)
    ).json()
    assert cuerpo["total"] == len(cuerpo["elementos"])
    return list(cuerpo["elementos"])


@pytest.fixture
async def datos(cargar: Cargar) -> DatosSinteticos:
    generados = generar(42, n_proveedores=15)
    await cargar(generados)
    return generados


async def test_lista_con_puntuacion_gasto_y_alertas(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos, hoy: date
) -> None:
    proveedores = await _lista(cliente, comprador)
    assert len(proveedores) == 15
    assert [p["nombre"] for p in proveedores] == sorted(
        (p["nombre"] for p in proveedores), key=_sin_acentos
    )
    alertas = (await cliente.get("/alertas", params={"limite": 200}, headers=comprador)).json()
    assert alertas["total"] <= 200
    por_proveedor = Counter(a["proveedor_id"] for a in alertas["elementos"])
    folios = {
        (fila["folio"], fila["rfc_proveedor"])
        for fila in datos.contratos
        if date.fromisoformat(fila["fecha_inicio"]) <= hoy <= date.fromisoformat(fila["fecha_fin"])
    }
    vigentes = Counter(rfc for _, rfc in folios)
    for p in proveedores:
        assert p["alertas"] == por_proveedor[p["id"]], p["nombre"]
        assert p["contratos_vigentes"] == vigentes[p["rfc"]], p["nombre"]
        assert 0 <= p["puntuacion"] <= 100
        assert p["confianza"] in {"normal", "baja"}
    tablero = (await cliente.get("/tablero", headers=comprador)).json()
    gasto = sum(Decimal(p["gasto_anual"]) for p in proveedores)
    assert abs(gasto - Decimal(tablero["gasto_anual"])) <= Decimal("0.01") * len(proveedores)


async def test_lista_filtra_ordena_y_pagina(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    todos = await _lista(cliente, comprador)
    azteca = await _lista(cliente, comprador, busqueda="AZTECA")
    assert azteca and all("Azteca" in p["nombre"] for p in azteca)
    rfc = todos[0]["rfc"]
    assert [p["rfc"] for p in await _lista(cliente, comprador, busqueda=rfc.lower())] == [rfc]
    nube = await _lista(cliente, comprador, categoria="nube")
    assert nube and all("nube" in p["categorias"] for p in nube)
    inactivos = await _lista(cliente, comprador, estado="inactivos")
    assert len(inactivos) == sum(not p.activo for p in datos.proveedores)
    en_riesgo = await _lista(cliente, comprador, en_riesgo="true")
    assert all(p["en_riesgo"] for p in en_riesgo)
    por_puntuacion = await _lista(cliente, comprador, orden="puntuacion", direccion="desc")
    puntuaciones = [p["puntuacion"] for p in por_puntuacion]
    assert puntuaciones == sorted(puntuaciones, reverse=True)
    pagina = (
        await cliente.get(
            "/proveedores", params={"pagina": 2, "tamano": 5}, headers=comprador
        )
    ).json()
    assert pagina == {"total": 15, "elementos": todos[5:10]}


@pytest.mark.parametrize(
    "params",
    [{"orden": "rfc"}, {"direccion": "arriba"}, {"tamano": "0"}, {"categoria": "otra"}],
)
async def test_lista_valida_los_parametros(
    cliente: httpx.AsyncClient, comprador: Cabeceras, params: dict[str, str]
) -> None:
    respuesta = await cliente.get("/proveedores", params=params, headers=comprador)
    assert respuesta.status_code == 422


async def test_puntuacion_de_un_proveedor(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    proveedor = (await _lista(cliente, comprador))[0]
    respuesta = await cliente.get(f"/proveedores/{proveedor['id']}/puntuacion", headers=comprador)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["puntuacion"] == proveedor["puntuacion"]
    assert cuerpo["categoria"] == proveedor["categorias"][0]
    assert cuerpo["historial_corto"] == (cuerpo["meses"] < 6)
    assert [c["kpi"] for c in cuerpo["componentes"]] == KPIS
    assert all(0 <= c["percentil"] <= 100 for c in cuerpo["componentes"])
    assert 0 < len(cuerpo["historial"]) <= 12
    assert cuerpo["historial"][-1] == {"mes": "2026-09-01", "puntuacion": cuerpo["puntuacion"]}


async def test_un_proveedor_que_no_existe(
    cliente: httpx.AsyncClient, comprador: Cabeceras
) -> None:
    for ruta in ("puntuacion", "mercado"):
        respuesta = await cliente.get(f"/proveedores/{uuid.uuid4()}/{ruta}", headers=comprador)
        assert (respuesta.status_code, respuesta.json()["codigo"]) == (
            404,
            "proveedor_no_encontrado",
        )
        invalido = await cliente.get(f"/proveedores/no-es-un-id/{ruta}", headers=comprador)
        assert invalido.status_code == 422


async def test_precio_contra_mercado_de_un_proveedor(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    proveedor = max(await _lista(cliente, comprador), key=lambda p: p["contratos_vigentes"])
    lineas = (
        await cliente.get(f"/proveedores/{proveedor['id']}/mercado", headers=comprador)
    ).json()
    assert len({linea["contrato_id"] for linea in lineas}) == proveedor["contratos_vigentes"]
    for linea in lineas:
        if linea["posicion"] is None:
            assert (linea["p50"], linea["ahorro_potencial"]) == (None, "0.00")
            continue
        p25, p50, p75 = (Decimal(linea[k]) for k in ("p25", "p50", "p75"))
        precio = Decimal(linea["precio"])
        assert p25 <= p50 <= p75
        if linea["posicion"] == "sobre_p75":
            assert precio >= p75 and Decimal(linea["ahorro_potencial"]) >= 0
        else:
            assert linea["ahorro_potencial"] == "0.00"
        if linea["posicion"] == "bajo_p25":
            assert precio <= p25


async def test_ranking(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    proveedores = await _lista(cliente, comprador)
    ranking = (await cliente.get("/ranking", headers=comprador)).json()
    assert [f["posicion"] for f in ranking] == list(range(1, len(ranking) + 1))
    puntuaciones = [f["puntuacion"] for f in ranking]
    assert puntuaciones == sorted(puntuaciones, reverse=True)
    assert {f["proveedor_id"] for f in ranking} == {p["id"] for p in proveedores if p["activo"]}
    for fila in ranking:
        assert list(fila["componentes"]) == KPIS
        assert fila["historial_corto"] == (fila["meses"] < 6)
    nube = (await cliente.get("/ranking", params={"categoria": "nube"}, headers=comprador)).json()
    assert {f["proveedor_id"] for f in nube} == {
        p["id"] for p in proveedores if p["activo"] and "nube" in p["categorias"]
    }
    assert [f["posicion"] for f in nube] == list(range(1, len(nube) + 1))
```

Cree `services/inteligencia/tests/test_api_ajustes.py`:

```python
import threading
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from generador.modelo import DatosSinteticos, generar
from inteligencia import entrenamiento
from inteligencia.modelo import DatosInsuficientes
from inteligencia.modelos import Outbox
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
Cargar = Callable[[DatosSinteticos], Awaitable[None]]
Cabeceras = dict[str, str]
INICIAL: dict[str, Any] = {
    "peso_sla": 30,
    "peso_resolucion": 20,
    "peso_incidentes": 20,
    "peso_entregas": 15,
    "peso_satisfaccion": 15,
    "umbral_riesgo": 40,
    "inflacion_anual": "4.50",
}


async def _eventos(fabrica: Fabrica, tipo: str) -> list[dict[str, Any]]:
    async with fabrica() as sesion:
        filas = await sesion.scalars(select(Outbox).where(Outbox.tipo == tipo))
        return [fila.payload for fila in filas]


async def test_leer_la_configuracion(cliente: httpx.AsyncClient, comprador: Cabeceras) -> None:
    respuesta = await cliente.get("/configuracion", headers=comprador)
    assert respuesta.json() == {**INICIAL, "actualizado_en": None, "actualizado_por": None}


async def test_guardar_publica_los_campos_cambiados(
    cliente: httpx.AsyncClient, admin: Cabeceras, fabrica: Fabrica
) -> None:
    nueva = {**INICIAL, "peso_sla": 40, "peso_satisfaccion": 5, "inflacion_anual": "5.2"}
    respuesta = await cliente.put("/configuracion", json=nueva, headers=admin)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["peso_sla"], cuerpo["inflacion_anual"]) == (40, "5.20")
    assert cuerpo["actualizado_por"] == "admin-1" and cuerpo["actualizado_en"] is not None
    assert await _eventos(fabrica, "configuracion.actualizada") == [
        {
            "cambios": [
                {"campo": "peso_sla", "anterior": 30, "nuevo": 40},
                {"campo": "peso_satisfaccion", "anterior": 15, "nuevo": 5},
                {"campo": "inflacion_anual", "anterior": "4.50", "nuevo": "5.20"},
            ],
            "actor": {"id": "admin-1", "nombre": "admin-1"},
        }
    ]
    assert (await cliente.get("/configuracion", headers=admin)).json()["peso_sla"] == 40


async def test_guardar_sin_cambios_no_publica(
    cliente: httpx.AsyncClient, admin: Cabeceras, fabrica: Fabrica
) -> None:
    respuesta = await cliente.put(
        "/configuracion", json={**INICIAL, "inflacion_anual": "4.5"}, headers=admin
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["actualizado_en"] is None
    assert await _eventos(fabrica, "configuracion.actualizada") == []


async def test_pesos_que_no_suman_100(
    cliente: httpx.AsyncClient, admin: Cabeceras, fabrica: Fabrica
) -> None:
    respuesta = await cliente.put(
        "/configuracion", json={**INICIAL, "peso_sla": 20}, headers=admin
    )
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "pesos_invalidos"
    assert cuerpo["errores"] == [
        {"campo": "body.pesos", "mensaje": "Los pesos deben sumar 100 (suman 90)."}
    ]
    assert (await cliente.get("/configuracion", headers=admin)).json()["peso_sla"] == 30
    assert await _eventos(fabrica, "configuracion.actualizada") == []


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"peso_sla": -10, "peso_resolucion": 60}, "body.peso_sla"),
        ({"umbral_riesgo": 101}, "body.umbral_riesgo"),
        ({"inflacion_anual": "50.01"}, "body.inflacion_anual"),
        ({"inflacion_anual": "4.555"}, "body.inflacion_anual"),
        ({"otro": 1}, "body.otro"),
    ],
)
async def test_valores_fuera_de_rango(
    cliente: httpx.AsyncClient, admin: Cabeceras, cambio: dict[str, Any], campo: str
) -> None:
    respuesta = await cliente.put("/configuracion", json={**INICIAL, **cambio}, headers=admin)
    assert respuesta.status_code == 422
    assert campo in {e["campo"] for e in respuesta.json()["errores"]}


async def test_la_configuracion_cambia_los_calculos(
    cliente: httpx.AsyncClient, comprador: Cabeceras, admin: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=15))
    antes = (await cliente.get("/tablero", headers=comprador)).json()
    assert antes["en_riesgo"] < antes["total_proveedores"]
    await cliente.put("/configuracion", json={**INICIAL, "umbral_riesgo": 100}, headers=admin)
    despues = (await cliente.get("/tablero", headers=comprador)).json()
    assert despues["en_riesgo"] == despues["total_proveedores"]


async def test_registro_de_modelos_vacio(cliente: httpx.AsyncClient, comprador: Cabeceras) -> None:
    respuesta = await cliente.get("/modelos", headers=comprador)
    assert respuesta.json() == {"entrenando": False, "activo": None, "elementos": []}


async def test_un_segundo_entrenamiento_mientras_corre_el_primero(
    app: FastAPI,
    cliente: httpx.AsyncClient,
    admin: Cabeceras,
    comprador: Cabeceras,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    liberar = threading.Event()

    def entrenar_lento(*_argumentos: object) -> None:
        liberar.wait(timeout=10)
        raise DatosInsuficientes("prueba")

    monkeypatch.setattr(entrenamiento, "entrenar", entrenar_lento)
    primera = await cliente.post("/modelos/entrenar", headers=admin)
    assert (primera.status_code, primera.json()) == (202, {"entrenando": True})
    segunda = await cliente.post("/modelos/entrenar", headers=admin)
    assert (segunda.status_code, segunda.json()["codigo"]) == (409, "entrenamiento_en_curso")
    assert (await cliente.get("/modelos", headers=comprador)).json()["entrenando"] is True
    liberar.set()
    await app.state.entrenador.esperar()
    assert (await cliente.get("/modelos", headers=comprador)).json()["entrenando"] is False


async def test_entrenar_registra_el_modelo(
    app: FastAPI,
    cliente: httpx.AsyncClient,
    admin: Cabeceras,
    comprador: Cabeceras,
    cargar: Cargar,
) -> None:
    await cargar(generar(42, n_proveedores=15))
    assert (await cliente.post("/modelos/entrenar", headers=admin)).status_code == 202
    await app.state.entrenador.esperar()
    registro = (await cliente.get("/modelos", headers=comprador)).json()
    [modelo] = registro["elementos"]
    assert (modelo["version"], modelo["origen"], modelo["actor_nombre"]) == (1, "manual", "admin-1")
    assert "artefacto" not in modelo
    assert registro["activo"] == (1 if modelo["promovido"] else None)


async def test_datos_de_la_copia_local(
    cliente: httpx.AsyncClient, admin: Cabeceras, comprador: Cabeceras, cargar: Cargar
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    assert (await cliente.get("/datos", headers=comprador)).status_code == 403
    cuerpo = (await cliente.get("/datos", headers=admin)).json()
    assert cuerpo["registros"] == {
        "proveedores": 15,
        "servicios": len(datos.servicios),
        "contratos": len({fila["folio"] for fila in datos.contratos}),
        "lineas_contrato": len(datos.contratos),
        "desempeno": len(datos.desempeno),
        "tipo_cambio": len(datos.tipo_cambio),
    }
    assert cuerpo["ultimo_evento"] is not None
    assert (cuerpo["modelo"], cuerpo["entrenando"]) == (None, False)
```

Cree `services/inteligencia/tests/test_api_permisos.py`:

```python
import re

import httpx
import pytest
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI

pytestmark = pytest.mark.integracion

SOLO_ADMIN = {
    ("PUT", "/configuracion"),
    ("POST", "/modelos/entrenar"),
    ("GET", "/datos"),
}


async def test_todas_las_rutas_exigen_su_rol(
    app: FastAPI, cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    externo = {"Authorization": f"Bearer {claves.token('proveedor')}"}
    comprador = {"Authorization": f"Bearer {claves.token('comprador')}"}
    # app.routes no aplana los routers incluidos: se recorre el esquema OpenAPI.
    rutas = [
        (metodo.upper(), ruta)
        for ruta, metodos in app.openapi()["paths"].items()
        if not ruta.startswith("/salud")
        for metodo in metodos
    ]
    assert len(rutas) >= 15  # que el recorrido no quede vacío si cambia cómo se declaran
    assert SOLO_ADMIN <= set(rutas)
    for metodo, plantilla in rutas:
        ruta = re.sub(r"\{[^}]+\}", "x", plantilla)
        sin_token = await cliente.request(metodo, ruta)
        assert sin_token.status_code == 401, (metodo, plantilla)
        de_externo = await cliente.request(metodo, ruta, headers=externo)
        assert de_externo.status_code == 403, (metodo, plantilla)
        if (metodo, plantilla) in SOLO_ADMIN:
            de_comprador = await cliente.request(metodo, ruta, headers=comprador)
            assert de_comprador.status_code == 403, (metodo, plantilla)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest services/inteligencia/tests/test_api_proveedores.py services/inteligencia/tests/test_api_ajustes.py services/inteligencia/tests/test_api_permisos.py -q`
Expected: FAIL; las rutas nuevas responden 404.

- [ ] **Step 3: Implement the schemas**

Agregue a `services/inteligencia/src/inteligencia/api/esquemas.py` (con `from datetime import date, datetime` y `from typing import Annotated, Literal`, y `Field` de pydantic):

```python
Categoria = Literal["licencia_saas", "nube", "consultoria", "soporte"]
Confianza = Literal["normal", "baja"]
Peso = Annotated[int, Field(ge=0, le=100)]


class ProveedorResumen(BaseModel):
    id: str
    rfc: str
    nombre: str
    tamano: str
    categorias: list[str]
    activo: bool
    puntuacion: float | None  # None: sin desempeño registrado
    confianza: Confianza | None  # baja: menos de 6 meses de historial
    tendencia: float | None  # puntos contra hace 3 meses
    gasto_anual: Decimal  # MXN, contratos vigentes
    contratos_vigentes: int
    alertas: int
    en_riesgo: bool


class PaginaProveedores(BaseModel):
    total: int
    elementos: list[ProveedorResumen]


class Componente(BaseModel):
    kpi: str
    valor: float  # promedio ponderado de 12 meses
    mediana_categoria: float
    percentil: float  # 0 a 100, más es mejor


class PuntoPuntuacion(BaseModel):
    mes: date
    puntuacion: float


class PuntuacionSalida(BaseModel):
    proveedor_id: str
    categoria: str | None  # la principal: contra la que se compara
    puntuacion: float | None
    sin_ajuste: float | None
    meses: int
    historial_corto: bool
    tendencia: float | None
    componentes: list[Componente]
    historial: list[PuntoPuntuacion]


class MercadoLinea(BaseModel):
    contrato_id: str
    folio: str
    codigo_servicio: str
    servicio: str
    moneda: str
    precio: Decimal
    posicion: Literal["bajo_p25", "justo", "sobre_p75"] | None  # None: sin referencia
    p25: Decimal | None
    p50: Decimal | None
    p75: Decimal | None
    metodo: Literal["linea_base", "modelo"] | None
    confianza: Confianza | None
    ahorro_potencial: Decimal


class FilaRanking(BaseModel):
    posicion: int
    proveedor_id: str
    nombre: str
    categoria: str
    puntuacion: float
    componentes: dict[str, float]
    meses: int
    historial_corto: bool
    tendencia: float | None


class ConfiguracionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    peso_sla: int
    peso_resolucion: int
    peso_incidentes: int
    peso_entregas: int
    peso_satisfaccion: int
    umbral_riesgo: int
    inflacion_anual: Decimal
    actualizado_en: datetime | None
    actualizado_por: str | None


class ConfiguracionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    peso_sla: Peso
    peso_resolucion: Peso
    peso_incidentes: Peso
    peso_entregas: Peso
    peso_satisfaccion: Peso
    umbral_riesgo: Annotated[int, Field(ge=0, le=100)]
    inflacion_anual: Annotated[Decimal, Field(ge=0, le=50, decimal_places=2)]


class ModeloSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    entrenado_en: datetime
    origen: str
    actor_nombre: str
    observaciones: int
    datos_hasta: date
    mape: Decimal
    mape_linea_base: Decimal
    cobertura: Decimal
    pinball: Decimal
    promovido: bool


class RegistroModelos(BaseModel):
    entrenando: bool
    activo: int | None  # versión en uso; None: se usa la línea base
    elementos: list[ModeloSalida]


class EntrenamientoIniciado(BaseModel):
    entrenando: bool


class DatosSalida(BaseModel):
    registros: dict[str, int]
    ultimo_evento: datetime | None
    modelo: ModeloSalida | None  # el activo
    entrenando: bool
```

- [ ] **Step 4: Implement the routes**

Cree `services/inteligencia/src/inteligencia/api/proveedores.py`:

```python
"""Proveedores con su puntuación, su precio frente al mercado y el ranking."""

import statistics
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from comun.errores import ErrorDominio
from fastapi import APIRouter, Query

from inteligencia.api import esquemas
from inteligencia.api.dependencias import Ctx
from inteligencia.api.esquemas import unitario
from inteligencia.contexto import Contexto, LineaMercado
from inteligencia.dominio.puntuacion import KPIS
from inteligencia.dominio.tablero import CENTAVOS, a_mxn, tipo_cambio_en
from inteligencia.modelos import Proveedor

router = APIRouter(tags=["proveedores"])

Orden = Literal["nombre", "puntuacion", "gasto_anual", "contratos_vigentes", "alertas"]


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para que "codigo" encuentre "Código"."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


def _proveedor(contexto: Contexto, proveedor_id: UUID) -> Proveedor:
    proveedor = contexto.proveedores.get(str(proveedor_id))
    if proveedor is None:
        raise ErrorDominio(
            404, "No encontrado", "El proveedor no existe.", {"codigo": "proveedor_no_encontrado"}
        )
    return proveedor


def _redondear(valor: float | None) -> float | None:
    return None if valor is None else round(valor, 1)


def _resumenes(contexto: Contexto) -> list[esquemas.ProveedorResumen]:
    ultimo = tipo_cambio_en(contexto.tipos_cambio, contexto.hoy)
    gasto: dict[str, Decimal] = defaultdict(Decimal)
    vigentes: Counter[str] = Counter()
    for contrato in contexto.contratos:
        if contrato.vigente(contexto.hoy):
            mensual = a_mxn(contrato.valor_mensual(), contrato.moneda, ultimo)
            gasto[contrato.proveedor_id] += mensual * 12
            vigentes[contrato.proveedor_id] += 1
    alertas = Counter(a.proveedor_id for a in contexto.alertas)
    en_riesgo = {a.proveedor_id for a in contexto.alertas if a.tipo == "riesgo"}
    resumenes = []
    for pid, proveedor in contexto.proveedores.items():
        actual = contexto.puntuaciones.get(pid)
        resumenes.append(
            esquemas.ProveedorResumen(
                id=pid,
                rfc=proveedor.rfc,
                nombre=proveedor.nombre,
                tamano=proveedor.tamano,
                categorias=list(proveedor.categorias),
                activo=proveedor.activo,
                puntuacion=None if actual is None else round(actual.puntuacion, 1),
                confianza=None
                if actual is None
                else ("baja" if actual.historial_corto else "normal"),
                tendencia=_redondear(contexto.tendencia(pid)),
                gasto_anual=gasto[pid].quantize(CENTAVOS),
                contratos_vigentes=vigentes[pid],
                alertas=alertas[pid],
                en_riesgo=pid in en_riesgo,
            )
        )
    return resumenes


@router.get("/proveedores")
async def listar(
    contexto: Ctx,
    busqueda: Annotated[str | None, Query(max_length=100)] = None,
    categoria: esquemas.Categoria | None = None,
    estado: Literal["activos", "inactivos"] | None = None,
    en_riesgo: bool | None = None,
    orden: Orden = "nombre",
    direccion: Literal["asc", "desc"] = "asc",
    pagina: Annotated[int, Query(ge=1, le=1000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
) -> esquemas.PaginaProveedores:
    texto = _normalizar((busqueda or "").strip())
    filas = [
        r
        for r in _resumenes(contexto)
        if (not texto or texto in _normalizar(f"{r.nombre} {r.rfc}"))
        and (categoria is None or categoria in r.categorias)
        and (estado is None or r.activo == (estado == "activos"))
        and (en_riesgo is None or r.en_riesgo == en_riesgo)
    ]
    filas.sort(key=lambda r: (_normalizar(r.nombre), r.id))
    if orden == "nombre":
        if direccion == "desc":
            filas.reverse()
    else:
        # Un proveedor sin puntuación (sin desempeño) va al final en las dos direcciones.
        con_valor = [r for r in filas if getattr(r, orden) is not None]
        con_valor.sort(key=lambda r: getattr(r, orden), reverse=direccion == "desc")
        filas = con_valor + [r for r in filas if getattr(r, orden) is None]
    return esquemas.PaginaProveedores(
        total=len(filas), elementos=filas[(pagina - 1) * tamano : pagina * tamano]
    )


@router.get("/proveedores/{proveedor_id}/puntuacion")
async def puntuacion(proveedor_id: UUID, contexto: Ctx) -> esquemas.PuntuacionSalida:
    proveedor = _proveedor(contexto, proveedor_id)
    pid = str(proveedor_id)
    categoria = proveedor.categorias[0] if proveedor.categorias else None
    actual = contexto.puntuaciones.get(pid)
    if actual is None:
        return esquemas.PuntuacionSalida(
            proveedor_id=pid,
            categoria=categoria,
            puntuacion=None,
            sin_ajuste=None,
            meses=0,
            historial_corto=True,
            tendencia=None,
            componentes=[],
            historial=[],
        )
    # Todo proveedor puntuado tiene categoría (contexto.construir lo garantiza).
    de_su_categoria = [
        p
        for otro, p in contexto.puntuaciones.items()
        if contexto.proveedores[otro].categorias[0] == categoria
    ]
    return esquemas.PuntuacionSalida(
        proveedor_id=pid,
        categoria=categoria,
        puntuacion=round(actual.puntuacion, 1),
        sin_ajuste=round(actual.sin_ajuste, 1),
        meses=actual.meses,
        historial_corto=actual.historial_corto,
        tendencia=_redondear(contexto.tendencia(pid)),
        componentes=[
            esquemas.Componente(
                kpi=kpi,
                valor=round(actual.valores[kpi], 2),
                mediana_categoria=round(statistics.median(p.valores[kpi] for p in de_su_categoria), 2),
                percentil=round(actual.componentes[kpi], 1),
            )
            for kpi in KPIS
        ],
        historial=[
            esquemas.PuntoPuntuacion(mes=mes, puntuacion=round(valor, 1))
            for mes, valor in contexto.historial.get(pid, [])
        ],
    )


def _linea(m: LineaMercado) -> esquemas.MercadoLinea:
    ref = m.referencia
    return esquemas.MercadoLinea(
        contrato_id=m.contrato.id,
        folio=m.contrato.folio,
        codigo_servicio=m.linea.codigo,
        servicio=m.linea.servicio,
        moneda=m.contrato.moneda,
        precio=m.linea.precio,
        posicion=m.posicion,
        p25=None if ref is None else unitario(ref.banda.p25),
        p50=None if ref is None else unitario(ref.banda.p50),
        p75=None if ref is None else unitario(ref.banda.p75),
        metodo=None if ref is None else ref.metodo,
        confianza=None if ref is None else ref.confianza,
        ahorro_potencial=m.ahorro,
    )


@router.get("/proveedores/{proveedor_id}/mercado")
async def mercado(proveedor_id: UUID, contexto: Ctx) -> list[esquemas.MercadoLinea]:
    """Cada línea de sus contratos vigentes frente al precio justo de su servicio."""
    _proveedor(contexto, proveedor_id)
    pid = str(proveedor_id)
    propias = [m for m in contexto.mercado if m.contrato.proveedor_id == pid]
    return [_linea(m) for m in sorted(propias, key=lambda m: (m.contrato.folio, m.linea.codigo))]


@router.get("/ranking")
async def ranking(
    contexto: Ctx, categoria: esquemas.Categoria | None = None
) -> list[esquemas.FilaRanking]:
    candidatos = [
        (pid, p)
        for pid, p in contexto.puntuaciones.items()
        if contexto.proveedores[pid].activo
        and (categoria is None or categoria in contexto.proveedores[pid].categorias)
    ]
    candidatos.sort(
        key=lambda par: (-par[1].puntuacion, _normalizar(contexto.proveedores[par[0]].nombre))
    )
    return [
        esquemas.FilaRanking(
            posicion=posicion,
            proveedor_id=pid,
            nombre=contexto.proveedores[pid].nombre,
            categoria=contexto.proveedores[pid].categorias[0],
            puntuacion=round(p.puntuacion, 1),
            componentes={kpi: round(p.componentes[kpi], 1) for kpi in KPIS},
            meses=p.meses,
            historial_corto=p.historial_corto,
            tendencia=_redondear(contexto.tendencia(pid)),
        )
        for posicion, (pid, p) in enumerate(candidatos, start=1)
    ]
```

Cree `services/inteligencia/src/inteligencia/api/ajustes.py` (no se llama `configuracion.py`: `crear_app` tiene un parámetro con ese nombre y taparía el módulo):

```python
"""Configuración de la puntuación, modelo de precios y estado de la copia local."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from comun.errores import ErrorDominio
from comun.outbox import registrar_evento
from fastapi import APIRouter, Request
from sqlalchemy import func, select

from inteligencia import consultas
from inteligencia.api import esquemas
from inteligencia.api.dependencias import Admin, Interno, Sesion
from inteligencia.db import Base
from inteligencia.dominio.puntuacion import validar_pesos
from inteligencia.entrenamiento import Entrenador
from inteligencia.modelos import (
    Configuracion,
    Contrato,
    Desempeno,
    EventoProcesado,
    LineaContrato,
    ModeloBenchmark,
    Outbox,
    Proveedor,
    Servicio,
    TipoCambio,
)

router = APIRouter(tags=["configuracion"])

MAX_MODELOS = 50
DOS_DECIMALES = Decimal("0.01")
ENTIDADES: dict[str, type[Base]] = {
    "proveedores": Proveedor,
    "servicios": Servicio,
    "contratos": Contrato,
    "lineas_contrato": LineaContrato,
    "desempeno": Desempeno,
    "tipo_cambio": TipoCambio,
}


def _para_evento(valor: Any) -> Any:
    return f"{valor:.2f}" if isinstance(valor, Decimal) else valor


@router.get("/configuracion")
async def leer_configuracion(sesion: Sesion, _: Interno) -> esquemas.ConfiguracionSalida:
    return esquemas.ConfiguracionSalida.model_validate(await consultas.configuracion(sesion))


@router.put("/configuracion")
async def guardar_configuracion(
    datos: esquemas.ConfiguracionEntrada, sesion: Sesion, usuario: Admin
) -> esquemas.ConfiguracionSalida:
    nuevos = datos.model_dump()
    nuevos["inflacion_anual"] = nuevos["inflacion_anual"].quantize(DOS_DECIMALES)
    error = validar_pesos({c: v for c, v in nuevos.items() if c.startswith("peso_")})
    if error is not None:
        raise ErrorDominio(
            422,
            "Solicitud inválida",
            "Revise los campos indicados.",
            {"codigo": "pesos_invalidos", "errores": [{"campo": "body.pesos", "mensaje": error}]},
        )
    async with sesion.begin():
        fila = await sesion.get(Configuracion, 1, with_for_update=True)
        if fila is None:
            raise LookupError("Falta la fila de configuración (la crea la migración 0001)")
        cambios = [
            {"campo": campo, "anterior": _para_evento(getattr(fila, campo)), "nuevo": _para_evento(valor)}
            for campo, valor in nuevos.items()
            if getattr(fila, campo) != valor
        ]
        if cambios:
            for campo, valor in nuevos.items():
                setattr(fila, campo, valor)
            fila.actualizado_en = datetime.now(UTC)
            fila.actualizado_por = usuario.nombre
            registrar_evento(
                sesion,
                Outbox,
                "configuracion.actualizada",
                {"cambios": cambios, "actor": {"id": usuario.id, "nombre": usuario.nombre}},
            )
    return esquemas.ConfiguracionSalida.model_validate(fila)


@router.get("/modelos")
async def modelos(request: Request, sesion: Sesion, _: Interno) -> esquemas.RegistroModelos:
    registros = await sesion.scalars(
        select(ModeloBenchmark).order_by(ModeloBenchmark.version.desc()).limit(MAX_MODELOS)
    )
    activo = await consultas.modelo_activo(sesion)
    entrenador: Entrenador = request.app.state.entrenador
    return esquemas.RegistroModelos(
        entrenando=entrenador.entrenando,
        activo=None if activo is None else activo.version,
        elementos=[esquemas.ModeloSalida.model_validate(r) for r in registros],
    )


@router.post("/modelos/entrenar", status_code=202)
async def entrenar(request: Request, usuario: Admin) -> esquemas.EntrenamientoIniciado:
    entrenador: Entrenador = request.app.state.entrenador
    if not entrenador.iniciar("manual", {"id": usuario.id, "nombre": usuario.nombre}):
        raise ErrorDominio(
            409,
            "Conflicto",
            "Ya hay un entrenamiento del modelo de precios en curso; espere a que termine.",
            {"codigo": "entrenamiento_en_curso"},
        )
    return esquemas.EntrenamientoIniciado(entrenando=True)


@router.get("/datos")
async def datos(request: Request, sesion: Sesion, _: Admin) -> esquemas.DatosSalida:
    """Lo que llegó a la copia local, para la tarjeta "Datos y modelo" del Panel."""
    fila = (
        await sesion.execute(
            select(
                *(
                    select(func.count()).select_from(modelo).scalar_subquery()
                    for modelo in ENTIDADES.values()
                ),
                select(func.max(EventoProcesado.procesado_en)).scalar_subquery(),
            )
        )
    ).one()
    activo = await consultas.modelo_activo(sesion)
    entrenador: Entrenador = request.app.state.entrenador
    return esquemas.DatosSalida(
        registros=dict(zip(ENTIDADES, fila[:-1], strict=True)),
        ultimo_evento=fila[-1],
        modelo=None if activo is None else esquemas.ModeloSalida.model_validate(activo),
        entrenando=entrenador.entrenando,
    )
```

En `services/inteligencia/src/inteligencia/main.py`, importe también `ajustes` y `proveedores` de `inteligencia.api` y agregue:

```python
    app.include_router(proveedores.router)
    app.include_router(ajustes.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest services/inteligencia -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio.

- [ ] **Step 6: Commit**

```bash
git add services/inteligencia
git commit -m "feat(inteligencia): API de proveedores, ranking, configuración, modelos y datos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Actividad — configuración y entrenamientos de inteligencia

**Files:**
- Create: `services/administracion/alembic/versions/0002_origen_inteligencia.py`
- Modify:
  - `services/administracion/src/administracion/eventos.py` (traduce `configuracion.actualizada` y `modelo.entrenado`)
  - `services/administracion/src/administracion/modelos.py` (la restricción de `origen` admite `inteligencia`)
  - `services/administracion/src/administracion/bitacora.py` (grupo `inteligencia`)
  - `services/administracion/src/administracion/textos.py`
  - `services/administracion/tests/test_eventos.py`, `test_textos.py` y `test_actividad.py`
  - `web/src/actividad.ts`, `web/src/actividad.test.ts`
  - `web/src/paginas/Actividad.tsx`, `web/src/paginas/Actividad.test.tsx`
  - `web/src/ayuda.ts` (el artículo de Actividad)

**Interfaces:**
- Consumes:
  - los payloads de `configuracion.actualizada` y `modelo.entrenado` (Tasks 11 y 13);
  - `administracion.eventos.atendedor` (Task 3);
  - la cola `administracion.actividad`, que ya enlaza `configuracion.*` y `modelo.*` (Task 2).
- Produces:
  - `Registro` gana `origen: str = "proveedores"` (último campo).
  - Registros de bitácora con `origen = "inteligencia"` y `clave_origen = "inteligencia:<event_id>"`:
    - `configuracion.actualizada`: objeto `("configuracion", "puntuacion", "configuración de la puntuación")`, detalle `{"cambios": [...]}`;
    - `modelo.entrenado`: objeto `("modelo", "<version>", "modelo de precios v<version>")`, detalle `{"version", "mape", "mape_linea_base", "promovido", "origen"}`.
  - `GrupoTipo` gana `"inteligencia"` (tipos `configuracion.*` y `modelo.*`).
  - Textos:
    - "Cambió la configuración de la puntuación: pesos, umbral de riesgo, inflación anual" (solo los campos cambiados; los cinco pesos se nombran una vez como "pesos");
    - "Reentrenó el modelo de precios: versión 4, MAPE 11.2 %, promovido";
    - "Reentrenó el modelo de precios: versión 5, MAPE 9.3 %, no se promovió (no mejoró la línea base)".

- [ ] **Step 1: Write the failing backend tests**

En `services/administracion/tests/test_eventos.py`, agregue:

```python
def test_traduce_un_cambio_de_configuracion() -> None:
    cambios = [
        {"campo": "peso_sla", "anterior": 30, "nuevo": 40},
        {"campo": "inflacion_anual", "anterior": "4.50", "nuevo": "5.20"},
    ]
    sobre = _sobre("configuracion.actualizada", {"cambios": cambios, "actor": ADMIN}, "e-9")
    assert traducir(sobre) == Registro(
        tipo="configuracion.actualizada",
        actor=Actor("admin-1", "admin1"),
        objeto=Objeto("configuracion", "puntuacion", "configuración de la puntuación"),
        detalle={"cambios": cambios},
        resultado="exito",
        clave_origen="inteligencia:e-9",
        fecha=datetime(2026, 10, 9, 15, tzinfo=UTC),
        origen="inteligencia",
    )


ENTRENAMIENTO = {
    "version": 4,
    "mape": 0.112,
    "mape_linea_base": 0.12,
    "cobertura": 0.48,
    "promovido": True,
    "origen": "automatico",
    "actor": {"id": None, "nombre": "Sistema (automático)"},
}


@pytest.mark.parametrize("promovido", [True, False])
def test_traduce_un_entrenamiento_del_modelo(promovido: bool) -> None:
    registro = traducir(_sobre("modelo.entrenado", {**ENTRENAMIENTO, "promovido": promovido}))
    assert registro is not None
    assert (registro.tipo, registro.origen) == ("modelo.entrenado", "inteligencia")
    assert registro.actor == Actor(None, "Sistema (automático)")
    assert registro.objeto == Objeto("modelo", "4", "modelo de precios v4")
    assert registro.detalle == {
        "version": 4,
        "mape": 0.112,
        "mape_linea_base": 0.12,
        "promovido": promovido,
        "origen": "automatico",
    }
    assert registro.clave_origen.startswith("inteligencia:")


@pytest.mark.integracion
async def test_guarda_los_registros_de_inteligencia_una_sola_vez(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    sobre = _sobre("modelo.entrenado", ENTRENAMIENTO)
    atender = atendedor(fabrica)
    await atender(sobre)
    await atender(sobre)  # el mismo evento entregado dos veces
    async with fabrica() as sesion:
        filas = await sesion.execute(
            text("SELECT origen, clave_origen, objeto_nombre, actor_id FROM actividad")
        )
        assert [tuple(f) for f in filas] == [
            ("inteligencia", f"inteligencia:{sobre['event_id']}", "modelo de precios v4", None)
        ]
```

y en `test_un_sobre_mal_formado_es_invalido`, al final:

```python
    with pytest.raises(EventoInvalido):
        traducir(_sobre("modelo.entrenado", {**ENTRENAMIENTO, "version": "cuatro"}))
    with pytest.raises(EventoInvalido):
        traducir(_sobre("configuracion.actualizada", {"cambios": ["peso_sla"], "actor": ADMIN}))
```

Si `ENTRENAMIENTO` queda definido después de su primer uso, súbalo junto a `ADMIN`. Asegúrese de que `text`, `AsyncSession` y `async_sessionmaker` sigan importados (la Task 3 pudo haber quitado alguno).

En `services/administracion/tests/test_textos.py`, agregue al final de `CASOS`:

```python
    (
        "configuracion.actualizada",
        "configuración de la puntuación",
        {
            "cambios": [
                {"campo": "peso_sla", "anterior": 30, "nuevo": 40},
                {"campo": "peso_satisfaccion", "anterior": 15, "nuevo": 5},
                {"campo": "umbral_riesgo", "anterior": 40, "nuevo": 35},
                {"campo": "inflacion_anual", "anterior": "4.50", "nuevo": "5.20"},
            ]
        },
        "Cambió la configuración de la puntuación: pesos, umbral de riesgo, inflación anual",
    ),
    (
        "configuracion.actualizada",
        "configuración de la puntuación",
        {},
        "Cambió la configuración de la puntuación",
    ),
    (
        "modelo.entrenado",
        "modelo de precios v4",
        {"version": 4, "mape": 0.112, "promovido": True},
        "Reentrenó el modelo de precios: versión 4, MAPE 11.2 %, promovido",
    ),
    (
        "modelo.entrenado",
        "modelo de precios v5",
        {"version": 5, "mape": 0.0934, "promovido": False},
        "Reentrenó el modelo de precios: versión 5, MAPE 9.3 %, no se promovió "
        "(no mejoró la línea base)",
    ),
```

En `services/administracion/tests/test_actividad.py`, agregue:

```python
async def test_filtro_de_inteligencia(
    cliente: httpx.AsyncClient, admin: dict[str, str], fabrica: async_sessionmaker[AsyncSession]
) -> None:
    async with fabrica() as sesion:
        await registrar(
            sesion,
            "configuracion.actualizada",
            Actor("admin-1", "admin1"),
            objeto=Objeto("configuracion", "puntuacion", "configuración de la puntuación"),
            origen="inteligencia",
        )
        await registrar(
            sesion,
            "modelo.entrenado",
            Actor(None, "Sistema (automático)"),
            objeto=Objeto("modelo", "1", "modelo de precios v1"),
            detalle={"version": 1, "mape": 0.08, "promovido": True},
            origen="inteligencia",
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
        await cliente.get("/actividad", params={"tipo": "inteligencia"}, headers=admin)
    ).json()
    assert sorted(e["tipo"] for e in cuerpo["elementos"]) == [
        "configuracion.actualizada",
        "modelo.entrenado",
    ]
```

- [ ] **Step 2: Run the backend tests to verify they fail**

Run: `uv run pytest services/administracion -q`
Expected: FAIL. `traducir` devuelve `None` para los tipos nuevos, `Registro` no acepta `origen`, `tipo=inteligencia` responde 422 y la base rechaza `origen = 'inteligencia'`.

- [ ] **Step 3: Implement the backend**

En `services/administracion/src/administracion/eventos.py`:
- agregue la constante `TIPOS_INTELIGENCIA = ("configuracion.", "modelo.")  # los publica inteligencia`;
- agregue el campo `origen: str = "proveedores"` al final de `Registro`;
- en `traducir`, reemplace la línea de `clave` por:

```python
        origen = "inteligencia" if tipo.startswith(TIPOS_INTELIGENCIA) else "proveedores"
        clave = f"{origen}:{sobre['event_id']}"
```

- antes del `return None` final de `traducir`, agregue:

```python
        if tipo == "configuracion.actualizada":
            cambios = [
                {"campo": str(c["campo"]), "anterior": c["anterior"], "nuevo": c["nuevo"]}
                for c in payload["cambios"]
            ]
            return Registro(
                tipo,
                _actor(payload),
                Objeto("configuracion", "puntuacion", "configuración de la puntuación"),
                {"cambios": cambios},
                "exito",
                clave,
                fecha,
                origen,
            )
        if tipo == "modelo.entrenado":
            version = int(payload["version"])
            detalle = {
                "version": version,
                "mape": float(payload["mape"]),
                "mape_linea_base": float(payload["mape_linea_base"]),
                "promovido": bool(payload["promovido"]),
                "origen": str(payload["origen"]),
            }
            return Registro(
                tipo,
                _actor(payload),
                Objeto("modelo", str(version), f"modelo de precios v{version}"),
                detalle,
                "exito",
                clave,
                fecha,
                origen,
            )
```

- en `guardar`, cambie `origen="proveedores"` por `origen=registro.origen`.

En `services/administracion/src/administracion/modelos.py`, la restricción de `Actividad` queda:

```python
        CheckConstraint(
            "origen IN ('keycloak', 'proveedores', 'administracion', 'inteligencia')",
            name="origen",
        ),
```

Cree `services/administracion/alembic/versions/0002_origen_inteligencia.py`:

```python
"""La bitácora acepta registros que vienen de inteligencia.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_actividad_origen"), "actividad", type_="check")
    op.create_check_constraint(
        op.f("ck_actividad_origen"),
        "actividad",
        "origen IN ('keycloak', 'proveedores', 'administracion', 'inteligencia')",
    )


def downgrade() -> None:
    # Falla si ya hay registros de inteligencia: la bitácora no se borra.
    op.drop_constraint(op.f("ck_actividad_origen"), "actividad", type_="check")
    op.create_check_constraint(
        op.f("ck_actividad_origen"),
        "actividad",
        "origen IN ('keycloak', 'proveedores', 'administracion')",
    )
```

En `services/administracion/src/administracion/bitacora.py`:

```python
GrupoTipo = Literal["sesiones", "usuarios", "importaciones", "catalogo", "inteligencia"]
PREFIJOS_GRUPO: dict[str, tuple[str, ...]] = {
    "sesiones": ("sesion.",),
    "usuarios": ("usuario.",),
    "importaciones": ("importacion.",),
    "catalogo": ("servicio.",),
    "inteligencia": ("configuracion.", "modelo."),
}
```

y en `_filtrada`:

```python
    if filtro.tipo:
        consulta = consulta.where(
            or_(*(Actividad.tipo.startswith(p) for p in PREFIJOS_GRUPO[filtro.tipo]))
        )
```

Busque otros usos de `PREFIJOS_GRUPO` (`grep -rn PREFIJOS_GRUPO services/administracion`) y ajústelos a la tupla.

En `services/administracion/src/administracion/textos.py`, agregue antes de `TEXTOS`:

```python
NOMBRES_AJUSTE = {"umbral_riesgo": "umbral de riesgo", "inflacion_anual": "inflación anual"}
CONFIGURACION = "Cambió la configuración de la puntuación"


def _ajustes(a: Actividad) -> str:
    """Los campos cambiados en lenguaje llano; los cinco pesos se nombran una vez."""
    cambios = a.detalle.get("cambios")
    nombres: list[str] = []
    for cambio in cambios if isinstance(cambios, list) else []:
        campo = str(cambio.get("campo", "")) if isinstance(cambio, dict) else ""
        nombre = "pesos" if campo.startswith("peso_") else NOMBRES_AJUSTE.get(campo, campo)
        if nombre not in nombres:
            nombres.append(nombre)
    return f"{CONFIGURACION}: {', '.join(nombres)}" if nombres else CONFIGURACION


def _entrenamiento(a: Actividad) -> str:
    mape = a.detalle.get("mape")
    porcentaje = f"{mape * 100:.1f}" if isinstance(mape, int | float) else "?"
    resultado = (
        "promovido"
        if a.detalle.get("promovido")
        else "no se promovió (no mejoró la línea base)"
    )
    return (
        f"Reentrenó el modelo de precios: versión {a.detalle.get('version', '?')}, "
        f"MAPE {porcentaje} %, {resultado}"
    )
```

y al final del diccionario `TEXTOS`:

```python
    "configuracion.actualizada": _ajustes,
    "modelo.entrenado": _entrenamiento,
```

- [ ] **Step 4: Run the backend tests**

Run: `uv run pytest services/administracion -q`
Expected: todo pasa salvo `test_los_mismos_tipos_que_la_web`, que falla hasta el paso 6 porque la web aún no tiene los tipos nuevos.

- [ ] **Step 5: Write the failing web tests**

En `web/src/actividad.test.ts`, agregue al `it.each`:

```ts
    [
      "configuracion.actualizada",
      {
        cambios: [
          { campo: "peso_sla", anterior: 30, nuevo: 40 },
          { campo: "peso_entregas", anterior: 15, nuevo: 5 },
          { campo: "inflacion_anual", anterior: "4.50", nuevo: "5.20" },
        ],
      },
      "Cambió la configuración de la puntuación: pesos, inflación anual",
    ],
    [
      "modelo.entrenado",
      { version: 4, mape: 0.112, promovido: true },
      "Reentrenó el modelo de precios: versión 4, MAPE 11.2 %, promovido",
    ],
    [
      "modelo.entrenado",
      { version: 5, mape: 0.0934, promovido: false },
      "Reentrenó el modelo de precios: versión 5, MAPE 9.3 %, no se promovió (no mejoró la línea base)",
    ],
```

En `web/src/paginas/Actividad.test.tsx`, agregue dentro del `describe`:

```tsx
  it("filtra la configuración y los entrenamientos de inteligencia", async () => {
    const simulado = api()
    renderizarPagina(<Actividad />, { ruta: "/sistema/actividad" })
    await screen.findByText("Importó 1,250 contratos")
    await userEvent.click(screen.getByRole("button", { name: "Inteligencia" }))
    expect(ubicacionActual()).toBe("/sistema/actividad?tipo=inteligencia")
    await vi.waitFor(() =>
      expect(llamadasDeLista(simulado).at(-1)).toContain("tipo=inteligencia")
    )
  })
```

Run: `cd web && npx vitest run src/actividad.test.ts src/paginas/Actividad.test.tsx`
Expected: FAIL; los tipos nuevos se muestran tal cual y no hay chip "Inteligencia".

- [ ] **Step 6: Implement the web**

En `web/src/actividad.ts`:
- agregue `"configuracion.actualizada"` y `"modelo.entrenado"` al final de `TIPOS_ACTIVIDAD`;
- agregue antes de `TEXTOS`:

```ts
const NOMBRES_AJUSTE: Record<string, string> = {
  umbral_riesgo: "umbral de riesgo",
  inflacion_anual: "inflación anual",
}
const CONFIGURACION = "Cambió la configuración de la puntuación"

/** Los campos cambiados en lenguaje llano; los cinco pesos se nombran una vez. */
function ajustes(a: RegistroActividad): string {
  const cambios = Array.isArray(a.detalle.cambios) ? a.detalle.cambios : []
  const nombres: string[] = []
  for (const cambio of cambios) {
    const campo =
      cambio && typeof cambio === "object"
        ? String((cambio as { campo?: unknown }).campo ?? "")
        : ""
    const nombre = campo.startsWith("peso_")
      ? "pesos"
      : (NOMBRES_AJUSTE[campo] ?? campo)
    if (!nombres.includes(nombre)) nombres.push(nombre)
  }
  return nombres.length
    ? `${CONFIGURACION}: ${nombres.join(", ")}`
    : CONFIGURACION
}

function entrenamiento(a: RegistroActividad): string {
  const mape = a.detalle.mape
  const porcentaje = typeof mape === "number" ? (mape * 100).toFixed(1) : "?"
  const resultado = a.detalle.promovido
    ? "promovido"
    : "no se promovió (no mejoró la línea base)"
  return `Reentrenó el modelo de precios: versión ${String(a.detalle.version ?? "?")}, MAPE ${porcentaje} %, ${resultado}`
}
```

- y al final de `TEXTOS`:

```ts
  "configuracion.actualizada": ajustes,
  "modelo.entrenado": entrenamiento,
```

En `web/src/paginas/Actividad.tsx`:
- agregue `["inteligencia", "Inteligencia"],` al final de `GRUPOS`;
- la descripción del estado vacío queda: `"Aquí aparecerán los inicios de sesión, las acciones sobre usuarios, las importaciones, los cambios del catálogo y los de la puntuación y el modelo de precios."`;
- la del encabezado queda: `"Quién hizo qué y cuándo: inicios de sesión, cambios de usuarios, importaciones, catálogo y puntuación. Nada de esto se puede borrar."`.

En `web/src/ayuda.ts`, el primer párrafo del artículo de Actividad queda: `"Actividad reúne los inicios de sesión (incluidos los intentos fallidos), las acciones sobre usuarios, las importaciones, los cambios del catálogo y los cambios de la configuración de la puntuación y los entrenamientos del modelo de precios. Nada de esto se puede borrar ni modificar."`.

Si alguna prueba compara las descripciones viejas, actualícela con el texto nuevo.

- [ ] **Step 7: Run all the checks**

Run: `uv run pytest services/administracion -q`, `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`; luego, en `web/`, `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check "src/**/*.{ts,tsx}"`.
Expected: todo limpio, incluida `test_los_mismos_tipos_que_la_web`.

- [ ] **Step 8: Commit**

```bash
git add services/administracion web/src
git commit -m "feat(administracion): la Actividad registra los cambios de la puntuación y los entrenamientos del modelo de precios" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Estado del sistema — inteligencia y mensajes fallidos

**Files:**
- Modify:
  - `services/administracion/src/administracion/config.py` (`inteligencia_url`)
  - `services/administracion/src/administracion/estado.py` (sexto servicio y colas de fallidos)
  - `services/administracion/tests/test_sistema.py`
  - `infra/docker-compose.yml` (`INTELIGENCIA_URL` en `administracion`)
  - `web/src/ayuda.ts` (el artículo de Estado del sistema)

**Interfaces:**
- Consumes:
  - `/salud/listo` de `inteligencia` (Task 6);
  - las colas `<cola>.dlq` de la topología (Task 2).
- Produces:
  - `Configuracion.inteligencia_url: str = "http://localhost:8000"`.
  - Comprobaciones, en este orden: `base_de_datos`, `proveedores`, `inteligencia` ("Servicio de inteligencia"), `identidad`, `mensajeria` y `correo`.
  - Detalle de `mensajeria`:
    - las colas de consumo con más de 100 mensajes listos: "Mensajes pendientes en: <cola> (<n>).";
    - las colas `.dlq` con algún mensaje: "Mensajes fallidos en: <cola> (<n>).";
    - si hay de los dos, van en ese orden, separados por un espacio.

- [ ] **Step 1: Write the failing tests**

En `services/administracion/tests/test_sistema.py`:
- en el fixture `rutas`, agregue `"intel": _ok`;
- en `cliente_sistema`, agregue `inteligencia_url="http://intel",` a la `Configuracion`;
- en `test_todo_sano`, la lista esperada de claves queda:

```python
    assert [s["clave"] for s in servicios] == [
        "base_de_datos",
        "proveedores",
        "inteligencia",
        "identidad",
        "mensajeria",
        "correo",
    ]
```

- en `test_un_servicio_caido_no_tumba_el_estado`, agregue `rutas["intel"] = error` y, al final, `assert servicios["inteligencia"]["estado"] == "caido"`;
- agregue:

```python
async def test_un_mensaje_en_una_cola_de_fallidos_es_un_problema(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    async def colas(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"name": "inteligencia.eventos", "messages_ready": 150, "messages": 150},
                {"name": "inteligencia.eventos.dlq", "messages_ready": 120, "messages": 120},
                {"name": "administracion.actividad", "messages_ready": 0, "messages": 0},
                {"name": "administracion.actividad.dlq", "messages_ready": 0, "messages": 0},
            ],
        )

    rutas["rmq"] = colas
    servicios = await _por_clave(cliente_sistema, admin)
    assert servicios["mensajeria"]["estado"] == "con_problemas"
    assert servicios["mensajeria"]["detalle"] == (
        "Mensajes pendientes en: inteligencia.eventos (150). "
        "Mensajes fallidos en: inteligencia.eventos.dlq (120)."
    )


async def test_colas_de_fallidos_vacias_no_son_problema(
    cliente_sistema: httpx.AsyncClient, admin: dict[str, str], rutas: dict[str, Manejador]
) -> None:
    async def colas(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[{"name": "inteligencia.eventos.dlq", "messages_ready": 0, "messages": 0}]
        )

    rutas["rmq"] = colas
    assert (await _por_clave(cliente_sistema, admin))["mensajeria"]["estado"] == "sano"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest services/administracion/tests/test_sistema.py -q`
Expected: FAIL. `Configuracion` no acepta `inteligencia_url` y no hay comprobación `inteligencia`.

- [ ] **Step 3: Implement**

En `services/administracion/src/administracion/config.py`, después de `proveedores_url`:

```python
    inteligencia_url: str = "http://localhost:8000"
```

En `services/administracion/src/administracion/estado.py`:
- agregue la constante `SUFIJO_FALLIDOS = ".dlq"`;
- después de `proveedores()`:

```python
    async def inteligencia() -> None:
        await obtener(f"{config.inteligencia_url}/salud/listo")
```

- reemplace el cuerpo de `mensajeria` después de leer `colas` por:

```python
        atrasadas = [
            f"{c['name']} ({c.get('messages_ready', 0)})"
            for c in colas
            if not c["name"].endswith(SUFIJO_FALLIDOS)
            and c.get("messages_ready", 0) > MAX_MENSAJES_EN_COLA
        ]
        # Un mensaje en una cola de fallidos agotó sus 5 entregas: alguien debe revisarlo.
        fallidas = [
            f"{c['name']} ({c.get('messages', 0)})"
            for c in colas
            if c["name"].endswith(SUFIJO_FALLIDOS) and c.get("messages", 0) > 0
        ]
        problemas = []
        if atrasadas:
            problemas.append(f"Mensajes pendientes en: {', '.join(atrasadas)}.")
        if fallidas:
            problemas.append(f"Mensajes fallidos en: {', '.join(fallidas)}.")
        return " ".join(problemas) or None
```

- agregue a `pruebas`, después de la de proveedores:

```python
        ("inteligencia", "Servicio de inteligencia", inteligencia),
```

En `infra/docker-compose.yml`, en el `environment` de `administracion`, después de `PROVEEDORES_URL`:

```yaml
      INTELIGENCIA_URL: http://inteligencia:8000
```

En `web/src/ayuda.ts`, el párrafo del artículo de Estado del sistema que empieza con "Estado del sistema comprueba cada 30 segundos" queda: `"Estado del sistema comprueba cada 30 segundos la base de datos, los servicios de proveedores y de inteligencia, la identidad (Keycloak), la mensajería (RabbitMQ) y el buzón de correo. En la mensajería avisa si una cola acumula mensajes sin procesar o si algún mensaje falló 5 veces y quedó apartado."`.

- [ ] **Step 4: Run all the checks**

Run: `uv run pytest services/administracion -q`, `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`; en `web/`, `npx vitest run src/ayuda.test.ts` y `npx prettier --check "src/**/*.{ts,tsx}"`. Con el stack arriba, ejecute además:

```bash
docker compose -f infra/docker-compose.yml up -d --build --wait administracion
```

Expected: todo limpio, y `up --wait` termina con código 0 (la prueba de humo de la Task 17 revisa el Estado del sistema completo).

- [ ] **Step 5: Commit**

```bash
git add services/administracion infra/docker-compose.yml web/src/ayuda.ts
git commit -m "feat(administracion): el Estado del sistema comprueba inteligencia y avisa de mensajes fallidos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Validación contra la verdad oculta

**Files:**
- Create:
  - `services/inteligencia/src/inteligencia/validacion.py` (CLI `python -m inteligencia.validacion`)
  - `services/inteligencia/tests/test_validacion.py`
  - `docs/qa/validacion-inteligencia.md` (lo escribe la CLI con el dataset por defecto)
- Modify: `services/inteligencia/tests/conftest.py` (`observaciones` usa `observaciones_de`)

**Interfaces:**
- Consumes:
  - `Observacion` y `plazo_en_meses` (Task 8);
  - `Mes`, `Pesos` y `puntuar` (Task 9);
  - `entrenar` y `Resultado`, con `cobertura_linea_base` (Task 11);
  - los CSV de `generador.salida.escribir`.
- Produces (`inteligencia.validacion`):
  - Metas: `META_MAPE = 0.15`, `META_COBERTURA = (0.40, 0.60)` y `META_SPEARMAN = 0.8`.
  - Conversión de filas:
    - `observaciones_de(contratos: Iterable[Mapping[str, str]], categorias: Mapping[str, str], tamanos: Mapping[str, str]) -> list[Observacion]`, con las filas como las del CSV de contratos;
    - `meses_de(desempeno: Iterable[Mapping[str, str]]) -> dict[str, list[Mes]]`, por RFC.
  - `Validacion(semilla, proveedores, lineas, hasta, precios: Resultado, spearman)`, con `mape_en_uso`, `cobertura_en_uso`, `cumple_precios` y `cumple_puntuacion`.
  - Funciones:
    - `validar(carpeta, verdad) -> Validacion`;
    - `informe(validacion, generado: date) -> str`;
    - `principal(argumentos) -> int`: 0 si cumple las dos metas, 1 si no.

El método "en uso" es el modelo si se promovió y la línea base si no: es el que responde en la API.

La puntuación usa los pesos por defecto y el desempeño hasta el último mes de los datos. La categoría de cada proveedor es la primera de su lista, como en la API.

- [ ] **Step 1: Write the failing tests**

Cree `services/inteligencia/tests/test_validacion.py`:

```python
from pathlib import Path

from generador.modelo import generar
from generador.salida import escribir
from inteligencia.validacion import principal, validar


def test_la_inteligencia_cumple_las_metas_con_el_dataset_por_defecto(tmp_path: Path) -> None:
    escribir(generar(42), tmp_path)
    validacion = validar(tmp_path, tmp_path / "verdad_oculta.json")
    assert (validacion.semilla, validacion.proveedores) == (42, 60)
    assert validacion.cumple_precios, (validacion.mape_en_uso, validacion.cobertura_en_uso)
    assert validacion.cumple_puntuacion, validacion.spearman


def test_escribe_el_informe_y_responde_con_el_resultado(tmp_path: Path) -> None:
    datos = tmp_path / "datos"
    escribir(generar(7, n_proveedores=20), datos)
    salida = tmp_path / "qa" / "validacion.md"
    codigo = principal(["--verdad", str(datos / "verdad_oculta.json"), "--salida", str(salida)])
    texto = salida.read_text(encoding="utf-8")
    assert texto.startswith("# Validación del servicio de inteligencia\n")
    for parte in ("MAPE del P50", "Cobertura [P25, P75]", "Spearman", "semilla 7", "20 proveedores"):
        assert parte in texto, parte
    assert codigo == (1 if "**no**" in texto else 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest services/inteligencia/tests/test_validacion.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'inteligencia.validacion'`.

- [ ] **Step 3: Implement**

Cree `services/inteligencia/src/inteligencia/validacion.py`:

```python
"""Valida el precio justo y la puntuación contra la verdad oculta del generador.

    uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json

Lee los CSV que exporta el generador (en la carpeta de la verdad, o en --datos) y escribe
docs/qa/validacion-inteligencia.md con las métricas y las metas de la especificación (§1). La
verdad oculta solo se lee aquí: nunca se carga a la plataforma.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from scipy.stats import spearmanr

from inteligencia.dominio.precios import Observacion, plazo_en_meses
from inteligencia.dominio.puntuacion import Mes, Pesos, puntuar
from inteligencia.modelo import MESES_VALIDACION, Resultado, entrenar

META_MAPE = 0.15
META_COBERTURA = (0.40, 0.60)
META_SPEARMAN = 0.8
INFLACION = 0.045  # la de la configuración por defecto
SALIDA = Path("docs/qa/validacion-inteligencia.md")


def observaciones_de(
    contratos: Iterable[Mapping[str, str]],
    categorias: Mapping[str, str],
    tamanos: Mapping[str, str],
) -> list[Observacion]:
    """Las filas de contratos (una por línea, como el CSV del ERP) como precios observados.

    `categorias` va del código de servicio a su categoría y `tamanos` del RFC al tamaño.
    """
    resultado = []
    for fila in contratos:
        inicio = date.fromisoformat(fila["fecha_inicio"])
        fin = date.fromisoformat(fila["fecha_fin"])
        resultado.append(
            Observacion(
                servicio=fila["codigo_servicio"],
                categoria=categorias[fila["codigo_servicio"]],
                moneda=fila["moneda"],
                fecha=inicio,
                cantidad=float(fila["cantidad"]),
                precio=float(fila["precio_unitario"]),
                plazo_meses=plazo_en_meses(inicio, fin),
                tamano=tamanos.get(fila["rfc_proveedor"]),
                tipo=fila["tipo"],
            )
        )
    return resultado


def meses_de(desempeno: Iterable[Mapping[str, str]]) -> dict[str, list[Mes]]:
    """El desempeño mensual de cada proveedor, por RFC."""
    meses: dict[str, list[Mes]] = defaultdict(list)
    for fila in desempeno:
        meses[fila["rfc_proveedor"]].append(
            Mes(
                date.fromisoformat(fila["periodo"]),
                sla=float(fila["sla_cumplimiento_pct"]),
                resolucion=float(fila["tiempo_resolucion_h"]),
                incidentes=float(fila["incidentes_criticos"]),
                entregas=float(fila["entregas_a_tiempo_pct"]),
                satisfaccion=float(fila["satisfaccion"]),
            )
        )
    return dict(meses)


@dataclass(frozen=True)
class Validacion:
    semilla: int
    proveedores: int
    lineas: int
    hasta: date
    precios: Resultado
    spearman: float

    @property
    def mape_en_uso(self) -> float:
        return self.precios.mape if self.precios.promovido else self.precios.mape_linea_base

    @property
    def cobertura_en_uso(self) -> float:
        p = self.precios
        return p.cobertura if p.promovido else p.cobertura_linea_base

    @property
    def cumple_precios(self) -> bool:
        minima, maxima = META_COBERTURA
        return self.mape_en_uso <= META_MAPE and minima <= self.cobertura_en_uso <= maxima

    @property
    def cumple_puntuacion(self) -> bool:
        return self.spearman >= META_SPEARMAN


def _leer(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def validar(carpeta: Path, verdad: Path) -> Validacion:
    servicios = _leer(carpeta / "servicios.csv")
    proveedores = _leer(carpeta / "proveedores.csv")
    contratos = _leer(carpeta / "contratos.csv")
    desempeno = meses_de(_leer(carpeta / "desempeno.csv"))
    oculta = json.loads(verdad.read_text(encoding="utf-8"))
    calidad = {p["rfc"]: float(p["calidad"]) for p in oculta["proveedores"]}

    observaciones = observaciones_de(
        contratos,
        {s["codigo"]: s["categoria"] for s in servicios},
        {p["rfc"]: p["tamano"] for p in proveedores},
    )
    precios = entrenar(observaciones, INFLACION, version=0)

    categorias = {p["rfc"]: p["categorias"].split("|")[0] for p in proveedores}
    hasta = max(m.periodo for meses in desempeno.values() for m in meses)
    puntuaciones = puntuar(
        {rfc: meses for rfc, meses in desempeno.items() if rfc in categorias},
        categorias,
        Pesos(),
        hasta,
    )
    rfcs = sorted(puntuaciones)
    correlacion = spearmanr(
        [puntuaciones[rfc].puntuacion for rfc in rfcs], [calidad[rfc] for rfc in rfcs]
    )
    return Validacion(
        semilla=int(oculta["semilla"]),
        proveedores=len(proveedores),
        lineas=len(contratos),
        hasta=hasta,
        precios=precios,
        spearman=float(correlacion.statistic),
    )


def _pct(valor: float) -> str:
    return f"{valor * 100:.1f} %"


def _cumple(si: bool) -> str:
    return "sí" if si else "**no**"


def informe(v: Validacion, generado: date) -> str:
    p = v.precios
    en_uso = (
        "el modelo, porque mejora la línea base"
        if p.promovido
        else "la línea base, porque el modelo no la mejoró"
    )
    minima, maxima = META_COBERTURA
    lineas = [
        "# Validación del servicio de inteligencia",
        "",
        f"Generado el {generado:%d/%m/%Y} con "
        "`uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json`.",
        "",
        f"Datos del generador: semilla {v.semilla}, {v.proveedores} proveedores, "
        f"{v.lineas:,} líneas de contrato y desempeño hasta {v.hasta:%m/%Y}. La verdad oculta "
        "(calidad de cada proveedor) solo se usa aquí, para medir; la plataforma nunca la ve.",
        "",
        "## Precio justo",
        "",
        f"Validación temporal: se entrena con los contratos hasta {MESES_VALIDACION} meses antes "
        "del último y se mide con los posteriores.",
        "",
        "| Método | MAPE del P50 | Cobertura [P25, P75] |",
        "|---|---|---|",
        f"| Línea base | {_pct(p.mape_linea_base)} | {_pct(p.cobertura_linea_base)} |",
        f"| Modelo (gradient boosting por cuantiles) | {_pct(p.mape)} | {_pct(p.cobertura)} |",
        "",
        f"Meta: MAPE del P50 ≤ {_pct(META_MAPE)} y cobertura entre {_pct(minima)} y "
        f"{_pct(maxima)}. En uso: {en_uso}. Cumple: {_cumple(v.cumple_precios)}.",
        "",
        "## Puntuación de proveedores",
        "",
        "| Medida | Valor | Meta |",
        "|---|---|---|",
        f"| Spearman entre la puntuación y la calidad oculta | {v.spearman:.3f} | "
        f"≥ {META_SPEARMAN} |",
        "",
        f"Con los pesos por defecto. Cumple: {_cumple(v.cumple_puntuacion)}.",
        "",
    ]
    return "\n".join(lineas)


def principal(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Valida la inteligencia contra la verdad oculta del generador"
    )
    parser.add_argument("--verdad", type=Path, required=True, help="verdad_oculta.json")
    parser.add_argument("--datos", type=Path, help="carpeta de los CSV; por defecto, la de --verdad")
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args(argumentos)
    validacion = validar(args.datos or args.verdad.parent, args.verdad)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(informe(validacion, date.today()), encoding="utf-8", newline="\n")
    print(
        f"Precio justo: MAPE {_pct(validacion.mape_en_uso)}, "
        f"cobertura {_pct(validacion.cobertura_en_uso)}; "
        f"Spearman {validacion.spearman:.3f} -> {args.salida}"
    )
    return 0 if validacion.cumple_precios and validacion.cumple_puntuacion else 1


if __name__ == "__main__":
    sys.exit(principal())
```

En `services/inteligencia/tests/conftest.py`, reemplace el cuerpo de `observaciones(datos)` para no repetir la conversión:

```python
def observaciones(datos: DatosSinteticos) -> list[Observacion]:
    return observaciones_de(
        datos.contratos,
        {s.codigo: s.categoria for s in datos.servicios},
        {p.rfc: p.tamano for p in datos.proveedores},
    )
```

(importe `from inteligencia.validacion import observaciones_de` y quite `plazo_en_meses` si queda sin uso).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest services/inteligencia -q`, luego `uv run ruff check`, `uv run ruff format --check` y `uv run mypy`.
Expected: todo limpio.

Si `test_la_inteligencia_cumple_las_metas_con_el_dataset_por_defecto` falla, **no** cambie las metas: reporte los números (BLOCKED). El prototipo del plan, con el dataset por defecto, dio:
- línea base: MAPE 9.3 %, cobertura 43.5 %;
- modelo: MAPE 8.3 %, cobertura 46.2 %;
- Spearman: 0.915.

- [ ] **Step 5: Write the validation report**

`datos/` no se versiona. Con la semilla por defecto, el generador produce siempre los mismos archivos.

```bash
uv run python -m generador --salida datos
uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json
```

Expected:
- el comando termina con código 0;
- escribe `docs/qa/validacion-inteligencia.md`, con "Cumple: sí" en las dos secciones.

- [ ] **Step 6: Commit**

```bash
git add services/inteligencia docs/qa/validacion-inteligencia.md
git commit -m "feat(inteligencia): validación del precio justo y la puntuación contra la verdad oculta" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: Prueba de humo, documentación y verificación final

**Files:**
- Modify:
  - `infra/smoke_test.py` (`verificar_inteligencia`)
  - `README.md`
  - `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md` (PRD: §2.1, §2.2, §4.1 y §5.1)
  - `docs/superpowers/specs/2026-10-01-experiencia-e-inteligencia-design.md` (nota de reemplazo)

**Interfaces:**
- Consumes:
  - las rutas `GET /api/inteligencia/tablero`, `/precios/servicios` y `/datos` (Tasks 12 y 13);
  - el servicio `HUMO-SERV` que crea `verificar_operacion`;
  - los comandos de `proveedores.reproceso` (Task 5) y de `inteligencia.validacion` (Task 16).
- Produces: la prueba de humo cubre inteligencia, y la documentación queda al día (§12 de la especificación).

- [ ] **Step 1: Extend the smoke test**

En `infra/smoke_test.py`:
- importe `from decimal import Decimal`;
- agregue, después de `verificar_operacion`:

```python
ESPERA_COPIA_S = 180


def verificar_inteligencia(cliente: httpx.Client) -> None:
    """La copia local de inteligencia recibe lo importado y los cambios del catálogo."""
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")
    # Inteligencia se llena por eventos: con el dataset completo tarda alrededor de un minuto.
    limite = time.monotonic() + ESPERA_COPIA_S
    while True:
        tablero = cliente.get("/api/inteligencia/tablero", headers=comprador)
        verificar(tablero.status_code == 200, f"el tablero de inteligencia falló: {tablero.text}")
        cuerpo = tablero.json()
        if cuerpo["total_proveedores"] > 0 and Decimal(cuerpo["gasto_anual"]) > 0:
            break
        verificar(
            time.monotonic() < limite,
            f"los datos importados no llegaron a inteligencia en {ESPERA_COPIA_S} s",
        )
        time.sleep(2)
    limite = time.monotonic() + 30
    while True:
        servicios = cliente.get("/api/inteligencia/precios/servicios", headers=comprador)
        verificar(servicios.status_code == 200, f"los servicios de precios fallaron: {servicios.text}")
        if SERVICIO_HUMO in {s["codigo"] for s in servicios.json()}:
            break
        verificar(time.monotonic() < limite, "el servicio de humo no llegó a inteligencia en 30 s")
        time.sleep(1)
    copia = cliente.get("/api/inteligencia/datos", headers=admin)
    verificar(
        copia.status_code == 200 and copia.json()["registros"]["contratos"] > 0,
        f"los datos de inteligencia fallaron: {copia.text}",
    )
    sin_permiso = cliente.get("/api/inteligencia/datos", headers=comprador)
    verificar(sin_permiso.status_code == 403, "un comprador no debe ver los datos de inteligencia")
```

- en `main`, después de `verificar_operacion(cliente)`, llame `verificar_inteligencia(cliente)`;
- el mensaje final queda: `f"OK: SPA, Keycloak, proveedores, administración, operación e inteligencia responden ({lista.json()['total']} proveedores)."`.

- [ ] **Step 2: Update the README**

En `README.md`:
- después de la lista de secretos de la administración (antes de "### Activar la administración…"), agregue:

```markdown
Los de la inteligencia son:

- `INTELIGENCIA_DB_PASSWORD`: contraseña con la que el servicio `inteligencia` entra a su base
  (consulta, inserta y actualiza su copia local; nunca borra).
- `INTELIGENCIA_DUENO_DB_PASSWORD`: contraseña del dueño de esa base, que solo crea y migra tablas.
```

- después de la sección "### Activar la administración en un entorno ya creado", agregue:

````markdown
### Activar la inteligencia en un entorno ya creado

Si su entorno ya existía antes del servicio de inteligencia, siga estos pasos, en este orden (en
Git Bash, ejecute antes `export MSYS_NO_PATHCONV=1`).

1. Agregue en `infra/.env` las dos variables de la inteligencia (cópielas de `infra/.env.example`)
   y vuelva a crear PostgreSQL para que las reciba:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --wait postgres
   ```

2. Cree la base de la inteligencia y sus dos usuarios. El comando es idempotente:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/30-inteligencia.sh
   ```

3. Levante el resto del stack. El contenedor `rabbitmq-topologia` declara las colas y termina:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --build --wait
   ```

4. Llene la copia local de la inteligencia con lo que ya estaba importado. El primer comando
   publica el estado actual del catálogo y del tipo de cambio; el segundo vuelve a publicar todos
   los eventos guardados. Los servicios ignoran lo que ya recibieron (la Actividad no se duplica),
   así que repetirlos es seguro:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --instantanea
   ```

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --todo
   ```

   Con el dataset por defecto, la copia se llena en alrededor de un minuto. Después, el modelo de
   precios se entrena solo.
````

- en la tabla de "## Desarrollo", agregue después de la fila del contrato OpenAPI de administración:

```markdown
| Contrato OpenAPI de inteligencia | <http://localhost:8080/api/inteligencia/docs> |
| Validación de la inteligencia contra la verdad oculta (escribe `docs/qa/validacion-inteligencia.md`) | `uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json` |
```

- en la tabla de "## Estructura":
  - la fila de `libs/comun` queda: `Infraestructura compartida: logs, errores RFC 9457, JWT, salud, outbox, topología de RabbitMQ y consumidor de eventos`;
  - agregue después de `services/administracion`: `| \`services/inteligencia\` | Microservicio de inteligencia: precio justo, puntuación de proveedores, alertas y Tablero (\`/api/inteligencia/\`) |`;
- en "## Limitaciones conocidas", reemplace el punto "**Eventos sin cola enlazada.**" completo por:

```markdown
- **Mensajes fallidos sin pantalla propia.** Un evento que falla 5 veces queda en la cola
  `<cola>.dlq` y el Estado del sistema lo avisa, pero todavía no hay una pantalla para revisarlo
  o reintentarlo: se hace desde la consola de RabbitMQ.
```

- [ ] **Step 3: Update the PRD and the origin spec**

En `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md`:
- §2.1, fila de **inteligencia** de la tabla de servicios: la responsabilidad queda `Precio justo (línea base y modelo por cuantiles), puntuación de proveedores, alertas y KPIs del Tablero, a partir de una copia local alimentada por eventos; después, recomendación de adjudicación y simulador de escenarios.`; los datos propios quedan `` `inteligencia_db` (copia local, configuración y registro de modelos) y el volumen `modelos` (artefactos) ``.
- §2.2:
  - la regla 5 queda: `**Contratos documentados:** OpenAPI por servicio (FastAPI). Los tipos de evento, las colas y sus bindings se declaran en \`libs/comun/src/comun/topologia.py\`, y una prueba verifica que \`infra/rabbitmq/definitions.json\` diga lo mismo.`;
  - en la tabla de eventos, la fila de `servicio.actualizado` queda `| \`servicio.actualizado\` | proveedores | administracion, inteligencia | Cambios del catálogo (con quién los hizo) y copia local del servicio, también al importar el catálogo. |`;
  - agregue al final de la tabla de eventos:

```markdown
| `tipo_cambio.registrado` | proveedores | inteligencia | Tipo de cambio mensual para llevar los montos a MXN. |
| `configuracion.actualizada` | inteligencia | administracion | Bitácora de los cambios de pesos, umbral e inflación. |
| `modelo.entrenado` | inteligencia | administracion | Bitácora de cada entrenamiento del modelo de precios. |
```

  - después de la tabla, agregue: `Colas: \`inteligencia.eventos\` y \`administracion.actividad\`, *quorum* con 5 entregas como máximo; lo que falla 5 veces pasa a \`<cola>.dlq\` (detalle en \`docs/superpowers/specs/2026-10-10-servicio-inteligencia-design.md\`, §3).`
- §4.1, la fila de **inteligencia** queda: `| inteligencia | Proveedor, Servicio, TipoCambio, Contrato, LineaContrato y Desempeno (copia local alimentada por eventos), Configuracion, ModeloBenchmark (registro de modelos), Outbox, EventoProcesado; Escenario (más adelante) |`.
- §5.1, en la matriz de permisos, agregue después de "Configurar catálogos, pesos, umbrales y usuarios": `| Reentrenar el modelo de precios y ver el estado de los datos de la inteligencia | ✔ | | | |`.

En `docs/superpowers/specs/2026-10-01-experiencia-e-inteligencia-design.md`, agregue justo después de la tabla del encabezado:

```markdown
> **Nota (2026-10-10):** las secciones §4 a §8 las reemplaza
> `docs/superpowers/specs/2026-10-10-servicio-inteligencia-design.md`, que las reconcilia con la
> administración ya construida.
```

- [ ] **Step 4: Verify the whole stack**

`infra/.env` ya tiene las variables de la inteligencia (Task 6) y la base existe. Levante el stack y llene la copia local como indica el README:

```bash
docker compose -f infra/docker-compose.yml up -d --build --wait
docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --instantanea
docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --todo
uv run python infra/smoke_test.py
```

Expected: la prueba de humo termina con `OK: SPA, Keycloak, proveedores, administración, operación e inteligencia responden (…)`. Esta corrida es también la verificación de la §10 de la especificación "el reproceso reconstruye la copia local": la copia de la inteligencia se llena solo con lo que republica el reproceso.

Luego corra todo:
- `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy` y `uv run pytest`;
- en `web/`: `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check "src/**/*.{ts,tsx}"`.

Expected: todo limpio.

- [ ] **Step 5: Commit**

```bash
git add infra/smoke_test.py README.md docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md docs/superpowers/specs/2026-10-01-experiencia-e-inteligencia-design.md
git commit -m "docs: servicio de inteligencia en el README, el PRD y la prueba de humo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
