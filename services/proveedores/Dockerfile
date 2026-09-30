# Contexto de construcción: la raíz del repositorio (ver infra/docker-compose.yml).
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app
# --locked valida uv.lock contra todos los miembros del workspace, así que se copia el repo
# completo (lo pesado queda fuera por .dockerignore).
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package proveedores

ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 servicio
USER servicio
EXPOSE 8000

# ponytail: migra al arrancar; con varias réplicas, mover a un job de migración previo al despliegue.
CMD ["sh", "-c", "alembic -c services/proveedores/alembic.ini upgrade head && exec uvicorn proveedores.main:crear_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
