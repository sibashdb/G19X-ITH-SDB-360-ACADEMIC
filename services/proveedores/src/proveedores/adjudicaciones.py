"""El contrato que nace de una adjudicación (spec §5): se registra como si se hubiera importado."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from comun.outbox import registrar_evento
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proveedores.importacion.aplicar import payload_contrato
from proveedores.modelos import Contrato, LineaContrato, Outbox, Proveedor, ServicioCatalogo


class _Linea(BaseModel):
    codigo_servicio: str
    cantidad: Decimal
    precio_unitario: Decimal


class _Terminos(BaseModel):
    """Los términos de §4.4 de la spec. Las reglas que la base también guarda (tipo, moneda y
    vigencia) se revisan aquí para que un error vaya directo a la cola de fallidos en vez de
    reintentarse; los demás límites los guardan las restricciones de la base."""

    folio: str
    tipo: Literal["nuevo", "renovacion"]
    moneda: Literal["MXN", "USD"]
    fecha_inicio: date
    fecha_fin: date
    plazo_pago_dias: int
    sla_disponibilidad: Decimal | None
    tope_aumento_pct: Decimal | None
    cuota_implementacion: Decimal
    lineas: list[_Linea] = Field(min_length=1)

    @model_validator(mode="after")
    def validar_contrato(self) -> "_Terminos":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        codigos = [linea.codigo_servicio for linea in self.lineas]
        if len(set(codigos)) != len(codigos):
            raise ValueError("Servicio repetido en el contrato")
        return self


class _Adjudicada(BaseModel):
    """Lo que `proveedores` lee de negociacion.adjudicada; el resto del payload es para otros."""

    proveedor_id: uuid.UUID
    contrato: _Terminos


async def registrar_adjudicacion(bd: AsyncSession, payload: dict[str, Any]) -> bool:
    """Crea el contrato con sus líneas y publica contrato.registrado, como la importación.

    False si el folio ya existe. Un payload mal formado lanza `ValueError` (no se arregla
    reintentándolo, como una moneda distinta a la de un servicio); un proveedor o servicio
    desconocido lanza `KeyError` (puede importarse después). En ambos casos no queda nada
    guardado si la transacción se revierte.
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
    if distintos := sorted(
        c for c, servicio in servicios.items() if servicio.moneda != terminos.moneda
    ):
        raise ValueError(
            f"La moneda del contrato ({terminos.moneda}) no coincide con la del servicio: "
            + ", ".join(distintos)
        )
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
