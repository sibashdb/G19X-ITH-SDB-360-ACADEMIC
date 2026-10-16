# 4′a · Adjudicación en los servicios — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que una negociación cerrada termine en una adjudicación aprobada que registra el contrato
nuevo. Comprende la recomendación en `inteligencia`; la propuesta, la aprobación, la desierta y los
avisos en `negociacion`; el contrato en `proveedores`; y la Actividad y los Correos en
`administracion`.

**Architecture:**
- **Recomendación.** Vive en `inteligencia`: un dominio puro (`dominio/adjudicacion.py`) y una ruta
  `POST /adjudicacion/recomendacion` que arma los criterios con el `Contexto` cacheado.
- **Adjudicación.** `negociacion` tiene un dominio puro para la regla de aprobación y los términos
  del contrato, una tabla `adjudicacion` y la ruta nueva `api/adjudicacion.py`. Llama a
  `inteligencia` como ya lo hace con la referencia de precios. Los avisos a los proveedores los manda
  la tarea periódica que ya corre cada minuto.
- **Contrato.** `proveedores` gana su primer consumidor de eventos.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 asíncrono, Alembic, aio-pika (`libs/comun`),
pytest, Hypothesis, Testcontainers, httpx `MockTransport`.

**Spec:** `docs/superpowers/specs/2026-10-16-adjudicacion-y-aprobacion-design.md` (§2–§6, §8–§10;
§12 4′a). El PRD padre es `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md`.

## Global Constraints

**Montos y cálculo**
- Los montos son `Decimal` en el dominio y texto decimal en el JSON; nunca `float` para dinero. Los
  puntajes, las fracciones de riesgo y los normalizados sí son `float`.
- Pesos de adjudicación por defecto: costo 40, desempeño 30, riesgo 15 y SLA 15, que suman 100.
  Umbral de aprobación por defecto: `500000.00` MXN.
- Unidades mensuales: `usuario_mes`, `vcpu_mes`, `gb_mes` y `mes`. El resto son de consumo y su
  cantidad ya es del contrato.

**Textos y errores**
- Todo texto para el usuario va en español y de «usted».
- Los errores siguen RFC 9457 (`comun.errores.ErrorDominio`) y llevan un `codigo` estable:
  `justificacion_requerida`, `estado_invalido`, `misma_persona`, `sesion_no_candidata`,
  `pesos_invalidos` y `dependencia_no_disponible`.

**Datos y eventos**
- Cada `registrar_evento(bd, Outbox, "tipo.evento", …)` lleva el tipo como literal: la prueba de
  topología lo busca con una expresión regular.
- Cada consumidor es idempotente por `event_id` (`evento_procesado`), con el patrón de
  `negociacion/eventos.py::aplicar`.
- `negociacion`: la bitácora, los mensajes y las ofertas siguen siendo de solo inserción. La tabla
  `adjudicacion` solo admite UPDATE en sus columnas de decisión.
- Los correos y el portal nunca revelan al ganador ni ningún monto a los proveedores.

**Reglas del repositorio**
- Sin dependencias nuevas. `ruff format`, `ruff check` y `mypy` (estricto) limpios.
- La cobertura de `inteligencia/dominio/adjudicacion.py` y de `negociacion/dominio/adjudicacion.py`
  debe ser de 80 % o más.
- Commits en español con Conventional Commits. La última línea es
  `Co-Authored-By: Claude <modelo real> 5.5 <noreply@anthropic.com>`.
- No editar planes ni bitácoras viejos. No hacer `git push`. Nunca hacer commit de `infra/.env`,
  `datos/`, `.superpowers/` ni `web/node_modules`.

**Puertas de verificación**
- Python, desde la raíz: `uv run ruff format --check . && uv run ruff check . && uv run mypy`
  más `uv run pytest services/<servicio> libs/comun -q`.
- Web, desde `web/`: `npm run lint && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`.

## Review Focus

1. **Negociación en USD.** El ranking no cambia, pero el umbral se compara en MXN con el tipo de
   cambio más reciente: un evento en USD de bajo monto en dólares puede pedir aprobación. Prueba:
   `test_evento_en_usd_compara_el_umbral_en_mxn` (Task 8).
2. **Un candidato sin historial ni puntuación** (proveedor nuevo). La recomendación no falla: el
   desempeño es la media de su categoría y el riesgo marca «sin historial». Prueba:
   `test_proveedor_sin_puntuacion_usa_la_media_de_su_categoria` (Task 4).
3. **Un usuario con los roles de comprador y aprobador** propone y luego intenta aprobar: recibe
   403 `misma_persona`. Prueba: `test_quien_propone_no_aprueba_aunque_tenga_los_dos_roles` (Task 8).
4. **Proponer de nuevo tras un rechazo** crea una segunda fila. La rechazada ya no se puede aprobar
   (409). Prueba: `test_tras_un_rechazo_se_propone_de_nuevo` (Task 8).
5. **Un acuerdo con plazo negociado** (palanca `plazo_meses`) usa ese plazo en el costo total y en
   la fecha de fin del contrato, no el del evento. Pruebas: `test_el_plazo_acordado_manda` (Task 6)
   y `test_candidatos_usan_los_valores_acordados` (Task 7).

---

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `libs/comun/src/comun/topologia.py`, `infra/rabbitmq/definitions.json` | Tipos de evento nuevos y la cola `proveedores.eventos` |
| `services/inteligencia/src/inteligencia/dominio/adjudicacion.py` (nuevo) | Costo total, riesgo, normalización, puntaje, orden, explicación y sensibilidad. Puro, sin E/S |
| `services/inteligencia/src/inteligencia/api/adjudicacion.py` (nuevo) | `POST /adjudicacion/recomendacion`: arma las entradas del dominio con el `Contexto` |
| `services/inteligencia/src/inteligencia/contexto.py` | Guarda los meses de desempeño por proveedor (`desempeno`), para la tendencia de incidentes |
| `services/inteligencia/alembic/versions/0002_adjudicacion.py` (nuevo), `modelos.py`, `api/esquemas.py`, `api/ajustes.py` | Pesos de adjudicación y umbral en `configuracion` |
| `services/inteligencia/src/inteligencia/validacion.py` | Sección «Adjudicación» del informe (200 eventos simulados) |
| `services/negociacion/alembic/versions/0002_adjudicacion.py` (nuevo), `modelos.py` | Tabla `adjudicacion`, estados nuevos, `motivo_desierta`, `resultado_avisado_en` y el actor `aprobador` |
| `services/negociacion/src/negociacion/dominio/adjudicacion.py` (nuevo) | Regla de aprobación, términos del contrato y `sumar_meses`. Puro |
| `services/negociacion/src/negociacion/adjudicacion.py` (nuevo) | Casos de uso: candidatos, evaluar, proponer, aprobar, rechazar y declarar desierta |
| `services/negociacion/src/negociacion/api/adjudicacion.py` (nuevo) | Las cinco rutas de la spec §4.2 |
| `services/negociacion/src/negociacion/avisos.py` (nuevo) | Envío de los avisos de resultado pendientes (correo y `negociacion.resultado_enviado`) |
| `services/negociacion/src/negociacion/integraciones.py`, `correo.py`, `turnos.py`, `vencimientos.py`, `consultas.py`, `api/esquemas.py`, `api/dependencias.py`, `bitacora.py`, `main.py` | Integración de lo anterior |
| `services/proveedores/src/proveedores/adjudicaciones.py` (nuevo), `eventos.py` (nuevo), `alembic/versions/0004_evento_procesado.py` (nuevo), `modelos.py`, `importacion/aplicar.py`, `main.py` | Consumidor de `negociacion.adjudicada` y el contrato nuevo |
| `services/administracion/src/administracion/eventos.py`, `textos.py`, `alembic/versions/0004_resultado_negociacion.py` (nuevo), `modelos.py`; `web/src/actividad.ts`, `web/src/paginas/Correos.tsx` | Actividad y Correos |
| `infra/smoke_test.py`, `docs/arquitectura/*`, `README.md`, PRD | Prueba de humo de punta a punta y documentación |

