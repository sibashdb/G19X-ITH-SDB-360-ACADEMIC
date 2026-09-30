"""Respuestas de error en formato Problem Details (RFC 9457)."""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from comun.logs import CABECERA_CORRELACION, correlation_id
from comun.mensajes import traducir_error

log = logging.getLogger(__name__)

# English default details from HTTPStatus (Starlette uses these)
DETALLES_INGLES = {
    404: "Not Found",
    405: "Method Not Allowed",
}

# Spanish details to use when Starlette's default is detected
DETALLES_ESPANOL = {
    404: "El recurso solicitado no existe.",
    405: "Método no permitido para este recurso.",
}

TITULOS = {
    400: "Solicitud incorrecta",
    401: "No autenticado",
    403: "Sin permiso",
    404: "No encontrado",
    405: "Método no permitido",
    409: "Conflicto",
    410: "Ya no disponible",
    413: "Contenido demasiado grande",
    422: "Solicitud inválida",
    429: "Demasiadas solicitudes",
    500: "Error interno",
    502: "Puerta de enlace incorrecta",
    503: "Servicio no disponible",
    504: "Tiempo de espera agotado",
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
        titulo = TITULOS.get(exc.status_code, f"Error {exc.status_code}")
        detalle = str(exc.detail)
        # Replace English default detail with Spanish if detected
        if exc.status_code in DETALLES_INGLES and detalle == DETALLES_INGLES[exc.status_code]:
            detalle = DETALLES_ESPANOL[exc.status_code]
        elif not detalle or detalle == "":
            # If no detail provided, use Spanish title as detail
            detalle = titulo
        return _problema(request, exc.status_code, titulo, detalle, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        errores = [
            {"campo": ".".join(str(parte) for parte in e["loc"]), "mensaje": traducir_error(e)}
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
            headers={CABECERA_CORRELACION: correlation_id.get()},
        )
