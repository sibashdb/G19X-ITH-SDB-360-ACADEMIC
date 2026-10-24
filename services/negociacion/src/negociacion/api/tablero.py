"""Tablero: las negociaciones por estado y el ahorro logrado (spec del Tablero, §3 y §4)."""

from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import func, select

from negociacion import adjudicacion, consultas, turnos
from negociacion.api import esquemas
from negociacion.api.dependencias import Bd, Lector
from negociacion.dominio.tablero import Adjudicada, ahorro
from negociacion.modelos import ESTADOS_EVENTO, Adjudicacion, Evento, SesionNegociacion

router = APIRouter(tags=["tablero"])


@router.get("/tablero")
async def tablero(_: Lector, bd: Bd) -> esquemas.TableroSalida:
    por_estado = await bd.execute(select(Evento.estado, func.count()).group_by(Evento.estado))
    conteos = {estado: cuantos for estado, cuantos in por_estado}
    # La adjudicación vigente de cada evento adjudicado; las rechazadas son historial.
    filas = await bd.execute(
        select(Evento, Adjudicacion, SesionNegociacion)
        .join(Adjudicacion, Adjudicacion.evento_id == Evento.id)
        .join(SesionNegociacion, SesionNegociacion.id == Adjudicacion.sesion_id)
        .where(Evento.estado == "adjudicado", Adjudicacion.estado.in_(("aprobada", "directa")))
    )
    adjudicadas = []
    # ponytail: una consulta por evento adjudicado, como en candidatos(); un JOIN si fueran cientos.
    for evento, fila, sesion in filas:
        primera = await turnos.primera_oferta_proveedor(bd, sesion.id)
        acordada = await turnos.ultima_oferta_proveedor(bd, sesion.id)
        if primera is None or acordada is None:
            raise RuntimeError("Una sesión adjudicada siempre tiene una oferta del proveedor")
        lineas = await consultas.lineas_de(bd, evento.id)
        candidato = adjudicacion.candidato_de(sesion, primera, lineas, evento)
        # Al plazo acordado: el ahorro son precios y cuota, no meses de más o de menos (spec D2).
        candidato["plazo_meses"] = adjudicacion.candidato_de(sesion, acordada, lineas, evento)[
            "plazo_meses"
        ]
        tasa = fila.costo_total_mxn / fila.costo_total if fila.costo_total else Decimal(1)
        adjudicadas.append(Adjudicada(adjudicacion.costo_de(candidato), fila.costo_total, tasa))
    resultado = ahorro(adjudicadas)
    return esquemas.TableroSalida(
        por_estado={estado: conteos.get(estado, 0) for estado in ESTADOS_EVENTO},
        ahorro=esquemas.AhorroSalida(
            adjudicadas=resultado.adjudicadas,
            primera_oferta_mxn=resultado.primera_oferta_mxn,
            adjudicado_mxn=resultado.adjudicado_mxn,
            ahorro_mxn=resultado.ahorro_mxn,
            ahorro_pct=resultado.ahorro_pct,
        ),
    )
