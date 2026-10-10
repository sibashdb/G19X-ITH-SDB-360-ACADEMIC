# Plan B — Servicio de inteligencia: especificación de diseño

| Campo | Valor |
|---|---|
| PRD padre | `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md` |
| Especificación de origen | `docs/superpowers/specs/2026-10-01-experiencia-e-inteligencia-design.md` (§4–§8; este documento las reemplaza) |
| Fecha | 2026-10-10 |
| Estado | Pendiente de revisión del residente |
| Base de código | `main` en `42d7103` (administración, planes 1 y 2, ya integrada) |

---

## 0. Contexto y decisiones

La especificación de origen se aprobó para el sub-proyecto 1 y su Plan A (sistema de diseño y experiencia) ya está en
`main`. Desde entonces se construyó la gestión de administración, que agregó eventos, una cola y pantallas que se
traslapan con el Plan B. Este documento reconcilia el Plan B con el estado actual.

| # | Decisión |
|---|---|
| D1 | El Plan B se divide en **dos planes**: **B1 "Servicio de inteligencia"** (topología, eventos, reproceso, servicio `inteligencia` con dominio, API y validación) y **B2 "Inteligencia en la interfaz"** (conectar las páginas y cerrar los pendientes de interfaz). |
| D2 | La tarjeta "Estado de los datos" no va en el Tablero: va al **Panel de administración** como "Datos y modelo". El Tablero es la vista del negocio, igual para todos los roles. `inteligencia` es el sexto servicio del **Estado del sistema**. |
| D3 | Los cambios de **configuración** y los **entrenamientos del modelo** quedan en la **Actividad**, con quién los hizo. |
| D4 | La **unidad** de un servicio con contratos se bloquea igual que la categoría y la moneda, porque el benchmark compara precios unitarios. El bloqueo también aplica a la **importación por CSV** del catálogo (hoy la importación lo salta). |
| D5 | El consumidor de eventos de `administracion` se mueve a `libs/comun` y lo usan los dos servicios. **No se agrega FastStream.** |
| D6 | La topología de RabbitMQ vive en `infra/rabbitmq/definitions.json`, pero **no se importa al arrancar** el nodo: un volumen nuevo que importa definiciones al arrancar no crea el usuario por defecto, y meterlo en el archivo pondría una contraseña en el repositorio. Un contenedor de inicio la aplica con la API de administración, que fusiona sin borrar lo existente. |
| D7 | La **lista de proveedores** se lee de `inteligencia`, que ya tiene la copia de los proveedores: así se puede ordenar por puntuación y filtrar "en riesgo" en todas las páginas. El detalle sigue viniendo de `proveedores`. |

---

## 1. Objetivo y criterios de éxito

**Objetivo:** al iniciar sesión, cada persona ve en qué se gasta, qué vence pronto, qué se paga de más y qué proveedores
rinden mejor, con datos reales.

| Criterio | Meta |
|---|---|
| Benchmark de precios | MAPE del P50 ≤ 15 % en validación temporal; cobertura del intervalo [P25, P75] de 50 % ± 10 |
| Puntuación | Spearman ≥ 0.8 contra la calidad oculta del generador |
| Tablero | `GET /tablero` ≤ 300 ms p95 con el dataset por defecto (60 proveedores, ~1,600 contratos) |
| Eventos | 0 eventos perdidos: todo evento llega a una cola o queda pendiente en el outbox; un mensaje que falla 5 veces queda en su DLQ |
| Accesibilidad | 0 violaciones de axe (con contraste) en cada página, a 375, 768, 1024 y 1440 px, en claro y oscuro |

---

## 2. Alcance

**B1 — Servicio de inteligencia**
- Topología de RabbitMQ, contenedor de inicio y relay con `mandatory=True`.
- Eventos nuevos en `proveedores` (copia del catálogo al importar, tipo de cambio), CLI de reproceso, bloqueo de la
  unidad (API e importación).
- Consumidor común en `libs/comun`; `administracion` lo usa y traduce los eventos nuevos de `inteligencia`.
- Servicio `inteligencia`: copia local, dominio (precio justo, puntuación, alertas, KPIs), registro de modelos,
  configuración, outbox, API y validación contra la verdad oculta.
