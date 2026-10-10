import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from administracion.identidad import PREFIJO_CUENTA_SERVICIO

Rol = Literal["admin", "comprador", "aprobador"]


def _no_reservado(usuario: str) -> str:
    # Keycloak usa este prefijo en sus cuentas de servicio y el adaptador las oculta de la lista.
    if usuario.startswith(PREFIJO_CUENTA_SERVICIO):
        raise ValueError("Ese nombre de usuario está reservado.")
    return usuario


# Pydantic valida el patrón antes de pasar a minúsculas: se aceptan mayúsculas y se normalizan.
NombreUsuario = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{1,28}[A-Za-z0-9])$",
    ),
    AfterValidator(_no_reservado),
]
# Keycloak guarda el correo en minúsculas: se normaliza aquí para que guardar igual no cambie nada.
Correo = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]
# Los que rechaza el validador person-name-prohibited-characters de Keycloak en nombre y apellidos.
CARACTERES_PROHIBIDOS_EN_NOMBRE = frozenset('<>&"$%!#?§;*~/\\|^=[]{}()')


def _sin_caracteres_prohibidos(texto: str) -> str:
    prohibidos = dict.fromkeys(c for c in texto if c in CARACTERES_PROHIBIDOS_EN_NOMBRE)
    if prohibidos:
        raise ValueError(f"No use estos caracteres: {' '.join(prohibidos)}")
    return texto


Nombre = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(_sin_caracteres_prohibidos),
]


class UsuarioNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: NombreUsuario
    nombre: Nombre
    apellidos: Nombre
    correo: Correo
    roles: Annotated[list[Rol], Field(min_length=1)]
    metodo: Literal["invitacion", "temporal"]


class CambioUsuario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Nombre | None = None
    apellidos: Nombre | None = None
    correo: Correo | None = None
    roles: Annotated[list[Rol], Field(min_length=1)] | None = None


class MetodoContrasena(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metodo: Literal["correo", "temporal"]


class UsuarioSalida(BaseModel):
    id: str
    usuario: str
    nombre: str
    apellidos: str
    correo: str
    roles: list[str]
    activo: bool
    creado_en: datetime
    ultimo_acceso: datetime | None


class PaginaUsuarios(BaseModel):
    total: int
    elementos: list[UsuarioSalida]


class ResultadoAlta(BaseModel):
    usuario: UsuarioSalida
    correo_enviado: bool | None
    contrasena_temporal: str | None


class ResultadoContrasena(BaseModel):
    contrasena_temporal: str | None


class CorreoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: datetime
    tipo: str
    destinatario: str
    solicitado_por: str
    estado: str
    error: str | None


class PaginaCorreos(BaseModel):
    total: int
    elementos: list[CorreoSalida]
    buzon_url: str | None


class ActividadSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: datetime
    actor_id: str | None
    actor_nombre: str
    tipo: str
    objeto_tipo: str | None
    objeto_id: str | None
    objeto_nombre: str | None
    detalle: dict[str, Any]
    resultado: str
    ip: str | None


class PaginaActividad(BaseModel):
    total: int
    elementos: list[ActividadSalida]


class EstadoServicio(BaseModel):
    clave: str
    nombre: str
    estado: Literal["sano", "con_problemas", "caido"]
    tiempo_ms: int | None
    detalle: str


class EstadoSistema(BaseModel):
    version: str
    comprobado_en: datetime
    servicios: list[EstadoServicio]


class Resumen(BaseModel):
    usuarios_activos: int | None
    intentos_fallidos_24h: int
    correos_7d: int