---

### Task 1: Topología de los eventos nuevos

**Files:**
- Modify: `libs/comun/src/comun/topologia.py`
- Modify: `infra/rabbitmq/definitions.json`
- Test: `libs/comun/tests/test_topologia.py`

**Interfaces:**
- Produces:
  - `TIPOS_EVENTO` suma `"negociacion.adjudicada"`, `"negociacion.desierta"` y
    `"negociacion.resultado_enviado"`;
  - `COLA_PROVEEDORES = Cola("proveedores.eventos", ("negociacion.adjudicada",))`, incluida en
    `COLAS` (en este orden: inteligencia, administración, negociación, proveedores).

- [ ] **Step 1: Escriba la prueba que falla** en `test_topologia.py`

```python
def test_la_adjudicacion_llega_a_proveedores_y_a_la_actividad() -> None:
    assert colas_de("negociacion.adjudicada") == ["administracion.actividad", "proveedores.eventos"]
    assert colas_de("negociacion.desierta") == ["administracion.actividad"]
    assert colas_de("negociacion.resultado_enviado") == ["administracion.actividad"]
```

- [ ] **Step 2: Córrala y vea que falla**

Run: `uv run pytest libs/comun/tests/test_topologia.py -q`
Expected: FAIL (la cola `proveedores.eventos` no existe).

- [ ] **Step 3: Agregue los tipos y la cola en `topologia.py`.** Después regenere
  `definitions.json` con el mismo formato:
  `json.dumps(definiciones(), ensure_ascii=False, indent=2) + "\n"`. Compare antes con el archivo
  actual para conservar la indentación.

- [ ] **Step 4: Corra la suite de topología**

Run: `uv run pytest libs/comun/tests/test_topologia.py -q`
Expected: PASS, incluidas `test_el_archivo_coincide_con_el_modulo` y la prueba que exige que todo
evento publicado llegue a una cola.

- [ ] **Step 5: Commit** — `feat(comun): eventos de adjudicación y la cola de proveedores`

---

### Task 2: Dominio de la recomendación (`inteligencia`)

**Files:**
- Create: `services/inteligencia/src/inteligencia/dominio/adjudicacion.py`
- Test: `services/inteligencia/tests/test_adjudicacion.py`

**Interfaces:**
- Produces (todas `@dataclass(frozen=True)` salvo las funciones):
  - **Datos de entrada:**
    - `LineaCandidato(codigo: str, unidad: str, cantidad: Decimal, precio: Decimal)`;
    - `Candidato(id: str, proveedor_id: str, nombre: str, plazo_meses: int, cuota: Decimal, sla: Decimal | None, lineas: tuple[LineaCandidato, ...])`;
    - `PesosAdjudicacion(costo: int = 40, desempeno: int = 30, riesgo: int = 15, sla: int = 15)`, con `como_dict() -> dict[str, int]`;
    - `Riesgo(valor: float, concentracion: float, tendencia: float, sin_historial: bool)`, con la propiedad `nivel -> Literal["bajo", "medio", "alto"]` (`< 1/3` bajo, `< 2/3` medio, si no, alto);
    - `Entrada(candidato: Candidato, costo_total: Decimal, costo_total_mxn: Decimal, desempeno: float, riesgo: Riesgo)`.
  - **Resultado:**
    - `Evaluado(entrada: Entrada, normalizados: dict[str, float], aportes: dict[str, float], puntaje: float, lugar: int)`;
    - `Sensibilidad(criterio: str, peso_actual: int, peso_necesario: int | None, ganaria: str | None)`, donde `ganaria` es el `id` del candidato;
    - `Recomendacion(pesos: PesosAdjudicacion, evaluados: list[Evaluado], recomendado: str, margen: float, explicacion: list[str], sensibilidad: list[Sensibilidad])`, con `evaluados` ordenados por lugar.
  - **Funciones:**
    - `costo_total(candidato: Candidato, unidades_mensuales: frozenset[str] = UNIDADES_MENSUALES) -> Decimal`;
    - `tendencia_incidentes(incidentes: Sequence[float]) -> float`: recibe los meses en orden cronológico y usa los últimos 6;
    - `concentracion(gasto_proveedor_mxn: Decimal, gasto_total_mxn: Decimal, costo_anual_mxn: Decimal) -> float`;
    - `riesgo(concentracion: float, tendencia: float, meses_historial: int) -> Riesgo`: sin historial si hay menos de 6 meses (`MESES_HISTORIAL_CORTO`);
    - `normalizar(valores: Sequence[float | None], mayor_es_mejor: bool) -> list[float]`;
    - `recomendar(entradas: Sequence[Entrada], pesos: PesosAdjudicacion) -> Recomendacion`.
  - Reusa `UNIDADES_MENSUALES` de `inteligencia.dominio.precios` y `MESES_HISTORIAL_CORTO` de
    `inteligencia.dominio.puntuacion`.

- [ ] **Step 1: Escriba las pruebas que fallan**, con estas aserciones (las fórmulas están en la
  spec §3.1–§3.3):

