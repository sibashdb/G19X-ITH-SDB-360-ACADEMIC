"""Adaptador de identidad para la API de administración de Keycloak.

Usa la cuenta de servicio del cliente "administracion" (client credentials), con permisos de
realm-management limitados a view-users, manage-users y view-events.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from administracion.identidad import (
    PREFIJO_CUENTA_SERVICIO,
    ROLES_ASIGNABLES,
    CorreoNoEnviado,
    DatoDuplicado,
    DatosUsuarioNuevo,
    EventoSesion,
    IdentidadNoDisponible,
    UsuarioIdentidad,
    UsuarioNoEncontrado,
)

log = logging.getLogger(__name__)

TIEMPO_LIMITE_S = 5
# ponytail: la lista completa cabe en memoria (hasta 1,000 usuarios); paginar en Keycloak si crece.
MAX_USUARIOS = 1000
TAMANO_PAGINA_EVENTOS = 200
MAX_PAGINAS_EVENTOS = 50
TIPOS_EVENTO = ("LOGIN", "LOGIN_ERROR", "LOGOUT")
MARGEN_TOKEN_S = 30


class IdentidadKeycloak:
    def __init__(
        self,
        url: str,
        realm: str,
        cliente: str,
        secreto: str,
        url_app: str,
        transporte: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url_token = f"{url}/realms/{realm}/protocol/openid-connect/token"
        self._cliente = cliente
        self._secreto = secreto
        self._url_app = url_app
        self._http = httpx.AsyncClient(
            base_url=f"{url}/admin/realms/{realm}", timeout=TIEMPO_LIMITE_S, transport=transporte
        )
        self._token: str | None = None
        self._vence = 0.0

    async def cerrar(self) -> None:
        await self._http.aclose()

    async def _cabeceras(self) -> dict[str, str]:
        if self._token is None or time.monotonic() >= self._vence:
            try:
                respuesta = await self._http.post(
                    self._url_token,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._cliente,
                        "client_secret": self._secreto,
                    },
                )
            except httpx.HTTPError as exc:
                raise IdentidadNoDisponible("Sin conexión con Keycloak") from exc
            if respuesta.status_code != 200:
                raise IdentidadNoDisponible(
                    f"Keycloak rechazó la cuenta de servicio ({respuesta.status_code})"
                )
            datos = respuesta.json()
            self._token = str(datos["access_token"])
            self._vence = time.monotonic() + float(datos.get("expires_in", 60)) - MARGEN_TOKEN_S
        return {"Authorization": f"Bearer {self._token}"}

    async def _pedir(self, metodo: str, ruta: str, **opciones: Any) -> httpx.Response:
        """404 → UsuarioNoEncontrado; red caída o 5xx → IdentidadNoDisponible.

        Un 500 se tolera solo si la llamada lo pide (tolerar_500).
        """
        tolerar_500 = bool(opciones.pop("tolerar_500", False))
        for intento in range(2):
            try:
                respuesta = await self._http.request(
                    metodo, ruta, headers=await self._cabeceras(), **opciones
                )
            except httpx.HTTPError as exc:
                raise IdentidadNoDisponible("Sin conexión con Keycloak") from exc
            if respuesta.status_code == 401 and intento == 0:
                self._token = None  # token revocado o vencido antes de tiempo: se pide otro
                continue
            break
        if respuesta.status_code == 404:
            raise UsuarioNoEncontrado(ruta)
        if respuesta.status_code >= 500 and not (tolerar_500 and respuesta.status_code == 500):
            raise IdentidadNoDisponible(f"Keycloak respondió {respuesta.status_code}")
        return respuesta

    @staticmethod
    def _exigir_exito(respuesta: httpx.Response) -> None:
        if not respuesta.is_success:
            log.warning(
                "Respuesta inesperada de Keycloak: %s %s", respuesta.status_code, respuesta.url
            )
            raise IdentidadNoDisponible(f"Keycloak respondió {respuesta.status_code}")

    @staticmethod
    def _a_usuario(datos: dict[str, Any], roles: set[str]) -> UsuarioIdentidad:
        return UsuarioIdentidad(
            id=str(datos["id"]),
            usuario=str(datos["username"]),
            nombre=str(datos.get("firstName") or ""),
            apellidos=str(datos.get("lastName") or ""),
            correo=str(datos.get("email") or ""),
            activo=bool(datos.get("enabled", False)),
            roles=frozenset(roles),
            creado_en=datetime.fromtimestamp(int(datos.get("createdTimestamp", 0)) / 1000, UTC),
        )

    async def listar_usuarios(self) -> list[UsuarioIdentidad]:
        respuesta = await self._pedir(
            "GET",
            "/users",
            params={"first": 0, "max": MAX_USUARIOS, "briefRepresentation": "false"},
        )
        self._exigir_exito(respuesta)
        roles: dict[str, set[str]] = {}
        for rol in ROLES_ASIGNABLES:  # tres consultas por rol, no una por usuario
            miembros = await self._pedir(
                "GET", f"/roles/{rol}/users", params={"first": 0, "max": MAX_USUARIOS}
            )
            self._exigir_exito(miembros)
            for miembro in miembros.json():
                roles.setdefault(str(miembro["id"]), set()).add(rol)
        return [
            self._a_usuario(u, roles.get(str(u["id"]), set()))
            for u in respuesta.json()
            if not str(u["username"]).startswith(PREFIJO_CUENTA_SERVICIO)
        ]

    async def _roles_de(self, usuario_id: str) -> list[dict[str, Any]]:
        respuesta = await self._pedir("GET", f"/users/{usuario_id}/role-mappings/realm")
        self._exigir_exito(respuesta)
        return [r for r in respuesta.json() if r.get("name") in ROLES_ASIGNABLES]

    async def obtener_usuario(self, usuario_id: str) -> UsuarioIdentidad:
        respuesta = await self._pedir("GET", f"/users/{usuario_id}")
        self._exigir_exito(respuesta)
        roles = {str(r["name"]) for r in await self._roles_de(usuario_id)}
        return self._a_usuario(respuesta.json(), roles)

    @staticmethod
    def _duplicado(respuesta: httpx.Response) -> DatoDuplicado:
        mensaje = str((respuesta.json() or {}).get("errorMessage", "")).lower()
        return DatoDuplicado("correo" if "email" in mensaje else "usuario")

    async def crear_usuario(self, datos: DatosUsuarioNuevo) -> str:
        respuesta = await self._pedir(
            "POST",
            "/users",
            json={
                "username": datos.usuario,
                "email": datos.correo,
                "firstName": datos.nombre,
                "lastName": datos.apellidos,
                "enabled": True,
                "emailVerified": True,
            },
        )
        if respuesta.status_code == 409:
            raise self._duplicado(respuesta)
        self._exigir_exito(respuesta)
        return respuesta.headers["Location"].rstrip("/").rsplit("/", 1)[-1]

    async def actualizar_datos(
        self, usuario_id: str, nombre: str, apellidos: str, correo: str
    ) -> None:
        respuesta = await self._pedir(
            "PUT",
            f"/users/{usuario_id}",
            json={"firstName": nombre, "lastName": apellidos, "email": correo},
        )
        if respuesta.status_code == 409:
            raise self._duplicado(respuesta)
        self._exigir_exito(respuesta)

    async def fijar_roles(self, usuario_id: str, roles: frozenset[str]) -> None:
        actuales = await self._roles_de(usuario_id)
        nombres_actuales = {str(r["name"]) for r in actuales}
        quitar = [r for r in actuales if r["name"] not in roles]
        agregar: list[dict[str, Any]] = []
        for nombre in sorted(roles - nombres_actuales):
            rol = await self._pedir("GET", f"/roles/{nombre}")
            self._exigir_exito(rol)
            agregar.append(rol.json())
        if agregar:
            self._exigir_exito(
                await self._pedir("POST", f"/users/{usuario_id}/role-mappings/realm", json=agregar)
            )
        if quitar:
            self._exigir_exito(
                await self._pedir("DELETE", f"/users/{usuario_id}/role-mappings/realm", json=quitar)
            )

    async def fijar_activo(self, usuario_id: str, activo: bool) -> None:
        self._exigir_exito(
            await self._pedir("PUT", f"/users/{usuario_id}", json={"enabled": activo})
        )

    async def enviar_correo_contrasena(self, usuario_id: str, vigencia_s: int) -> None:
        respuesta = await self._pedir(
            "PUT",
            f"/users/{usuario_id}/execute-actions-email",
            params={"lifespan": vigencia_s, "client_id": "web", "redirect_uri": self._url_app},
            json=["UPDATE_PASSWORD"],
            tolerar_500=True,
        )
        if respuesta.status_code in (400, 500):  # sin correo o el SMTP no aceptó el mensaje
            log.warning("Keycloak no pudo enviar el correo: %s", respuesta.text[:200])
            raise CorreoNoEnviado(respuesta.text[:200])
        self._exigir_exito(respuesta)

    async def fijar_contrasena_temporal(self, usuario_id: str, contrasena: str) -> None:
        self._exigir_exito(
            await self._pedir(
                "PUT",
                f"/users/{usuario_id}/reset-password",
                json={"type": "password", "value": contrasena, "temporary": True},
            )
        )

    async def cerrar_sesiones(self, usuario_id: str) -> None:
        self._exigir_exito(await self._pedir("POST", f"/users/{usuario_id}/logout"))

    @staticmethod
    def _a_evento(datos: dict[str, Any]) -> EventoSesion:
        detalles = datos.get("details") or {}
        tiempo = int(datos["time"])
        # Keycloak 26 trae "id"; si faltara, la combinación tiempo-tipo-usuario-sesión lo sustituye.
        clave = datos.get("id") or (
            f"{tiempo}-{datos.get('type')}-{datos.get('userId')}-{datos.get('sessionId')}"
        )
        return EventoSesion(
            id=str(clave),
            tipo=str(datos["type"]),
            fecha=datetime.fromtimestamp(tiempo / 1000, UTC),
            usuario_id=datos.get("userId"),
            usuario=detalles.get("username"),
            ip=datos.get("ipAddress"),
            error=datos.get("error"),
        )

    async def eventos_de_sesion(self, desde: datetime) -> list[EventoSesion]:
        eventos: list[EventoSesion] = []
        for pagina in range(MAX_PAGINAS_EVENTOS):
            parametros = [
                *(("type", tipo) for tipo in TIPOS_EVENTO),
                ("dateFrom", desde.astimezone(UTC).date().isoformat()),
                ("first", str(pagina * TAMANO_PAGINA_EVENTOS)),
                ("max", str(TAMANO_PAGINA_EVENTOS)),
            ]
            respuesta = await self._pedir("GET", "/events", params=parametros)
            self._exigir_exito(respuesta)
            lote = respuesta.json()
            eventos += [self._a_evento(e) for e in lote]
            if len(lote) < TAMANO_PAGINA_EVENTOS:
                break
        return sorted((e for e in eventos if e.fecha >= desde), key=lambda e: e.fecha)
