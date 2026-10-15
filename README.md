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
`aprobador1`) y sus contraseñas están en `infra/keycloak/realm-plataforma.json`; todos entran
con usuario y contraseña. Verificación automática: `uv run python infra/smoke_test.py`.
La prueba de humo deja un usuario `humo.prueba` desactivado. Lo reutiliza en cada corrida.
También deja un servicio `HUMO-SERV` en el catálogo, que reactiva en cada corrida.

Los secretos van en `infra/.env` (cópielo desde `infra/.env.example`). Los de la administración son:

- `ADMINISTRACION_DB_PASSWORD`: contraseña con la que el servicio `administracion` entra a su base
  (solo puede consultar e insertar en la bitácora).
- `ADMINISTRACION_DUENO_DB_PASSWORD`: contraseña del dueño de esa base, que solo crea y migra tablas.
- `KEYCLOAK_ADMINISTRACION_SECRET`: secreto del cliente de Keycloak con el que `administracion`
  gestiona usuarios y lee los inicios de sesión.

Los de la inteligencia son:

- `INTELIGENCIA_DB_PASSWORD`: contraseña con la que el servicio `inteligencia` entra a su base
  (consulta, inserta y actualiza su copia local; nunca borra).
- `INTELIGENCIA_DUENO_DB_PASSWORD`: contraseña del dueño de esa base, que solo crea y migra tablas.

Los de la negociación son:

- `NEGOCIACION_DB_PASSWORD`: contraseña con la que el servicio `negociacion` entra a su base
  (nunca cambia ni borra la bitácora, los mensajes ni las ofertas).
- `NEGOCIACION_DUENO_DB_PASSWORD`: contraseña del dueño de esa base, que solo crea y migra tablas.

### Activar la administración en un entorno ya creado

El volumen de PostgreSQL y el realm de Keycloak solo se inicializan la primera vez. Si su entorno
ya existía antes de la administración, siga estos tres pasos, en este orden (en Git Bash, ejecute
antes `export MSYS_NO_PATHCONV=1`).

1. Agregue en `infra/.env` las tres variables de la administración (`ADMINISTRACION_DB_PASSWORD`,
   `ADMINISTRACION_DUENO_DB_PASSWORD` y `KEYCLOAK_ADMINISTRACION_SECRET`). Defina también las dos
   `INTELIGENCIA_*` y las dos `NEGOCIACION_*` (el `docker-compose.yml` las exige; vea las
   secciones de la inteligencia y de la negociación, más abajo) y vuelva a crear PostgreSQL y
   Keycloak para que las reciban:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --wait postgres keycloak
   ```

2. Cree la base y configure Keycloak. Ambos comandos son idempotentes: puede repetirlos sin riesgo.
   El primero crea la base y sus dos usuarios. El segundo configura en Keycloak el cliente, los
   eventos, el correo y el tema.

   ```bash
   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/20-administracion.sh
   ```

   ```bash
   docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/configurar-administracion.sh
   ```

3. Levante el resto del stack. Antes del paso 2, este comando falla porque la base de
   administración todavía no existe:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --build --wait
   ```

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

4. Llene la copia local de la inteligencia con lo que ya estaba importado. Corra los dos comandos
   en este orden: el primero vuelve a publicar todos los eventos guardados y el segundo publica el
   estado actual del catálogo y del tipo de cambio. La instantánea va al final porque la copia se
   queda con lo último que recibe: si fuera antes, los eventos viejos que repite `--todo` (por
   ejemplo, el nombre de un servicio anterior a su última edición) la dejarían con datos
   desactualizados. Los servicios ignoran lo que ya recibieron (la Actividad no se duplica), así
   que repetirlos es seguro:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --todo
   ```

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --instantanea
   ```

   Con el dataset por defecto, la copia tarda de uno a dos minutos en llenarse, según el equipo.
   Espere a que termine antes de correr la prueba de humo o de usar la plataforma: abra la consola
   de RabbitMQ (<http://localhost:15672>, usuario `plataforma` y la contraseña `RABBITMQ_PASSWORD`
   de `infra/.env`) y, en *Queues*, espere a que la cola `inteligencia.eventos` muestre 0 mensajes
   listos (*Ready*) y deje de recibir mensajes nuevos. Después, el modelo de precios se entrena
   solo.

### Activar la negociación en un entorno ya creado

Si su entorno ya existía antes del servicio de negociación, siga estos pasos, en este orden (en
Git Bash, ejecute antes `export MSYS_NO_PATHCONV=1`).

1. Agregue en `infra/.env` las dos variables de la negociación (cópielas de `infra/.env.example`)
   y vuelva a crear PostgreSQL para que las reciba:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --wait postgres
   ```

2. Cree la base de la negociación y sus dos usuarios. El comando es idempotente:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T postgres bash /docker-entrypoint-initdb.d/40-negociacion.sh
   ```

3. Levante el stack, construyendo la imagen nueva:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --build --wait
   ```

4. Llene las copias de proveedores y servicios de la negociación con lo que ya estaba importado.
   Corra los dos comandos en este orden: primero `--todo` y después `--instantanea`. Los demás
   servicios ignoran lo que ya recibieron, así que repetirlos es seguro:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --todo
   ```

   ```bash
   docker compose -f infra/docker-compose.yml exec -T proveedores python -m proveedores.reproceso --instantanea
   ```

