# Plataforma de Negociación Automática con Proveedores

Proyecto 064 de residencias profesionales (ITH) para PluriOne. Plataforma de apoyo a compras
de servicios de TI: inteligencia de precios, desempeño de proveedores, negociación asistida por
IA con límites fijados por el comprador y adjudicación con aprobación humana.

- Para empezar: el PRD en una página, [`docs/PRD.md`](docs/PRD.md); el alcance vigente del
  MVP, [`docs/MVP.md`](docs/MVP.md), y el plan del proyecto,
  [`docs/plan-del-proyecto.md`](docs/plan-del-proyecto.md)
- Requerimientos y diseño completos: [`docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md`](docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md)
- Propuesta técnica: [`docs/propuesta-tecnica.md`](docs/propuesta-tecnica.md)
- Arquitectura (C4, modelo de datos, eventos, contratos y ADR): [`docs/arquitectura/`](docs/arquitectura/README.md)
- Planes de implementación: [`docs/superpowers/plans/`](docs/superpowers/plans/)

## Qué está hecho y qué falta

Estado al 22/10/2026 frente a las 10 capacidades del MVP del PRD (§1.3). La negociación
determinista y la adjudicación con aprobación ya funcionan de punta a punta, en los servicios y
en la interfaz, hasta el contrato registrado, y el Tablero muestra cómo van las negociaciones y
cuánto se ahorró.

| # | Capacidad del PRD | Estado | Dónde | Qué falta |
|---|---|---|---|---|
| 1 | Proveedores, contratos e historial | Hecho | `services/proveedores`: importación por CSV (CLI y `POST /importaciones/{entidad}`); pantallas Proveedores e Importación | — |
| 2 | Inteligencia de precios | Hecho | `services/inteligencia`: precio justo P25 · P50 · P75 (línea base y modelo), sobreprecios y vencimientos; pantallas Precios y Alertas | — |
| 3 | Desempeño del proveedor | Hecho | Puntuación de 0 a 100 con pesos configurables; Ranking y ficha del proveedor | — |
| 4 | Eventos de negociación | Hecho | `services/negociacion`: compra o renovación, líneas, invitados, ideal y límite por término, palancas con peso y fecha límite; pantalla Negociaciones | — |
| 5 | Negociación con agente en el portal | Parcial | Motor de concesiones determinista, portal del proveedor, escalamiento a una persona y control manual | Los mensajes del agente son plantillas y la nota del proveedor no se interpreta (el LLM llega con N2) |
| 6 | Propuestas de negociación | Falta | — | Documento de estrategia y argumentos para negociar a mano |
| 7 | Recomendación de adjudicación | Hecho | `services/inteligencia`: `POST /adjudicacion/recomendacion` ordena los acuerdos por costo total, desempeño, riesgo y SLA (pesos configurables, 40 · 30 · 15 · 15 por defecto) y explica el orden con plantillas y un análisis de sensibilidad. Acierto top-1 de 85.0 % en 200 eventos simulados (ver Métricas); `services/negociacion`: propuesta del comprador, que justifica si se aparta de la recomendación, y desierta. Pantalla: la evaluación de los acuerdos con la recomendación explicada y los pesos ajustables, la propuesta con su justificación y el resumen de la negociación adjudicada o desierta; en Configuración, la sección «Adjudicación» con los pesos y el umbral | — |
| 8 | Simulador de escenarios | Falta | — | Después de la adjudicación, si hay tiempo |
| 9 | Aprobaciones y bitácora | Hecho | Aprobación en `services/negociacion`: sobre el umbral (500,000 MXN por defecto) o fuera de límites decide un aprobador, y nunca quien propuso ([ADR-011](docs/arquitectura/adr/011-quien-aprueba-una-adjudicacion.md)); la adjudicación aprobada registra el contrato en `proveedores`. Aviso del resultado a los proveedores por correo. Bitácora inmutable en `administracion` (pantalla Actividad, con adjudicaciones y desiertas; pantalla Correos) y en `negociacion`. Pantalla: aprobar o rechazar la propuesta por una persona distinta de quien propuso, el filtro «Por aprobar» de Negociaciones, el resumen con el folio del contrato y el aviso del resultado en el portal del proveedor | — |
| 10 | Tablero | Hecho | Gasto, contratos por vencer, proveedores en riesgo y ahorro potencial, de `inteligencia`. De `negociacion` (`GET /tablero`), las negociaciones en cada estado, con acceso a la lista filtrada, y el ahorro logrado: el costo total adjudicado frente a la primera oferta de cada proveedor ganador, en MXN y en porcentaje | — |