- Infraestructura (base, compose, gateway, CI, Dependabot) y prueba de humo.

**B2 — Inteligencia en la interfaz**
- Tablero, Proveedores (lista y detalle), Precios, Ranking, Alertas (con la campana), Configuración, tarjeta "Datos y
  modelo" del Panel y artículos del Centro de ayuda.
- Pendientes de interfaz del Plan A y del plan 2 que tocan esas mismas pantallas (§7.2).
- Revisión en navegador y documento de QA.

**No incluye:** negociación con agente IA, simulador, adjudicación y aprobaciones, notificaciones por correo, Power BI,
estado "atendida" de las alertas.

---

## 3. Topología y eventos (B1)

### 3.1 Rutas

Exchange `eventos` (topic, ya existe). Colas *quorum* con `x-delivery-limit = 5`:

| Cola | Bindings | Consumidor |
|---|---|---|
| `inteligencia.eventos` | `proveedor.*`, `servicio.*`, `contrato.*`, `desempeno.*`, `tipo_cambio.*` | `inteligencia` |
| `administracion.actividad` (ya existe) | `importacion.*`, `servicio.*`, `configuracion.*`, `modelo.*` | `administracion` |

- `definitions.json` declara el exchange `eventos`, el exchange `eventos.dlx` (direct), las dos colas con **exactamente**
  los argumentos que usa el código, sus bindings, y una cola DLQ por servicio (`inteligencia.eventos.dlq`,
  `administracion.actividad.dlq`).
- La dead-letter se configura con **políticas** (`dead-letter-exchange: eventos.dlx` y `dead-letter-routing-key` con el
  nombre de la cola), no con argumentos: cambiar los argumentos de una cola existente falla con `PRECONDITION_FAILED`.
- Un contenedor `rabbitmq-topologia` aplica el archivo con `POST /api/definitions` (credenciales por variables de
  entorno) cuando RabbitMQ está sano, y termina. Los servicios que publican o consumen dependen de que haya terminado
  bien. Aplicarlo dos veces no cambia nada.
- El relay del outbox (`libs/comun`) pasa a `mandatory=True`: un evento devuelto por no tener ruta queda pendiente y se
  registra en el log.
- Una prueba verifica que todo tipo de evento que publica el código tiene al menos un binding en `definitions.json`, y
  que los argumentos de las colas en el archivo coinciden con los del código.

### 3.2 Eventos nuevos

| Evento | Productor | Payload | Cuándo |
|---|---|---|---|
| `servicio.actualizado` (copia) | proveedores | `{id, codigo, nombre, categoria, unidad, moneda, activo}`, **sin** `cambio`, `campos` ni `actor` | Al importar el catálogo y en el reproceso. `administracion` ignora estas copias (ya lo hace). |
| `tipo_cambio.registrado` | proveedores | `{periodo: "AAAA-MM-01", usd_mxn: "17.1234"}` | Al importar el tipo de cambio y en el reproceso |
| `configuracion.actualizada` | inteligencia | `{cambios: [{campo, anterior, nuevo}], actor}` | Al guardar la configuración |
| `modelo.entrenado` | inteligencia | `{version, mape, mape_linea_base, cobertura, promovido, origen: "manual" \| "automatico", actor}` | Al terminar cada entrenamiento |

- El `actor` sigue la forma `{id, nombre}` de los eventos actuales. En un entrenamiento automático es
  `{"id": null, "nombre": "Sistema (automático)"}`.
- `servicio.actualizado` con `cambio` (ediciones del Catálogo, plan 2) sigue igual; `inteligencia` usa ambas formas
  para actualizar su copia.

### 3.3 Reproceso y carga inicial

`python -m proveedores.reproceso`:
- `--todo`: marca todos los eventos del outbox como no publicados; el relay los vuelve a publicar.
- `--instantanea`: emite `servicio.actualizado` (copia) y `tipo_cambio.registrado` del estado actual, para los datos que
  existían antes de estos eventos.

Los consumidores son idempotentes; repetirlo es seguro. El README documenta la carga inicial de un entorno existente.

---

## 4. Servicio `inteligencia` (B1)

### 4.1 Estructura

