# Sub-proyecto 1 — Experiencia + Inteligencia: especificación de diseño

| Campo | Valor |
|---|---|
| PRD padre | `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md` |
| Fecha | 2026-10-01 |
| Estado | Pendiente de revisión del residente |
| Base de código | Incremento 1 (rama `worktree-feat+incremento-1`, commit `a44ee57`) |

---

## 0. Contexto y decisiones

Tras ver el Incremento 1 funcionando, el residente indicó que la plataforma **no se siente completa**, que **la interfaz no es buena** y que **no le encuentra utilidad**. Causa real: el Incremento 1 solo construyó los cimientos (proveedores, importación, login). Lo que hace útil la plataforma está en los incrementos 2–4 del PRD y no existía todavía.

| # | Decisión |
|---|---|
| D1 | Se quiere el producto completo: negociación con agente IA, tablero y alertas, precio justo y ranking, simulación y adjudicación. |
| D2 | Se divide en **4 sub-proyectos**, cada uno con spec → plan → implementación → revisión: **1. Experiencia + Inteligencia** (este documento) · 2. Negociación con agente IA · 3. Decisión (simulador, adjudicación, aprobaciones) · 4. Endurecimiento y cierre. |
| D3 | Dirección visual **A — Corporativa clara** (generada con *ui-ux-pro-max*), con **tema oscuro que el usuario puede elegir** (claro / oscuro / sistema). |
| D4 | La inteligencia vive en un **nuevo microservicio `inteligencia`** que consume eventos, como manda el PRD (sección 2). |

---

## 1. Objetivo y criterios de éxito

**Objetivo:** al iniciar sesión, cada persona ve de inmediato en qué gastamos, qué vence pronto, qué estamos pagando de más y qué proveedores rinden mejor, en una interfaz profesional y consistente en tema claro y oscuro.

| Criterio | Meta |
|---|---|
| Consistencia visual | Toda pantalla usa los tokens del sistema de diseño; ningún color literal en componentes (verificado por lint) |
| Accesibilidad | 0 violaciones de axe en cada página, en ambos temas; contraste ≥ 4.5:1 en todos los pares texto/fondo de los tokens (prueba automática) |
| Responsivo | Usable a 375, 768, 1024 y 1440 px; sin scroll horizontal de página (las tablas desplazan dentro de su contenedor) |
| Tablero | Respuesta del endpoint ≤ 300 ms p95 con el dataset por defecto (60 proveedores, ~1,600 contratos) |
| Benchmark de precios | MAPE del P50 ≤ 15 % en validación temporal; cobertura del intervalo [P25, P75] de 50 % ± 10 (PRD 1.6 y 4.3) |
| Puntuación | Spearman ≥ 0.8 contra la calidad oculta del generador (PRD 4.4) |
| Eventos | 0 eventos perdidos: todo evento publicado llega a su cola o queda pendiente en el outbox |

---

## 2. Alcance

**Incluye**
- Sistema de diseño (tokens claro/oscuro, tipografía, componentes) y selector de tema.
- Nuevo armazón de la aplicación: menú lateral por rol, barra superior con alertas, tema y usuario.
- Tema de inicio de sesión de Keycloak con la misma identidad visual.
- Rediseño de las páginas existentes: Proveedores (lista y detalle) e Importación.
- Páginas nuevas: **Tablero**, **Precios** (inteligencia de precios por servicio), **Ranking** de proveedores, **Alertas**, **Configuración** de la puntuación (solo admin).
- Servicio `inteligencia`: modelos de lectura, benchmark (línea base + ML), puntuación, alertas, KPIs, registro de modelos.
- Cierre de las obligaciones R12 y R27 del Incremento 1: colas declaradas antes de publicar, reproceso del outbox, eventos de catálogo y tipo de cambio.

**No incluye** (sub-proyectos posteriores): eventos de negociación y agente IA, simulador, adjudicación y aprobaciones, notificaciones por correo, Power BI, OTP por rol (sub-proyecto 4).

