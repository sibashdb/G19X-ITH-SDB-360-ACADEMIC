"""Eventos de otros servicios que `proveedores` aplica: la adjudicación (spec §5).

Cada evento se aplica en una transacción que también registra su event_id, así que uno repetido no
se aplica dos veces.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from comun.consumidor import Atender
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from proveedores.adjudicaciones import registrar_adjudicacion
from proveedores.modelos import EventoProcesado

log = logging.getLogger(__name__)

APLICADORES: dict[str, Callable[[AsyncSession, dict[str, Any]], Awaitable[bool]]] = {
    "negociacion.adjudicada": registrar_adjudicacion,
}


async def aplicar(bd: AsyncSession, sobre: dict[str, Any]) -> bool:
    """Aplica el evento en la transacción en curso; False si no cambió nada: ese event_id ya se
    había aplicado o, en una adjudicación, el folio ya tenía su contrato."""
    tipo = str(sobre["type"])
    nuevo = await bd.scalar(
        insert(EventoProcesado)
        .values(event_id=str(sobre["event_id"]), tipo=tipo)
        .on_conflict_do_nothing(index_elements=[EventoProcesado.event_id])
        .returning(EventoProcesado.event_id)
    )
    aplicador = APLICADORES.get(tipo)
    if nuevo is None or aplicador is None:
        return False
    if await aplicador(bd, sobre["payload"]):
        return True
    # Ya validado por el aplicador; solo el folio llega al registro, nunca los términos.
    log.warning(
        "Adjudicación descartada: el folio %s ya tiene contrato (evento %s)",
        sobre["payload"]["contrato"]["folio"],
        sobre["event_id"],
    )
    return False


def atendedor(fabrica: async_sessionmaker[AsyncSession]) -> Atender:
    """La función que el consumidor común llama con cada sobre de evento.

    Un `ValueError` (payload mal formado) va directo a la cola de fallidos; un `KeyError`
    (proveedor o servicio desconocido) se reintenta, y tras 5 entregas va a la cola de fallidos.
    """

    async def atender(sobre: dict[str, Any]) -> None:
        async with fabrica() as bd, bd.begin():
            await aplicar(bd, sobre)

    return atender