`services/inteligencia` (FastAPI, SQLAlchemy async, Alembic, scikit-learn), base `inteligencia_db` con usuario propio
(`REVOKE CONNECT … FROM PUBLIC`), siguiendo la plantilla de `administracion`:
- `dominio/`: cálculos puros, sin E/S.
- `datos/`: modelos y consultas de la copia local (proveedor, servicio, tipo de cambio, contrato y líneas, desempeño),
  `evento_procesado`, `configuracion`, `modelo_benchmark` y su outbox.
- `eventos.py`: traducción de eventos a cambios de la copia local, con el consumidor común.
- `api/`: rutas.

**Idempotencia:** cada evento se procesa en una transacción que inserta su `event_id` en `evento_procesado` (clave
primaria) junto con el cambio de la copia local. Un evento repetido choca con la clave y se confirma sin efecto.

### 4.2 Cálculos de dominio

Se mantienen los de la especificación de origen (§4.4), con estos ajustes:

- **Normalización:** precio unitario a la moneda del servicio; a MXN con el tipo de cambio del mes del contrato; para la
  línea base, ajuste por inflación con la tasa configurable (4.5 % anual por defecto).
- **Línea base:** P25, P50 y P75 por servicio y tercil de cantidad con los contratos de los últimos 24 meses. Con menos de
  8 observaciones se usa la de la categoría y se marca **baja confianza**.
- **Modelo ML:** tres `HistGradientBoostingRegressor(loss="quantile")` (0.25 / 0.5 / 0.75) sobre log(precio), con las
  variables de la especificación de origen; predicciones ordenadas para garantizar P25 ≤ P50 ≤ P75; validación temporal
  con los últimos 6 meses; **se promueve solo si mejora el MAPE de la línea base**. Artefacto con `joblib` en un volumen.
- **Reentrenamiento:** por botón del administrador o automático al acumular ≥ 50 precios nuevos. Corre en segundo plano,
  nunca dos a la vez (un segundo pedido mientras corre responde 409 `entrenamiento_en_curso`). Publica
  `modelo.entrenado`.
- **Precio justo** para (servicio, cantidad, plazo, fecha): el modelo promovido si existe; si no, la línea base.
- **Puntuación (0–100):** KPIs de 12 meses con decaimiento exponencial (vida media 6 meses), percentiles por categoría
  (resolución e incidentes invertidos), pesos configurables (SLA 30, resolución 20, incidentes 20, entregas 15,
  satisfacción 15), contracción bayesiana con k = 6 meses y tendencia contra hace 3 meses.
- **Alertas** (se calculan al consultar): vencimiento a 90 / 60 / 30 días; sobreprecio sobre P75 con ahorro potencial =
  (precio − P50) × cantidad × meses restantes; riesgo por puntuación menor que el umbral (40) o caída mayor a 10 puntos en
  3 meses.
- **KPIs del Tablero:** gasto anual contratado (valor mensual de los contratos vigentes × 12, en MXN al último tipo de
  cambio, con variación contra hace 12 meses), contratos por vencer, proveedores en riesgo, ahorro potencial total,
  gasto por categoría, gasto comprometido por mes (24 meses), distribución de puntuaciones y mejores y peores 5.
- **Servicios inactivos:** no aparecen en el selector de Precios ni en `GET /precios/servicios`, pero sus contratos
  vigentes cuentan en los KPIs y las alertas.
- **Configuración:** pesos ≥ 0 que suman 100, umbral entre 0 y 100, inflación entre 0 % y 50 %. Un cambio publica
  `configuracion.actualizada` con cada campo modificado.

### 4.3 API (gateway: `/api/inteligencia/`)

"Interno" son los tres roles internos (comprador, aprobador, admin).

