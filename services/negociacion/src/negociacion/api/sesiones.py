"""Rutas del comprador sobre una sesión (y, desde la Task 10, su supervisión)."""

import uuid

from fastapi import APIRouter

from negociacion import publicacion
from negociacion.api import esquemas
from negociacion.api.dependencias import Bd, Comprador, Config, Correo, Reloj
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