---

## 3. Experiencia de usuario

### 3.1 Sistema de diseño

**Paleta (tokens semánticos; los componentes solo usan los tokens)**

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `background` | `#F8FAFC` | `#0B1220` | Fondo de página |
| `card` | `#FFFFFF` | `#111A2E` | Tarjetas, tablas, paneles |
| `foreground` | `#020617` | `#E2E8F0` | Texto principal |
| `muted` | `#E8ECF1` | `#1A2438` | Fondos secundarios, filas alternas |
| `muted-foreground` | `#475569` | `#94A3B8` | Texto secundario |
| `border` | `#E2E8F0` | `#24324A` | Bordes de 1 px |
| `primary` | `#0F172A` | `#E2E8F0` | Botón principal, barra lateral (claro) |
| `accent` | `#0369A1` | `#38BDF8` | Enlaces, foco, selección, serie principal |
| `success` | `#15803D` | `#4ADE80` | Precio justo, mejora |
| `warning` | `#B45309` | `#FBBF24` | Por vencer, baja confianza |
| `destructive` | `#DC2626` | `#F87171` | Sobreprecio, riesgo, errores |
| `sidebar` | `#0F172A` | `#0B1220` | Menú lateral (marino en ambos temas) |
| `chart-1..5` | `#0369A1 #0F766E #B45309 #64748B #6D28D9` | `#38BDF8 #2DD4BF #FBBF24 #94A3B8 #A78BFA` | Series de gráficas |

Reglas:
- El color **nunca es la única señal**. Los estados llevan icono y texto ("Sobreprecio", "Justo"), y las series de gráficas llevan etiqueta directa o leyenda.
- Una prueba automática calcula el contraste WCAG de cada par texto/fondo de la tabla en ambos temas y falla si alguno es menor a 4.5:1 (3:1 para elementos gráficos).

**Tipografía:** Fira Sans (texto y títulos) y Fira Code (identificadores como RFC, folios y códigos), **auto-hospedadas** con `@fontsource`. La CSP del gateway solo permite fuentes de `'self'`; se elimina Geist.
- Todas las cifras usan `font-variant-numeric: tabular-nums`, para que los montos se alineen en columnas.
- Escala de tamaños: 12 / 14 / 16 (base) / 18 / 20 / 24 / 30 px, con interlineado de 1.5.

**Espaciado y forma:**
- Escala densa de tablero: 4 / 8 / 12 / 16 / 24 / 32 px.
- Radio de 8 px en controles y 12 px en tarjetas.
- Sombra solo en elementos flotantes (menús, diálogos).

**Iconos:** lucide-react, siempre con texto o `aria-label`. Nunca emojis.

**Movimiento:**
- Transiciones de 150–200 ms en hover, foco y apertura de paneles.
- Se respeta `prefers-reduced-motion`.
- Sin animaciones de entrada decorativas (no se agrega GSAP).

**Tema:**
- `ThemeProvider` propio, siguiendo el patrón de shadcn para Vite: valores `claro | oscuro | sistema`, guardado en `localStorage` y aplicado con la clase `.dark` en `<html>`.
- Un script mínimo en `index.html` aplica el tema guardado antes del primer render, para evitar el destello de tema incorrecto.

**Componentes shadcn que se agregan:** `sidebar`, `chart` (Recharts 3), `dropdown-menu`, `tabs`, `select`, `skeleton`, `tooltip`, `sheet`, `progress`, `separator`, `breadcrumb`, `sonner` (avisos). Los existentes se re-tematizan con los tokens.

### 3.2 Armazón de la aplicación

```
┌───────────┬───────────────────────────────────────────────────────────┐
│ ▣ PluriOne│  Tablero › Resumen                 🔔 7   ◐ tema   Carlos ▾│
│           ├───────────────────────────────────────────────────────────┤
│ RESUMEN   │                                                           │
│  Tablero  │                  (contenido de la página)                 │
│ PROVEEDOR │                                                           │
│  Lista    │                                                           │
│  Ranking  │                                                           │
│ INTELIGEN │                                                           │
│  Precios  │                                                           │
│  Alertas 7│                                                           │
│ DATOS     │                                                           │
│  Importar*│                                                           │
│  Config.* │                                                           │
└───────────┴───────────────────────────────────────────────────────────┘
 * solo admin
```