```python
def test_costo_total_por_tipo_de_unidad() -> None:
    mensual = LineaCandidato("SAAS-CRM", "usuario_mes", Decimal("10"), Decimal("100.00"))
    consumo = LineaCandidato("CONS-QA", "hora", Decimal("50"), Decimal("500.00"))
    c = candidato(plazo_meses=12, cuota=Decimal("1000.00"), lineas=(mensual, consumo))
    assert costo_total(c) == Decimal("10") * Decimal("100.00") * 12 + Decimal("50") * Decimal("500.00") + Decimal("1000.00")

def test_tendencia_de_incidentes() -> None:
    assert tendencia_incidentes([1, 1, 1, 1, 1, 1]) == 0.0
    assert tendencia_incidentes([2, 2, 2, 3, 3, 3]) == 0.5   # (9 − 6) / 6
    assert tendencia_incidentes([0, 0, 0, 5, 5, 5]) == 1.0   # acotado a 1, divisor max(0, 1)
    assert tendencia_incidentes([3, 3, 3, 1, 1, 1]) == 0.0   # bajar no es riesgo

def test_concentracion() -> None:
    assert concentracion(Decimal("100"), Decimal("1000"), Decimal("100")) == pytest.approx(200 / 1100)

def test_normalizar_min_max_e_iguales() -> None:
    assert normalizar([10.0, 20.0, 30.0], mayor_es_mejor=False) == [1.0, 0.5, 0.0]
    assert normalizar([5.0, 5.0], mayor_es_mejor=True) == [1.0, 1.0]
    assert normalizar([None, 99.5, 99.9], mayor_es_mejor=True) == [0.0, 0.0, 1.0]
    assert normalizar([None, None], mayor_es_mejor=True) == [1.0, 1.0]

def test_un_solo_candidato_se_recomienda() -> None:
    r = recomendar([entrada("a")], PesosAdjudicacion())
    assert r.recomendado == "a" and r.evaluados[0].puntaje == 100.0
    assert r.explicacion[0] == "Es el único acuerdo tentativo."

def test_el_puntaje_es_la_suma_ponderada_y_ordena() -> None:
    # a: más barato; b: mejor desempeño; mismo riesgo y SLA → con 40/30/15/15 gana a (70 contra 60).
    ...

def test_empate_por_menor_costo_luego_desempeno_luego_nombre() -> None: ...

def test_sensibilidad_encuentra_el_peso_que_cambia_al_ganador() -> None:
    # Con a más barato y b mejor en desempeño, bajar el peso del costo lo bastante hace ganar a b:
    s = next(x for x in r.sensibilidad if x.criterio == "costo")
    assert s.ganaria == "b" and s.peso_necesario is not None and s.peso_necesario < 40

def test_la_explicacion_nombra_margen_y_aportes() -> None:
    assert r.explicacion[0].startswith("Recomendamos a ")  # «Recomendamos a {A}: obtiene {pA} de 100 contra {pB} de {B}, un margen de {m}.»
```

- **Pruebas de propiedades** (Hypothesis, de 2 a 5 candidatos con valores aleatorios):
  - `test_propiedad_puntajes_entre_0_y_100`;
  - `test_propiedad_el_recomendado_tiene_el_maximo`;
  - `test_propiedad_subir_un_peso_no_baja_al_mejor_en_ese_criterio`: reescala los otros pesos en
    proporción, como en la spec §3.3.

- [ ] **Step 2: Córralas y vea que fallan**

Run: `uv run pytest services/inteligencia/tests/test_adjudicacion.py -q`
Expected: FAIL (`ModuleNotFoundError: inteligencia.dominio.adjudicacion`).

- [ ] **Step 3: Implemente el módulo.** Algunas decisiones que las pruebas no fijan:
  - el puntaje se calcula como `sum(peso × normalizado) / 100 × 100` y se redondea a 1 decimal solo
    al presentarlo;
  - en la sensibilidad, para cada criterio se recorre el peso de 0 a 100 de 1 en 1, reescalando los
    demás en proporción a sus valores actuales (si todos valen 0, se reparten por igual); se elige el
    peso más cercano al actual con el que otro candidato queda primero;
  - los textos de la explicación son constantes del módulo, en «usted»;
  - el aporte de cada criterio se describe con su dato: costo en MXN con `$` y separador de miles,
    puntuación con 1 decimal, riesgo como «bajo/medio/alto» y SLA en %.

- [ ] **Step 4: Corra las pruebas y la cobertura**

Run: `uv run pytest services/inteligencia/tests/test_adjudicacion.py -q --cov=inteligencia.dominio.adjudicacion --cov-report=term-missing`
Expected: PASS y cobertura de 80 % o más.

- [ ] **Step 5: Commit** — `feat(inteligencia): dominio de la recomendación de adjudicación`

---

### Task 3: Pesos de adjudicación y umbral en la configuración

**Files:**
- Create: `services/inteligencia/alembic/versions/0002_adjudicacion.py`
- Modify:
  - `services/inteligencia/src/inteligencia/modelos.py` (`Configuracion`);
  - `services/inteligencia/src/inteligencia/api/esquemas.py` (`ConfiguracionSalida`, `ConfiguracionEntrada`);
  - `services/inteligencia/src/inteligencia/api/ajustes.py`.
- Test: `services/inteligencia/tests/test_api_ajustes.py`, `test_migraciones.py`

**Interfaces:**
- Produces: columnas y campos `adjudicacion_costo`, `adjudicacion_desempeno`,
  `adjudicacion_riesgo` y `adjudicacion_sla` (enteros, 40/30/15/15 por defecto) y
  `umbral_aprobacion` (`Numeric(14, 2)`, `500000.00` por defecto).
  - **Ruling:** se llaman `adjudicacion_*` y no `peso_*` como en la spec §3.4, porque `peso_sla` ya
    existe y es un peso de la puntuación. Además, `guardar_configuracion` valida como pesos de la
    puntuación todo campo que empieza con `peso_`.
- En `ConfiguracionEntrada` los cinco campos son **opcionales** (`None` = sin cambio): la pantalla
  actual de Configuración no los envía hasta 4′b. Si viene alguno de los cuatro pesos, deben venir
  los cuatro y sumar 100. Si no: 422 con `codigo` `pesos_invalidos` y el campo
  `body.pesos_adjudicacion`.

- [ ] **Step 1: Escriba las pruebas que fallan**

```python
async def test_la_configuracion_trae_los_pesos_de_adjudicacion(cliente, comprador) -> None:
    datos = (await cliente.get("/configuracion", headers=comprador)).json()
    assert (datos["adjudicacion_costo"], datos["adjudicacion_desempeno"], datos["adjudicacion_riesgo"], datos["adjudicacion_sla"]) == (40, 30, 15, 15)
    assert datos["umbral_aprobacion"] == "500000.00"

async def test_guardar_sin_los_campos_de_adjudicacion_los_conserva(cliente, admin) -> None: ...

async def test_los_pesos_de_adjudicacion_deben_sumar_100(cliente, admin) -> None:
    # 50/30/15/15 → 422, codigo pesos_invalidos, campo body.pesos_adjudicacion

async def test_cambiar_el_umbral_publica_el_cambio(cliente, admin, fabrica) -> None:
    # el Outbox recibe configuracion.actualizada con {"campo": "umbral_aprobacion", ...}
```

- [ ] **Step 2: Córralas y vea que fallan**

Run: `uv run pytest services/inteligencia/tests/test_api_ajustes.py -q`
Expected: FAIL (`KeyError: 'adjudicacion_costo'`).

- [ ] **Step 3: Implemente la migración y los cambios.**
  - La migración `0002_adjudicacion` agrega las columnas con `server_default`. No hace falta
    `GRANT` nuevo: el usuario de la aplicación ya actualiza `configuracion`.
  - El modelo y los esquemas ganan los campos.
  - `guardar_configuracion` ignora los campos `None` y valida los cuatro pesos juntos.

- [ ] **Step 4: Corra la suite del servicio**

Run: `uv run pytest services/inteligencia -q`
Expected: PASS, incluida `test_migraciones.py` (modelos = migraciones).

- [ ] **Step 5: Commit** — `feat(inteligencia): pesos de adjudicación y umbral de aprobación en la configuración`

---

### Task 4: Ruta de la recomendación (`inteligencia`)

