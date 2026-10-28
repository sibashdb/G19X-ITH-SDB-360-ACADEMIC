# Imágenes en GHCR (entregable 5): plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** publicar en `ghcr.io` las seis imágenes propias de PluriOne al subir una etiqueta `mvp-*`, probarlas sin compilar y poder arrancar la plataforma con ellas desde `arrancar.py`.

**Architecture:** un flujo nuevo de GitHub Actions (`imagenes.yml`) tiene tres jobs: publicar (una matriz de seis imágenes), probar (arranque con las imágenes publicadas y la prueba de humo) y mover `latest`. El compose nombra cada imagen propia con la variable `PLURIONE_VERSION` (`local` por defecto), y `arrancar.py --imagenes <etiqueta>` las descarga en lugar de compilarlas.

**Tech Stack:** GitHub Actions (`docker/login-action`, `docker/setup-buildx-action`, `docker/metadata-action`, `docker/build-push-action`), Docker Compose y Python 3.13 con `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-28-imagenes-ghcr-design.md`

## Global Constraints

- Prefijo de las imágenes: `ghcr.io/sibashdb/g19x-ith-sdb-360-academic`, en minúsculas.
- Servicios propios, con este nombre y en este orden: `proveedores`, `administracion`, `inteligencia`, `ia`, `negociacion` y `gateway`. El Dockerfile de `gateway` es `web/Dockerfile`; el de los demás, `services/<servicio>/Dockerfile`. El contexto de construcción es siempre la raíz del repositorio.
- Etiquetas que disparan el flujo: `mvp-*`. Las candidatas `mvp-X.Y-rcN` publican y prueban, pero no mueven `latest`.
- Solo `linux/amd64`.
- Permisos: `contents: read` en todo el flujo; `packages: write` solo en los jobs que publican; `packages: read` en `probar`. Se usa el `GITHUB_TOKEN` del flujo, sin secretos nuevos.
- Sin `--imagenes`, `arrancar.py` hace exactamente lo de hoy. El job `stack` del CI no cambia.
- Una etiqueta subida no se mueve. Integración solo con un PR y el CI en verde (regla del 27/10).
- Textos en español; en la documentación, el usuario se trata de «usted».

## Review Focus

1. **Una etiqueta mal escrita en `--imagenes`** (`1.2`, `mvp1.2`): `arrancar.py` la rechaza antes de llamar a Docker, con un mensaje claro. Prueba en la Tarea 1.
2. **Que el compose, `arrancar.py` y el flujo nombren distinto un servicio:** la descarga o la publicación fallarían con un error confuso. Hay una prueba de consistencia entre los tres en la Tarea 2.
3. **Que una candidata mueva `latest`:** el job `latest` solo corre para una etiqueta sin `-rc`. Prueba sobre el texto del flujo en la Tarea 2.
4. **Que GHCR cree los paquetes como privados:** `probar` inicia sesión con el `GITHUB_TOKEN`, así que no depende de la visibilidad. La descarga pública se comprueba a mano en la Tarea 4.
5. **Que alguien ya haya compilado las imágenes en su equipo:** se llaman `…:local`, así que no chocan con `…:mvp-1.2`. Se comprueba en la medición de la Tarea 4, con un equipo que ya tiene las `:local`.

---

### Task 1: `arrancar.py --imagenes` y el compose con `image:`

**Files:**
- Modify: `infra/arrancar.py`
- Modify: `infra/docker-compose.yml`, en los seis servicios propios
- Create: `infra/tests/test_arrancar.py`
- Modify: `pyproject.toml`, para agregar `infra/tests` a `testpaths`

**Interfaces:**
- Produces (en `infra/arrancar.py`):
  - `IMAGENES = "ghcr.io/sibashdb/g19x-ith-sdb-360-academic"`
  - `SERVICIOS_PROPIOS: tuple[str, ...]`, los seis de las Global Constraints
  - `ETIQUETA = re.compile(r"mvp-\d+\.\d+(-rc\d+)?|latest")`
  - `def pasos(version: str | None, con_datos: bool) -> list[list[str]]`: sin versión, los pasos de hoy. Con versión, sin cambios en los pasos de datos, importación y prueba de humo; el `up` se cambia por `[*COMPOSE, "pull", *SERVICIOS_PROPIOS]` seguido de `[*COMPOSE, "up", "-d", "--no-build", "--wait"]`. Con `con_datos=True` se omite el paso del generador, como hoy.
  - `def entorno(version: str | None) -> dict[str, str]`: `{}` sin versión; si no, `{"PLURIONE_VERSION": version, "VERSION_APP": version}`.
  - `main(argv: list[str] | None = None) -> int`, con `argparse` y `--imagenes ETIQUETA`. Si la etiqueta no cumple `ETIQUETA` (con `fullmatch`), devuelve 2 con el mensaje «La etiqueta debe ser como mvp-1.2, mvp-1.2-rc1 o latest.» sin correr ningún paso.
