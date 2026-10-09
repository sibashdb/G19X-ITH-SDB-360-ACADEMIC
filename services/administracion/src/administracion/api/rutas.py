"""API de gestión de usuarios y correos (solo administración)."""

import logging
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Literal

from comun.auth import Usuario, requiere_rol
from comun.errores import ErrorDominio
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from administracion.api import esquemas
from administracion.bitacora import Actor, Objeto, registrar, ultimos_accesos
from administracion.db import obtener_sesion
from administracion.identidad import (
    ROLES_ASIGNABLES,
    CorreoNoEnviado,
    DatoDuplicado,
    DatosUsuarioNuevo,
    IdentidadNoDisponible,
    ProveedorIdentidad,
    UsuarioIdentidad,
    UsuarioNoEncontrado,
)
from administracion.modelos import CorreoEnviado
from administracion.reglas import (
    ReglaProteccion,
    generar_contrasena_temporal,
    verificar_cambio_de_roles,
    verificar_desactivacion,
)

log = logging.getLogger(__name__)
router = APIRouter()

VIGENCIA_INVITACION_S = 72 * 3600
VIGENCIA_RESTABLECIMIENTO_S = 24 * 3600

Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]
Admin = Annotated[Usuario, Depends(requiere_rol("admin"))]


def _identidad(request: Request) -> ProveedorIdentidad:
    proveedor: ProveedorIdentidad = request.app.state.identidad
    return proveedor


Identidad = Annotated[ProveedorIdentidad, Depends(_identidad)]

MENSAJES_DUPLICADO = {
    "usuario": "Ya existe un usuario con ese nombre de usuario.",
    "correo": "Ya existe un usuario con ese correo.",
}


@contextmanager
def _traducir_errores() -> Iterator[None]:
    """Convierte los errores de identidad y de las reglas en respuestas para la persona."""
    try:
        yield
    except IdentidadNoDisponible as exc:
        log.warning("Servicio de identidad no disponible: %s", exc)
        raise ErrorDominio(
            503,
            "Servicio no disponible",
            "No se pudo conectar con el servicio de identidad. Intente de nuevo en unos minutos.",
            {"codigo": "identidad_no_disponible"},
        ) from exc
    except UsuarioNoEncontrado as exc:
        raise ErrorDominio(
            404, "No encontrado", "El usuario no existe.", {"codigo": "usuario_no_encontrado"}
        ) from exc
    except DatoDuplicado as exc:
        mensaje = MENSAJES_DUPLICADO[exc.campo]
        raise ErrorDominio(
            409,
            "Conflicto",
            mensaje,
            {
                "codigo": f"{exc.campo}_duplicado",
                "errores": [{"campo": exc.campo, "mensaje": mensaje}],
            },
        ) from exc
    except ReglaProteccion as exc:
        raise ErrorDominio(409, "Conflicto", str(exc), {"codigo": "regla_proteccion"}) from exc


def _sin_bitacora(exc: SQLAlchemyError) -> ErrorDominio:
    log.error("La acción se aplicó, pero no quedó en la bitácora", exc_info=exc)
    return ErrorDominio(
        500,
        "Error interno",
        "La acción se aplicó, pero no quedó en la bitácora.",
        {"codigo": "bitacora_no_registrada"},
    )


def _actor(usuario: Usuario, request: Request) -> Actor:
    return Actor(usuario.id, usuario.nombre, request.client.host if request.client else None)


def _nombre_completo(u: UsuarioIdentidad) -> str:
    return f"{u.nombre} {u.apellidos}".strip() or u.usuario


def _objeto(u: UsuarioIdentidad) -> Objeto:
    return Objeto("usuario", u.id, _nombre_completo(u))


def _roles_ordenados(roles: frozenset[str]) -> list[str]:
    return [r for r in ROLES_ASIGNABLES if r in roles]