**Files:**
- Create: `services/inteligencia/src/inteligencia/api/adjudicacion.py`
- Modify:
  - `services/inteligencia/src/inteligencia/contexto.py` (campo `desempeno: dict[str, list[Mes]]`, el diccionario `desempeno` que ya arma `construir`);
  - `services/inteligencia/src/inteligencia/api/esquemas.py`;
  - `services/inteligencia/src/inteligencia/main.py` (incluir el router).
- Test: `services/inteligencia/tests/test_api_adjudicacion.py`

**Interfaces:**
- Consumes: Task 2 (`recomendar`, `Entrada`, `Candidato`, `costo_total`, `riesgo`,
  `concentracion`, `tendencia_incidentes`) y Task 3 (configuración).
- Produces: `POST /adjudicacion/recomendacion` (rol interno, `Interno`).
  - **Cuerpo (`RecomendacionEntrada`):**
    - `moneda: Literal["MXN", "USD"]`;
    - `pesos: PesosEntrada | None` (cuatro enteros de 0 a 100 que suman 100);
    - `candidatos: list[CandidatoEntrada]`, de 1 a 10 elementos con `id` únicos. Cada
      `CandidatoEntrada` lleva `id`, `proveedor_id: UUID`, `nombre`, `plazo_meses` (de 1 a 60),
      `cuota_implementacion: Decimal`, `sla: Decimal | None` y `lineas` (de 1 a 20 elementos con
      `codigo_servicio`, `unidad`, `cantidad` y `precio`).
  - **Respuesta (`RecomendacionSalida`):**
    - `pesos`, `umbral_aprobacion` y `tipo_cambio: {periodo, usd_mxn} | None`;
    - `candidatos`, en orden de lugar. Cada uno lleva `id`, `proveedor_id`, `nombre`,
      `costo_total`, `costo_total_mxn`, `desempeno`, `riesgo` (`valor`, `nivel`, `concentracion`,
      `tendencia` y `sin_historial`), `sla`, `normalizados`, `aportes`, `puntaje` y `lugar`;
    - `recomendado`, `margen`, `explicacion: list[str]` y `sensibilidad: list[{criterio, peso_actual, peso_necesario, ganaria}]`.
- **Cómo arma las entradas:**
  - **Desempeño:** `ctx.puntuaciones[pid].puntuacion`. Sin puntuación, el promedio de las
    puntuaciones de los proveedores de su categoría principal (`proveedores[pid].categorias[0]`), o
    de todos si su categoría no tiene ninguna, o 50.0 si nadie tiene.
  - **Meses de historial:** `ctx.puntuaciones[pid].meses`, o 0 si no tiene puntuación.
  - **Tendencia:** los `incidentes` de `ctx.desempeno[pid]`.
  - **Concentración:** el gasto anual vigente en MXN por proveedor y el total, con los
    `ContratoInfo` vigentes a `ctx.hoy`, `valor_mensual() × 12` y `a_mxn`. El costo anual del
    candidato es `(costo_total − cuota) / plazo × 12`, convertido a MXN.
  - **Tipo de cambio:** `tipo_cambio_en(ctx.tipos_cambio, ctx.hoy)`.

- [ ] **Step 1: Escriba las pruebas que fallan**, con la fixture `datos` (`generar(42, n_proveedores=15)`
  cargada, como en `test_api_proveedores.py`):

```python
async def test_recomienda_y_explica(cliente, comprador, datos) -> None:
    r = await cliente.post("/adjudicacion/recomendacion", json=cuerpo(datos, 3), headers=comprador)
    assert r.status_code == 200
    c = r.json()
    assert [x["lugar"] for x in c["candidatos"]] == [1, 2, 3]
    assert c["recomendado"] == c["candidatos"][0]["id"]
    assert c["pesos"] == {"costo": 40, "desempeno": 30, "riesgo": 15, "sla": 15}
    assert c["umbral_aprobacion"] == "500000.00" and c["explicacion"][0].startswith("Recomendamos a ")

async def test_usa_los_pesos_del_cuerpo(cliente, comprador, datos) -> None: ...
async def test_pesos_que_no_suman_100(cliente, comprador, datos) -> None:  # 422 pesos_invalidos
async def test_candidatos_repetidos_o_vacios(cliente, comprador, datos) -> None:  # 422
async def test_proveedor_sin_puntuacion_usa_la_media_de_su_categoria(cliente, comprador, datos) -> None:
    # un proveedor_id que inteligencia no conoce → sin_historial True, desempeño = media, 200
async def test_en_usd_convierte_el_costo_a_mxn(cliente, comprador, datos) -> None:
    # costo_total_mxn == costo_total × usd_mxn del tipo de cambio más reciente
async def test_sin_token_401_y_proveedor_externo_no_entra(cliente) -> None: ...
```

- [ ] **Step 2: Córralas y vea que fallan**

Run: `uv run pytest services/inteligencia/tests/test_api_adjudicacion.py -q`
Expected: FAIL (404 en la ruta).

- [ ] **Step 3: Implemente la ruta.** Use `Sesion` + `Ctx`; lea los pesos y el umbral con
  `consultas.configuracion(sesion)`, porque el `Contexto` no los tiene. Agregue `desempeno` al
  `Contexto`.

- [ ] **Step 4: Corra la suite del servicio**

Run: `uv run pytest services/inteligencia -q`
Expected: PASS.

- [ ] **Step 5: Commit** — `feat(inteligencia): ruta de la recomendación de adjudicación`

---

### Task 5: Validación con 200 eventos simulados

**Files:**
- Modify: `services/inteligencia/src/inteligencia/validacion.py`
- Modify: `docs/qa/validacion-inteligencia.md` (regenerado)
- Test: `services/inteligencia/tests/test_validacion.py`

**Interfaces:**
- Consumes: Task 2.
- Produces:
  - `ResultadoAdjudicacion(eventos: int, acierto_top1: float, acierto_top2: float, margen_fallos: float | None)`;
  - `validar_adjudicacion(proveedores: list[dict[str, str]], contratos: list[dict[str, str]], desempeno: dict[str, list[Mes]], puntuaciones: dict[str, Puntuacion], oculta: dict[str, dict[str, Any]], hasta: date, eventos: int = 200, semilla: int = 4242) -> ResultadoAdjudicacion`;
  - `META_ADJUDICACION = 0.85`;
  - `Validacion` gana el campo `adjudicacion: ResultadoAdjudicacion` y la propiedad
    `cumple_adjudicacion`.
- **Diseño de los eventos** (spec §3.6; el resto queda a su criterio y se documenta en el informe):
  - una categoría y de 2 a 5 proveedores con puntuación y con esa categoría;
  - el precio acordado es el P50 del servicio en `contratos` × `nivel_precio` latente;
  - el plazo es de 12 meses;
  - el SLA es nulo o, con la semilla, entre 99.0 y 99.9.
  - **Recomendado:** `recomendar` con la puntuación observada.
  - **Verdadero:** el mismo cálculo con `desempeno = calidad × 100`. El costo, el riesgo y el SLA
    son los mismos.
- El informe gana la sección «Adjudicación» con el acierto top-1 y top-2, el margen promedio de los
  fallos y «Cumple: sí/no». El código de salida de `principal` no cambia: el PRD solo reporta esta
  meta.

