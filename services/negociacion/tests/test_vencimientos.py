import asyncio
import contextlib
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from negociacion import vencimientos
from negociacion.config import Configuracion
from negociacion.modelos import Bitacora, Evento, Mensaje, Outbox, SesionNegociacion
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]


async def _contar(fabrica: Fabrica, consulta: Any) -> int:
    async with fabrica() as bd:
        return int(await bd.scalar(consulta) or 0)


async def _terminar_sesiones(fabrica: Fabrica, primera: str, segunda: str) -> None:
    """Deja las dos sesiones del evento en esos estados finales, sin pasar por un turno."""
    async with fabrica() as bd:
        ids = (await bd.scalars(select(SesionNegociacion.id).order_by(SesionNegociacion.id))).all()
        for sesion_id, estado in zip(ids, (primera, segunda), strict=True):
            await bd.execute(
                update(SesionNegociacion)
                .where(SesionNegociacion.id == sesion_id)
                .values(estado=estado)
            )
        await bd.commit()


async def _estado(
    cliente: httpx.AsyncClient, comprador: dict[str, str], evento: dict[str, Any]
) -> str:
    return str((await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()["estado"])


async def _desiertas(fabrica: Fabrica) -> list[dict[str, Any]]:
    async with fabrica() as bd:
        consulta = select(Outbox.payload).where(Outbox.tipo == "negociacion.desierta")
        return list((await bd.scalars(consulta)).all())


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


async def test_una_sesion_a_medio_turno_retiene_el_cierre_de_un_evento_vencido_sin_acuerdos(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    momento = datetime.fromisoformat(evento["fecha_limite"]) + timedelta(seconds=1)
    a_medio_turno = uuid.UUID(enlaces[1]["sesion_id"])
    async with fabrica() as turno, turno.begin():  # un turno que aún no confirma
        consulta = select(SesionNegociacion).where(SesionNegociacion.id == a_medio_turno)
        await turno.execute(consulta.with_for_update())
        assert await vencimientos.cerrar_vencidos(fabrica, momento) == 1  # solo la otra sesión
        assert await _estado(cliente, comprador, evento) == "abierto"  # podría terminar en acuerdo
        assert await _desiertas(fabrica) == []
    assert await vencimientos.cerrar_vencidos(fabrica, momento) == 2  # la sesión y el evento
    assert await _estado(cliente, comprador, evento) == "desierto"
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert {s["estado"] for s in detalle["sesiones"]} == {"expirada"}
    assert len(await _desiertas(fabrica)) == 1


async def test_vencido_con_un_acuerdo_pasa_a_evaluacion_aunque_otra_sesion_este_a_medio_turno(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    momento = datetime.fromisoformat(evento["fecha_limite"]) + timedelta(seconds=1)
    acordada, a_medio_turno = (uuid.UUID(e["sesion_id"]) for e in enlaces)
    async with fabrica() as bd:
        await bd.execute(
            update(SesionNegociacion)
            .where(SesionNegociacion.id == acordada)
            .values(estado="acuerdo_tentativo")
        )
        await bd.commit()
    async with fabrica() as turno, turno.begin():
        consulta = select(SesionNegociacion).where(SesionNegociacion.id == a_medio_turno)
        await turno.execute(consulta.with_for_update())
        assert await vencimientos.cerrar_vencidos(fabrica, momento) == 1  # solo el evento
    assert await _estado(cliente, comprador, evento) == "en_evaluacion"
    assert await _desiertas(fabrica) == []


@pytest.mark.parametrize("estado", ["pendiente_aprobacion", "adjudicado"])
async def test_la_sesion_saltada_se_expira_aunque_el_evento_ya_se_haya_propuesto_o_adjudicado(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    fabrica: Fabrica,
    estado: str,
) -> None:
    evento, enlaces = await publicar()
    momento = datetime.fromisoformat(evento["fecha_limite"]) + timedelta(seconds=1)
    acordada, a_medio_turno = (uuid.UUID(e["sesion_id"]) for e in enlaces)
    async with fabrica() as bd:
        await bd.execute(
            update(SesionNegociacion)
            .where(SesionNegociacion.id == acordada)
            .values(estado="acuerdo_tentativo")
        )
        await bd.commit()
    async with fabrica() as turno, turno.begin():
        consulta = select(SesionNegociacion).where(SesionNegociacion.id == a_medio_turno)
        await turno.execute(consulta.with_for_update())
        assert await vencimientos.cerrar_vencidos(fabrica, momento) == 1  # solo el evento
    # Antes de la siguiente vuelta el comprador propone o adjudica.
    async with fabrica() as bd:
        await bd.execute(
            update(Evento).where(Evento.id == uuid.UUID(evento["id"])).values(estado=estado)
        )
        await bd.commit()

    assert await vencimientos.cerrar_vencidos(fabrica, momento) == 1  # la sesión que se saltó

    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == estado  # solo expira sesiones: no toca el evento
    assert sorted(s["estado"] for s in detalle["sesiones"]) == ["acuerdo_tentativo", "expirada"]
    assert await vencimientos.cerrar_vencidos(fabrica, momento) == 0


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
    await _terminar_sesiones(fabrica, "acuerdo_tentativo", "sin_acuerdo")
    assert await vencimientos.cerrar_vencidos(fabrica, reloj.momento) == 1
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "en_evaluacion"


async def test_cierra_como_desierto_el_evento_cuyas_sesiones_terminaron_sin_acuerdo(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    fabrica: Fabrica,
    reloj: Any,
) -> None:
    evento, _ = await publicar()
    await _terminar_sesiones(fabrica, "sin_acuerdo", "expirada")
    assert await vencimientos.cerrar_vencidos(fabrica, reloj.momento) == 1
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "desierto"
    assert await vencimientos.cerrar_vencidos(fabrica, reloj.momento) == 0
    assert len(await _desiertas(fabrica)) == 1


async def test_al_vencer_sin_ningun_acuerdo_el_evento_queda_desierto(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, fabrica: Fabrica
) -> None:
    evento, _ = await publicar()
    momento = datetime.fromisoformat(evento["fecha_limite"]) + timedelta(seconds=1)
    assert await vencimientos.cerrar_vencidos(fabrica, momento) == 3  # dos sesiones y el evento
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "desierto"
    assert {s["estado"] for s in detalle["sesiones"]} == {"expirada"}
    [desierta] = await _desiertas(fabrica)
    assert (desierta["motivo"], desierta["actor"]["nombre"]) == ("sin_acuerdos", "Sistema")
    assert (
        await _contar(fabrica, select(func.count()).where(Bitacora.accion == "evento.desierto"))
        == 1
    )
    en_evaluacion = select(func.count()).where(Bitacora.accion == "evento.en_evaluacion")
    assert await _contar(fabrica, en_evaluacion) == 0
    assert await vencimientos.cerrar_vencidos(fabrica, momento) == 0
    assert len(await _desiertas(fabrica)) == 1  # repetirla no la publica otra vez


async def test_la_tarea_periodica_cierra_lo_vencido_y_avisa_el_resultado(
    publicar: Any, fabrica: Fabrica, buzon: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    evento, _ = await publicar()
    buzon.enviados.clear()  # las invitaciones
    vencido = datetime.fromisoformat(evento["fecha_limite"]) + timedelta(minutes=1)
    monkeypatch.setattr(vencimientos, "INTERVALO_S", 0.01)
    tarea = asyncio.create_task(
        vencimientos.ejecutar_periodicamente(
            fabrica, lambda: vencido, buzon.enviar, Configuracion()
        )
    )
    try:
        for _ in range(200):
            consulta = select(func.count()).where(SesionNegociacion.estado == "expirada")
            if await _contar(fabrica, consulta) == 2 and len(buzon.enviados) == 2:
                break
            await asyncio.sleep(0.02)
        else:
            pytest.fail("La tarea no expiró las sesiones ni avisó el resultado")
        await asyncio.sleep(0.1)  # unas vueltas más: no vuelve a avisar
        assert len(buzon.enviados) == 2
    finally:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
