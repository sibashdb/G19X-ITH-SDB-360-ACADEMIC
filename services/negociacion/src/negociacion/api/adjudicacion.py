"""Rutas de la adjudicación: la evaluación de los acuerdos (y, desde la Task 8, la decisión)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from negociacion import adjudicacion
from negociacion.api import esquemas
from negociacion.api.dependencias import Bd, Integ, Lector, TokenUsuario

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