- [ ] **Step 1: Escriba las pruebas que fallan**

```python
def test_la_validacion_reporta_la_adjudicacion(tmp_path) -> None:
    v = validar(carpeta_con_datos(tmp_path), verdad)  # como las pruebas existentes
    assert v.adjudicacion.eventos == 200
    assert 0.0 <= v.adjudicacion.acierto_top1 <= v.adjudicacion.acierto_top2 <= 1.0

def test_el_informe_incluye_la_seccion_de_adjudicacion(tmp_path) -> None:
    assert "## Adjudicación" in informe(v, date(2026, 10, 16)) and "top-1" in informe(...)

def test_misma_semilla_mismo_resultado(tmp_path) -> None: ...
```

- [ ] **Step 2: Córralas y vea que fallan.** Run: `uv run pytest services/inteligencia/tests/test_validacion.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implemente `validar_adjudicacion`** y la sección del informe.
- [ ] **Step 4: Corra las pruebas y regenere el informe**

Run: `uv run pytest services/inteligencia/tests/test_validacion.py -q` y después
`uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json`.
Expected: PASS, y `docs/qa/validacion-inteligencia.md` con la sección nueva. Si el acierto top-1
queda bajo 85 %, no ajuste los criterios: reporte el número y escriba en el informe por qué falla
(por ejemplo, en qué tipo de eventos).

- [ ] **Step 5: Commit** — `feat(inteligencia): validación de la recomendación con 200 eventos simulados`

---

### Task 6: Datos y dominio de la adjudicación (`negociacion`)

**Files:**
- Create:
  - `services/negociacion/alembic/versions/0002_adjudicacion.py`;
  - `services/negociacion/src/negociacion/dominio/adjudicacion.py`.
- Modify: `services/negociacion/src/negociacion/modelos.py` y `bitacora.py`.
- Test:
  - `services/negociacion/tests/test_dominio_adjudicacion.py` (nuevo);
  - `services/negociacion/tests/test_migraciones.py`.

**Interfaces:**
- Produces (modelos):
  - `ESTADOS_EVENTO = ("borrador", "abierto", "en_evaluacion", "pendiente_aprobacion", "adjudicado", "desierto", "cancelado")`;
  - `Evento.motivo_desierta: str | None` (500);
  - `SesionNegociacion.resultado_avisado_en: datetime | None`;
  - el `CHECK` de `bitacora.actor_tipo` suma `aprobador`;
  - modelo `Adjudicacion` con las columnas de la spec §4.1:
    - `estado` en `("pendiente", "aprobada", "rechazada", "directa")`;
    - `motivo_aprobacion` como `ARRAY(String)` con los valores `umbral` y `fuera_de_limites`;
    - `recomendacion` como `JSONB`;
    - los montos como `Numeric(16, 2)`;
    - `CHECK (NOT se_aparta OR justificacion IS NOT NULL)`.
- Produces (permisos en la migración):
  - `GRANT SELECT, INSERT ON adjudicacion TO negociacion`;
  - `GRANT UPDATE (estado, decidida_por_id, decidida_por_nombre, decidida_en, motivo_rechazo, contrato_folio) ON adjudicacion TO negociacion`.
- Produces (bitácora): `de_usuario(usuario: Usuario, tipo: str = "comprador") -> Actor`.
- Produces (dominio puro):
  - `sumar_meses(fecha: date, meses: int) -> date`, que acota el día al fin de mes;
  - `requiere_aprobacion(costo_total_mxn: Decimal, umbral: Decimal, fuera_de_limites: bool) -> tuple[bool, list[str]]`, que devuelve `(True, ["umbral", "fuera_de_limites"])` según el caso;
  - `TerminosContrato` (dataclass con los campos de la spec §4.4) y su `para_evento() -> dict[str, Any]` (montos como texto);
  - `terminos_contrato(*, folio_evento: str, tipo_evento: str, moneda: str, plazo_evento: int, valores: Valores, lineas: Sequence[LineaTerminos], contrato_vigente: Mapping[str, Any] | None, decidida_en: datetime) -> TerminosContrato`, con `LineaTerminos(id: str, codigo_servicio: str, cantidad: Decimal)` y `Valores` de `negociacion.dominio.terminos`.

- [ ] **Step 1: Escriba las pruebas que fallan**

```python
def test_regla_de_aprobacion() -> None:
    assert requiere_aprobacion(Decimal("400000"), Decimal("500000"), False) == (False, [])
    assert requiere_aprobacion(Decimal("500000.01"), Decimal("500000"), False) == (True, ["umbral"])
    assert requiere_aprobacion(Decimal("1"), Decimal("500000"), True) == (True, ["fuera_de_limites"])
    assert requiere_aprobacion(Decimal("600000"), Decimal("500000"), True) == (True, ["umbral", "fuera_de_limites"])

def test_sumar_meses_acota_el_fin_de_mes() -> None:
    assert sumar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)

def test_compra_empieza_el_dia_siguiente_en_hora_de_mexico() -> None:
    # decidida_en = 2026-11-02T05:30Z (aún 1/11 en CDMX) → fecha_inicio 2026-11-02, fin 2027-11-01 con 12 meses
def test_renovacion_empieza_al_dia_siguiente_del_contrato_vigente() -> None:
def test_lo_no_negociado_sale_del_contrato_vigente_o_del_valor_por_defecto() -> None:
    # compra: plazo_pago_dias 30, sla None, tope None, cuota 0; renovación: los de foto.contrato
def test_el_plazo_acordado_manda() -> None:
    # valores.palancas["plazo_meses"] = 24 con plazo_evento 12 → fecha_fin a 24 meses
def test_folio_del_contrato() -> None:
    assert terminos(...).folio == "C-NEG-2026-0004"
```

```python
# test_migraciones.py
async def test_la_aplicacion_no_reescribe_la_propuesta(urls_bd) -> None:
    # como usuario negociacion: UPDATE adjudicacion SET justificacion = 'x' → permiso denegado;
    # UPDATE adjudicacion SET estado = 'aprobada' → permitido
```

- [ ] **Step 2: Córralas y vea que fallan.**
  Run: `uv run pytest services/negociacion/tests/test_dominio_adjudicacion.py services/negociacion/tests/test_migraciones.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implemente la migración, los modelos y el dominio.** `test_modelos_y_migraciones_coinciden` tiene que seguir en verde.