5. Espere a que termine antes de correr la prueba de humo o de crear una negociación: abra la
   consola de RabbitMQ (<http://localhost:15672>) y, en *Queues*, espere a que la cola
   `negociacion.eventos` muestre 0 mensajes listos (*Ready*). La cola `negociacion.eventos.dlq`
   debe quedar vacía.

### Tema de inicio de sesión en un realm ya importado

Keycloak importa el realm solo la primera vez. Si su volumen de PostgreSQL ya tenía el realm
`plataforma`, aplique el tema de inicio de sesión una sola vez (no borra datos). Primero, en
cualquier terminal:

```bash
docker compose -f infra/docker-compose.yml up -d --wait keycloak
```

Después, este comando. Sirve igual en Git Bash y en PowerShell porque no lleva comillas dobles, y
la contraseña viaja en la variable `KC_CLI_PASSWORD` dentro del contenedor: no aparece en la línea
de comandos ni en la lista de procesos. En **Git Bash**, ejecute antes `export MSYS_NO_PATHCONV=1`;
sin eso, Git Bash convierte `/opt/…` y `/tmp/…` en rutas de Windows y el comando falla.

```bash
docker compose -f infra/docker-compose.yml exec keycloak bash -c 'KC_CLI_PASSWORD=$KC_BOOTSTRAP_ADMIN_PASSWORD /opt/keycloak/bin/kcadm.sh config credentials --config /tmp/kcadm.config --server http://localhost:8080/auth --realm master --user admin && /opt/keycloak/bin/kcadm.sh update realms/plataforma --config /tmp/kcadm.config -s loginTheme=plataforma'
```

**Sin línea de comandos**: abra <http://localhost:8080/auth/admin/>, entre como `admin` (contraseña
`KEYCLOAK_ADMIN_PASSWORD` de `infra/.env`), elija el realm `plataforma` y vaya a
*Realm settings → Themes → Login theme*, seleccione `plataforma` y guarde.

### Quitar el OTP en un realm ya importado

Las versiones anteriores pedían OTP a `admin1` y `aprobador1`. Si su realm se importó entonces,
quíteselo una sola vez (solo retira la acción pendiente y la credencial OTP; no toca contraseñas
ni otros datos). El comando funciona igual en PowerShell y en Git Bash (en Git Bash, ejecute antes
`export MSYS_NO_PATHCONV=1`):

```bash
docker compose -f infra/docker-compose.yml exec -T keycloak bash /opt/keycloak/data/import/quitar-otp.sh
```

**Sin línea de comandos**: en <http://localhost:8080/auth/admin/>, realm `plataforma` →
*Users* → `admin1` → deje vacío *Required user actions* y, en *Credentials*, borre la de tipo
`otp`; repita con `aprobador1`.

### Notas para Windows (Git Bash)

- Antes del último comando (`docker compose … exec … /datos`), ejecute `export MSYS_NO_PATHCONV=1`:
  Git Bash convierte `/datos` en una ruta de Windows y la importación no encuentra la carpeta.
- Si `uv` no encuentra su Python administrado, indíquele la versión con `export UV_PYTHON=3.13`.

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
- Revisión de accesibilidad y diseño adaptable: `docs/qa/revision-visual-plan-a.md` (Plan A) y `docs/qa/revision-inteligencia-interfaz.md` (inteligencia en la interfaz).
- Guía "Cómo usar PluriOne" en el Tablero; se oculta y vuelve desde el menú de usuario, y se recuerda por persona (no por navegador). El menú
  muestra icono y nombre; el propósito de cada opción aparece en la ayuda emergente del menú
  contraído y lo lee el lector de pantalla.
- Los términos técnicos (P25/P50/P75, sobreprecio, puntuación, SLA…) tienen una ayuda que se
  abre con clic, toque o teclado; las definiciones viven en `web/src/glosario.ts`.
- Área **Sistema** (solo administración): Panel, Usuarios, Actividad (con exportación a CSV), Catálogo, Estado del sistema, Correos, Importación y Configuración.
- Área **Soporte**: Centro de ayuda con guías, preguntas frecuentes y glosario (`web/src/ayuda.ts`); se abre también con el botón "?" de la barra superior.
- **Inteligencia**: el Tablero, Proveedores (lista y ficha), Precios, Ranking, Alertas, la campana de la barra superior y Configuración muestran los datos del servicio `inteligencia` (`web/src/inteligencia.ts`); el Panel resume sus datos y su modelo en "Datos y modelo".
- Cada página se descarga la primera vez que se visita (rutas diferidas en `web/src/rutas.tsx`).

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

## Limitaciones conocidas (Incremento 1)

- **Mensajes fallidos sin pantalla propia.** Un evento que falla 5 veces queda en la cola
  `<cola>.dlq` y el Estado del sistema lo avisa, pero todavía no hay una pantalla para revisarlo
  o reintentarlo: se hace desde la consola de RabbitMQ.
- **Realm solo para desarrollo.** El realm incluido (`infra/keycloak/realm-plataforma.json`)
  trae credenciales de prueba y el cliente `pruebas-humo` con *password grant*; no debe usarse
  fuera de un entorno local.
- **Negociación sin interfaz todavía.** El servicio y su API están completos, pero las pantallas
  del comprador y el portal del proveedor llegan con N1b; mientras tanto se usan por la API
  (`/api/negociacion/docs`).
- **Agente sin LLM.** Los mensajes del agente son plantillas y la nota del proveedor no se
  interpreta; la IA llega con N2.

## Convenciones

- *Trunk-based*: ramas cortas `feat/…` o `fix/…` y PR hacia `main`.
- Mensajes con [Conventional Commits](https://www.conventionalcommits.org/es/).
- Toda regla de negocio nueva se desarrolla con TDD.
