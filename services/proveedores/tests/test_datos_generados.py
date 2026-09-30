from pathlib import Path

import pytest
from generador.modelo import generar
from generador.salida import escribir
from proveedores.importacion.aplicar import ORDEN_CARGA
from proveedores.importacion.cli import cargar_carpeta
from proveedores.modelos import Contrato, Outbox
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion


async def test_los_datos_generados_se_importan_sin_errores(
    fabrica: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    datos = generar(21, n_proveedores=8)
    escribir(datos, tmp_path)
    resumenes = await cargar_carpeta(fabrica, tmp_path)
    assert [r.entidad for r in resumenes] == list(ORDEN_CARGA)
    folios = len({fila["folio"] for fila in datos.contratos})
    async with fabrica() as sesion:
        contratos = await sesion.scalar(select(func.count()).select_from(Contrato))
        eventos = await sesion.scalar(
            select(func.count()).select_from(Outbox).where(Outbox.tipo == "contrato.registrado")
        )
    assert contratos == folios
    assert eventos == folios