- [ ] **Step 4: Corra la suite del servicio.** Run: `uv run pytest services/negociacion -q`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(negociacion): datos y reglas de la adjudicación`

---

### Task 7: Candidatos y evaluación (`negociacion`)

**Files:**
- Create: `services/negociacion/src/negociacion/adjudicacion.py` (casos de uso; esta tarea crea `candidatos` y `evaluar`)
- Create: `services/negociacion/src/negociacion/api/adjudicacion.py` (router; esta tarea crea el `GET`)
- Modify:
  - `integraciones.py`: `async def recomendacion(self, token: str, cuerpo: dict[str, Any]) -> dict[str, Any]`, que hace `POST {inteligencia}/adjudicacion/recomendacion`; un 422 de inteligencia o cualquier falla responde `no_disponible()`;
  - `api/esquemas.py`;
  - `main.py` (incluir el router).
- Modify (pruebas): `services/negociacion/tests/conftest.py`. `Externos` responde al `POST` de
  `intel` con una recomendación determinista. Esa respuesta:
  - ordena por la suma de `precio × cantidad` de cada candidato;
  - usa `costo_total_mxn = costo_total × externos.usd_mxn` si la moneda es USD;
  - expone `umbral = externos.umbral` (500000.00);
  - guarda la petición en `externos.peticiones`.
- Test: `services/negociacion/tests/test_api_adjudicacion.py` (nuevo)

**Interfaces:**
- Consumes: Task 6 (modelos) y `turnos.ultima_oferta_proveedor`.
- Produces:
  - `async def candidatos(bd: AsyncSession, evento: Evento) -> list[dict[str, Any]]`. Arma el
    `CandidatoEntrada` de cada sesión en `acuerdo_tentativo`:
    - los precios salen de `valores["precios"][str(linea.id)]`;
    - el plazo, de `valores["palancas"].get("plazo_meses")` o, si no se negoció,
      `evento.plazo_meses`;
    - la cuota, de `palancas.get("cuota_implementacion")` o 0;
    - el SLA, de `palancas.get("sla_disponibilidad")`. Si no se negoció, el de
      `evento.foto["contrato"]` en una renovación, y nulo en una compra.
  - `async def evaluar(bd: AsyncSession, integ: Integraciones, token: str, evento: Evento, pesos: dict[str, int] | None) -> dict[str, Any]`,
    que devuelve la respuesta de `inteligencia`.
  - `GET /eventos/{evento_id}/evaluacion?pesos=40,30,15,15` (`Lector`). Responde
    `esquemas.Evaluacion`:
    - `recomendacion`, que es `null` si el evento es `desierto` o no tiene candidatos;
    - `vigente`, la adjudicación pendiente o decidida, o `null`;
    - `historial`, las propuestas anteriores.
  - **Errores:** en otro estado, 409 `estado_invalido`; pesos mal formados, 422 `pesos_invalidos`.

- [ ] **Step 1: Escriba las pruebas que fallan.** Use `publicar` y `ofertar` y acepte con la
  propuesta del agente, como en `test_supervision.py`, para dejar sesiones en `acuerdo_tentativo`.

```python
async def test_la_evaluacion_pide_la_recomendacion_con_los_acuerdos(...) -> None:
    # dos proveedores con acuerdo tentativo → la petición a intel lleva 2 candidatos con los precios acordados
async def test_candidatos_usan_los_valores_acordados(...) -> None:
    # con palanca plazo_meses acordada en 24, el candidato lleva plazo_meses 24
async def test_evaluacion_fuera_de_estado(...) -> None:  # abierto → 409 estado_invalido
async def test_inteligencia_caida_responde_503(...) -> None:
async def test_el_aprobador_puede_ver_la_evaluacion(...) -> None:  # Lector
```

- [ ] **Step 2: Córralas y vea que fallan.** Run: `uv run pytest services/negociacion/tests/test_api_adjudicacion.py -q`. Expected: FAIL.
- [ ] **Step 3: Implemente** `recomendacion`, `candidatos`, `evaluar` y la ruta.
- [ ] **Step 4: Corra la suite del servicio.** Run: `uv run pytest services/negociacion -q`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(negociacion): evaluación de los acuerdos con la recomendación de inteligencia`

---

### Task 8: Proponer, aprobar, rechazar y declarar desierta

**Files:**
- Modify:
  - `services/negociacion/src/negociacion/adjudicacion.py`;
  - `services/negociacion/src/negociacion/api/adjudicacion.py`;
  - `api/esquemas.py` (`EstadoEvento` con los tres estados nuevos);
  - `api/dependencias.py` (`Aprobador = Annotated[Usuario, Depends(requiere_rol("aprobador"))]`).
- Test: `services/negociacion/tests/test_api_adjudicacion.py`

**Interfaces:**
- Consumes: Tasks 6 y 7.
- Produces (rutas, todas con el evento bloqueado `FOR UPDATE` y validando el estado de origen):
  - `POST /eventos/{id}/adjudicacion` (`Comprador`), con cuerpo `{sesion_id, pesos?, justificacion?}`:
    - vuelve a evaluar en el servidor;
    - `se_aparta = sesion_id != recomendado`, y con `se_aparta` la justificación es obligatoria:
      de 10 a 1,000 caracteres sin espacios sobrantes, o 422 `justificacion_requerida`;
    - aplica `requiere_aprobacion` con `costo_total_mxn`, el `umbral_aprobacion` de la respuesta y
      `sesion.fuera_de_limites`;
    - si no la requiere: fila `directa`, decidida por el comprador, y evento `adjudicado`;
    - si la requiere: fila `pendiente` y evento `pendiente_aprobacion`.
  - `POST /eventos/{id}/adjudicacion/aprobar` (`Aprobador`): si el usuario es quien propuso, 403
    `misma_persona`; si no, fila `aprobada` y evento `adjudicado`.
  - `POST /eventos/{id}/adjudicacion/rechazar` (`Aprobador`), con cuerpo `{motivo}` (de 1 a 500):
    misma regla de persona; fila `rechazada` y evento `en_evaluacion`.
  - `POST /eventos/{id}/desierta` (`Comprador`), con cuerpo `{motivo}`: desde `en_evaluacion`, el
    evento pasa a `desierto` y guarda `motivo_desierta`.
  - **Al adjudicar** (directa o aprobada):
    - se calculan los `terminos_contrato`;
    - se guarda `contrato_folio`;
    - se publica `registrar_evento(bd, Outbox, "negociacion.adjudicada", …)` con el payload de la
      spec §4.5 (`aprobacion` es `directa` o `aprobada`).
  - **Al declarar desierta:** `negociacion.desierta` con el `motivo` del comprador.
  - **Bitácora:** `adjudicacion.propuesta`, `adjudicacion.directa`, `adjudicacion.aprobada`,
    `adjudicacion.rechazada` y `evento.desierto`. El aprobador va con
    `de_usuario(usuario, "aprobador")`.
  - **Respuesta:** `esquemas.Evaluacion` actualizada.
  - **Errores:** `sesion_no_candidata` (422) si la sesión no es de ese evento o no está en
    `acuerdo_tentativo`; `estado_invalido` (409) en cualquier transición desde otro estado.

- [ ] **Step 1: Escriba las pruebas que fallan**

