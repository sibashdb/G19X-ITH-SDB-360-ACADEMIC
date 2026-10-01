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
`aprobador1`) y sus contraseñas están en `infra/keycloak/realm-plataforma.json`; admin y
aprobador configuran OTP en su primer inicio de sesión. Verificación automática:
`uv run python infra/smoke_test.py`.

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

## Estructura

| Carpeta | Contenido |
|---|---|
| `libs/comun` | Infraestructura compartida: logs, errores RFC 9457, JWT, salud, outbox |
| `services/proveedores` | Microservicio de proveedores, contratos, precios y desempeño |
| `tools/generador` | Datos sintéticos reproducibles del ERP simulado |
| `web` | SPA en React servida por el gateway |
| `infra` | Docker Compose, Nginx, Keycloak, PostgreSQL |

## Limitaciones conocidas (Incremento 1)

- **OTP por usuario, no por rol.** Keycloak exige OTP solo a los usuarios sembrados
  `admin1` y `aprobador1`, no a todo usuario con esos roles. Antes de cualquier despliegue no
  local hay que configurar en Keycloak un flujo de autenticación condicional por rol.
- **Eventos sin cola enlazada.** Un evento que se publica en RabbitMQ sin colas enlazadas al
  exchange se descarta; el outbox conserva el registro. El Incremento 2 declarará las colas
  antes de publicar y agregará el reproceso.
- **Realm solo para desarrollo.** El realm incluido (`infra/keycloak/realm-plataforma.json`)
  trae credenciales de prueba y el cliente `pruebas-humo` con *password grant*; no debe usarse
  fuera de un entorno local.

## Convenciones

- *Trunk-based*: ramas cortas `feat/…` o `fix/…` y PR hacia `main`.
- Mensajes con [Conventional Commits](https://www.conventionalcommits.org/es/).
- Toda regla de negocio nueva se desarrolla con TDD.