**Métricas medidas** (PRD §1.6):

- Precio justo: MAPE del P50 de 8.3 % (meta ≤ 15 %). Puntuación: correlación de Spearman de
  0.923 con la calidad oculta de los proveedores (meta ≥ 0.8). Ambas en
  [`docs/qa/validacion-inteligencia.md`](docs/qa/validacion-inteligencia.md).
- Negociación contra los bots, 74 sesiones: 81.1 % de acuerdos (meta ≥ 70 %), 16.5 % de ahorro
  frente a la primera oferta (meta ≥ 8 %) y 0 acuerdos fuera de los límites del comprador
  (meta 0), en [`docs/qa/simulacion-negociacion.md`](docs/qa/simulacion-negociacion.md).
- Recomendación de adjudicación, 200 eventos simulados (semilla 4242): acierto top-1 de 85.0 %
  (meta ≥ 85 %), acierto top-2 de 99.5 % y margen promedio de los fallos de 7.6 puntos, en
  [`docs/qa/validacion-inteligencia.md`](docs/qa/validacion-inteligencia.md). El 85.0 % queda
  exactamente sobre la meta, sin holgura: con 200 eventos, el intervalo de 95 % va de 80.1 % a
  89.9 %, así que el resultado no demuestra por sí solo que se supere la meta.
- Aprobación: 0 adjudicaciones sin aprobación cuando superan el umbral o salen de límites y 0
  aprobaciones hechas por quien propuso (pruebas de la API de `negociacion`); cada adjudicación
  aprobada llega a un contrato registrado en `proveedores` (prueba de humo).
- Faltan las métricas del LLM (interpretación, filtraciones y latencia), que dependen de N2.

**Entregables del cronograma** (PRD §6.5):

| # | Entregable | Estado |
|---|---|---|
| 1 | Documento de requerimientos | Hecho: el PRD ([`docs/PRD.md`](docs/PRD.md)) y su alcance vigente ([`docs/MVP.md`](docs/MVP.md)) |
| 2 | Propuesta técnica | Hecho: [`docs/propuesta-tecnica.md`](docs/propuesta-tecnica.md) |
| 3 | Documento de arquitectura | Hecho: [`docs/arquitectura/`](docs/arquitectura/README.md) (C4, modelo de datos, eventos, OpenAPI, AsyncAPI y ADR) |
| 4 | Plan del proyecto | Hecho: [`docs/plan-del-proyecto.md`](docs/plan-del-proyecto.md) (incrementos hechos, calendario, backlog y riesgos) |
| 5 | Sistema funcional | En curso: este repositorio; falta publicar las imágenes en GHCR |
| 6 | Reporte QA | Parcial: validaciones y revisiones en `docs/qa/` |
| 7–10 | Manuales, plan de mantenimiento, acta de capacitación e informe final | Falta; programados del 12/11 al 07/12 |

**Lo siguiente** (decisión del 22/10/2026, PRD §6.6.2): el LLM recortado (N2), del 29/10 al
04/11, con fecha límite. Las propuestas (6) y el
simulador de escenarios (8) quedan como trabajo futuro. Calendario completo en
[`docs/MVP.md`](docs/MVP.md).

## Cómo se trabajó con IA

El proyecto se desarrolló con Claude Code (Anthropic) como asistente. Casi todos los commits se
escribieron con él y lo declaran con la línea `Co-Authored-By: Claude …`, que nombra el modelo
usado (Opus, Sonnet o Haiku). El método:

- **Primero la especificación.** Cada incremento empieza con una spec en
  [`docs/superpowers/specs/`](docs/superpowers/specs/), escrita en conversación con el residente.
  El residente aprueba el alcance y las decisiones antes de que se programe; el PRD lo aprobó
  sección por sección.
- **Después el plan.** De cada spec sale un plan en
  [`docs/superpowers/plans/`](docs/superpowers/plans/), con las tareas, las interfaces y las
  pruebas de cada una. El residente lo aprueba antes de implementar.
