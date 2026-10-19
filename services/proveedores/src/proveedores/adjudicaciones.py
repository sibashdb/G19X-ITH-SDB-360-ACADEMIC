"""El contrato que nace de una adjudicación (spec §5): se registra como si se hubiera importado."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from comun.outbox import registrar_evento
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proveedores.importacion.aplicar import payload_contrato
from proveedores.modelos import Contrato, LineaContrato, Outbox, Proveedor, ServicioCatalogo


class _Linea(BaseModel):
    codigo_servicio: str
    cantidad: Decimal
    precio_unitario: Decimal


class _Terminos(BaseModel):
    """Los términos de §4.4 de la spec. Solo la forma: los límites los guardan las restricciones
    de la base, como con cualquier contrato."""

    folio: str
    tipo: str
    moneda: str
    fecha_inicio: date
    fecha_fin: date
    plazo_pago_dias: int
    sla_disponibilidad: Decimal | None
    tope_aumento_pct: Decimal | None
    cuota_implementacion: Decimal
    lineas: list[_Linea] = Field(min_length=1)


class _Adjudicada(BaseModel):
    """Lo que `proveedores` lee de negociacion.adjudicada; el resto del payload es para otros."""

    proveedor_id: uuid.UUID
    contrato: _Terminos


async def registrar_adjudicacion(bd: AsyncSession, payload: dict[str, Any]) -> bool:
    """Crea el contrato con sus líneas y publica contrato.registrado, como la importación.

    False si el folio ya existe. Un payload mal formado lanza `ValueError` (no se arregla
    reintentándolo); un proveedor o servicio desconocido lanza `KeyError` (puede importarse
    después). En ambos casos no queda nada guardado si la transacción se revierte.
    """
    adjudicada = _Adjudicada.model_validate(payload)
    terminos = adjudicada.contrato
    if await bd.scalar(select(Contrato.id).where(Contrato.folio == terminos.folio)) is not None:
        return False
    proveedor = await bd.get(Proveedor, adjudicada.proveedor_id)
    if proveedor is None:
        raise KeyError(f"Proveedor desconocido: {adjudicada.proveedor_id}")
    codigos = {linea.codigo_servicio for linea in terminos.lineas}
    servicios = {
        servicio.codigo: servicio
        for servicio in await bd.scalars(
            select(ServicioCatalogo).where(ServicioCatalogo.codigo.in_(codigos))
        )
    }
    if desconocidos := sorted(codigos - servicios.keys()):
        raise KeyError(f"Servicio desconocido: {', '.join(desconocidos)}")
    contrato = Contrato(
        id=uuid.uuid4(),
        proveedor_id=proveedor.id,
        **terminos.model_dump(exclude={"lineas"}),
        lineas=[
            LineaContrato(
                servicio_id=servicios[linea.codigo_servicio].id,
                cantidad=linea.cantidad,
                precio_unitario=linea.precio_unitario,
            )
            for linea in terminos.lineas
        ],
    )
    bd.add(contrato)
    registrar_evento(
        bd, Outbox, "contrato.registrado", payload_contrato(contrato, proveedor.rfc, servicios)
    )
    return True
