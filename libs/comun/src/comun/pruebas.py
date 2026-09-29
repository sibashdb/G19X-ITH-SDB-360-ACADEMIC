"""Claves RSA efímeras y tokens firmados para pruebas automatizadas."""

import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from comun.auth import ValidadorJWT


class ClavesPrueba:
    EMISOR = "http://prueba/realms/plataforma"
    AUDIENCIA = "plataforma-api"

    def __init__(self) -> None:
        self._privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def validador(self) -> ValidadorJWT:
        publica = self._privada.public_key()
        return ValidadorJWT(self.EMISOR, self.AUDIENCIA, lambda _token: publica)

    def token(self, *roles: str, sub: str = "usuario-prueba", **extra: Any) -> str:
        ahora = int(time.time())
        datos: dict[str, Any] = {
            "sub": sub,
            "preferred_username": sub,
            "iss": self.EMISOR,
            "aud": self.AUDIENCIA,
            "iat": ahora,
            "exp": ahora + 300,
            "realm_access": {"roles": list(roles)},
            **extra,
        }
        return jwt.encode(datos, self._privada, algorithm="RS256")