- **Implementación con revisión independiente.** Un agente implementa cada tarea con pruebas
  primero (TDD). Otro agente, que no comparte el contexto del primero, la revisa contra la spec.
  Al final, un revisor revisa la rama completa, y sus hallazgos se corrigen antes de integrar.
- **Verificación con evidencia.** Algo está terminado cuando lo dicen las pruebas (pytest y
  Vitest), el CI con la prueba de humo del stack completo y las revisiones en el navegador con
  axe ([`docs/qa/`](docs/qa/)), no cuando lo afirma el agente.
- **Decisiones del residente.** El residente fija el alcance y las prioridades (por ejemplo, la
  opción A del 15/10 y la decisión sobre el LLM del 22/10), entra con sus usuarios a las
  revisiones en el navegador y decide qué se integra y cuándo se publica.
- **Datos.** Los datos de la plataforma son sintéticos (generador con semilla), así que el
  asistente no trabajó con datos reales de compras.

## Requisitos

- Docker Desktop (WSL 2 en Windows)
- [uv](https://docs.astral.sh/uv/)
- Node 24, solo para desarrollar la SPA (la imagen del gateway la construye por su cuenta)

Si `uv` no encuentra su Python administrado, indíquele la versión con `export UV_PYTHON=3.13`.

## Arranque rápido

```bash
uv run python infra/arrancar.py
```

El script se puede repetir sin dañar nada:

1. copia `infra/.env` desde `infra/.env.example` si falta;
2. genera los datos sintéticos en `datos/` si faltan;
3. levanta el stack y espera a que esté sano;
4. importa los datos;
5. corre la prueba de humo (`infra/smoke_test.py`), que llega de una negociación aprobada a su
   contrato registrado en `proveedores`.

Desde un clon limpio, en el equipo de desarrollo, tarda de 3 a 8 minutos según la red
([`docs/qa/arranque-desde-cero.md`](docs/qa/arranque-desde-cero.md)). La primera vez en un
equipo nuevo, Docker además descarga las imágenes base (PostgreSQL, RabbitMQ, Keycloak, Python,
Node, Nginx, Mailpit y curl), unos 1.9 GB sin comprimir; ese tiempo depende de la conexión.

Abrir <http://localhost:8080>. Los usuarios de desarrollo (`admin1`, `comprador1`,
`aprobador1`) y sus contraseñas están en `infra/keycloak/realm-plataforma.json`; todos entran
con usuario y contraseña. La prueba de humo deja un usuario `humo.prueba` desactivado, que
reutiliza en cada corrida, y un servicio `HUMO-SERV` en el catálogo, que reactiva en cada
corrida. Cada corrida también deja una negociación cancelada y otra adjudicada, con su contrato
`C-NEG-…` en el historial de `proveedores`. Ese contrato (1,000 unidades, unos $36.9
millones de MXN al año) es real para el sistema: entra al precio de referencia del
servicio, al «gasto anual contratado» del Tablero de ese proveedor y a la concentración
de las recomendaciones que se calculen después. Solo afecta al entorno local.

Si su entorno ya existía antes de alguno de los servicios, siga
[`docs/actualizar-entorno.md`](docs/actualizar-entorno.md).

### Secretos de `infra/.env`

Los valores de `infra/.env.example` solo sirven para desarrollo. Cada servicio con base propia usa
dos contraseñas: la de la aplicación, con los permisos mínimos, y la del dueño de la base, que solo
crea y migra tablas.

| Variable | Para qué |
|---|---|
| `ADMINISTRACION_DB_PASSWORD` | El servicio `administracion` entra a su base: solo consulta e inserta en la bitácora |
| `ADMINISTRACION_DUENO_DB_PASSWORD` | Dueño de la base de la administración |
| `KEYCLOAK_ADMINISTRACION_SECRET` | Cliente de Keycloak con el que `administracion` gestiona usuarios y lee los inicios de sesión |
| `INTELIGENCIA_DB_PASSWORD` | El servicio `inteligencia` entra a su base: consulta, inserta y actualiza su copia local; nunca borra |
| `INTELIGENCIA_DUENO_DB_PASSWORD` | Dueño de la base de la inteligencia |
| `NEGOCIACION_DB_PASSWORD` | El servicio `negociacion` entra a su base: nunca cambia ni borra la bitácora, los mensajes ni las ofertas |
| `NEGOCIACION_DUENO_DB_PASSWORD` | Dueño de la base de la negociación |