```python
async def test_bajo_el_umbral_el_comprador_adjudica_directo(...) -> None:
    # estado adjudicado, vigente.estado "directa", Outbox con negociacion.adjudicada y contrato.folio "C-<folio>"
async def test_sobre_el_umbral_queda_pendiente_y_el_aprobador_aprueba(...) -> None:
async def test_fuera_de_limites_siempre_pide_aprobacion(...) -> None:
    # sesión aceptada a mano con confirmar_fuera_de_limites → pendiente aunque esté bajo el umbral
async def test_apartarse_de_la_recomendacion_exige_justificacion(...) -> None:  # 422 justificacion_requerida
async def test_quien_propone_no_aprueba_aunque_tenga_los_dos_roles(...) -> None:
    # token con roles comprador y aprobador, mismo sub → propone (pendiente) y al aprobar recibe 403 misma_persona
async def test_tras_un_rechazo_se_propone_de_nuevo(...) -> None:
    # rechazar → en_evaluacion; nueva propuesta → historial con la rechazada; aprobar dos veces → 409
async def test_evento_en_usd_compara_el_umbral_en_mxn(...) -> None:
    # externos.usd_mxn = 20; costo 30,000 USD (600,000 MXN) → pendiente
async def test_declarar_desierta(...) -> None:  # motivo guardado, negociacion.desierta en el Outbox
async def test_transiciones_desde_otro_estado_dan_409(...) -> None:
async def test_solo_el_comprador_propone_y_solo_el_aprobador_aprueba(...) -> None:  # 403
async def test_cada_accion_queda_en_la_bitacora(...) -> None:
```

- [ ] **Step 2: Córralas y vea que fallan.** Run: `uv run pytest services/negociacion/tests/test_api_adjudicacion.py -q`. Expected: FAIL.
- [ ] **Step 3: Implemente** los casos de uso y las rutas. La lista de eventos (`GET /eventos?estado=`) acepta los estados nuevos a través de `EstadoEvento`.
- [ ] **Step 4: Corra la suite del servicio.** Run: `uv run pytest services/negociacion -q`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(negociacion): propuesta, aprobación, rechazo y desierta`

---

### Task 9: Desierta automática, avisos y resultado en el portal

**Files:**
- Create: `services/negociacion/src/negociacion/avisos.py`
- Modify:
  - `turnos.py` (`cerrar_eventos_terminados`);
  - `vencimientos.py` (`ejecutar_periodicamente` también llama a `avisos.enviar_pendientes`);
  - `correo.py` (`resultado(...)`);
  - `consultas.py` (`vista_portal`);
  - `api/esquemas.py` (`VistaPortal.resultado`);
  - `main.py` (pasarle a la tarea `enviar_correo` y `config`).
- Test:
  - `services/negociacion/tests/test_avisos.py` (nuevo);
  - `test_vencimientos.py`;
  - `test_portal.py`.

**Interfaces:**
- Consumes: Tasks 6 y 8 y `publicacion.enlace` / `correo.NO_ENTREGADO`, con su patrón.
- Produces:
  - `cerrar_eventos_terminados` lleva a `desierto` los eventos que cierra sin ninguna sesión en
    `acuerdo_tentativo`. En ese caso:
    - la bitácora registra `evento.desierto` con `SISTEMA`;
    - se publica `negociacion.desierta` con `motivo` `"sin_acuerdos"` y el actor `SISTEMA`.
  - `correo.resultado(*, remitente: str, destinatario: str, contacto: str, titulo: str, folio: str, resultado: Literal["adjudicada", "no_elegida", "desierta"]) -> EmailMessage`.
    - El asunto es «Resultado de la negociación {folio}».
    - El cuerpo usa los textos de la spec §4.6. No incluye el nombre del ganador, ningún monto ni
      ningún enlace.
  - `async def enviar_pendientes(fabrica: async_sessionmaker[AsyncSession], enviar: EnviarCorreo, config: Configuracion, momento: datetime) -> int`:
    - trabaja las sesiones con `resultado_avisado_en IS NULL` de eventos `adjudicado` o `desierto`;
    - manda el correo de cada una y, en la misma transacción, marca `resultado_avisado_en`;
    - publica `negociacion.resultado_enviado` (payload como `invitacion_enviada`, más `resultado`);
    - registra `resultado.enviado` en la bitácora;
    - devuelve cuántos procesó. Un correo que falla queda `fallido` y no se reintenta, como una
      invitación.
  - `VistaPortal.resultado: Literal["adjudicada", "no_elegida", "desierta"] | None`.

- [ ] **Step 1: Escriba las pruebas que fallan**

```python
async def test_cerrar_sin_acuerdos_deja_la_negociacion_desierta(...) -> None:
    # la única sesión termina sin acuerdo → evento desierto, Outbox negociacion.desierta motivo "sin_acuerdos"
async def test_avisos_al_adjudicar(...) -> None:
    # dos sesiones; adjudica a una; enviar_pendientes → 2 correos: «adjudicada» y «no_elegida»,
    # resultado_avisado_en marcado, 2 negociacion.resultado_enviado; repetir → 0
async def test_el_aviso_no_revela_ganador_ni_montos(...) -> None:
    # ningún correo contiene el nombre del otro proveedor ni dígitos de precios ni "#t="
async def test_correo_caido_queda_fallido(...) -> None:  # buzon.falla = True
async def test_el_portal_muestra_el_resultado(...) -> None:
    # antes de la fecha límite: tras adjudicar, vista.resultado es "adjudicada" para la ganadora y "no_elegida" para la otra
```

- [ ] **Step 2: Córralas y vea que fallan.** Run: `uv run pytest services/negociacion/tests/test_avisos.py services/negociacion/tests/test_portal.py services/negociacion/tests/test_vencimientos.py -q`. Expected: FAIL.
- [ ] **Step 3: Implemente** lo descrito.
- [ ] **Step 4: Corra la suite del servicio.** Run: `uv run pytest services/negociacion -q`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(negociacion): desierta automática y aviso del resultado a los proveedores`

---

### Task 10: El contrato nuevo en `proveedores`

**Files:**
- Create:
  - `services/proveedores/alembic/versions/0004_evento_procesado.py`;
  - `services/proveedores/src/proveedores/eventos.py` (`aplicar` y `atendedor`, con el patrón de `negociacion/eventos.py`);
  - `services/proveedores/src/proveedores/adjudicaciones.py`.
- Modify:
  - `modelos.py` (`EventoProcesado`);
  - `importacion/aplicar.py` (extraer `payload_contrato`);
  - `main.py` (el ciclo de vida arranca `ConsumidorEventos(config.rabbitmq_url, COLA_PROVEEDORES, atendedor(sesiones))`).
- Test: `services/proveedores/tests/test_adjudicaciones.py` (nuevo)

**Interfaces:**
- Consumes: Task 1 (`COLA_PROVEEDORES`) y el payload de `negociacion.adjudicada` (spec §4.5 y Task 8).
- Produces:
  - `payload_contrato(contrato: Contrato, rfc_proveedor: str, servicios: Mapping[str, ServicioCatalogo]) -> dict[str, Any]`.
    Es el mismo payload de `contrato.registrado` que hoy arma `_payload_contrato`, y ahora lo usan
    la importación y la adjudicación. Las pruebas de importación existentes no cambian.
  - `async def registrar_adjudicacion(bd: AsyncSession, payload: dict[str, Any]) -> bool`:
    - crea el `Contrato` y sus líneas, resolviendo el servicio por código y el proveedor por id;
    - publica `registrar_evento(bd, Outbox, "contrato.registrado", …)`;
    - devuelve False si el folio ya existe;
    - un proveedor o servicio desconocido lanza `KeyError`, y el consumidor común lo trata como
      evento inválido.
  - `aplicar(bd, sobre) -> bool` con `APLICADORES = {"negociacion.adjudicada": …}`.