def _salida(u: UsuarioIdentidad, ultimo_acceso: datetime | None) -> esquemas.UsuarioSalida:
    return esquemas.UsuarioSalida(
        id=u.id,
        usuario=u.usuario,
        nombre=u.nombre,
        apellidos=u.apellidos,
        correo=u.correo,
        roles=_roles_ordenados(u.roles),
        activo=u.activo,
        creado_en=u.creado_en,
        ultimo_acceso=ultimo_acceso,
    )


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para que "lopez" encuentre "López"."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


async def _enviar_correo(
    identidad: ProveedorIdentidad,
    sesion: AsyncSession,
    usuario: UsuarioIdentidad,
    tipo: Literal["invitacion", "restablecimiento"],
    actor: Actor,
) -> bool:
    """Pide el correo y deja su registro en la transacción; devuelve si salió."""
    vigencia = VIGENCIA_INVITACION_S if tipo == "invitacion" else VIGENCIA_RESTABLECIMIENTO_S
    error: str | None = None
    try:
        await identidad.enviar_correo_contrasena(usuario.id, vigencia)
    except CorreoNoEnviado:
        log.warning("No se pudo enviar el correo de %s a %s", tipo, usuario.id)
        error = "No se pudo entregar el correo al servidor de correo."
    sesion.add(
        CorreoEnviado(
            tipo=tipo,
            destinatario=usuario.correo,
            usuario_id=usuario.id,
            solicitado_por=actor.nombre,
            estado="fallido" if error else "enviado",
            error=error,
        )
    )
    return error is None


