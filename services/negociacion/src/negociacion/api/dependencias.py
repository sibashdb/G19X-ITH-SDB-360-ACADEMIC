"""Base de datos, roles, reloj y dependencias externas para las rutas."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from comun.auth import ROLES_INTERNOS, Usuario, requiere_rol
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion.config import Configuracion
from negociacion.correo import EnviarCorreo
from negociacion.db import obtener_sesion
from negociacion.integraciones import Integraciones

_bearer = HTTPBearer(auto_error=False)


def _token(credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> str:
    """El token del comprador, para consultar a los otros servicios en su nombre (spec D5).

    Las rutas que lo usan también exigen el rol, que es lo que valida el token.
    """
    return "" if credenciales is None else credenciales.credentials


def _reloj(request: Request) -> Callable[[], datetime]:
    reloj: Callable[[], datetime] = request.app.state.reloj
    return reloj


def _integraciones(request: Request) -> Integraciones:
    integraciones: Integraciones = request.app.state.integraciones
    return integraciones


def _enviar_correo(request: Request) -> EnviarCorreo:
    enviar: EnviarCorreo = request.app.state.enviar_correo
    return enviar


def _config(request: Request) -> Configuracion:
    config: Configuracion = request.app.state.config
    return config


Bd = Annotated[AsyncSession, Depends(obtener_sesion)]
Lector = Annotated[Usuario, Depends(requiere_rol(*ROLES_INTERNOS))]
Comprador = Annotated[Usuario, Depends(requiere_rol("comprador"))]
Aprobador = Annotated[Usuario, Depends(requiere_rol("aprobador"))]
TokenUsuario = Annotated[str, Depends(_token)]
Reloj = Annotated[Callable[[], datetime], Depends(_reloj)]
Integ = Annotated[Integraciones, Depends(_integraciones)]
Correo = Annotated[EnviarCorreo, Depends(_enviar_correo)]
Config = Annotated[Configuracion, Depends(_config)]
ClaveIdempotencia = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]
