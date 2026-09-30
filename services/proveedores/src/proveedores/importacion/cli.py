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


class ErrorCarga(ErrorImportacion):
    """`ErrorImportacion` que además indica qué archivo falló y qué ya se había importado.

    Cada archivo se confirma por separado: los anteriores al que falló ya están en la base.
    """

    def __init__(self, origen: ErrorImportacion, entidad: str, importadas: list[str]) -> None:
        super().__init__(origen.errores)
        self.entidad = entidad
        self.importadas = importadas

    def mensaje(self) -> str:
        previo = (
            f"Ya se importaron: {', '.join(self.importadas)}."
            if self.importadas
            else "No se había importado ningún archivo antes del error."
        )
        return f"Error en {self.entidad}.csv: {self.detalle.rstrip('.')}. {previo}"


async def cargar_carpeta(
    fabrica: async_sessionmaker[AsyncSession], carpeta: Path
) -> list[ResumenImportacion]:
    """Importa en ORDEN_CARGA; cada archivo en su propia transacción.

    Si un archivo trae errores lanza `ErrorCarga` (un `ErrorImportacion`).
    """
    resumenes: list[ResumenImportacion] = []
    for entidad in ORDEN_CARGA:
        contenido = (carpeta / f"{entidad}.csv").read_bytes()
        try:
            async with fabrica() as sesion, sesion.begin():
                resumenes.append(await importar(sesion, entidad, contenido))
        except ErrorImportacion as error:
            raise ErrorCarga(error, entidad, [r.entidad for r in resumenes]) from error
    return resumenes


async def _principal(carpeta: Path) -> int:
    faltantes = [f"{e}.csv" for e in ORDEN_CARGA if not (carpeta / f"{e}.csv").is_file()]
    if faltantes:
        print(f"Faltan archivos en {carpeta}: {', '.join(faltantes)}", file=sys.stderr)
        return 1
    motor = create_async_engine(Configuracion().database_url)
    try:
        resumenes = await cargar_carpeta(async_sessionmaker(motor, expire_on_commit=False), carpeta)
    except ErrorCarga as error:
        print(error.mensaje(), file=sys.stderr)
        for e in error.errores[:20]:
            print(f"  {error.entidad}.csv, fila {e.fila}, {e.campo}: {e.mensaje}", file=sys.stderr)
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