| Método y ruta | Rol | Respuesta |
|---|---|---|
| `GET /tablero` | interno | KPIs, series y listas del Tablero |
| `GET /alertas?tipo=&severidad=&limite=` | interno | Alertas activas (la campana usa `limite=5`) |
| `GET /precios/servicios` | interno | Servicios activos con su categoría y número de observaciones |
| `GET /precios/servicios/{codigo}/referencia?cantidad=&plazo=` | interno | P25, P50, P75, método, confianza y n |
| `GET /precios/servicios/{codigo}/historial` | interno | Puntos de precio y bandas por mes |
| `GET /precios/sobreprecios?codigo=` | interno | Contratos sobre P75 con ahorro potencial |
| `GET /proveedores?busqueda=&categoria=&estado=&en_riesgo=&orden=&pagina=&tamano=` | interno | Lista con puntuación, confianza, gasto anual, contratos vigentes y alertas |
| `GET /proveedores/{id}/puntuacion` | interno | Puntuación, componentes contra la mediana de la categoría, historial de 12 meses y tendencia |
| `GET /proveedores/{id}/mercado` | interno | Por línea de contrato vigente: posición ("bajo P25", "justo", "sobre P75"), P25, P50, P75 y ahorro |
| `GET /ranking?categoria=` | interno | Ranking ajustado |
| `GET /modelos` · `POST /modelos/entrenar` | interno · admin | Registro de modelos · entrenamiento (202) |
| `GET /configuracion` · `PUT /configuracion` | interno · admin | Pesos, umbral e inflación |
| `GET /datos` | admin | Registros por entidad en la copia local, último evento recibido y modelo activo con su MAPE |

Todas cumplen lo mismo que `proveedores` y `administracion`: Problem Details en español con `codigo` y errores
`{campo, mensaje}`, montos como texto decimal, `correlation_id`, logs JSON y `/salud/vivo` y `/salud/listo` (esta, solo
PostgreSQL).

---

## 5. Cambios en `proveedores` (B1)

- `PATCH /servicios/{codigo}`: `unidad` se agrega a los campos bloqueados con contratos (409 `servicio_con_contratos` con
  el error junto al campo).
- Importación del catálogo: una fila que cambia la categoría, la unidad o la moneda de un servicio con contratos es un
  error de fila ("El servicio tiene contratos: no se puede cambiar la unidad") y el archivo se rechaza completo, como
  cualquier otro error.
- Emite `servicio.actualizado` (copia) al importar el catálogo y `tipo_cambio.registrado` al importar el tipo de cambio.
- CLI de reproceso (§3.3).

## 6. Cambios en `administracion` (B1)

- Usa el consumidor común. Su cola gana los bindings `configuracion.*` y `modelo.*`.
- Textos nuevos en `textos.py` y `web/src/actividad.ts` (la prueba de paridad los cubre):
  - "Cambió la configuración de la puntuación: pesos, umbral" (los nombres legibles de los campos cambiados).
  - "Reentrenó el modelo de precios: versión 4, MAPE 11.2 %, promovido" / "…, no se promovió (no mejoró la línea base)".
- Actividad gana el filtro de tipo "Inteligencia".
- Estado del sistema: sexto servicio "Inteligencia" (`/salud/listo` de `inteligencia`) y la cola
  `inteligencia.eventos` entra en el umbral de mensajes pendientes.

---

## 7. Interfaz (B2)

### 7.1 Páginas

Lo de la especificación de origen (§3.3), con estos cambios:
- **Tablero:** datos reales; se quitan `AvisoInteligencia` y la sección "Estado de los datos".
- **Proveedores — lista:** columnas Puntuación (barra, color por rango e indicador de baja confianza), Gasto anual,
  Contratos vigentes y Alertas; filtro "en riesgo"; orden por columna. Lee `GET /inteligencia/proveedores`; si
  `inteligencia` no responde, muestra el error con "Reintentar".
- **Proveedores — detalle:** encabezado con puntuación, tendencia de 12 meses y alertas; Resumen con cada KPI contra la
  mediana de su categoría; Contratos con "precio vs. mercado" por línea (icono y texto, nunca solo color).
- **Precios, Ranking y Alertas:** como en la especificación de origen. La campana de la barra superior muestra el número
  de alertas y las 5 principales.
- **Configuración:** formulario de pesos (que sumen 100, con el total visible), umbral e inflación; botón "Reentrenar
  modelo de precios" con el resultado (versión, MAPE y si se promovió) y el registro de modelos.
- **Panel de administración:** tarjeta "Datos y modelo" con `GET /datos` y enlace a Configuración.
- **Centro de ayuda:** se actualizan "Consultar proveedores" y "Precio justo" con los datos reales, y se agrega
  "Configurar la puntuación y el modelo" (solo admin).

### 7.2 Pendientes que se cierran en B2

