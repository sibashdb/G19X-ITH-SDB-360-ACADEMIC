# Tablero: estado de las negociaciones y ahorro logrado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar la capacidad 10 (Tablero) con el estado de las negociaciones y el ahorro logrado frente a la primera oferta.

**Architecture:** La regla de costo total pasa de `inteligencia` a `libs/comun`. `negociacion` expone `GET /tablero`, con los conteos por estado y el ahorro, que calcula una función pura del dominio. La SPA agrega al Tablero una fila «Negociaciones» con su propia consulta.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest con Testcontainers; React 19 con TypeScript, TanStack Query 5, Vitest, Testing Library y axe-core.

**Spec:** `docs/superpowers/specs/2026-10-22-tablero-negociaciones-design.md`

## Global Constraints

- Rama `feat/tablero-negociaciones`, en el worktree `.claude/worktrees/feat+incremento-1`.
- Código, nombres, mensajes y comentarios en español, como el código vecino. La interfaz trata al usuario de «usted».
- Montos con `Decimal`, redondeados a centavos (`Decimal("0.01")`). En el JSON van como texto, por ejemplo `"150000.00"`.
- La interfaz usa solo los tokens del sistema de diseño; `npm run lint` rechaza colores literales.
- Commits con Conventional Commits, terminados en `Co-Authored-By: Claude <modelo> <noreply@anthropic.com>` con el modelo que los escribe.
- Puertas de calidad:
  - Python: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy` y las pruebas de lo que se tocó.
  - SPA: `npm run lint`, `npx tsc -b` y `npm test -- --run`.

## Review Focus

1. **Propuesta rechazada y vuelta a proponer.** La negociación cuenta una sola vez, con los números de la propuesta aprobada (prueba en la Tarea 3).
2. **Evento en USD.** El ahorro en MXN usa la tasa implícita de su adjudicación, no 1 (prueba de dominio en la Tarea 2).
3. **`negociacion` no responde.** El resto del Tablero se ve completo; solo la fila muestra su error y permite reintentar (prueba en la Tarea 4).
4. **Sin ningún evento.** Los 7 estados valen 0 y `ahorro_pct` es `null`. La tarjeta dice que todavía no hay negociaciones adjudicadas, y nunca muestra «NaN» ni «0 %» (pruebas en las Tareas 3 y 4).
5. **Ahorro negativo.** Se muestra con su signo, sin ocultarlo (prueba de dominio en la Tarea 2).

---

### Task 1: Costo total compartido en `libs/comun`

**Files:**
- Create: `libs/comun/src/comun/costos.py`
- Create: `libs/comun/tests/test_costos.py`
- Modify: `services/inteligencia/src/inteligencia/dominio/precios.py:16` (importa `UNIDADES_MENSUALES` de `comun.costos`)
- Modify: `services/inteligencia/src/inteligencia/dominio/adjudicacion.py:118-126` (`costo_total(candidato)` delega en `comun.costos`)

**Interfaces:**
- Produces:
  - `comun.costos.UNIDADES_MENSUALES: frozenset[str]`, que vale `frozenset({"usuario_mes", "vcpu_mes", "gb_mes", "mes"})`.
  - `comun.costos.costo_total(lineas: Iterable[tuple[str, Decimal, Decimal]], plazo_meses: int, cuota: Decimal) -> Decimal`.
    - Cada tupla es `(unidad, cantidad, precio)`.
    - Devuelve la suma de `precio * cantidad`, multiplicada por `plazo_meses` en las unidades mensuales, más `cuota`.
    - No redondea.
- `inteligencia.dominio.adjudicacion.costo_total(candidato: Candidato) -> Decimal` conserva su firma y su resultado. Pierde el parámetro `unidades_mensuales`, que nadie pasa.

- [ ] **Step 1: Escribir la prueba que falla** en `libs/comun/tests/test_costos.py`

```python
from decimal import Decimal as D

from comun.costos import UNIDADES_MENSUALES, costo_total


