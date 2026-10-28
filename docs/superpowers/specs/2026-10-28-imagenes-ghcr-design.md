# Imágenes en GitHub Container Registry (entregable 5)

- **Fecha:** 2026-10-28.
- **Estado:** el residente delegó todas las decisiones («lo que veas más conveniente, decide
  tú»). Cada decisión de abajo es de Claude.
- **Contexto:** PRD §6.5 (entregable 5, «Sistema funcional»); plan del proyecto, del 05/11 al
  11/11, adelantado a la holgura que dejó N2; revisión del asesor del corte 5, criterio
  «Entrega»: «Falta fijar qué commit se entrega y publicar las imágenes en GHCR».

## Para qué

Hoy, instalar PluriOne compila seis imágenes en la máquina de quien lo instala. El arranque
desde un clon limpio tardó de 192 a 455 s (`docs/qa/arranque-desde-cero.md`), sin contar la
descarga de las imágenes base. Cada compilación es además un punto donde puede fallar algo que
no es PluriOne: `npm ci`, `uv sync`, la red o un proxy.

Con las imágenes publicadas, quien haga la revisión completa, o alguien de PluriOne, descarga lo
mismo que pasó la prueba de humo en GitHub y lo levanta sin compilar nada. La etiqueta de git y
la de las imágenes son la misma, así que «lo que se entrega» queda fijo en un solo nombre.

## Metas

1. Al subir una etiqueta `mvp-*`, GitHub Actions construye y publica en `ghcr.io` las seis
   imágenes propias: `proveedores`, `administracion`, `inteligencia`, `negociacion`, `ia` y
   `gateway` (la SPA con Nginx).
2. Las imágenes son públicas: `docker pull` funciona sin iniciar sesión.
3. El mismo flujo, después de publicar, levanta el stack con las imágenes recién publicadas, sin
   compilar, importa los datos y corre la prueba de humo. `latest` solo se mueve si eso pasa.
4. `uv run python infra/arrancar.py --imagenes mvp-1.2` levanta la plataforma con esas imágenes;
   sin `--imagenes`, todo sigue como hoy.
5. Una medición documentada del arranque desde un clon limpio con las imágenes, comparada con la
   de compilar.

## No metas

- Imágenes para ARM (`linux/arm64`): solo `linux/amd64`. Se agrega si alguien lo pide.
- Firma (cosign), SBOM y escaneo de vulnerabilidades (Trivy). El escaneo ya está en la fase de
  calidad, del 12/11 al 20/11.
- Desplegar en un servidor, Kubernetes o Helm.
- Volver a publicar las imágenes de terceros (PostgreSQL, RabbitMQ, Keycloak, Mailpit, curl):
  se siguen bajando de sus registros oficiales.
- Ollama: corre en el anfitrión, fuera de Docker (ADR-003).

## Lo que no debe pasar

- Que el arranque de hoy, el que compila, cambie de comportamiento o se rompa. El job `stack`
  del CI sigue compilando.
- Que una imagen publicada lleve un secreto. Se construyen en GitHub desde un clon limpio: no
  existe `infra/.env`, y `.dockerignore` ya excluye `.env`, `datos/` y `.superpowers/`.
- Que `latest` apunte a algo que no pasó la prueba de humo.
- Mover una etiqueta `mvp-*` ya subida (regla de la revisión del corte 5).

## Decisiones

