# Contexto de construcción: la raíz del repositorio (ver infra/docker-compose.yml).
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app
# --locked valida uv.lock contra todos los miembros del workspace, así que se copia el repo
# completo (lo pesado queda fuera por .dockerignore).
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package ia

ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 servicio
USER servicio
EXPOSE 8000

# Sin base de datos ni migraciones: no guarda estado.
CMD ["uvicorn", "ia.main:crear_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
