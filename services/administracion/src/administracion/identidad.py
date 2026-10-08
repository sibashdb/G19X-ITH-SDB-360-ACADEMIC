"""Puerto de identidad: lo que el servicio necesita del proveedor de identidad (hoy Keycloak).

Migrar a Entra ID = escribir otra implementación de ProveedorIdentidad.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from comun.auth import ROLES_INTERNOS

ROLES_ASIGNABLES: tuple[str, ...] = ROLES_INTERNOS


@dataclass(frozen=True)
class UsuarioIdentidad:
    id: str
    usuario: str
    nombre: str
    apellidos: str
    correo: str
    activo: bool
    roles: frozenset[str]
    creado_en: datetime


@dataclass(frozen=True)
class DatosUsuarioNuevo:
    usuario: str
    nombre: str
    apellidos: str
    correo: str


@dataclass(frozen=True)
class EventoSesion:
    id: str
    tipo: str  # LOGIN, LOGIN_ERROR o LOGOUT
    fecha: datetime
    usuario_id: str | None
    usuario: str | None  # nombre de usuario (el intentado, en LOGIN_ERROR)
    ip: str | None
    error: str | None


class IdentidadNoDisponible(Exception):
    """El proveedor de identidad no respondió o respondió con un error inesperado."""


class UsuarioNoEncontrado(Exception):
    """No existe un usuario con ese id."""


class DatoDuplicado(Exception):
    """Ya existe otro usuario con el mismo nombre de usuario o correo."""

    def __init__(self, campo: Literal["usuario", "correo"]) -> None:
        super().__init__(campo)
        self.campo: Literal["usuario", "correo"] = campo


class CorreoNoEnviado(Exception):
    """El proveedor de identidad no pudo entregar el correo al servidor de correo."""


class ProveedorIdentidad(Protocol):
    async def listar_usuarios(self) -> list[UsuarioIdentidad]: ...

    async def obtener_usuario(self, usuario_id: str) -> UsuarioIdentidad: ...

    async def crear_usuario(self, datos: DatosUsuarioNuevo) -> str: ...

    async def actualizar_datos(
        self, usuario_id: str, nombre: str, apellidos: str, correo: str
    ) -> None: ...

    async def fijar_roles(self, usuario_id: str, roles: frozenset[str]) -> None: ...

    async def fijar_activo(self, usuario_id: str, activo: bool) -> None: ...

    async def enviar_correo_contrasena(self, usuario_id: str, vigencia_s: int) -> None: ...

    async def fijar_contrasena_temporal(self, usuario_id: str, contrasena: str) -> None: ...

    async def cerrar_sesiones(self, usuario_id: str) -> None: ...

    async def eventos_de_sesion(self, desde: datetime) -> list[EventoSesion]: ...
