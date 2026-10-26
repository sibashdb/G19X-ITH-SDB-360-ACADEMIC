"""Aplicación FastAPI del servicio ia: sin base de datos y fuera del gateway (spec D3 y D6)."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.salud import crear_router_salud
from fastapi import FastAPI

from ia import api
from ia.config import Configuracion
from ia.llm import ClienteLLM


def crear_app(
    configuracion: Configuracion | None = None,
    transporte: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    config = configuracion or Configuracion()
    configurar_logs(config.nombre_servicio, config.log_level)
    http = httpx.AsyncClient(transport=transporte)
    llm = ClienteLLM(http, config.llm_url, config.llm_modelo, config.llm_espera_s)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        precarga = asyncio.create_task(llm.precargar()) if config.llm_url else None
        yield
        if precarga is not None:
            precarga.cancel()
        await http.aclose()

    app = FastAPI(title="Servicio ia", version="0.1.0", lifespan=ciclo_de_vida)
    app.state.llm = llm
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)
    # Sin verificaciones: el contenedor está sano aunque Ollama no exista (degradación).
    app.include_router(crear_router_salud({}))
    app.include_router(api.router)

    @app.get("/llm")
    async def estado_llm() -> dict[str, object]:
        return {"disponible": await llm.disponible(), "modelo": llm.modelo}

    return app
