# Arranque desde un clon limpio con las imágenes de GHCR

Prueba del 28/10/2026 para el entregable 5 (spec
`docs/superpowers/specs/2026-10-28-imagenes-ghcr-design.md`). Mismo método que
[`arranque-desde-cero.md`](arranque-desde-cero.md), pero sin compilar: las seis imágenes
propias se descargan de GitHub Container Registry.

## Cómo se corrió

```bash
git clone --branch mvp-1.2-rc1 --depth 1 <repositorio> arranque-imagenes
cd arranque-imagenes
uv run python infra/arrancar.py --imagenes mvp-1.2-rc1
```

- **Versión:** la etiqueta candidata `mvp-1.2-rc1`, sobre `c69e1e2`, el mismo código que
  `mvp-1.2`. El flujo «Imágenes» la publicó y la probó en GitHub (corrida 40710157755): `publicar`
  y `probar` en verde, y `latest` omitido, como corresponde a una candidata.
- **Equipo:** el de desarrollo (Ryzen 5 5600H, 14 GB de RAM, Windows 11), con Docker Desktop
  29.8.1. Git Bash como terminal.
- **Aislamiento:**
  - `COMPOSE_PROJECT_NAME=plataforma-imagenes`: las bases, la cola y Keycloak nacieron vacías.
  - Caché de uv vacía (`UV_CACHE_DIR` en una carpeta nueva).
  - Ninguna imagen propia en el equipo: se borraron antes, y no había ninguna `…:local`.
- **Lo que sí estaba en caché:**
  - las imágenes de terceros (PostgreSQL, RabbitMQ, Keycloak, Mailpit y curl);
  - la imagen base de Python, cuyas capas comparten las cinco imágenes de los servicios.

  Con las imágenes publicadas ya no hacen falta las de Node ni de Nginx: solo se usaban para
  compilar.
- **Docker Desktop** estaba apagado; se encendió antes y su arranque no cuenta.
- **Rutas largas:** en una carpeta con ruta muy larga, `git clone` necesitó
  `-c core.longpaths=true`. Es un límite de Windows, no del proyecto.

## Resultado

**218 s** de punta a punta, con la prueba de humo en verde: «OK: SPA, Keycloak, proveedores,
administración, operación, inteligencia, negociación y adjudicación responden (60 proveedores).».

| Paso | Qué hizo |
|---|---|
| Datos | Generó los datos sintéticos; con la caché de uv vacía, primero descargó las dependencias de Python |
| Imágenes | `docker compose pull` de las seis imágenes propias. Medido aparte, con las mismas capas en caché: **26 s** |
| Stack | `up -d --no-build --wait`: ninguna imagen se compiló |
| Importación y prueba de humo | Igual que al compilar |

**Cuánto se descarga:**
- Las seis imágenes suman **411 MB comprimidos**, contando cada capa una sola vez; en el disco
  ocupan unos 2.5 GB sin comprimir, con capas compartidas.
- Si el equipo ya tiene la imagen base de Python, como este, se baja menos.
- La de `inteligencia` es la mayor (139 MB propios, por scikit-learn) y la de `gateway`, la
  menor (25 MB).

**Frente a compilar:**
- Compilando, el arranque desde un clon limpio tardó de 192 a 455 s, también con las imágenes
  base en caché (`arranque-desde-cero.md`).
- Con las imágenes, en este equipo, tarda parecido: casi todo el tiempo se va en generar los
  datos, esperar a que Keycloak y los servicios estén sanos y la prueba de humo, que no cambian.
- **Lo que cambia es lo que puede fallar.**
  - Ya no corren `npm ci`, `npm run build` ni el `uv sync` de cada imagen, que dependen de la red
    y de los registros de paquetes.
  - Lo que corre es lo mismo que pasó la prueba de humo en GitHub, y su etiqueta OCI `revision`
    dice de qué commit salió (`c69e1e2`).
- En un equipo nuevo, sin ninguna imagen, la diferencia crece. Las de terceros se bajan en los
  dos casos. Pero en lugar de bajar las imágenes base de Python, Node y Nginx y compilar seis
  imágenes, se bajan unos 411 MB de imágenes ya hechas.

## Otras comprobaciones

- **Imágenes públicas.** `docker pull ghcr.io/sibashdb/g19x-ith-sdb-360-academic/negociacion:mvp-1.2-rc1`,
  sin iniciar sesión en GHCR, funcionó. Los paquetes heredaron la visibilidad pública del
  repositorio, así que no hizo falta cambiar nada a mano.
- **Etiquetas OCI.** `docker buildx imagetools inspect` sobre esa imagen dio:
  - `source`: el repositorio;
  - `revision`: `c69e1e23d451957877043d3ec8395707cf559ef1`, el commit de la etiqueta;
  - `version`: `mvp-1.2-rc1`.
