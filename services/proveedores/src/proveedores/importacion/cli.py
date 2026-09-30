"""Carga masiva de una carpeta con los CSV del ERP.

Uso (dentro del contenedor): python -m proveedores.importacion.cli /datos
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from proveedores.config import Configuracion
from proveedores.importacion.aplicar import (
    ORDEN_CARGA,
    ErrorImportacion,
    ResumenImportacion,
    importar,
)


async def cargar_carpeta(
    fabrica: async_sessionmaker[AsyncSession], carpeta: Path
) -> list[ResumenImportacion]:
    """Importa en ORDEN_CARGA; cada archivo en su propia transacción."""
    resumenes = []
    for entidad in ORDEN_CARGA:
        contenido = (carpeta / f"{entidad}.csv").read_bytes()
        async with fabrica() as sesion, sesion.begin():
            resumenes.append(await importar(sesion, entidad, contenido))
    return resumenes


async def _principal(carpeta: Path) -> int:
    faltantes = [f"{e}.csv" for e in ORDEN_CARGA if not (carpeta / f"{e}.csv").is_file()]
    if faltantes:
        print(f"Faltan archivos en {carpeta}: {', '.join(faltantes)}", file=sys.stderr)
        return 1
    motor = create_async_engine(Configuracion().database_url)
    try:
        resumenes = await cargar_carpeta(async_sessionmaker(motor, expire_on_commit=False), carpeta)
    except ErrorImportacion as error:
        print(error.detalle, file=sys.stderr)
        for e in error.errores[:20]:
            print(f"  fila {e.fila}, {e.campo}: {e.mensaje}", file=sys.stderr)
        return 1
    finally:
        await motor.dispose()
    for r in resumenes:
        print(f"{r.entidad}: {r.registros} registros, {r.omitidos} omitidos, {r.eventos} eventos")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python -m proveedores.importacion.cli <carpeta>")
    sys.exit(asyncio.run(_principal(Path(sys.argv[1]))))
