"""Rutas de la adjudicación: la evaluación de los acuerdos, su propuesta y su decisión."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from negociacion import adjudicacion
from negociacion.api import esquemas
from negociacion.api.dependencias import (
    Aprobador,
    Bd,
    Comprador,
    Integ,
    Lector,
    Reloj,
    TokenUsuario,
)

router = APIRouter(tags=["adjudicacion"])


@router.get("/eventos/{evento_id}/evaluacion")
async def ver_evaluacion(
    evento_id: uuid.UUID,
    _: Lector,
    token: TokenUsuario,
    bd: Bd,
    integraciones: Integ,
    pesos: Annotated[
        str | None,
        Query(description="Pesos de costo,desempeno,riesgo,sla: cuatro enteros que suman 100."),
    ] = None,
) -> esquemas.Evaluacion:
    return await adjudicacion.evaluacion(
        bd, integraciones, token, evento_id, adjudicacion.pesos_de(pesos)
    )


@router.post("/eventos/{evento_id}/adjudicacion")
async def proponer_adjudicacion(
    evento_id: uuid.UUID,
    datos: esquemas.Propuesta,
    usuario: Comprador,
    token: TokenUsuario,
    bd: Bd,
    integraciones: Integ,
    reloj: Reloj,
) -> esquemas.Evaluacion:
    return await adjudicacion.proponer(bd, integraciones, token, usuario, evento_id, datos, reloj())


@router.post("/eventos/{evento_id}/adjudicacion/aprobar")
async def aprobar_adjudicacion(
    evento_id: uuid.UUID, datos: esquemas.Aprobacion, usuario: Aprobador, bd: Bd, reloj: Reloj
) -> esquemas.Evaluacion:
    return await adjudicacion.aprobar(bd, usuario, evento_id, datos.adjudicacion_id, reloj())


@router.post("/eventos/{evento_id}/adjudicacion/rechazar")
async def rechazar_adjudicacion(
    evento_id: uuid.UUID, datos: esquemas.Rechazo, usuario: Aprobador, bd: Bd, reloj: Reloj
) -> esquemas.Evaluacion:
    return await adjudicacion.rechazar(
        bd, usuario, evento_id, datos.adjudicacion_id, datos.motivo, reloj()
    )


@router.post("/eventos/{evento_id}/desierta")
async def declarar_desierta(
    evento_id: uuid.UUID, datos: esquemas.Desierta, usuario: Comprador, bd: Bd, reloj: Reloj
) -> esquemas.Evaluacion:
    return await adjudicacion.declarar_desierta(bd, usuario, evento_id, datos.motivo, reloj())