- Del Plan A: carga diferida de las rutas (el bundle mide ~1,000 kB); `outline-hidden` en lugar de `outline-none` en
  `button`, `input`, `select`, `tabs` y `#contenido` (foco visible en alto contraste); Precios a 375 px (llevar el foco o
  desplazar al detalle, `minmax(0,1fr)`, `break-words`); términos con `Termino` en los pasos de la guía; la guía
  recordada por usuario y no por navegador; el README usa `KC_CLI_PASSWORD` en lugar de `--password`.
- Del plan 2: `Paginacion` con `aria-disabled` en lugar de `disabled`; foco tras "Quitar filtros" en Alertas y tras
  "Ir a la primera página" en Proveedores; un solo "Limpiar filtros" en Proveedores.

---

## 8. Infraestructura (B1)

- `infra/rabbitmq/definitions.json` y el contenedor `rabbitmq-topologia` (§3.1).
- `infra/postgres/inteligencia.sh`: crea `inteligencia_db` y sus dos usuarios (migración y aplicación), idempotente;
  corre solo en volúmenes nuevos y se ejecuta a mano en uno existente, como `administracion.sh`.
- Compose: servicio `inteligencia` con healthcheck y volumen de artefactos de modelos; sus variables en
  `infra/.env.example`.
- Gateway: `/api/inteligencia/` con el mismo límite de tasa y cabeceras que las otras rutas de API.
- CI: los trabajos de Python y del stack incluyen el servicio; Dependabot incluye su directorio.
- Prueba de humo: `GET /api/inteligencia/tablero` responde con datos y un cambio del catálogo llega a la copia local.

## 9. Seguridad

- Todas las rutas exigen un rol interno; reentrenar, cambiar la configuración y `GET /datos` exigen `admin`. Una prueba
  recorre todas las rutas del servicio.
- Ningún secreto en el repositorio ni en los logs: las credenciales viajan por variables de entorno.
- La configuración y los parámetros de consulta se validan en la frontera (cantidad > 0, plazo entre 1 y 120 meses,
  códigos con el patrón del catálogo).

## 10. Calidad y validación

- **Dominio con TDD** y pruebas de propiedades con Hypothesis: P25 ≤ P50 ≤ P75; puntuación en [0, 100]; la contracción
  acerca a la media y nunca la cruza; el ahorro potencial nunca es negativo; los pesos inválidos se rechazan.
- **Integración con Testcontainers** (PostgreSQL y RabbitMQ reales): un evento repetido no duplica nada; un mensaje que
  falla 5 veces termina en la DLQ; el reproceso reconstruye la copia local; ningún tipo de evento queda sin binding;
  `GET /tablero` ≤ 300 ms p95 con el dataset por defecto.
- **Validación contra la verdad oculta:** `python -m inteligencia.validacion --verdad datos/verdad_oculta.json` calcula
  MAPE, cobertura y Spearman y escribe `docs/qa/validacion-inteligencia.md` con las metas de la §1.
- **Interfaz (B2):** Vitest y Testing Library por página (carga, vacío, error y datos), axe en cada página y en ambos
  temas, y revisión en navegador con axe con contraste a 4 anchos y 2 temas.

## 11. Entrega

1. **B1 — Servicio de inteligencia**, en la rama `feat/servicio-inteligencia`. Termina con el servicio funcionando por
   API, la validación escrita y la prueba de humo en verde. Las páginas siguen mostrando sus estados vacíos.
2. **B2 — Inteligencia en la interfaz**, en una rama nueva desde `main` después de integrar B1. Termina con datos reales
   en todas las páginas y la revisión en navegador.

Cada plan se ejecuta con subagentes, con revisión por tarea, revisión final y fusión a `main`.

## 12. Documentación a actualizar

- **PRD:** mapa y tabla de servicios (`inteligencia`), eventos y colas (§2.2), entidades por servicio (§4.1) y matriz de
  permisos (configuración y entrenamiento: admin).
- **README:** servicio y puerto, variables nuevas, topología y carga inicial (reproceso), validación.
- **Especificación de origen:** nota de que sus §4–§8 los reemplaza este documento.
- **`docs/qa/`:** `validacion-inteligencia.md` (B1) y la revisión en navegador (B2).