### Sin el script

```bash
cp infra/.env.example infra/.env
uv sync --all-packages
uv run python -m generador --salida datos
docker compose -f infra/docker-compose.yml up -d --build --wait
docker compose -f infra/docker-compose.yml exec proveedores python -m proveedores.importacion.cli /datos
```

En Git Bash, ejecute `export MSYS_NO_PATHCONV=1` antes del último comando: Git Bash convierte
`/datos` en una ruta de Windows y la importación no encuentra la carpeta.

## Desarrollo

| Tarea | Comando |
|---|---|
| Pruebas de Python (requieren Docker) | `uv run pytest --cov` |
| Lint, formato y tipos | `uv run ruff format . && uv run ruff check . && uv run mypy` |
| Dependencias del frontend (una vez, antes de `npm run dev` o las pruebas) | `cd web && npm ci` |
| SPA con recarga en caliente | `cd web && npm run dev` → <http://localhost:5173> |
| Pruebas del frontend | `cd web && npm test -- --run` |
| Contrato OpenAPI de proveedores | <http://localhost:8080/api/proveedores/docs> |
| Consola de RabbitMQ | <http://localhost:15672> |
| Contrato OpenAPI de administración | <http://localhost:8080/api/administracion/docs> |
| Contrato OpenAPI de inteligencia | <http://localhost:8080/api/inteligencia/docs> |
| Contrato OpenAPI de negociación | <http://localhost:8080/api/negociacion/docs> |
| Exportar los contratos OpenAPI a `docs/arquitectura/openapi/` (con el stack levantado) | `uv run python infra/exportar_contratos.py` |
| Validación de la inteligencia contra la verdad oculta (escribe `docs/qa/validacion-inteligencia.md`) | `uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json` |
| Simulación con bots (escribe `docs/qa/simulacion-negociacion.md`) | `SIMULACION_REPORTE=docs/qa/simulacion-negociacion.md uv run pytest services/negociacion/tests/test_simulacion.py` |
| Mailpit, buzón de desarrollo de los correos de Keycloak y de las invitaciones a negociar (solo en este equipo) | <http://localhost:8025> |
| Versión que muestra el Estado del sistema | variable `VERSION_APP` de `infra/.env` (por defecto `desarrollo`) |

## Interfaz

- Sistema de diseño: tokens claro/oscuro en `web/src/index.css` (los componentes solo usan tokens;
  `npm run lint` rechaza colores literales y `src/tokens.node.test.ts` verifica el contraste WCAG).
- Tema claro, oscuro o del sistema desde la barra superior; la preferencia se guarda en el navegador.
- Fuentes Fira Sans y Fira Code servidas por la propia aplicación (sin CDN).
- Revisión de accesibilidad y diseño adaptable: `docs/qa/revision-visual-plan-a.md` (Plan A), `docs/qa/revision-inteligencia-interfaz.md` (inteligencia en la interfaz), `docs/qa/revision-negociacion.md` (negociación y portal del proveedor) y `docs/qa/revision-adjudicacion.md` (adjudicación y aprobación, revisadas en el navegador).
- Guía "Cómo usar PluriOne" en el Tablero; se oculta y vuelve desde el menú de usuario, y se recuerda por persona (no por navegador). El menú
  muestra icono y nombre; el propósito de cada opción aparece en la ayuda emergente del menú
  contraído y lo lee el lector de pantalla.
- Los términos técnicos (P25/P50/P75, sobreprecio, puntuación, SLA…) tienen una ayuda que se
  abre con clic, toque o teclado; las definiciones viven en `web/src/glosario.ts`.