- La prueba carga `infra/arrancar.py` con `importlib.util.spec_from_file_location`, porque `infra` no es un paquete.

- [ ] **Step 1: Escribir las pruebas que fallan** en `infra/tests/test_arrancar.py`:
  - `test_sin_imagenes_compila_como_hoy`: `pasos(None, con_datos=True)` contiene `[*COMPOSE, "up", "-d", "--build", "--wait"]` y ningún paso con `"pull"`.
  - `test_con_imagenes_descarga_y_no_compila`: `pasos("mvp-1.2", con_datos=True)` contiene `[*COMPOSE, "pull", *SERVICIOS_PROPIOS]` antes de `[*COMPOSE, "up", "-d", "--no-build", "--wait"]`, y ningún paso contiene `"--build"`.
  - `test_sin_datos_genera_primero`: `pasos("mvp-1.2", con_datos=False)[0]` es el paso del generador.
  - `test_la_version_llega_al_compose_y_al_estado_del_sistema`: `entorno("mvp-1.2") == {"PLURIONE_VERSION": "mvp-1.2", "VERSION_APP": "mvp-1.2"}` y `entorno(None) == {}`.
  - `test_una_etiqueta_mal_escrita_se_rechaza_sin_llamar_a_docker`: para `"1.2"`, `"mvp1.2"` y `"mvp-1.2; rm -rf /"`, `main(["--imagenes", etiqueta])` devuelve 2, y un `subprocess.run` reemplazado con `monkeypatch` nunca se llama.
  - `test_el_compose_nombra_cada_servicio_propio_con_su_imagen`: para cada servicio de `SERVICIOS_PROPIOS`, el texto de `infra/docker-compose.yml` contiene `image: {IMAGENES}/{servicio}:${{PLURIONE_VERSION:-local}}`.
- [ ] **Step 2:** `uv run pytest infra/tests -v`. Esperado: FALLA (no existen `pasos`, `entorno` ni los `image:`).
- [ ] **Step 3:** Implementar las interfaces de arriba en `arrancar.py`. Se conservan el docstring con los pasos (se agrega `--imagenes`), la copia de `.env` y los mensajes de FALLA. En `main`, `entorno(version)` se aplica a `os.environ` antes de los pasos. En el compose, cada servicio propio gana su línea `image:` junto a su `build:`.
- [ ] **Step 4:** `uv run pytest infra/tests -v` y las puertas de Python (`uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`). Esperado: PASA. Además, `docker compose -f infra/docker-compose.yml config --quiet` termina sin error.
- [ ] **Step 5: Commit** `feat(infra): arrancar.py --imagenes levanta las imágenes publicadas sin compilar`

### Task 2: El flujo `imagenes.yml`

**Files:**
- Create: `.github/workflows/imagenes.yml`
- Modify: `infra/tests/test_arrancar.py`, con una prueba de consistencia

**Interfaces:**
- Consumes: `SERVICIOS_PROPIOS` e `IMAGENES` de la Tarea 1.
- Produces: imágenes `ghcr.io/sibashdb/g19x-ith-sdb-360-academic/<servicio>:<etiqueta>`, con las etiquetas OCI de `docker/metadata-action`, y `:latest` para las etiquetas que no son candidatas.

- [ ] **Step 1: Escribir las pruebas que fallan**, en el mismo archivo:
  - `test_el_flujo_publica_los_mismos_servicios`: el texto de `.github/workflows/imagenes.yml` contiene, para cada servicio, una entrada de la matriz con su Dockerfile (`servicio: gateway` con `dockerfile: web/Dockerfile`; los demás con `services/<servicio>/Dockerfile`).
  - `test_el_flujo_corre_con_las_etiquetas_mvp`: el texto contiene `tags: ["mvp-*"]` y `workflow_dispatch:`.
  - `test_una_candidata_no_mueve_latest`: el job `latest` tiene una condición `if:` que excluye las etiquetas con `-rc`.