| # | Decisión | Por qué |
|---|---|---|
| D1 | Nombres: `ghcr.io/sibashdb/g19x-ith-sdb-360-academic/<servicio>`, en minúsculas como exige GHCR. Etiquetas de imagen: la de git (`mvp-1.2`) y `latest` | Un nombre por servicio, junto al repositorio. La etiqueta de git y la de imagen dicen lo mismo |
| D2 | Etiquetas OCI `org.opencontainers.image.source` (el repositorio), `.version` (la etiqueta) y `.revision` (el commit), con `docker/metadata-action` | `source` enlaza cada paquete al repositorio en GitHub. `revision` dice de qué commit salió |
| D3 | Un flujo nuevo, `.github/workflows/imagenes.yml`, que corre al subir una etiqueta `mvp-*` y también a mano (`workflow_dispatch`) para una etiqueta existente | Separado del CI: corre pocas veces y con permiso de escritura en paquetes, que el CI no necesita |
| D4 | Tres jobs: `publicar` (una matriz de seis imágenes, con caché de GitHub Actions), `probar` (sin compilar: `pull`, `up --no-build`, la importación y la prueba de humo) y `latest` (copia las etiquetas a `latest` con `docker buildx imagetools create`, solo si `probar` pasó) | Se prueba lo que de verdad se publicó. `latest` queda como señal de «probado» |
| D5 | Permisos mínimos: `contents: read` en todo el flujo y `packages: write` solo en `publicar` y `latest`, con el `GITHUB_TOKEN` del flujo | Sin secretos nuevos ni tokens personales |
| D6 | En `infra/docker-compose.yml`, cada servicio propio gana `image: ghcr.io/…/<servicio>:${PLURIONE_VERSION:-local}` junto a su `build:` | Un solo archivo de compose. Sin la variable, la imagen compilada se llama `…:local` y todo sigue como hoy |
| D7 | `arrancar.py --imagenes <etiqueta>` define `PLURIONE_VERSION` y `VERSION_APP` con esa etiqueta, corre `docker compose pull` de los seis servicios y después `up -d --no-build --wait`. Los demás pasos (datos, importación y prueba de humo) no cambian | El Estado del sistema muestra la versión que corre. Quien instala sigue necesitando git, uv y Docker: la configuración de `infra/` (realm de Keycloak, scripts de PostgreSQL) se monta desde el clon |
| D8 | `mvp-1.1` se queda en `41c0900`, sin imágenes: ese commit no tiene el flujo ni los `image:` del compose. La integración de este trabajo se etiqueta **`mvp-1.2`**: la primera con imágenes y la nueva versión que se entrega | Una etiqueta subida no se mueve, y `mvp-1.1` ya está documentada |
| D9 | Si GHCR crea los paquetes como privados, el residente los cambia a públicos en GitHub (Package settings → Change visibility), una vez por paquete. Claude no cambia la visibilidad: es publicar contenido | Una acción pública que decide el dueño de la cuenta |
| D10 | La medición va en `docs/qa/arranque-desde-imagenes.md`, con el mismo método que `arranque-desde-cero.md`: clon limpio, `COMPOSE_PROJECT_NAME` aparte, sin las imágenes propias en el equipo, con el tiempo total y cuánto se descargó | Comparable con la medición que ya existe |
| D11 | Una etiqueta candidata `mvp-X.Y-rcN` (por ejemplo `mvp-1.2-rc1`) publica y prueba igual, pero no mueve `latest`. Orden: se integra el PR, se sube `mvp-1.2-rc1`, se mide con esas imágenes y, con la medición y la documentación integradas en un segundo PR, `mvp-1.2` va sobre ese último commit | El flujo solo existe en GitHub después de integrarse, así que se prueba con una candidata sin gastar `mvp-1.2`. Así la etiqueta que se entrega incluye su propia medición |

## Qué cambia en la documentación

- **README:** en «Arranque rápido», una opción con las imágenes publicadas: qué se descarga y
  qué hace falta igual (git, uv, Docker). La fila del entregable 5 pasa a «Hecho».
- **`docs/MVP.md`, «Versión que se entrega»:** se agrega `mvp-1.2`, con imágenes, como la
  versión que se entrega.
- **`docs/plan-del-proyecto.md`:** el entregable 5 y las imágenes en GHCR, hechos.
- **`docs/arquitectura/`:** una línea en C4, o en el documento que corresponda, sobre de dónde
  salen las imágenes.

## Cómo se acepta

- El flujo `imagenes.yml` corre al subir `mvp-1.2-rc1`: publica las seis imágenes, `probar`
  pasa la prueba de humo con ellas y `latest` no se mueve. Al subir `mvp-1.2`, lo mismo, y
  `latest` sí se mueve.
- `docker pull ghcr.io/sibashdb/g19x-ith-sdb-360-academic/negociacion:mvp-1.2` funciona sin
  iniciar sesión.
- En el equipo de desarrollo, un clon limpio de `mvp-1.2` arranca con `--imagenes mvp-1.2` sin
  compilar ninguna imagen propia, la prueba de humo responde «OK» y el tiempo queda medido.
- Sin `--imagenes`, `arrancar.py` y el job `stack` del CI se comportan como hoy.
- Un PR con el CI en verde integra el trabajo a `main` (regla del 27/10).

## Lo que decide quien lo construya

- Las versiones de las acciones de Docker (`login`, `setup-buildx`, `metadata` y `build-push`),
  siempre fijadas a una versión mayor, como las que ya usa el CI.
- Cómo prueba la lógica nueva de `arrancar.py`: al menos una prueba que corra con `pytest`.
- Cuánto tarda cada job y sus límites de tiempo.
