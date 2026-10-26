"""Rutas del comprador sobre una sesión (y, desde la Task 10, su supervisión)."""

import uuid

from fastapi import APIRouter

from negociacion import consultas, publicacion, turnos
from negociacion.api import esquemas
from negociacion.api.dependencias import (
    IA,
    Bd,
    ClaveIdempotencia,
    Comprador,
    Config,
    Correo,
    Hasta,
    Lector,
    Reloj,
)
from negociacion.bitacora import de_usuario

router = APIRouter(tags=["sesiones"])


@router.post("/sesiones/{sesion_id}/invitacion")
async def reenviar_invitacion(
    sesion_id: uuid.UUID,
    usuario: Comprador,
    bd: Bd,
    reloj: Reloj,
    enviar: Correo,
    config: Config,
) -> esquemas.EnlaceSalida:
    momento, actor = reloj(), de_usuario(usuario)
    async with bd.begin():
        evento, invitacion = await publicacion.preparar_reenvio(bd, sesion_id, momento)
    [envio] = await publicacion.enviar_invitaciones(enviar, config, evento, [invitacion])
    async with bd.begin():
        await publicacion.registrar_envios(bd, evento, [envio], actor, momento, reenvio=True)
    return esquemas.EnlaceSalida(
        sesion_id=envio.sesion_id,
        proveedor_nombre=envio.proveedor_nombre,
        destinatario=envio.destinatario,
        enlace=envio.enlace,
        correo_estado=envio.estado,
    )


@router.get("/sesiones/{sesion_id}")
async def ver_sesion(sesion_id: uuid.UUID, _: Lector, bd: Bd) -> esquemas.SesionDetalle:
    return await consultas.sesion_detalle(bd, sesion_id)


@router.post("/sesiones/{sesion_id}/control")
async def cambiar_control(
    sesion_id: uuid.UUID,
    datos: esquemas.Control,
    usuario: Comprador,
    bd: Bd,
    reloj: Reloj,
    ia: IA,
    hasta: Hasta,
) -> esquemas.SesionDetalle:
    actor = de_usuario(usuario)
    async with bd.begin():
        if datos.accion == "tomar":
            await turnos.tomar_control(bd, sesion_id, actor, reloj())
        else:
            await turnos.devolver_control(bd, sesion_id, actor, reloj(), ia, hasta)
    return await consultas.sesion_detalle(bd, sesion_id)


@router.post("/sesiones/{sesion_id}/respuestas")
async def responder(
    sesion_id: uuid.UUID,
    datos: esquemas.Respuesta,
    clave: ClaveIdempotencia,
    usuario: Comprador,
    bd: Bd,
    reloj: Reloj,
) -> esquemas.SesionDetalle:
    async with bd.begin():
        await turnos.responder_a_mano(bd, sesion_id, datos, de_usuario(usuario), clave, reloj())
    return await consultas.sesion_detalle(bd, sesion_id)
