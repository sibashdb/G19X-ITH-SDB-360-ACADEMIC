"""Validación de JWT emitidos por Keycloak y autorización por roles de realm."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWKClientConnectionError

ROLES_INTERNOS = ("admin", "comprador", "aprobador")


@dataclass(frozen=True)
class Usuario:
    id: str
    nombre: str
    roles: frozenset[str]


def _no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detalle, headers={"WWW-Authenticate": "Bearer"}
    )


class ValidadorJWT:
    """Valida firma RS256, emisor, audiencia y vigencia.

    `obtener_clave` recibe el token y devuelve la clave pública con la que se firmó.
    """

    def __init__(self, emisor: str, audiencia: str, obtener_clave: Callable[[str], Any]) -> None:
        self._emisor = emisor
        self._audiencia = audiencia
        self._obtener_clave = obtener_clave

    def validar(self, token: str) -> Usuario:
        try:
            datos = jwt.decode(
                token,
                self._obtener_clave(token),
                algorithms=["RS256"],
                audience=self._audiencia,
                issuer=self._emisor,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except PyJWKClientConnectionError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "El servicio de identidad no está disponible"
            ) from exc
        except jwt.PyJWTError as exc:
            raise _no_autenticado("Token inválido o vencido") from exc
        roles = (datos.get("realm_access") or {}).get("roles") or []
        return Usuario(
            id=datos["sub"],
            nombre=datos.get("preferred_username", datos["sub"]),
            roles=frozenset(roles),
        )


def validador_desde_jwks(emisor: str, audiencia: str, url_jwks: str) -> ValidadorJWT:
    cliente = jwt.PyJWKClient(url_jwks)
    return ValidadorJWT(
        emisor, audiencia, lambda token: cliente.get_signing_key_from_jwt(token).key
    )


_esquema_bearer = HTTPBearer(auto_error=False)


def usuario_actual(
    request: Request,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_esquema_bearer)],
) -> Usuario:
    # Dependencia síncrona a propósito: PyJWKClient hace HTTP bloqueante y FastAPI
    # ejecuta las dependencias `def` en el threadpool.
    if credenciales is None:
        raise _no_autenticado("Se requiere iniciar sesión")
    validador: ValidadorJWT = request.app.state.validador
    return validador.validar(credenciales.credentials)


def requiere_rol(*roles: str) -> Callable[[Usuario], Usuario]:
    permitidos = frozenset(roles)

    def verificar(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> Usuario:
        if not usuario.roles & permitidos:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permiso para esta acción")
        return usuario

    return verificar
