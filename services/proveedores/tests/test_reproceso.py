from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from proveedores.modelos import Outbox, ServicioCatalogo, TipoCambio
from proveedores.reproceso import _principal, emitir_instantanea, republicar_todo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]


async def _outbox(fabrica: Fabrica) -> list[Outbox]:
    async with fabrica() as sesion:
        return list((await sesion.scalars(select(Outbox).order_by(Outbox.ocurrido_en))).all())


async def test_republicar_todo_marca_los_publicados_como_pendientes(fabrica: Fabrica) -> None:
    async with fabrica() as sesion, sesion.begin():
        for n, publicado in enumerate((True, True, False)):
            sesion.add(
                Outbox(
                    tipo="proveedor.actualizado",
                    payload={"n": n},
                    correlation_id="c",
                    publicado_en=datetime.now(UTC) if publicado else None,
                )
            )
    assert await republicar_todo(fabrica) == 2
    assert [f.publicado_en for f in await _outbox(fabrica)] == [None, None, None]


async def test_la_instantanea_emite_el_catalogo_y_el_tipo_de_cambio(fabrica: Fabrica) -> None:
    async with fabrica() as sesion, sesion.begin():
        sesion.add(
            ServicioCatalogo(
                codigo="SOP-MESA-TK",
                nombre="Mesa de ayuda - ticket",
                categoria="soporte",
                unidad="ticket",
                moneda="MXN",
                activo=False,
            )
        )
        sesion.add(TipoCambio(periodo=date(2026, 9, 1), usd_mxn=Decimal("18.2500")))
    assert await emitir_instantanea(fabrica) == (1, 1)
    eventos = {f.tipo: f.payload for f in await _outbox(fabrica)}
    servicio = eventos["servicio.actualizado"]
    assert (servicio["codigo"], servicio["activo"]) == ("SOP-MESA-TK", False)
    assert "cambio" not in servicio
    assert eventos["tipo_cambio.registrado"] == {"periodo": "2026-09-01", "usd_mxn": "18.2500"}


@pytest.mark.usefixtures("fabrica")
async def test_la_cli_exige_una_sola_opcion(capsys: pytest.CaptureFixture[str]) -> None:
    assert await _principal(["--instantanea"]) == 0
    assert capsys.readouterr().out.strip() == (
        "Se emitieron 0 copias de servicios y 0 tipos de cambio; el relay los publicará."
    )
    with pytest.raises(SystemExit):
        await _principal([])
    with pytest.raises(SystemExit):
        await _principal(["--todo", "--instantanea"])
