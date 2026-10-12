"""Vuelve a publicar eventos para (re)construir las copias de los otros servicios.

Uso (dentro del contenedor de proveedores, con el servicio corriendo: su relay los publica):
  python -m proveedores.reproceso --todo         # todos los eventos del outbox, otra vez
  python -m proveedores.reproceso --instantanea  # el catálogo y el tipo de cambio actuales

Los consumidores ignoran los eventos repetidos, así que repetirlo es seguro.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from comun.outbox import registrar_evento
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from proveedores.config import Configuracion
from proveedores.importacion.aplicar import copia_servicio, copia_tipo_cambio
from proveedores.modelos import Outbox, ServicioCatalogo, TipoCambio


async def republicar_todo(fabrica: async_sessionmaker[AsyncSession]) -> int:
    async with fabrica() as sesion, sesion.begin():
        resultado = await sesion.execute(
            update(Outbox).where(Outbox.publicado_en.is_not(None)).values(publicado_en=None)
        )
    return int(resultado.rowcount)  # type: ignore[attr-defined]


async def emitir_instantanea(fabrica: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    async with fabrica() as sesion, sesion.begin():
        servicios = (await sesion.scalars(select(ServicioCatalogo))).all()
        for servicio in servicios:
            registrar_evento(sesion, Outbox, "servicio.actualizado", copia_servicio(servicio))
        tipos = (await sesion.scalars(select(TipoCambio))).all()
        for tipo in tipos:
            registrar_evento(
                sesion,
                Outbox,
                "tipo_cambio.registrado",
                copia_tipo_cambio(tipo.periodo, tipo.usd_mxn),
            )
    return len(servicios), len(tipos)


async def _principal(argumentos: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m proveedores.reproceso")
    opcion = parser.add_mutually_exclusive_group(required=True)
    opcion.add_argument("--todo", action="store_true", help="vuelve a publicar todo el outbox")
    opcion.add_argument(
        "--instantanea",
        action="store_true",
        help="publica el catálogo y el tipo de cambio actuales",
    )
    elegido = parser.parse_args(argumentos)
    motor = create_async_engine(
        Configuracion().database_url, pool_pre_ping=True, hide_parameters=True
    )
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    try:
        if elegido.todo:
            marcados = await republicar_todo(fabrica)
            print(f"Se marcaron {marcados} eventos para volver a publicarse.")
        else:
            servicios, tipos = await emitir_instantanea(fabrica)
            print(
                f"Se emitieron {servicios} copias de servicios y {tipos} tipos de cambio; "
                "el relay los publicará."
            )
    finally:
        await motor.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_principal(sys.argv[1:])))
