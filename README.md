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

### Activar la administración en un entorno ya creado

El volumen de PostgreSQL y el realm de Keycloak solo se inicializan la primera vez. Si su entorno
ya existía antes de la administración, siga estos tres pasos, en este orden (en Git Bash, ejecute
antes `export MSYS_NO_PATHCONV=1`).

1. Agregue en `infra/.env` las tres variables de arriba y vuelva a crear PostgreSQL y Keycloak para
   que las reciban:

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

### Tema de inicio de sesión en un realm ya importado

Keycloak importa el realm solo la primera vez. Si su volumen de PostgreSQL ya tenía el realm
`plataforma`, aplique el tema de inicio de sesión una sola vez (no borra datos). Primero, en
cualquier terminal:

```bash
docker compose -f infra/docker-compose.yml up -d --wait keycloak
```

Después, el comando según su terminal. **Git Bash**: necesita `MSYS_NO_PATHCONV=1`; sin él
convierte `/opt/…` y `/tmp/…` en rutas de Windows y el comando falla.

```bash
export MSYS_NO_PATHCONV=1
docker compose -f infra/docker-compose.yml exec keycloak bash -c '/opt/keycloak/bin/kcadm.sh config credentials --config /tmp/kcadm.config --server http://localhost:8080/auth --realm master --user admin --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" && /opt/keycloak/bin/kcadm.sh update realms/plataforma --config /tmp/kcadm.config -s loginTheme=plataforma'
```

**PowerShell**: pierde las comillas dobles internas al llamar a un programa externo y el comando
anterior falla, así que se usa sin ellas (la contraseña `KEYCLOAK_ADMIN_PASSWORD` de
`infra/.env` no debe tener espacios ni caracteres especiales del shell):

```powershell
docker compose -f infra/docker-compose.yml exec keycloak bash -c '/opt/keycloak/bin/kcadm.sh config credentials --config /tmp/kcadm.config --server http://localhost:8080/auth --realm master --user admin --password $KC_BOOTSTRAP_ADMIN_PASSWORD && /opt/keycloak/bin/kcadm.sh update realms/plataforma --config /tmp/kcadm.config -s loginTheme=plataforma'
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
| Mailpit, buzón de desarrollo de los correos de Keycloak (solo en este equipo) | <http://localhost:8025> |
| Versión que muestra el Estado del sistema | variable `VERSION_APP` de `infra/.env` (por defecto `desarrollo`) |

## Interfaz

- Sistema de diseño: tokens claro/oscuro en `web/src/index.css` (los componentes solo usan tokens;
  `npm run lint` rechaza colores literales y `src/tokens.node.test.ts` verifica el contraste WCAG).
- Tema claro, oscuro o del sistema desde la barra superior; la preferencia se guarda en el navegador.
- Fuentes Fira Sans y Fira Code servidas por la propia aplicación (sin CDN).
- Revisión de accesibilidad y diseño adaptable: `docs/qa/revision-visual-plan-a.md`.
- Guía "Cómo usar PluriOne" en el Tablero (se oculta y vuelve desde el menú de usuario) y menú
  con una línea de propósito en cada opción.
- Los términos técnicos (P25/P50/P75, sobreprecio, puntuación, SLA…) tienen una ayuda que se
  abre con clic, toque o teclado; las definiciones viven en `web/src/glosario.ts`.
- Área **Sistema** (solo administración): Panel, Usuarios, Actividad (con exportación a CSV), Catálogo, Estado del sistema, Correos, Importación y Configuración.
- Área **Soporte**: Centro de ayuda con guías, preguntas frecuentes y glosario (`web/src/ayuda.ts`); se abre también con el botón "?" de la barra superior.

## Estructura

| Carpeta | Contenido |
|---|---|
| `libs/comun` | Infraestructura compartida: logs, errores RFC 9457, JWT, salud, outbox |
| `services/proveedores` | Microservicio de proveedores, contratos, precios y desempeño |
| `services/administracion` | Microservicio de administración: usuarios, bitácora, correos, estado del sistema y panel (`/api/administracion/`) |
| `tools/generador` | Datos sintéticos reproducibles del ERP simulado |
| `web` | SPA en React servida por el gateway |
| `infra` | Docker Compose, Nginx, Keycloak, PostgreSQL |

## Limitaciones conocidas (Incremento 1)

- **Eventos sin cola enlazada.** Un evento que se publica sin colas enlazadas al exchange se
  descarta; el outbox conserva el registro. `administracion` declara su cola
  (`administracion.actividad`) al arrancar, así que solo se pierden los eventos publicados antes
  de su primer arranque. El Plan B declarará toda la topología antes de publicar y agregará el
  reproceso.
- **Realm solo para desarrollo.** El realm incluido (`infra/keycloak/realm-plataforma.json`)
  trae credenciales de prueba y el cliente `pruebas-humo` con *password grant*; no debe usarse
  fuera de un entorno local.

## Convenciones

- *Trunk-based*: ramas cortas `feat/…` o `fix/…` y PR hacia `main`.
- Mensajes con [Conventional Commits](https://www.conventionalcommits.org/es/).
- Toda regla de negocio nueva se desarrolla con TDD.