- **Menú lateral** (`Sidebar` de shadcn, `collapsible="icon"`): agrupado por secciones. Se colapsa a iconos en escritorio y se convierte en panel deslizable (`Sheet`) en móvil. La opción activa se resalta con el token `accent`.
- **Barra superior:**
  - Migas de pan.
  - Campana de alertas con el conteo de alertas activas; abre un menú con las 5 más severas y un enlace a "Alertas".
  - Selector de tema.
  - Menú de usuario con nombre, rol y "Cerrar sesión".
- **Estados estándar:**
  - Esqueletos (`Skeleton`) mientras carga.
  - Estado vacío con título, una línea de explicación y una acción.
  - Error en `Alert` con el mensaje en español y un botón "Reintentar".

### 3.3 Páginas

**Tablero** (página de inicio, todos los roles)

```
[ Gasto anual contratado ] [ Por vencer (90 d) ] [ Proveedores en riesgo ] [ Ahorro potencial ]
   $48.2 M MXN  ▲3.1 %        12 contratos           4 de 60                  $1.9 M MXN
[ Gasto por categoría (barras horizontales) ] [ Gasto comprometido por mes, 24 meses (línea) ]
[ Próximos vencimientos (lista: proveedor, servicio, fecha, días, monto) ] [ Alertas principales ]
[ Mejores 5 y peores 5 proveedores por puntuación ]
```

- Cada tarjeta de KPI muestra la cifra y un enlace a su detalle. Por ejemplo, "Por vencer" lleva a Alertas filtradas.
- Solo "Gasto anual contratado" muestra variación: contra el mismo cálculo hecho con los contratos vigentes hace 12 meses.
- El administrador ve además una tarjeta **Estado de los datos**: fecha de la última importación, número de registros por entidad, versión del modelo de precios activo y su MAPE.

**Proveedores — lista**
- Tabla con columnas:
  - Nombre y RFC.
  - Categorías (chips).
  - **Puntuación** (0–100), con barra y color por rango, más un indicador de baja confianza.
  - Gasto anual (MXN).
  - Contratos vigentes.
  - Indicador de alertas.
- Búsqueda, filtros como chips (categoría, estado, en riesgo), orden por columna y paginación.

**Proveedores — detalle**
- **Encabezado:** nombre, RFC, tamaño, contacto, puntuación grande con tendencia (mini-gráfica de 12 meses) y alertas activas.
- **Pestaña Resumen:** barras de cada KPI de desempeño contra la mediana de su categoría (gráfica *bullet*), gasto por servicio y contratos vigentes.
- **Pestaña Contratos:** tabla con un indicador **precio vs. mercado** por línea:
  - "Por debajo de P25", "Justo" o "Sobre P75", con icono y texto.
  - Tooltip con P25, P50 y P75 y el ahorro potencial.
- **Pestaña Desempeño:** línea de 24 meses por KPI con selector de KPI, más la tabla de datos (alternativa accesible a la gráfica).

**Precios** (inteligencia de precios)
- Se elige un servicio del catálogo, con buscador por nombre o código.
- **Panel de referencia:** P25, P50 y P75 para una cantidad y plazo ajustables, el método usado ("modelo v3" o "línea base"), la confianza y el número de observaciones.
- **Gráfica histórica:** precios de contratos en el tiempo (puntos) sobre la banda P25–P75 (área), con la línea P50.
- **Tabla de sobreprecios:** contratos vigentes de ese servicio por encima de P75, con el ahorro potencial anual.
- **Vista "Todos los sobreprecios":** lista global ordenada por ahorro potencial.