def test_las_unidades_mensuales_se_cobran_por_el_plazo_y_las_demas_una_vez() -> None:
    lineas = [("usuario_mes", D("100"), D("30.00")), ("ticket", D("10"), D("500.00"))]
    # 100 × 30 × 12 + 10 × 500 + la cuota de 1,000
    assert costo_total(lineas, 12, D("1000.00")) == D("42000.00")


def test_sin_lineas_vale_la_cuota() -> None:
    assert costo_total([], 12, D("250.00")) == D("250.00")


def test_unidades_mensuales() -> None:
    assert frozenset({"usuario_mes", "vcpu_mes", "gb_mes", "mes"}) == UNIDADES_MENSUALES
```

- [ ] **Step 2:** `uv run pytest libs/comun/tests/test_costos.py -v`. Esperado: FALLA con `ModuleNotFoundError: comun.costos`.
- [ ] **Step 3: Implementar `comun/costos.py`.**
  - Docstring del módulo: «Costo total de un contrato: la regla que comparten la recomendación de adjudicación (`inteligencia`) y el Tablero (`negociacion`).».
  - `UNIDADES_MENSUALES` se mueve de `precios.py`. `precios.py` la importa de `comun.costos` para que `cantidad_mensual` y quienes la importan de ahí sigan funcionando.
  - El `costo_total` de `inteligencia` delega: `costos.costo_total(((l.unidad, l.cantidad, l.precio) for l in candidato.lineas), candidato.plazo_meses, candidato.cuota)`.
- [ ] **Step 4:** `uv run pytest libs/comun/tests services/inteligencia/tests/test_adjudicacion.py services/inteligencia/tests/test_precios.py -v` y `uv run mypy`. Esperado: PASA, y las pruebas de la recomendación no cambian.
- [ ] **Step 5: Commit** `refactor(comun): la regla de costo total vive en comun para que la usen inteligencia y negociacion`

### Task 2: La regla del ahorro en el dominio de `negociacion`

**Files:**
- Create: `services/negociacion/src/negociacion/dominio/tablero.py`
- Create: `services/negociacion/tests/test_dominio_tablero.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Adjudicada`, con tres campos:
    - `primera: Decimal` y `adjudicado: Decimal`: costos totales en la moneda del evento;
    - `tasa: Decimal`: MXN por unidad de esa moneda (1 en MXN).
  - `@dataclass(frozen=True) class Ahorro`: `adjudicadas: int`, `primera_oferta_mxn: Decimal`, `adjudicado_mxn: Decimal`, `ahorro_mxn: Decimal` y `ahorro_pct: float | None`.
  - `def ahorro(adjudicadas: Sequence[Adjudicada]) -> Ahorro`:
    - convierte cada costo con su tasa y redondea cada conversión a centavos antes de sumar;
    - `ahorro_mxn = primera_oferta_mxn - adjudicado_mxn`;
    - `ahorro_pct = round(float(ahorro_mxn / primera_oferta_mxn * 100), 1)`, o `None` si no hay adjudicadas o la primera oferta suma 0.

- [ ] **Step 1: Escribir las pruebas que fallan** en `test_dominio_tablero.py`:
  - `test_en_mxn_el_ahorro_es_la_diferencia_contra_la_primera_oferta`: `[Adjudicada(D("400"), D("300"), D("1"))]` da `Ahorro(1, D("400.00"), D("300.00"), D("100.00"), 25.0)`.
  - `test_un_evento_en_usd_se_convierte_con_su_tasa`: `[Adjudicada(D("100"), D("90"), D("18.50")), Adjudicada(D("1000"), D("800"), D("1"))]` da:
    - `primera_oferta_mxn == D("2850.00")`;
    - `adjudicado_mxn == D("2465.00")`;
    - `ahorro_mxn == D("385.00")`;
    - `ahorro_pct == 13.5`.
  - `test_el_ahorro_negativo_se_conserva`: `[Adjudicada(D("300"), D("330"), D("1"))]` da `ahorro_mxn == D("-30.00")` y `ahorro_pct == -10.0`.
  - `test_sin_adjudicadas_no_hay_porcentaje`: `ahorro([])` da `Ahorro(0, D("0.00"), D("0.00"), D("0.00"), None)`.
- [ ] **Step 2:** `uv run pytest services/negociacion/tests/test_dominio_tablero.py -v`. Esperado: FALLA con `ModuleNotFoundError`.
- [ ] **Step 3:** Implementar `ahorro`. El módulo es puro: no importa la base ni FastAPI.
- [ ] **Step 4:** El mismo comando. Esperado: PASA.
- [ ] **Step 5: Commit** `feat(negociacion): regla del ahorro logrado frente a la primera oferta`

### Task 3: `GET /tablero` en `negociacion`

**Files:**
- Create: `services/negociacion/src/negociacion/api/tablero.py`
- Create: `services/negociacion/tests/test_api_tablero.py`
- Modify: `services/negociacion/src/negociacion/adjudicacion.py:90-131`:
  - extraer `candidato_de(sesion: SesionNegociacion, oferta: Oferta, lineas: Sequence[Linea], evento: Evento) -> dict[str, Any]`, el cuerpo que hoy arma cada candidato dentro de `candidatos()`; `candidatos()` lo llama y no cambia;
  - agregar `costo_de(candidato: dict[str, Any]) -> Decimal`, con `comun.costos.costo_total`.
- Modify: `services/negociacion/src/negociacion/turnos.py:454`: agregar `primera_oferta_proveedor(bd, sesion_id) -> Oferta | None`, igual que `ultima_oferta_proveedor` pero con `secuencia` ascendente.
- Modify: `services/negociacion/src/negociacion/api/esquemas.py`: `AhorroSalida` y `TableroSalida`.
- Modify: `services/negociacion/src/negociacion/main.py:97-100`: `app.include_router(tablero.router)`.
- Modify: `services/negociacion/tests/test_api_permisos.py:11-27`: `("GET", "/tablero")` entra a `ESPERADAS`.
- Modify: `docs/arquitectura/openapi/negociacion.json`. Con el stack arriba, `uv run python infra/exportar_contratos.py`. Si no está arriba, generarlo con `app.openapi()` en el mismo formato que escribe ese script.

**Interfaces:**
- Consumes:
  - `negociacion.dominio.tablero.Adjudicada`, `Ahorro` y `ahorro` (Tarea 2);
  - `comun.costos.costo_total` (Tarea 1).
- Produces:
  - `GET /tablero`, con la dependencia `Lector` (los tres roles internos).
  - Responde `TableroSalida(por_estado: dict[EstadoEvento, int], ahorro: AhorroSalida)`.
  - `AhorroSalida` lleva los campos de `Ahorro`, con los montos como `Decimal`.
  - `por_estado` trae siempre las 7 claves de `ESTADOS_EVENTO`.
  - La forma del JSON es la de la spec, §4.
- **Datos del ahorro:** cada `Evento` en estado `adjudicado`, junto con su `Adjudicacion` en estado `aprobada` o `directa`.
  - `primera = costo_de(candidato_de(sesion, await primera_oferta_proveedor(bd, sesion.id), lineas, evento))`.
  - `adjudicado = adjudicacion.costo_total`.
  - `tasa = costo_total_mxn / costo_total`, o 1 si `costo_total` es 0.
  - `# ponytail:` una consulta por evento adjudicado, como en `candidatos()`; un solo JOIN si fueran cientos.

