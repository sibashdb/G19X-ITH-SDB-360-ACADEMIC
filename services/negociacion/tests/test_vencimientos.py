import asyncio
import contextlib
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from negociacion import vencimientos
from negociacion.modelos import Bitacora, Mensaje, SesionNegociacion
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]


async def _contar(fabrica: Fabrica, consulta: Any) -> int:
    async with fabrica() as bd:
        return int(await bd.scalar(consulta) or 0)


async def test_al_vencer_expira_lo_que_sigue_en_curso_y_el_evento_pasa_a_evaluacion(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    fabrica: Fabrica,
) -> None:
    evento, enlaces = await publicar()
    linea = str(evento["lineas"][0]["id"])
    propuesta = (await ofertar(enlaces[0], {linea: "40.00"})).json()["ultima_propuesta"]
    await ofertar(enlaces[0], propuesta["precios"], propuesta["palancas"])  # acuerdo
    momento = datetime.fromisoformat(evento["fecha_limite"]) + timedelta(seconds=1)
    assert await vencimientos.cerrar_vencidos(fabrica, momento) == 2  # una sesión y el evento
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "en_evaluacion"
    assert sorted(s["estado"] for s in detalle["sesiones"]) == ["acuerdo_tentativo", "expirada"]
    expiradas = select(func.count()).where(Mensaje.texto == vencimientos.textos.EXPIRADA)
    assert await _contar(fabrica, expiradas) == 1
    for accion in ("sesion.expirada", "evento.en_evaluacion"):
        assert await _contar(fabrica, select(func.count()).where(Bitacora.accion == accion)) == 1
    assert await vencimientos.cerrar_vencidos(fabrica, momento) == 0  # repetirla no cambia nada


async def test_antes_de_la_fecha_limite_no_cambia_nada(
    publicar: Any, fabrica: Fabrica, reloj: Any
) -> None:
    await publicar()
    assert await vencimientos.cerrar_vencidos(fabrica, reloj.momento + timedelta(days=1)) == 0


async def test_cierra_un_evento_cuyas_sesiones_ya_terminaron(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    fabrica: Fabrica,
    reloj: Any,
) -> None:
    evento, _ = await publicar()
    # Como si dos turnos simultáneos hubieran cerrado las dos últimas sesiones.
    async with fabrica() as bd:
        await bd.execute(update(SesionNegociacion).values(estado="sin_acuerdo"))
        await bd.commit()
    assert await vencimientos.cerrar_vencidos(fabrica, reloj.momento) == 1
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "en_evaluacion"


async def test_la_tarea_periodica_cierra_lo_vencido(
    publicar: Any, fabrica: Fabrica, monkeypatch: pytest.MonkeyPatch
) -> None:
    evento, _ = await publicar()
    vencido = datetime.fromisoformat(evento["fecha_limite"]) + timedelta(minutes=1)
    monkeypatch.setattr(vencimientos, "INTERVALO_S", 0.01)
    tarea = asyncio.create_task(vencimientos.ejecutar_periodicamente(fabrica, lambda: vencido))
    try:
        for _ in range(200):
            consulta = select(func.count()).where(SesionNegociacion.estado == "expirada")
            if await _contar(fabrica, consulta) == 2:
                break
            await asyncio.sleep(0.02)
        else:
            pytest.fail("La tarea no expiró las sesiones")
    finally:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