**Ranking**
- Tabla por categoría con:
  - Posición.
  - Proveedor.
  - Puntuación ajustada.
  - Componentes: SLA, resolución, incidentes, entregas a tiempo y satisfacción.
  - Meses de historial.
  - Tendencia (▲ ▼ ●).
- Etiqueta "Historial corto" para proveedores con menos de 6 meses; su puntuación se acerca a la media por la contracción bayesiana.

**Alertas**
- Lista filtrable por tipo y severidad. Cada alerta muestra icono, título, explicación de una línea, entidad enlazada y fecha.
- Tipos:
  - Contrato por vencer en 90, 60 o 30 días (severidad informativa, media o alta).
  - Sobreprecio sobre P75.
  - Puntuación baja (menor a 40) o en caída (más de 10 puntos en 3 meses).

**Importación** (admin)
- Flujo de 3 pasos:
  1. Tipo de archivo, con el orden recomendado.
  2. Arrastrar y soltar el CSV, o elegirlo.
  3. Resultado: resumen o tabla de errores por fila.
- Se mantiene la lógica actual; solo cambia la experiencia.

**Configuración** (admin)
- Pesos de la puntuación (deben sumar 100), umbral de "en riesgo" y tasa de inflación anual para la línea base.
- Botón "Reentrenar modelo de precios", que muestra el resultado (nueva versión, MAPE y si se promovió).

**Inicio de sesión (Keycloak)**
- Tema `plataforma` que extiende el tema de login de Keycloak 26, **solo con CSS**: colores, tipografía, nombre del producto y foco visible.
- Se monta en `infra/keycloak/themes/` y se asigna con `loginTheme` en el realm.
- Para el realm de desarrollo ya importado, un comando `kcadm.sh` documentado aplica el tema sin borrar datos.

---

## 4. Inteligencia (servicio nuevo)

### 4.1 Responsabilidad y estructura

`services/inteligencia` (FastAPI + FastStream + scikit-learn), con base de datos `inteligencia_db` y usuario propio (`REVOKE CONNECT … FROM PUBLIC`). Sigue la plantilla de `proveedores`:
- `dominio/`: cálculos puros, sin I/O.
- `datos/`: modelos y repositorio.
- `eventos/`: consumidores.
- `api/`: rutas.

### 4.2 Consumo de eventos

| Evento | Productor | Efecto en `inteligencia` |
|---|---|---|
| `proveedor.actualizado` | proveedores | Inserta o actualiza la copia de proveedor |
| `servicio.actualizado` (**nuevo**) | proveedores | Inserta o actualiza la copia de servicio |
| `tipo_cambio.registrado` (**nuevo**) | proveedores | Inserta o actualiza el tipo de cambio mensual |
| `contrato.registrado` | proveedores | Inserta contrato y líneas; cuenta registros nuevos de precio |
| `desempeno.registrado` | proveedores | Inserta o actualiza el registro mensual |

- **Cola durable** `inteligencia.eventos` de tipo *quorum*, con `x-delivery-limit = 5` y dead-letter hacia `eventos.dlx`, que la reenvía a `inteligencia.eventos.dlq`.
- Bindings: `proveedor.*`, `servicio.*`, `tipo_cambio.*`, `contrato.*` y `desempeno.*`.
- **Idempotencia:** cada evento se procesa en una transacción que inserta su `event_id` en `evento_procesado` (clave primaria) junto con el cambio del modelo de lectura. Un evento repetido choca con esa clave y se confirma sin efecto.
- **Topología declarada antes de publicar** (cierra R12): `infra/rabbitmq/definitions.json` declara exchanges, colas y bindings, y RabbitMQ lo carga al arrancar. Así ninguna publicación ocurre sin colas enlazadas.
- Con la topología garantizada, el relay del outbox pasa a `mandatory=True` con devolución como error. Un evento sin ruta queda pendiente y se registra en el log, en vez de perderse.
- Una prueba verifica que todo tipo de evento que publica el código tiene al menos un binding en `definitions.json`.

### 4.3 Reproceso y carga inicial (cierra R12 y R27)

