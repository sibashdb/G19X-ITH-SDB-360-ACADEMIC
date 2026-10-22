# Arranque desde un clon limpio

Prueba del 22/10/2026, pedida en la revisión del asesor: clonar el repositorio en otra carpeta,
correr `uv run python infra/arrancar.py` y anotar cuánto tarda y qué falla.

## Cómo se corrió

```bash
git clone <repositorio> arranque-limpio
cd arranque-limpio
uv run python infra/arrancar.py
```

- **Equipo:** el de desarrollo (Ryzen 5 5600H, 14 GB de RAM, Windows 11), con Docker Desktop
  29.8.1 y 6.7 GB asignados a su máquina virtual. Git Bash como terminal.
- **Aislamiento:** `COMPOSE_PROJECT_NAME=plataforma-limpio`, para que el clon no reutilizara
  los volúmenes ni las imágenes del entorno de desarrollo. Las bases, la cola y Keycloak
  nacieron vacías.
- **Caché de uv vacía** (`UV_CACHE_DIR` en una carpeta nueva): las dependencias de Python se
  descargaron de cero.
- **Lo que sí estaba en caché:** las imágenes base de Docker (PostgreSQL, RabbitMQ, Keycloak,
  Python, Node, Nginx, Mailpit y curl, unos 1.9 GB sin comprimir). En un equipo nuevo, su descarga se
  suma al tiempo de abajo y depende de la conexión.
- Docker Desktop estaba apagado y tardó 31 s en arrancar; ese tiempo no cuenta en la tabla.

## Resultado

Las dos corridas terminaron bien, con la prueba de humo en verde:
- **La primera,** con el commit `82af244` (el `main` publicado), tardó **192 s**.
- **La segunda,** con las correcciones de abajo (`15b3044`), tardó **455 s**. La diferencia es de
  la red: la descarga de los paquetes de Python tardó 5 minutos en lugar de 15 s.

| Paso | 1.ª corrida | 2.ª corrida |
|---|---|---|
| Entorno de Python (`uv` crea el entorno, descarga e instala 80 paquetes) | 23 s | 317 s |
| Datos sintéticos (`generador`) | 2 s | 1 s |
| Construcción de las imágenes | 68 s | 42 s |
| Arranque del stack hasta que todos los servicios están sanos | 60 s | 54 s |
| Importación de los datos (4,742 registros) | 4 s | 5 s |
| Prueba de humo, de la SPA a una negociación aprobada con su contrato registrado | 35 s | 35 s |
| **Total** | **192 s** | **455 s** |

## Qué falló y qué se corrigió

Nada impidió el arranque. Aparecieron dos defectos, corregidos en `15b3044`:

1. **uv sin versión fija en las imágenes.** Los Dockerfile copiaban `ghcr.io/astral-sh/uv:latest`.
   Esa etiqueta ya apunta a uv 0.13.5, y el proyecto pide `uv-build>=0.12,<0.13`. La
   construcción solo avisaba, pero una versión nueva de uv podía romperla sin ningún cambio en el
   repositorio. Ahora las imágenes y el CI usan uv 0.12.20, la versión del equipo de desarrollo.
2. **Acentos rotos en Git Bash.** En Git Bash la salida es una tubería y Python escribía en
   cp1252, así que aparecía «Se cre� infra/.env». Ahora `arrancar.py` escribe en UTF-8, y la
   prueba de humo que lanza también.

La segunda corrida confirmó las dos correcciones: la construcción ya no avisa sobre uv y los
mensajes salen con sus acentos.

## Observaciones para la fase de calidad

- **`npm ci` reporta 9 vulnerabilidades (8 altas, 1 moderada)** en dependencias del frontend:
  - el servidor de desarrollo de vite (`launch-editor`);
  - la CLI de shadcn (`@modelcontextprotocol/sdk`, `ts-morph`, `fast-glob`, `braces`,
    `micromatch` e `ip-address`).

  Son herramientas de construcción y de desarrollo. La imagen del gateway solo sirve con Nginx
  los archivos ya construidos. Se revisan en las pruebas de seguridad del Reporte QA
  (entregable 6).
- **Docker Desktop apagado.** Si el demonio no responde, el paso de `docker compose` termina con
  el error de Docker («failed to connect to the docker API») y `arrancar.py` reporta el código de
  salida. El README ya pide Docker Desktop en sus Requisitos.
