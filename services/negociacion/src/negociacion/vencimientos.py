"""Cierre por fecha límite (spec §8.4): una tarea del servicio que corre cada minuto.

También cierra los eventos cuyas sesiones ya terminaron y que ningún turno alcanzó a cerrar
(ver turnos.cerrar_eventos_terminados). Es idempotente: repetirla no cambia nada.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from negociacion import textos
from negociacion.bitacora import SISTEMA, registrar
from negociacion.modelos import FINALES, Evento, Mensaje, SesionNegociacion
from negociacion.turnos import cerrar_eventos_terminados

log = logging.getLogger(__name__)
INTERVALO_S: float = 60


async def cerrar_vencidos(fabrica: async_sessionmaker[AsyncSession], momento: datetime) -> int:
    """Expira las sesiones en curso de los eventos vencidos y cierra esos eventos."""
    async with fabrica() as bd, bd.begin():
        # skip_locked: una sesión en pleno turno se expira en la siguiente vuelta.
        vencidas = (
            await bd.scalars(
                select(SesionNegociacion)
                .join(Evento, Evento.id == SesionNegociacion.evento_id)
                .where(
                    Evento.fecha_limite <= momento,
                    Evento.estado.in_(("abierto", "en_evaluacion")),
                    SesionNegociacion.estado.not_in(FINALES),
                )
                .with_for_update(of=SesionNegociacion, skip_locked=True)
            )
        ).all()
        for sesion in vencidas:
            sesion.estado, sesion.actualizado_en = "expirada", momento
            bd.add(
                Mensaje(
                    sesion_id=sesion.id,
                    autor="sistema",
                    texto=textos.EXPIRADA,
                    ronda=sesion.ronda,
                    creado_en=momento,
                )
            )
            registrar(
                bd,
                "sesion.expirada",
                SISTEMA,
                evento_id=sesion.evento_id,
                sesion_id=sesion.id,
                fecha=momento,
            )
        await bd.flush()
        cerrados = await cerrar_eventos_terminados(bd, momento)
    return len(vencidas) + len(cerrados)


async def ejecutar_periodicamente(
    fabrica: async_sessionmaker[AsyncSession], reloj: Callable[[], datetime]
) -> None:
    while True:
        try:
            await cerrar_vencidos(fabrica, reloj())
        except Exception:
            log.exception("No se pudieron cerrar las negociaciones vencidas; se reintentará")
        await asyncio.sleep(INTERVALO_S)
