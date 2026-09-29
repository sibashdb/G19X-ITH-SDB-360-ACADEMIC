"""Respuestas de error en formato Problem Details (RFC 9457)."""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from comun.logs import correlation_id

log = logging.getLogger(__name__)

TITULOS = {
    400: "Solicitud incorrecta",
    401: "No autenticado",
    403: "Sin permiso",
    404: "No encontrado",
    405: "Método no permitido",
    413: "Contenido demasiado grande",
    422: "Solicitud inválida",
    429: "Demasiadas solicitudes",
    503: "Servicio no disponible",
}


class ErrorDominio(Exception):
    """Error esperado del negocio; se devuelve al cliente tal cual."""

    def __init__(
        self, estado: int, titulo: str, detalle: str, extra: dict[str, Any] | None = None
    ) -> None:
        super().__init__(detalle)
        self.estado = estado
        self.titulo = titulo
        self.detalle = detalle
        self.extra = extra or {}


def _problema(
    request: Request,
    estado: int,
    titulo: str,
    detalle: str,
    extra: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    cuerpo: dict[str, Any] = {
        "type": "about:blank",
        "title": titulo,
        "status": estado,
        "detail": detalle,
        "instance": request.url.path,
        "correlation_id": correlation_id.get(),
        **(extra or {}),
    }
    return JSONResponse(
        cuerpo, status_code=estado, media_type="application/problem+json", headers=headers
    )


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDominio)
    async def _dominio(request: Request, exc: ErrorDominio) -> JSONResponse:
        return _problema(request, exc.estado, exc.titulo, exc.detalle, exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        titulo = TITULOS.get(exc.status_code, HTTPStatus(exc.status_code).phrase)
        return _problema(request, exc.status_code, titulo, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        errores = [
            {"campo": ".".join(str(parte) for parte in e["loc"]), "mensaje": e["msg"]}
            for e in exc.errors()
        ]
        return _problema(
            request, 422, TITULOS[422], "Revise los campos indicados.", {"errores": errores}
        )

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Error no controlado en %s", request.url.path)
        return _problema(
            request,
            500,
            "Error interno",
            "Ocurrió un error inesperado. Reporte el correlation_id a soporte.",
        )
