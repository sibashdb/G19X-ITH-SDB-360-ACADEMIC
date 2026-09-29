"""Logs JSON estructurados con identificador de correlación por petición."""

import json
import logging
import re
import sys
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import Request, Response

CABECERA_CORRELACION = "X-Request-ID"
_CORRELACION_VALIDA = re.compile(r"^[A-Za-z0-9-]{1,64}$")

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class FormatoJSON(logging.Formatter):
    """Una línea JSON por registro, con el servicio y el correlation id vigente."""

    def __init__(self, servicio: str) -> None:
        super().__init__()
        self.servicio = servicio

    def format(self, record: logging.LogRecord) -> str:
        datos = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "servicio": self.servicio,
            "logger": record.name,
            "mensaje": record.getMessage(),
            "correlation_id": correlation_id.get(),
        }
        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False)


def configurar_logs(servicio: str, nivel: str = "INFO") -> None:
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormatoJSON(servicio))
    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(nivel)


async def middleware_correlacion(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Toma X-Request-ID del gateway (o genera uno) y lo devuelve en la respuesta."""
    recibido = request.headers.get(CABECERA_CORRELACION, "")
    valor = recibido if _CORRELACION_VALIDA.fullmatch(recibido) else uuid.uuid4().hex
    # Sin reset: cada petición corre en su propia tarea, y así el manejador de
    # errores 500 (que corre fuera de este middleware) todavía ve el valor.
    correlation_id.set(valor)
    respuesta = await call_next(request)
    respuesta.headers[CABECERA_CORRELACION] = valor
    return respuesta