- Área **Sistema** (solo administración): Panel, Usuarios, Actividad (con exportación a CSV), Catálogo, Estado del sistema, Correos, Importación y Configuración.
- Área **Soporte**: Centro de ayuda con guías, preguntas frecuentes y glosario (`web/src/ayuda.ts`); se abre también con el botón "?" de la barra superior.
- **Inteligencia**: el Tablero, Proveedores (lista y ficha), Precios, Ranking, Alertas, la campana de la barra superior y Configuración muestran los datos del servicio `inteligencia` (`web/src/inteligencia.ts`); el Panel resume sus datos y su modelo en "Datos y modelo".
- Cada página se descarga la primera vez que se visita (rutas diferidas en `web/src/rutas.tsx`).
- **Negociación** (`web/src/negociacion.ts`):
  - Negociaciones: lista, creación de compras y de renovaciones, y editor de límites con la referencia de precios;
  - publicación, con enlaces que se muestran una sola vez;
  - supervisión de cada sesión, que se actualiza cada 3 s, e intervención manual;
  - «Renovar» en el Tablero, en las Alertas y en la ficha del proveedor.
- **Adjudicación y aprobación** (`web/src/adjudicacion.ts`):
  - evaluación de los acuerdos con la recomendación explicada y los pesos ajustables, para adjudicar al recomendado o a otro con justificación, o declarar desierta la negociación;
  - quien aprueba entra por el filtro «Por aprobar» de Negociaciones y aprueba o rechaza la propuesta; nunca lo hace quien la propuso;
  - resumen de la negociación adjudicada, con el folio del contrato, o desierta;
  - el portal del proveedor muestra el resultado mientras su enlace siga vigente;
  - Configuración tiene la sección «Adjudicación» (pesos y umbral de aprobación) y la Actividad registra el cambio.
- **Negociaciones en el Tablero**: la fila «Negociaciones» muestra cuántas hay en cada estado, y cada número abre la lista filtrada. También muestra el ahorro logrado frente a la primera oferta; si `negociacion` no responde, solo esa fila muestra el error.
- **Portal del proveedor** (`/portal`): el proveedor entra con el enlace de su invitación, sin cuenta. Ve qué se negocia, la conversación y la última propuesta del agente, y puede enviar ofertas o pedir hablar con una persona.

## Estructura

| Carpeta | Contenido |
|---|---|
| `libs/comun` | Infraestructura compartida: logs, errores RFC 9457, JWT, salud, outbox, topología de RabbitMQ y consumidor de eventos |
| `services/proveedores` | Microservicio de proveedores, contratos, precios y desempeño |
| `services/administracion` | Microservicio de administración: usuarios, bitácora, correos, estado del sistema y panel (`/api/administracion/`) |
| `services/inteligencia` | Microservicio de inteligencia: precio justo, puntuación de proveedores, alertas y Tablero (`/api/inteligencia/`) |
| `services/negociacion` | Microservicio de negociación: eventos, sesiones, motor de concesiones, portal del proveedor, adjudicación, bitácora y los indicadores de negociaciones del Tablero (`/api/negociacion/`) |
| `tools/generador` | Datos sintéticos reproducibles del ERP simulado |
| `tools/simulador` | Bots de proveedor que negocian por el portal y miden al agente |
| `web` | SPA en React servida por el gateway |
| `infra` | Docker Compose, Nginx, Keycloak, PostgreSQL |

## Limitaciones conocidas

- **Mensajes fallidos sin pantalla propia.** Un evento que falla 5 veces queda en la cola
  `<cola>.dlq` y el Estado del sistema lo avisa, pero todavía no hay una pantalla para revisarlo
  o reintentarlo: se hace desde la consola de RabbitMQ.
- **Realm solo para desarrollo.** El realm incluido (`infra/keycloak/realm-plataforma.json`)
  trae credenciales de prueba y el cliente `pruebas-humo` con *password grant*; no debe usarse
  fuera de un entorno local.
- **Agente sin LLM.** Los mensajes del agente son plantillas y la nota del proveedor no se
  interpreta; la IA llega con N2.
- **Portal solo con HTTPS o localhost.** El portal del proveedor genera claves de idempotencia
  con `crypto.randomUUID`, que el navegador solo ofrece en un contexto seguro; publicado por HTTP
  en otro host, enviar una oferta falla.

## Convenciones

- *Trunk-based*: ramas cortas `feat/…` o `fix/…` y PR hacia `main`.
- Mensajes con [Conventional Commits](https://www.conventionalcommits.org/es/).
- Toda regla de negocio nueva se desarrolla con TDD.