- [ ] **Step 1: Escribir las pruebas que fallan** en `test_api_tablero.py`, con las fixtures de `conftest.py` (`cliente`, `comprador`, `nueva_compra`, `publicar`, `ofertar`, `acordar` y `proponer`):
  - **`test_sin_negociaciones_todo_vale_cero`:**
    - los 7 estados valen 0;
    - `ahorro == {"adjudicadas": 0, "primera_oferta_mxn": "0.00", "adjudicado_mxn": "0.00", "ahorro_mxn": "0.00", "ahorro_pct": None}`.
  - **`test_cuenta_las_negociaciones_por_estado`:** un borrador (`nueva_compra()`) y una publicada (`publicar()`) dan `borrador == 1`, `abierto == 1` y 0 en los demás.
  - **`test_el_ahorro_compara_la_primera_oferta_con_lo_adjudicado`:**
    1. `publicar(plazo_meses=1)`. El falso de `inteligencia` en las pruebas cuenta precio por cantidad sin el plazo; con 1 mes coincide con la regla real.
    2. El primer proveedor ofrece `"40.00"` con `ofertar`. Queda sobre el límite (la referencia de SAAS-CRM-PRO llega a 36.00 en el P75), así que el agente contraoferta.
    3. Después `acordar(enlace, linea, "30.00")` y `proponer`, que queda directa.
    4. Con la cantidad de 100 del cuerpo de la compra, se espera:
       - `adjudicadas == 1`;
       - `primera_oferta_mxn == "4000.00"`, `adjudicado_mxn == "3000.00"` y `ahorro_mxn == "1000.00"`;
       - `ahorro_pct == 25.0`;
       - `por_estado["adjudicado"] == 1`.
  - **`test_una_propuesta_rechazada_no_se_cuenta_dos_veces`:**
    1. Con el umbral bajo del falso (`umbral`, como en `test_api_adjudicacion.py`), proponer el primer acuerdo.
    2. El aprobador lo rechaza.
    3. Proponer el segundo acuerdo y aprobarlo.
    4. Se espera `adjudicadas == 1` y `adjudicado_mxn` igual al costo del aprobado.