CLI `python -m proveedores.reproceso`:
- `--todo` marca como no publicados todos los eventos del outbox; el relay los vuelve a publicar.
- `--instantanea` emite eventos de estado actual (`servicio.actualizado` y `tipo_cambio.registrado`) para los datos que existían antes de crear esos eventos.

Los consumidores son idempotentes, así que repetirlo es seguro.

### 4.4 Cálculos de dominio

**Normalización de precios**
- El precio unitario se lleva a la moneda del servicio.
- Para comparar en MXN se usa el tipo de cambio del mes del contrato.
- Para la línea base se ajusta por inflación con la tasa configurable (por defecto 4.5 % anual).

**Línea base del benchmark**
- Percentiles P25, P50 y P75 por servicio y por tercil de cantidad, con los contratos de los últimos 24 meses.
- Con menos de 8 observaciones se usa la línea base de la categoría y se marca **baja confianza**.

**Modelo ML**
- Tres `HistGradientBoostingRegressor(loss="quantile")` (0.25 / 0.5 / 0.75) sobre log(precio).
- Variables: servicio, categoría, log(cantidad), plazo, meses transcurridos, moneda, tamaño del proveedor y tipo (nuevo o renovación).
- Las predicciones se ordenan para garantizar P25 ≤ P50 ≤ P75.
- Validación temporal: los últimos 6 meses quedan como prueba.
- **Se promueve solo si mejora el MAPE de la línea base.**
- Registro en `modelo_benchmark`: versión, fecha, datos usados, MAPE, cobertura, pinball y si fue promovido. El artefacto se guarda con `joblib` en un volumen.
- Reentrenamiento por botón de admin y automático al acumular ≥ 50 registros nuevos de precio.

**Precio justo** para (servicio, cantidad, plazo, fecha): el modelo promovido si existe; si no, la línea base.

**Puntuación (0–100)**
1. Se toman los KPIs de 12 meses con decaimiento exponencial (vida media de 6 meses).
2. Se normalizan por percentil dentro de la categoría; tiempo de resolución e incidentes se invierten.
3. Se combinan con pesos configurables: SLA 30, resolución 20, incidentes 20, entregas 15, satisfacción 15.
4. Se aplica contracción bayesiana: `ajustada = (n·score + k·media_categoría) / (n + k)`, con k = 6 meses.
5. La tendencia es la diferencia contra la puntuación de hace 3 meses.

**Alertas** (se calculan al consultar; no tienen estado "atendida" en este sub-proyecto)
- Vencimiento: 90 / 60 / 30 días.
- Sobreprecio: precio vigente mayor que P75. Ahorro potencial = (precio − P50) × cantidad × meses restantes.
- Riesgo: puntuación menor que el umbral (por defecto 40) o caída mayor a 10 puntos en 3 meses.

**KPIs del tablero**
- Gasto anual contratado: suma del valor mensual de los contratos vigentes × 12, en MXN al último tipo de cambio.
- Contratos por vencer, proveedores en riesgo y ahorro potencial total.
- Gasto por categoría, gasto comprometido por mes (24 meses), distribución de puntuaciones, y mejores y peores 5 proveedores.

### 4.5 API (bajo el gateway en `/api/inteligencia/`)

| Método y ruta | Rol | Respuesta |
|---|---|---|
| `GET /tablero` | interno | KPIs, series y listas del tablero |
| `GET /alertas?tipo=&severidad=` | interno | Alertas activas |
| `GET /precios/servicios/{codigo}/referencia?cantidad=&plazo=` | interno | P25, P50 y P75, método, confianza y n |
| `GET /precios/servicios/{codigo}/historial` | interno | Puntos de precio y bandas por mes |
| `GET /precios/sobreprecios?codigo=` | interno | Contratos sobre P75 con ahorro potencial |
| `GET /proveedores/{id}/puntuacion` | interno | Puntuación, componentes e historial de 12 meses |
| `GET /ranking?categoria=` | interno | Ranking ajustado |
| `GET /modelos` · `POST /modelos/entrenar` | interno · admin | Registro de modelos · entrenamiento |
| `GET /configuracion` · `PUT /configuracion` | interno · admin | Pesos, umbral e inflación (validados: pesos ≥ 0 y suma de 100) |

