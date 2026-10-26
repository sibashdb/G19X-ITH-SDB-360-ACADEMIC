"""API del portal del proveedor (spec §8): autentica con el token de invitación, no con un JWT."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select

from negociacion import consultas, turnos
from negociacion.api import esquemas
from negociacion.api.dependencias import IA, Bd, ClaveIdempotencia, Hasta, Reloj
from negociacion.modelos import Evento, SesionNegociacion
from negociacion.tokens import hash_de

router = APIRouter(prefix="/portal", tags=["portal"])


def _sin_acceso() -> HTTPException:
    # Siempre la misma respuesta: no distingue un token falso, uno revocado y uno vencido.
    return HTTPException(
        401, "El enlace no es válido o ya venció.", headers={"WWW-Authenticate": "Invitacion"}
    )


async def _sesion_del_enlace(
    bd: Bd, reloj: Reloj, authorization: Annotated[str | None, Header()] = None
) -> uuid.UUID:
    esquema, _, token = (authorization or "").partition(" ")
    if esquema.lower() != "invitacion" or not token.strip():
        raise _sin_acceso()
    async with bd.begin():
        fila = (
            await bd.execute(
                select(SesionNegociacion.id, Evento.estado, Evento.fecha_limite)
                .join(Evento, Evento.id == SesionNegociacion.evento_id)
                .where(SesionNegociacion.token_hash == hash_de(token.strip()))
            )
        ).first()
    if fila is None:
        raise _sin_acceso()
    sesion_id, estado, fecha_limite = fila
    if estado == "cancelado" or reloj() >= fecha_limite:
        raise _sin_acceso()
    return sesion_id


SesionDelEnlace = Annotated[uuid.UUID, Depends(_sesion_del_enlace)]


@router.get("/sesion")
async def ver_sesion(sesion_id: SesionDelEnlace, bd: Bd) -> esquemas.VistaPortal:
    return await consultas.vista_portal(bd, sesion_id)


@router.post("/ofertas")
async def ofertar(
    datos: esquemas.OfertaPortal,
    sesion_id: SesionDelEnlace,
    clave: ClaveIdempotencia,
    bd: Bd,
    reloj: Reloj,
    ia: IA,
    hasta: Hasta,
) -> esquemas.VistaPortal:
    async with bd.begin():
        await turnos.recibir_oferta(bd, sesion_id, datos, clave, reloj(), ia, hasta)
    return await consultas.vista_portal(bd, sesion_id)


@router.post("/mensajes")
async def escribir(
    datos: esquemas.MensajeEntrada,
    sesion_id: SesionDelEnlace,
    clave: ClaveIdempotencia,
    bd: Bd,
    reloj: Reloj,
    ia: IA,
    hasta: Hasta,
) -> esquemas.VistaPortal:
    """El proveedor le escribe al agente; lo interpretado vuelve como sugerencia, no como oferta."""
    async with bd.begin():
        sugerencia = await turnos.recibir_mensaje(bd, sesion_id, datos, clave, reloj(), ia, hasta)
    vista = await consultas.vista_portal(bd, sesion_id)
    if sugerencia is not None:
        vista.sugerencia = consultas.valores_salida(sugerencia)
    return vista


@router.post("/escalar")
async def escalar(
    sesion_id: SesionDelEnlace, clave: ClaveIdempotencia, bd: Bd, reloj: Reloj
) -> esquemas.VistaPortal:
    async with bd.begin():
        await turnos.escalar(bd, sesion_id, clave, reloj())
    return await consultas.vista_portal(bd, sesion_id)