- [ ] **Step 2:** `uv run pytest services/negociacion/tests/test_api_tablero.py services/negociacion/tests/test_api_permisos.py -v` (requiere Docker). Esperado: FALLA, con 404 en `/tablero` y la ruta ausente de `ESPERADAS`.
- [ ] **Step 3:** Implementar:
  - el router;
  - los esquemas;
  - la extracción en `adjudicacion.py`;
  - `primera_oferta_proveedor`;
  - la inclusión en `main.py`;
  - `ESPERADAS`;
  - la exportación del OpenAPI.
- [ ] **Step 4:** `uv run pytest services/negociacion -v` y las puertas de Python. Esperado: PASA todo `negociacion`.
- [ ] **Step 5: Commit** `feat(negociacion): GET /tablero con los conteos por estado y el ahorro logrado`

### Task 4: La fila «Negociaciones» en el Tablero

**Files:**
- Modify: `web/src/negociacion.ts`: tipo `TableroNegociacion`, igual a `TableroSalida`.
- Modify: `web/src/paginas/Tablero.tsx`: componente `FilaNegociaciones`, entre la cuadrícula de indicadores y la fila que sigue.
- Modify: `web/src/paginas/Tablero.test.tsx`
- Modify: `web/src/glosario.ts`: clave `ahorroLogrado`.
- Modify: `web/src/ayuda.ts`: la guía del Tablero menciona la fila nueva.

**Interfaces:**
- Consumes:
  - `GET /api/negociacion/tablero` (Tarea 3), con `useNegociacion<TableroNegociacion>("/tablero")`;
  - `NOMBRES_ESTADO_EVENTO`, `TarjetaKpi`, `montoCorto`, `formatoPorcentaje` y `Termino`.
- Glosario `ahorroLogrado`:
  - `termino: "Ahorro logrado"`;
  - `definicion: "Lo que bajó el costo total de los contratos adjudicados frente a la primera oferta de cada proveedor ganador."`.