Todas las respuestas cumplen lo mismo que `proveedores`: Problem Details en español, montos como texto decimal, `correlation_id` y logs JSON.

---

## 5. Cambios en `proveedores`

- Emite `servicio.actualizado` al importar servicios y `tipo_cambio.registrado` al importar tipo de cambio.
- Relay con `mandatory=True` (sección 4.2).
- CLI de reproceso (sección 4.3).
- La lista de proveedores no cambia su contrato. La interfaz combina la lista con `GET /ranking` para mostrar la puntuación.

## 6. Infraestructura

- **RabbitMQ:** `definitions.json` montado y cargado al arrancar (exchanges `eventos` y `eventos.dlx`, cola quorum, DLQ y bindings).
- **PostgreSQL:** `inteligencia_db` con usuario propio.
  - Volumen nuevo: lo crea el script de inicio.
  - Volumen existente: un comando documentado de una sola vez.
- **Compose:**
  - Servicio `inteligencia` con healthcheck.
  - Volumen para artefactos de modelos.
  - Ruta `/api/inteligencia/` en el gateway, con el mismo límite de tasa y cabeceras que `/api/proveedores/`.
- **Keycloak:** montaje del tema `plataforma` y `loginTheme` en el realm.
- **CI:** los trabajos de Python y del stack incluyen el nuevo servicio; la prueba de humo verifica `GET /api/inteligencia/tablero`.

## 7. Calidad y validación

- **Dominio con TDD**, incluidas pruebas de propiedades con Hypothesis:
  - P25 ≤ P50 ≤ P75 siempre.
  - La puntuación está siempre en [0, 100].
  - La contracción acerca a la media y nunca la cruza.
  - El ahorro potencial nunca es negativo.
  - Los pesos inválidos se rechazan.
- **Integración con Testcontainers** (PostgreSQL y RabbitMQ reales):
  - Un evento repetido no duplica nada.
  - Un mensaje que falla 5 veces termina en la DLQ.
  - El reproceso de punta a punta reconstruye el modelo de lectura.
  - Ningún tipo de evento queda sin binding.
- **Validación contra la verdad oculta:** `python -m inteligencia.validacion --verdad datos/verdad_oculta.json` calcula MAPE, cobertura y Spearman, y escribe `docs/qa/validacion-inteligencia.md` con las metas de la sección 1.
- **Frontend:**
  - Pruebas de Vitest + Testing Library por página: carga, vacío, error y datos.
  - Revisión automática de accesibilidad con axe por página, en ambos temas.
  - Prueba de contraste de los tokens.
  - Prueba del selector de tema: persiste y respeta "sistema".
- **Lint** que prohíbe colores literales (`#hex`, `rgb(`) en `web/src/paginas` y `web/src/componentes`.
- **Rendimiento:** prueba de integración que mide `GET /tablero` con el dataset por defecto (≤ 300 ms p95 en el entorno de prueba).

## 8. Entrega

El sub-proyecto se ejecuta con **dos planes de implementación**, en este orden, cada uno con sus propias revisiones:

1. **Plan A — Sistema de diseño y experiencia** (solo frontend y Keycloak): tokens, tema, armazón, rediseño de Proveedores e Importación, y la estructura de las páginas nuevas con sus estados vacíos.
2. **Plan B — Servicio de inteligencia**: topología de RabbitMQ, eventos nuevos, reproceso, servicio `inteligencia` con dominio, API y validación. Al final se conectan con datos reales las páginas Tablero, Precios, Ranking, Alertas y Configuración.

Al terminar el Plan A la plataforma ya se ve y navega como el producto final. Al terminar el Plan B muestra datos reales en todas las páginas nuevas.
