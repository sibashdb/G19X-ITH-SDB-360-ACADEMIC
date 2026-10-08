"""Proveedor de identidad en memoria para pruebas; permite simular caídas y fallas de correo."""

from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime

from administracion.identidad import (
    CorreoNoEnviado,
    DatoDuplicado,
    DatosUsuarioNuevo,
    EventoSesion,
    IdentidadNoDisponible,
    UsuarioIdentidad,
    UsuarioNoEncontrado,
)


class IdentidadFalsa:
    def __init__(self) -> None:
        self.usuarios: dict[str, UsuarioIdentidad] = {}
        self.temporales: dict[str, str] = {}
        self.correos: list[tuple[str, int]] = []
        self.sesiones_cerradas: list[str] = []
        self.eventos: list[EventoSesion] = []
        self.caida = False
        self.falla_correo = False

    def agregar(
        self,
        usuario: str,
        roles: Iterable[str] = (),
        *,
        activo: bool = True,
        nombre: str = "Nombre",
        apellidos: str = "Apellido",
        correo: str | None = None,
    ) -> UsuarioIdentidad:
        nuevo = UsuarioIdentidad(
            id=usuario,
            usuario=usuario,
            nombre=nombre,
            apellidos=apellidos,
            correo=correo or f"{usuario}@plataforma.example",
            activo=activo,
            roles=frozenset(roles),
            creado_en=datetime(2026, 10, 1, tzinfo=UTC),
        )
        self.usuarios[nuevo.id] = nuevo
        return nuevo

    def _disponible(self) -> None:
        if self.caida:
            raise IdentidadNoDisponible("Proveedor de identidad simulado caído")

    def _buscar(self, usuario_id: str) -> UsuarioIdentidad:
        self._disponible()
        try:
            return self.usuarios[usuario_id]
        except KeyError as exc:
            raise UsuarioNoEncontrado(usuario_id) from exc

    async def listar_usuarios(self) -> list[UsuarioIdentidad]:
        self._disponible()
        return list(self.usuarios.values())

    async def obtener_usuario(self, usuario_id: str) -> UsuarioIdentidad:
        return self._buscar(usuario_id)

    async def crear_usuario(self, datos: DatosUsuarioNuevo) -> str:
        self._disponible()
        if any(u.usuario == datos.usuario for u in self.usuarios.values()):
            raise DatoDuplicado("usuario")
        if any(u.correo == datos.correo for u in self.usuarios.values()):
            raise DatoDuplicado("correo")
        nuevo = UsuarioIdentidad(
            id=f"id-{datos.usuario}",
            usuario=datos.usuario,
            nombre=datos.nombre,
            apellidos=datos.apellidos,
            correo=datos.correo,
            activo=True,
            roles=frozenset(),
            creado_en=datetime.now(UTC),
        )
        self.usuarios[nuevo.id] = nuevo
        return nuevo.id

    async def actualizar_datos(
        self, usuario_id: str, nombre: str, apellidos: str, correo: str
    ) -> None:
        actual = self._buscar(usuario_id)
        if any(u.correo == correo and u.id != usuario_id for u in self.usuarios.values()):
            raise DatoDuplicado("correo")
        self.usuarios[usuario_id] = replace(
            actual, nombre=nombre, apellidos=apellidos, correo=correo
        )

    async def fijar_roles(self, usuario_id: str, roles: frozenset[str]) -> None:
        self.usuarios[usuario_id] = replace(self._buscar(usuario_id), roles=roles)

    async def fijar_activo(self, usuario_id: str, activo: bool) -> None:
        self.usuarios[usuario_id] = replace(self._buscar(usuario_id), activo=activo)

    async def enviar_correo_contrasena(self, usuario_id: str, vigencia_s: int) -> None:
        self._buscar(usuario_id)
        if self.falla_correo:
            raise CorreoNoEnviado("Servidor de correo simulado caído")
        self.correos.append((usuario_id, vigencia_s))

    async def fijar_contrasena_temporal(self, usuario_id: str, contrasena: str) -> None:
        self._buscar(usuario_id)
        self.temporales[usuario_id] = contrasena

    async def cerrar_sesiones(self, usuario_id: str) -> None:
        self._buscar(usuario_id)
        self.sesiones_cerradas.append(usuario_id)

    async def eventos_de_sesion(self, desde: datetime) -> list[EventoSesion]:
        self._disponible()
        return sorted((e for e in self.eventos if e.fecha >= desde), key=lambda e: e.fecha)
