"""Endpoints de salud para los healthchecks de Docker Compose."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Response

log = logging.getLogger(__name__)


def crear_router_salud(verificaciones: dict[str, Callable[[], Awaitable[None]]]) -> APIRouter:
    router = APIRouter(prefix="/salud", tags=["salud"])

    @router.get("/vivo")
    async def vivo() -> dict[str, str]:
        return {"estado": "ok"}

    @router.get("/listo")
    async def listo(response: Response) -> dict[str, object]:
        dependencias: dict[str, str] = {}
        for nombre, verificar in verificaciones.items():
            try:
                await asyncio.wait_for(verificar(), timeout=2)
                dependencias[nombre] = "ok"
            except Exception:
                log.warning("Dependencia no disponible: %s", nombre, exc_info=True)
                dependencias[nombre] = "error"
        sano = all(estado == "ok" for estado in dependencias.values())
        if not sano:
            response.status_code = 503
        return {"estado": "ok" if sano else "degradado", "dependencias": dependencias}

    return router