**Comportamiento:**
- **Tarjeta «Ahorro logrado»:** un `TarjetaKpi` con:
  - título `<Termino clave="ahorroLogrado">Ahorro logrado</Termino>`;
  - valor `montoCorto(ahorro_mxn)`;
  - detalle `` `${formatoPorcentaje(ahorro_pct)} frente a la primera oferta, en ${n} negociaciones adjudicadas.` ``, o «negociación adjudicada» si n = 1;
  - enlace `/negociaciones?estado=adjudicado` con el texto «Ver adjudicadas».
  - Con `adjudicadas === 0`: valor «—» y detalle «Todavía no hay negociaciones adjudicadas.».
  - Si `ahorro_pct` es `null` aunque haya adjudicadas (la primera oferta sumó 0), el detalle omite el porcentaje: «En n negociaciones adjudicadas.».
- **Tarjeta «Estado de las negociaciones»:**
  - una lista con los 7 estados, en el orden de `NOMBRES_ESTADO_EVENTO`;
  - cada uno con su etiqueta, su número y un enlace a `/negociaciones?estado=<estado>`;
  - el nombre accesible de cada enlace incluye la etiqueta y el número.
- **Carga y error:**
  - La fila tiene su propio esqueleto mientras carga.
  - Si falla, muestra «No se pudo cargar el estado de las negociaciones.» y un botón «Reintentar» (`refetch`), con el mismo patrón que el Tablero usa para el error de inteligencia.
  - El resto del Tablero no se ve afectado.

- [ ] **Step 1: Escribir las pruebas que fallan** en `Tablero.test.tsx`. `/negociacion/tablero` se simula igual que el archivo simula `/inteligencia/tablero`:
  - **`muestra el ahorro logrado y el estado de las negociaciones`:**
    - el monto;
    - «25.0 % frente a la primera oferta, en 3 negociaciones adjudicadas.»;
    - el enlace «Ver adjudicadas» a `/negociaciones?estado=adjudicado`;
    - cada estado con su número y su enlace.
  - **`sin adjudicadas, el ahorro lo explica`:** muestra «Todavía no hay negociaciones adjudicadas.», y la tarjeta no contiene «NaN» ni «%».
  - **`si negociacion no responde, el resto del tablero sigue y la fila permite reintentar`:**
    - los 4 indicadores de inteligencia siguen visibles;
    - se ve el texto del error;
    - «Reintentar» vuelve a consultar.
  - **`no tiene violaciones de accesibilidad`** se amplía con la fila cargada.
- [ ] **Step 2:** `cd web && npm test -- --run src/paginas/Tablero.test.tsx`. Esperado: FALLA.
- [ ] **Step 3:** Implementar la fila, el tipo, el término del glosario y el texto de la guía.
- [ ] **Step 4:** `npm run lint && npx tsc -b && npm test -- --run`. Esperado: PASA.
- [ ] **Step 5: Commit** `feat(web): el Tablero muestra el estado de las negociaciones y el ahorro logrado`

### Task 5: Revisión en el navegador y documentación

**Files:**
- Create: `docs/qa/revision-tablero-negociaciones.md`
- Modify: `README.md`: la capacidad 10 pasa a «Hecho» y dice qué muestra; el apartado «Interfaz» menciona la fila.
- Modify: `docs/MVP.md`: la fila 10 pasa a «Hecho».
- Modify: `docs/arquitectura/c4.md:91`: la fila de `negociacion` dice que también sirve los indicadores de las negociaciones del Tablero.

- [ ] **Step 1:** Levantar el stack con las imágenes de la rama. Comprobar con `/api/negociacion/tablero` que los datos de la prueba de humo (una negociación adjudicada) dan un ahorro.
- [ ] **Step 2:** Revisar el Tablero en el navegador, con el residente dentro como `comprador1`:
  - en claro y en oscuro;
  - a 375 y a 1440 px;
  - axe sin violaciones;
  - los enlaces de cada estado abren la lista filtrada.
- [ ] **Step 3:** Registrar la revisión en `docs/qa/revision-tablero-negociaciones.md` con el formato de las demás revisiones de `docs/qa/`: qué se revisó, el resultado y cada defecto con su corrección.
- [ ] **Step 4:** Actualizar el README, `MVP.md` y `c4.md`.
- [ ] **Step 5: Commit** `docs: el Tablero completa la capacidad 10; revisión en el navegador`