- [ ] **Step 1: Escriba las pruebas que fallan**

```python
async def test_la_adjudicacion_crea_el_contrato_y_lo_publica(fabrica, catalogo_y_proveedor) -> None:
    # aplicar(sobre negociacion.adjudicada) → Contrato C-NEG-2026-0001 con sus líneas y Outbox contrato.registrado con rfc_proveedor
async def test_el_mismo_evento_dos_veces_no_duplica(fabrica, ...) -> None:  # event_id repetido → False
async def test_folio_existente_no_duplica(fabrica, ...) -> None:  # otro event_id, mismo folio → sin contrato nuevo
async def test_servicio_desconocido_es_evento_invalido(fabrica, ...) -> None:
```

- [ ] **Step 2: Córralas y vea que fallan.** Run: `uv run pytest services/proveedores/tests/test_adjudicaciones.py -q`. Expected: FAIL.
- [ ] **Step 3: Implemente** la migración (`GRANT` no hace falta: `proveedores` tiene un solo usuario), el modelo, el consumidor y la extracción de `payload_contrato`.
- [ ] **Step 4: Corra la suite del servicio.** Run: `uv run pytest services/proveedores -q`. Expected: PASS, incluidas las pruebas de importación.
- [ ] **Step 5: Commit** — `feat(proveedores): registrar el contrato de una adjudicación`

---

### Task 11: Actividad y Correos (`administracion` y su web)

**Files:**
- Create: `services/administracion/alembic/versions/0004_resultado_negociacion.py`, que agrega
  `resultado_negociacion` al `CHECK` de `correo_enviado.tipo`.
- Modify:
  - `services/administracion/src/administracion/eventos.py` (`_negociacion` traduce los tres tipos; `CorreoNegociacion` gana `tipo: str`);
  - `textos.py`;
  - `modelos.py`;
  - `web/src/actividad.ts`;
  - `web/src/paginas/Correos.tsx` (`resultado_negociacion: "Resultado de negociación"`).
- Test: `services/administracion/tests/test_eventos.py`, `test_textos.py`; `web/src/actividad.test.ts`
  (si existe) o la prueba de Correos.

**Interfaces:**
- Consumes: los payloads de Tasks 8 y 9.
- Produces (textos, iguales en `textos.py` y `actividad.ts`):
  - `negociacion.adjudicada`: «Adjudicó la negociación {objeto} a {proveedor}», seguido de
    « (directa)» o « (aprobada)» según `aprobacion`;
  - `negociacion.desierta`: «Declaró desierta la negociación {objeto}», y si hay motivo, «: {motivo}».
    Con `sin_acuerdos`: «La negociación {objeto} quedó desierta: ningún proveedor llegó a un
    acuerdo»;
  - `negociacion.resultado_enviado`: «Envió a {proveedor} el resultado de la negociación {objeto}»,
    más la marca de fallido igual que `_invitacion`.

- [ ] **Step 1: Escriba las pruebas que fallan**

```python
def test_traduce_la_adjudicacion() -> None:  # Registro con detalle {"proveedor", "aprobacion", "contrato_folio"}
def test_traduce_la_desierta_automatica() -> None:  # actor Sistema, detalle motivo "sin_acuerdos"
def test_el_resultado_enviado_registra_su_correo() -> None:  # Registro.correo.tipo == "resultado_negociacion"
```

`test_la_tabla_cubre_todos_los_tipos` y `test_cada_texto_igual_al_de_la_web` deben pasar con los
textos nuevos.

- [ ] **Step 2: Córralas y vea que fallan.** Run: `uv run pytest services/administracion -q`. Expected: FAIL.
- [ ] **Step 3: Implemente** la migración, la traducción, los textos de los dos lados y la etiqueta de Correos.
- [ ] **Step 4: Corra las dos puertas**

Run: `uv run pytest services/administracion -q` y, desde `web/`,
`npm run lint && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`.
Expected: PASS.

- [ ] **Step 5: Commit** — `feat(administracion): adjudicaciones, desiertas y avisos en la Actividad y en Correos`

---

### Task 12: Prueba de humo de punta a punta y documentación

**Files:**
- Modify:
  - `infra/smoke_test.py` (`verificar_adjudicacion`);
  - `docs/arquitectura/eventos.md`, `asyncapi.yaml`, `modelo-de-datos.md`, `c4.md` (la cola de `proveedores`), `README.md`;
  - `docs/arquitectura/openapi/*.json` (con `infra/exportar_contratos.py`);
  - el PRD: una nota en §3.5 sobre D9.
- Create: `docs/arquitectura/adr/011-quien-aprueba-una-adjudicacion.md`
- Modify: `README.md`, en «Qué está hecho y qué falta»:
  - capacidad 7: «Hecho», con el acierto medido;
  - capacidad 9: «Hecho» (aprobaciones y bitácora);
  - capacidad 5: deja de decir que los acuerdos quedan tentativos hasta la aprobación;
  - las métricas.

**Interfaces:**
- Consumes: todo lo anterior.

- [ ] **Step 1: Escriba `verificar_adjudicacion(cliente)` en `smoke_test.py`.** Recorre esta
  secuencia (sin cancelar la negociación, a diferencia de `verificar_negociacion`):
  1. Crea una compra con un proveedor activo y la publica.
  2. Abre el portal con el enlace.
  3. Envía la `ultima_propuesta` del agente como oferta (la acepta). Si el agente no propone en la
     primera ronda, ofrece el límite de la línea.
  4. Espera a que el evento quede `en_evaluacion`.
  5. `GET /evaluacion`.
  6. `POST /adjudicacion` con el recomendado.
  7. Si queda `pendiente_aprobacion`, aprueba con `aprobador1`.
  8. Espera hasta `ESPERA_EVENTOS_S` a que `GET /api/proveedores/proveedores/{id}/contratos`
     contenga el folio `C-<folio>`.

  Llámela desde `main()` después de `verificar_negociacion`.
- [ ] **Step 2: Levante el stack y corra la prueba**

Run: `uv run python infra/arrancar.py`
Expected: `OK: …` con la negociación y la adjudicación. Si el stack ya existía, primero aplique las
migraciones nuevas: las corren las imágenes al arrancar con `--build`.

- [ ] **Step 3: Actualice la documentación.**
  - En `eventos.md` y `asyncapi.yaml`: los tres eventos y la cola `proveedores.eventos`. La
    comprobación de la AsyncAPI contra `colas_de` (la que usó el entregable 3) debe seguir sin
    diferencias.
  - En `modelo-de-datos.md`: `adjudicacion`, las columnas nuevas y `evento_procesado` de
    `proveedores`.
  - Regenere los contratos con `uv run python infra/exportar_contratos.py`.
  - Escriba la ADR-011: D5 a D7 de la spec, con Contexto, Decisión y Consecuencias.
  - Complete el README y la nota del PRD.
- [ ] **Step 4: Corra la puerta completa de Python** (Global Constraints) y `uv run python infra/smoke_test.py`.
  Expected: todo en verde.
- [ ] **Step 5: Commit** — `docs: adjudicación en la arquitectura, el README y la prueba de humo`
