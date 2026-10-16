# Plataforma de Negociación Automática con Proveedores

Proyecto 064 de residencias profesionales (ITH) para PluriOne. Plataforma de apoyo a compras
de servicios de TI: inteligencia de precios, desempeño de proveedores, negociación asistida por
IA con límites fijados por el comprador y adjudicación con aprobación humana.

- Requerimientos y diseño: [`docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md`](docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md)
- Planes de implementación: [`docs/superpowers/plans/`](docs/superpowers/plans/)

## Qué está hecho y qué falta

Estado al 15/10/2026 frente a las 10 capacidades del MVP del PRD (§1.3). La negociación
determinista ya funciona de punta a punta; lo siguiente es la adjudicación con aprobación.

| # | Capacidad del PRD | Estado | Dónde | Qué falta |
|---|---|---|---|---|
| 1 | Proveedores, contratos e historial | Hecho | `services/proveedores`: importación por CSV (CLI y `POST /importaciones/{entidad}`); pantallas Proveedores e Importación | — |
| 2 | Inteligencia de precios | Hecho | `services/inteligencia`: precio justo P25 · P50 · P75 (línea base y modelo), sobreprecios y vencimientos; pantallas Precios y Alertas | — |
| 3 | Desempeño del proveedor | Hecho | Puntuación de 0 a 100 con pesos configurables; Ranking y ficha del proveedor | — |
| 4 | Eventos de negociación | Hecho | `services/negociacion`: compra o renovación, líneas, invitados, ideal y límite por término, palancas con peso y fecha límite; pantalla Negociaciones | — |
| 5 | Negociación con agente en el portal | Parcial | Motor de concesiones determinista, portal del proveedor, escalamiento a una persona y control manual | Los mensajes del agente son plantillas y la nota del proveedor no se interpreta (el LLM llega con N2). Los acuerdos quedan tentativos hasta que exista la aprobación (9) |
| 6 | Propuestas de negociación | Falta | — | Documento de estrategia y argumentos para negociar a mano |
| 7 | Recomendación de adjudicación | Falta | — | Siguiente incremento |
| 8 | Simulador de escenarios | Falta | — | Después de la adjudicación, si hay tiempo |
| 9 | Aprobaciones y bitácora | Parcial | Bitácora inmutable en `administracion` (pantalla Actividad) y en `negociacion` | La aprobación de la adjudicación (siguiente incremento) |
| 10 | Tablero | Parcial | Gasto, contratos por vencer, proveedores en riesgo y ahorro potencial | Estado de las negociaciones y ahorro logrado |

**Métricas medidas** (PRD §1.6):

- Precio justo: MAPE del P50 de 8.3 % (meta ≤ 15 %). Puntuación: correlación de Spearman de
  0.923 con la calidad oculta de los proveedores (meta ≥ 0.8). Ambas en
  [`docs/qa/validacion-inteligencia.md`](docs/qa/validacion-inteligencia.md).
- Negociación contra los bots, 74 sesiones: 81.1 % de acuerdos (meta ≥ 70 %), 16.5 % de ahorro
  frente a la primera oferta (meta ≥ 8 %) y 0 acuerdos fuera de los límites del comprador
  (meta 0), en [`docs/qa/simulacion-negociacion.md`](docs/qa/simulacion-negociacion.md).
- Faltan el acierto de la adjudicación (meta ≥ 85 %) y las métricas del LLM (interpretación,
  filtraciones y latencia), que dependen de N2.

**Entregables del cronograma** (PRD §6.5):

| # | Entregable | Estado |
|---|---|---|
| 1 | Documento de requerimientos | Hecho: el PRD |
| 2 | Propuesta técnica | Falta (`docs/propuesta-tecnica.md`) |
| 3 | Documento de arquitectura | Falta (`docs/arquitectura/`: C4 y ADRs) |
| 4 | Plan del proyecto | Parcial: planes por incremento y plan del PRD (§6.6) |
| 5 | Sistema funcional | En curso: este repositorio; falta publicar las imágenes en GHCR |
| 6 | Reporte QA | Parcial: validaciones y revisiones en `docs/qa/` |
| 7–10 | Manuales, plan de mantenimiento, acta de capacitación e informe final | Falta; programados del 12/11 al 07/12 |

**Lo siguiente** (replanificación del 15/10/2026, PRD §6.6.1): adjudicación y aprobación
(capacidades 7 y 9) del 21/10 al 11/11. Después, solo si hay tiempo: el LLM (N2), las propuestas
(6) y el simulador de escenarios (8).

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
5. corre la prueba de humo (`infra/smoke_test.py`).

Abrir <http://localhost:8080>. Los usuarios de desarrollo (`admin1`, `comprador1`,
`aprobador1`) y sus contraseñas están en `infra/keycloak/realm-plataforma.json`; todos entran
con usuario y contraseña. La prueba de humo deja un usuario `humo.prueba` desactivado, que
reutiliza en cada corrida, y un servicio `HUMO-SERV` en el catálogo, que reactiva en cada corrida.

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
| Validación de la inteligencia contra la verdad oculta (escribe `docs/qa/validacion-inteligencia.md`) | `uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json` |
| Simulación con bots (escribe `docs/qa/simulacion-negociacion.md`) | `SIMULACION_REPORTE=docs/qa/simulacion-negociacion.md uv run pytest services/negociacion/tests/test_simulacion.py` |
| Mailpit, buzón de desarrollo de los correos de Keycloak y de las invitaciones a negociar (solo en este equipo) | <http://localhost:8025> |
| Versión que muestra el Estado del sistema | variable `VERSION_APP` de `infra/.env` (por defecto `desarrollo`) |

## Interfaz

- Sistema de diseño: tokens claro/oscuro en `web/src/index.css` (los componentes solo usan tokens;
  `npm run lint` rechaza colores literales y `src/tokens.node.test.ts` verifica el contraste WCAG).
- Tema claro, oscuro o del sistema desde la barra superior; la preferencia se guarda en el navegador.
- Fuentes Fira Sans y Fira Code servidas por la propia aplicación (sin CDN).
- Revisión de accesibilidad y diseño adaptable: `docs/qa/revision-visual-plan-a.md` (Plan A), `docs/qa/revision-inteligencia-interfaz.md` (inteligencia en la interfaz) y `docs/qa/revision-negociacion.md` (negociación y portal del proveedor).
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
- **Portal del proveedor** (`/portal`): el proveedor entra con el enlace de su invitación, sin cuenta. Ve qué se negocia, la conversación y la última propuesta del agente, y puede enviar ofertas o pedir hablar con una persona.

## Estructura

| Carpeta | Contenido |
|---|---|
| `libs/comun` | Infraestructura compartida: logs, errores RFC 9457, JWT, salud, outbox, topología de RabbitMQ y consumidor de eventos |
| `services/proveedores` | Microservicio de proveedores, contratos, precios y desempeño |
| `services/administracion` | Microservicio de administración: usuarios, bitácora, correos, estado del sistema y panel (`/api/administracion/`) |
| `services/inteligencia` | Microservicio de inteligencia: precio justo, puntuación de proveedores, alertas y Tablero (`/api/inteligencia/`) |
| `services/negociacion` | Microservicio de negociación: eventos, sesiones, motor de concesiones, portal del proveedor y bitácora (`/api/negociacion/`) |
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