- [ ] **Step 2:** `uv run pytest infra/tests -v`. Esperado: FALLA (no existe el archivo).
- [ ] **Step 3: Escribir el flujo:**
  - **Disparadores:** `push` de etiquetas `mvp-*`, y `workflow_dispatch` con la entrada `etiqueta` (requerida).
  - **Variable `ETIQUETA` del flujo:** en un `push`, `github.ref_name`; a mano, `inputs.etiqueta`.
  - **`concurrency`:** por etiqueta.
  - **Job `publicar`:**
    - una matriz con los seis `servicio` y su `dockerfile`;
    - `checkout` en `ref: ${{ env.ETIQUETA }}`;
    - `setup-buildx`, `login` a `ghcr.io` con `github.actor` y el `GITHUB_TOKEN`, y `metadata` con `images: <prefijo>/<servicio>` y `tags: type=raw,value=<etiqueta>`;
    - `build-push` con `context: .`, `platforms: linux/amd64`, `push: true` y caché `type=gha` por servicio.
  - **Job `probar`:**
    - corre después de `publicar`;
    - `checkout` de la etiqueta, `login` con permiso de lectura y `setup-uv` (0.12.20);
    - `uv sync --all-packages --locked` y después `uv run python infra/arrancar.py --imagenes "$ETIQUETA"`;
    - los logs del compose si falla.
  - **Job `latest`:**
    - corre después de `probar` y solo si la etiqueta no contiene `-rc`;
    - `login` y, por servicio, `docker buildx imagetools create -t <img>:latest <img>:<etiqueta>`.
- [ ] **Step 4:** `uv run pytest infra/tests -v` y las puertas de Python. Esperado: PASA. Revisar el YAML a mano contra las Global Constraints; el flujo solo corre de verdad en la Tarea 4.
- [ ] **Step 5: Commit** `ci: imagenes.yml publica y prueba las imágenes en GHCR con cada etiqueta mvp-*`

### Task 3: Documentación e integración (primer PR)

**Files:**
- Modify: `README.md`:
  - en «Arranque rápido», «Con las imágenes publicadas»: el comando, qué se descarga y qué hace falta igual (git, uv y Docker);
  - en «Desarrollo», una fila sobre cómo publicar una versión.
- Modify: `docs/MVP.md`, «Versión que se entrega»: una fila para `mvp-1.2` («con las imágenes en GHCR; se publica al integrar el entregable 5»).
- Modify: `docs/arquitectura/c4.md`: una línea bajo la tabla de contenedores sobre de dónde salen las imágenes propias.

- [ ] **Step 1:** Escribir los tres cambios.
- [ ] **Step 2:** `uv run pytest infra/tests -q` y las puertas de Python. Esperado: PASA.
- [ ] **Step 3: Commit** `docs: cómo arrancar con las imágenes de GHCR y qué publica cada versión`
- [ ] **Step 4:** Subir la rama, abrir el PR hacia `main` con `gh pr create` y vincularlo (`get_status` / `bind_pr`). Esperado: los cinco checks del CI en verde. Integrar con `gh pr merge --merge` solo entonces.

### Task 4: Publicar la candidata, medir y entregar `mvp-1.2`

**Files:**
- Create: `docs/qa/arranque-desde-imagenes.md`
- Modify: `README.md` (el entregable 5 pasa a «Hecho»), `docs/MVP.md` (`mvp-1.2` es la versión que se entrega) y `docs/plan-del-proyecto.md` (el entregable 5 y las imágenes en GHCR, hechos; en «Lo hecho», una fila del 28/10)

- [ ] **Step 1:** Sobre el commit integrado de `main`: `git tag -a mvp-1.2-rc1 -m "…"` y `git push origin mvp-1.2-rc1`. Esperado: `imagenes.yml` corre; `publicar` y `probar` en verde; `latest` no corre.
- [ ] **Step 2:** Sin iniciar sesión en GHCR (`docker logout ghcr.io`), `docker pull ghcr.io/sibashdb/g19x-ith-sdb-360-academic/negociacion:mvp-1.2-rc1`. Si GHCR responde que no existe o pide credenciales, los paquetes son privados: pedirle al residente que los haga públicos (spec D9) y repetir.
- [ ] **Step 3: Medir** como `docs/qa/arranque-desde-cero.md`:
  - clonar el repositorio en una carpeta nueva, en la etiqueta `mvp-1.2-rc1`, con `COMPOSE_PROJECT_NAME=plataforma-imagenes`;
  - borrar del equipo las imágenes `…:mvp-1.2-rc1`;
  - correr `uv run python infra/arrancar.py --imagenes mvp-1.2-rc1` y anotar el tiempo total, lo descargado y el resultado de la prueba de humo.

  Esperado: ninguna imagen propia se compila y la prueba de humo responde «OK». Escribirlo en `docs/qa/arranque-desde-imagenes.md`.
- [ ] **Step 4:** Actualizar README, MVP y plan como dice **Files**. Commit `docs: medición del arranque con las imágenes de GHCR; el entregable 5 queda hecho`. Segundo PR con el CI en verde e integración, igual que en la Tarea 3.
- [ ] **Step 5:** Sobre ese commit integrado, `git tag -a mvp-1.2 -m "…"` y `git push origin mvp-1.2`. Esperado: los tres jobs en verde y `latest` apunta a `mvp-1.2`. Comprobar con `docker buildx imagetools inspect <img>:latest` que el digest es el de `mvp-1.2`.