@router.get("/usuarios", tags=["usuarios"])
async def listar_usuarios(
    sesion: Sesion,
    identidad: Identidad,
    _: Admin,
    busqueda: Annotated[str | None, Query(max_length=100)] = None,
    rol: esquemas.Rol | None = None,
    estado: Literal["activos", "inactivos"] | None = None,
    pagina: Annotated[int, Query(ge=1, le=1000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
) -> esquemas.PaginaUsuarios:
    with _traducir_errores():
        usuarios = await identidad.listar_usuarios()
    texto = _normalizar((busqueda or "").strip())
    filtrados = sorted(
        (
            u
            for u in usuarios
            if (
                not texto
                or texto in _normalizar(f"{u.usuario} {u.nombre} {u.apellidos} {u.correo}")
            )
            and (rol is None or rol in u.roles)
            and (estado is None or u.activo == (estado == "activos"))
        ),
        key=lambda u: (_normalizar(u.nombre), _normalizar(u.apellidos), u.usuario),
    )
    visibles = filtrados[(pagina - 1) * tamano : pagina * tamano]
    accesos = await ultimos_accesos(sesion, [u.id for u in visibles])
    return esquemas.PaginaUsuarios(
        total=len(filtrados), elementos=[_salida(u, accesos.get(u.id)) for u in visibles]
    )


@router.post("/usuarios", status_code=201, tags=["usuarios"])
async def crear_usuario(
    datos: esquemas.UsuarioNuevo,
    request: Request,
    sesion: Sesion,
    identidad: Identidad,
    admin: Admin,
) -> esquemas.ResultadoAlta:
    actor = _actor(admin, request)
    temporal: str | None = None
    correo_enviado: bool | None = None
    with _traducir_errores():
        usuario_id = await identidad.crear_usuario(
            DatosUsuarioNuevo(datos.usuario, datos.nombre, datos.apellidos, datos.correo)
        )
        await identidad.fijar_roles(usuario_id, frozenset(datos.roles))
        nuevo = await identidad.obtener_usuario(usuario_id)
        if datos.metodo == "temporal":
            temporal = generar_contrasena_temporal()
            await identidad.fijar_contrasena_temporal(usuario_id, temporal)
        else:
            correo_enviado = await _enviar_correo(identidad, sesion, nuevo, "invitacion", actor)
    try:
        await registrar(
            sesion,
            "usuario.creado",
            actor,
            objeto=_objeto(nuevo),
            detalle={"roles": _roles_ordenados(nuevo.roles)},
        )
        if temporal is not None:
            await registrar(sesion, "usuario.contrasena_temporal", actor, objeto=_objeto(nuevo))
        else:
            await registrar(
                sesion,
                "usuario.correo_contrasena",
                actor,
                objeto=_objeto(nuevo),
                detalle={"tipo": "invitacion"},
                resultado="exito" if correo_enviado else "fallo",
            )
        await sesion.commit()
    except SQLAlchemyError as exc:
        raise _sin_bitacora(exc) from exc
    return esquemas.ResultadoAlta(
        usuario=_salida(nuevo, None), correo_enviado=correo_enviado, contrasena_temporal=temporal
    )


@router.get("/usuarios/{usuario_id}", tags=["usuarios"])
async def obtener_usuario(
    usuario_id: str, sesion: Sesion, identidad: Identidad, _: Admin
) -> esquemas.UsuarioSalida:
    with _traducir_errores():
        usuario = await identidad.obtener_usuario(usuario_id)
    accesos = await ultimos_accesos(sesion, [usuario.id])
    return _salida(usuario, accesos.get(usuario.id))


@router.patch("/usuarios/{usuario_id}", tags=["usuarios"])
async def editar_usuario(
    usuario_id: str,
    datos: esquemas.CambioUsuario,
    request: Request,
    sesion: Sesion,
    identidad: Identidad,
    admin: Admin,
) -> esquemas.UsuarioSalida:
    actor = _actor(admin, request)
    with _traducir_errores():
        objetivo = await identidad.obtener_usuario(usuario_id)
        nuevos = {"nombre": datos.nombre, "apellidos": datos.apellidos, "correo": datos.correo}
        campos = sorted(k for k, v in nuevos.items() if v is not None and v != getattr(objetivo, k))
        roles_nuevos = frozenset(datos.roles) if datos.roles is not None else objetivo.roles
        if roles_nuevos != objetivo.roles:
            verificar_cambio_de_roles(
                admin.id, objetivo, roles_nuevos, await identidad.listar_usuarios()
            )
        if campos:
            await identidad.actualizar_datos(
                usuario_id,
                datos.nombre or objetivo.nombre,
                datos.apellidos or objetivo.apellidos,
                datos.correo or objetivo.correo,
            )
        if roles_nuevos != objetivo.roles:
            await identidad.fijar_roles(usuario_id, roles_nuevos)
        actualizado = await identidad.obtener_usuario(usuario_id)
    try:
        if campos:
            await registrar(
                sesion,
                "usuario.actualizado",
                actor,
                objeto=_objeto(actualizado),
                detalle={"campos": campos},
            )
        if roles_nuevos != objetivo.roles:
            await registrar(
                sesion,
                "usuario.roles_cambiados",
                actor,
                objeto=_objeto(actualizado),
                detalle={
                    "antes": _roles_ordenados(objetivo.roles),
                    "despues": _roles_ordenados(roles_nuevos),
                },
            )
        await sesion.commit()
    except SQLAlchemyError as exc:
        raise _sin_bitacora(exc) from exc
    accesos = await ultimos_accesos(sesion, [usuario_id])
    return _salida(actualizado, accesos.get(usuario_id))


async def _cambiar_activo(
    usuario_id: str,
    activo: bool,
    request: Request,
    sesion: AsyncSession,
    identidad: ProveedorIdentidad,
    admin: Usuario,
) -> esquemas.UsuarioSalida:
    actor = _actor(admin, request)
    with _traducir_errores():
        objetivo = await identidad.obtener_usuario(usuario_id)
        if not activo:
            verificar_desactivacion(admin.id, objetivo, await identidad.listar_usuarios())
        cambia = objetivo.activo != activo
        if cambia:
            await identidad.fijar_activo(usuario_id, activo)
            if not activo:
                await identidad.cerrar_sesiones(usuario_id)  # que salga de inmediato
        actualizado = await identidad.obtener_usuario(usuario_id)
    if cambia:
        try:
            tipo = "usuario.activado" if activo else "usuario.desactivado"
            await registrar(sesion, tipo, actor, objeto=_objeto(actualizado))
            await sesion.commit()
        except SQLAlchemyError as exc:
            raise _sin_bitacora(exc) from exc
    accesos = await ultimos_accesos(sesion, [usuario_id])
    return _salida(actualizado, accesos.get(usuario_id))


@router.post("/usuarios/{usuario_id}/desactivar", tags=["usuarios"])
async def desactivar_usuario(
    usuario_id: str, request: Request, sesion: Sesion, identidad: Identidad, admin: Admin
) -> esquemas.UsuarioSalida:
    return await _cambiar_activo(usuario_id, False, request, sesion, identidad, admin)


@router.post("/usuarios/{usuario_id}/activar", tags=["usuarios"])
async def activar_usuario(
    usuario_id: str, request: Request, sesion: Sesion, identidad: Identidad, admin: Admin
) -> esquemas.UsuarioSalida:
    return await _cambiar_activo(usuario_id, True, request, sesion, identidad, admin)


@router.post("/usuarios/{usuario_id}/contrasena", tags=["usuarios"])
async def contrasena_usuario(
    usuario_id: str,
    datos: esquemas.MetodoContrasena,
    request: Request,
    sesion: Sesion,
    identidad: Identidad,
    admin: Admin,
) -> esquemas.ResultadoContrasena:
    actor = _actor(admin, request)
    temporal: str | None = None
    enviado = True
    tipo: Literal["invitacion", "restablecimiento"] = "invitacion"
    with _traducir_errores():
        objetivo = await identidad.obtener_usuario(usuario_id)
        if datos.metodo == "temporal":
            temporal = generar_contrasena_temporal()
            await identidad.fijar_contrasena_temporal(usuario_id, temporal)
        else:
            if not objetivo.correo:
                raise ErrorDominio(
                    409,
                    "Conflicto",
                    "El usuario no tiene correo; agregue uno o asígnele una contraseña temporal.",
                    {"codigo": "sin_correo"},
                )
            if await ultimos_accesos(sesion, [usuario_id]):
                tipo = "restablecimiento"
            enviado = await _enviar_correo(identidad, sesion, objetivo, tipo, actor)
    try:
        if temporal is not None:
            await registrar(sesion, "usuario.contrasena_temporal", actor, objeto=_objeto(objetivo))
        else:
            await registrar(
                sesion,
                "usuario.correo_contrasena",
                actor,
                objeto=_objeto(objetivo),
                detalle={"tipo": tipo},
                resultado="exito" if enviado else "fallo",
            )
        await sesion.commit()
    except SQLAlchemyError as exc:
        raise _sin_bitacora(exc) from exc
    if not enviado:
        raise ErrorDominio(
            503,
            "Servicio no disponible",
            "No se pudo enviar el correo. Intente de nuevo en unos minutos o asigne una "
            "contraseña temporal.",
            {"codigo": "correo_no_enviado"},
        )
    return esquemas.ResultadoContrasena(contrasena_temporal=temporal)


@router.post("/usuarios/{usuario_id}/cerrar-sesiones", status_code=204, tags=["usuarios"])
async def cerrar_sesiones(
    usuario_id: str, request: Request, sesion: Sesion, identidad: Identidad, admin: Admin
) -> Response:
    actor = _actor(admin, request)
    with _traducir_errores():
        objetivo = await identidad.obtener_usuario(usuario_id)
        await identidad.cerrar_sesiones(usuario_id)
    try:
        await registrar(sesion, "usuario.sesiones_cerradas", actor, objeto=_objeto(objetivo))
        await sesion.commit()
    except SQLAlchemyError as exc:
        raise _sin_bitacora(exc) from exc
    return Response(status_code=204)


@router.get("/correos", tags=["correos"])
async def listar_correos(
    request: Request,
    sesion: Sesion,
    _: Admin,
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
) -> esquemas.PaginaCorreos:
    total = await sesion.scalar(select(func.count()).select_from(CorreoEnviado)) or 0
    filas = await sesion.scalars(
        select(CorreoEnviado)
        .order_by(CorreoEnviado.fecha.desc(), CorreoEnviado.id)
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return esquemas.PaginaCorreos(
        total=total,
        elementos=[esquemas.CorreoSalida.model_validate(f) for f in filas],
        buzon_url=request.app.state.config.buzon_url or None,
    )
