import logging
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal as D
from email.message import EmailMessage
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from negociacion import avisos, correo
from negociacion.modelos import Bitacora, Outbox, SesionNegociacion
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]
Avisar = Callable[[], Awaitable[int]]
ADJUDICADA = "Su oferta fue adjudicada; el equipo de compras se pondrá en contacto"
OTRA_PROPUESTA = "La negociación se adjudicó a otra propuesta"
DESIERTA = "La negociación se declaró desierta"


def _linea(evento: dict[str, Any]) -> str:
    return str(evento["lineas"][0]["id"])


async def _acordar(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    ofertar: Any,
    enlace: dict[str, Any],
    linea: str,
    precio: str,
) -> None:
    """Deja la sesión en acuerdo tentativo: el comprador toma el control y acepta la oferta."""
    sesion = enlace["sesion_id"]
    await cliente.post(f"/sesiones/{sesion}/control", json={"accion": "tomar"}, headers=comprador)
    await ofertar(enlace, {linea: precio})
    aceptada = await cliente.post(
        f"/sesiones/{sesion}/respuestas",
        json={"tipo": "aceptar"},
        headers=comprador | {"Idempotency-Key": f"aceptar-{sesion}"},
    )
    assert aceptada.json()["estado"] == "acuerdo_tentativo", aceptada.text


async def _sin_acuerdo(
    cliente: httpx.AsyncClient, comprador: dict[str, str], enlace: dict[str, Any]
) -> None:
    """Cierra la sesión sin acuerdo: el comprador toma el control y la da por terminada."""
    sesion = enlace["sesion_id"]
    await cliente.post(f"/sesiones/{sesion}/control", json={"accion": "tomar"}, headers=comprador)
    cerrada = await cliente.post(
        f"/sesiones/{sesion}/respuestas",
        json={"tipo": "cerrar"},
        headers=comprador | {"Idempotency-Key": f"cerrar-{sesion}"},
    )
    assert cerrada.json()["estado"] == "sin_acuerdo", cerrada.text


async def _proponer(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    evento: dict[str, Any],
    enlace: dict[str, Any],
) -> httpx.Response:
    return await cliente.post(
        f"/eventos/{evento['id']}/adjudicacion",
        json={"sesion_id": enlace["sesion_id"]},
        headers=comprador,
    )


async def _publicados(fabrica: Fabrica, tipo: str) -> list[dict[str, Any]]:
    async with fabrica() as bd:
        consulta = select(Outbox).where(Outbox.tipo == tipo).order_by(Outbox.ocurrido_en)
        return [fila.payload for fila in await bd.scalars(consulta)]


async def _bitacora(fabrica: Fabrica, accion: str) -> list[Bitacora]:
    async with fabrica() as bd:
        return list(await bd.scalars(select(Bitacora).where(Bitacora.accion == accion)))


async def _sesiones(fabrica: Fabrica) -> list[SesionNegociacion]:
    async with fabrica() as bd:
        return list(await bd.scalars(select(SesionNegociacion)))


def _cuerpo(mensaje: EmailMessage) -> str:
    return str(mensaje.get_content())


def _enviado(evento: dict[str, Any], proveedor: str, destinatario: str, resultado: str) -> Any:
    """El payload de negociacion.resultado_enviado: el de invitacion_enviada, más el resultado."""
    return {
        "folio": evento["folio"],
        "titulo": evento["titulo"],
        "proveedor": proveedor,
        "destinatario": destinatario,
        "estado": "enviado",
        "error": None,
        "reenvio": False,
        "resultado": resultado,
        "actor": {"id": None, "nombre": "Sistema"},
    }


@pytest.fixture
def avisar(app: FastAPI, fabrica: Fabrica, buzon: Any, reloj: Any) -> Avisar:
    async def _avisar() -> int:
        return await avisos.enviar_pendientes(
            fabrica, buzon.enviar, app.state.config, reloj.momento
        )

    return _avisar


@pytest.fixture
async def adjudicado(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    buzon: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Un evento adjudicado al segundo proveedor (Datos del Sur, 30.00; el otro ofreció 31.00).

    El buzón queda vacío: sin las invitaciones, solo recibirá los avisos del resultado.
    """
    evento, enlaces = await publicar()
    buzon.enviados.clear()
    await _acordar(cliente, comprador, ofertar, enlaces[0], _linea(evento), "31.00")
    await _acordar(cliente, comprador, ofertar, enlaces[1], _linea(evento), "30.00")
    propuesta = await _proponer(cliente, comprador, evento, enlaces[1])
    assert propuesta.json()["vigente"]["estado"] == "directa", propuesta.text
    return evento, enlaces


async def test_cerrar_sin_acuerdos_deja_la_negociacion_desierta(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ids: dict[str, str],
    fabrica: Fabrica,
) -> None:
    evento, enlaces = await publicar(proveedores=[ids["nube_norte"]])
    await _sin_acuerdo(cliente, comprador, enlaces[0])

    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "desierto"
    assert detalle["motivo_desierta"] is None  # spec §4.7: solo la desierta manual lleva motivo
    assert await _publicados(fabrica, "negociacion.desierta") == [
        {
            "folio": evento["folio"],
            "titulo": evento["titulo"],
            "motivo": "sin_acuerdos",
            "actor": {"id": None, "nombre": "Sistema"},
        }
    ]
    [desierto] = await _bitacora(fabrica, "evento.desierto")
    assert (desierto.actor_tipo, desierto.detalle) == ("sistema", {"motivo": "sin_acuerdos"})
    assert str(desierto.evento_id) == evento["id"]
    assert await _bitacora(fabrica, "evento.en_evaluacion") == []


async def test_avisos_al_adjudicar(
    adjudicado: Any, avisar: Avisar, buzon: Any, reloj: Any, fabrica: Fabrica
) -> None:
    evento, _ = adjudicado

    assert await avisar() == 2

    por_destinatario = {m["To"]: _cuerpo(m) for m in buzon.enviados}
    assert set(por_destinatario) == {"lucia@nubenorte.example", "ventas@datossur.example"}
    assert ADJUDICADA in por_destinatario["ventas@datossur.example"]
    assert OTRA_PROPUESTA in por_destinatario["lucia@nubenorte.example"]
    for mensaje in buzon.enviados:
        assert mensaje["Subject"] == f"Resultado de la negociación {evento['folio']}"
        assert mensaje["From"] == "compras@plataforma.example"
    assert {s.resultado_avisado_en for s in await _sesiones(fabrica)} == {reloj.momento}
    enviados = await _publicados(fabrica, "negociacion.resultado_enviado")
    assert sorted(enviados, key=lambda p: p["proveedor"]) == [
        _enviado(evento, "Datos del Sur S.A.", "ventas@datossur.example", "adjudicada"),
        _enviado(evento, "Nube Norte S.A. de C.V.", "lucia@nubenorte.example", "no_elegida"),
    ]
    assert len(await _bitacora(fabrica, "resultado.enviado")) == 2

    assert await avisar() == 0  # ya se avisó a las dos
    assert len(buzon.enviados) == 2
    assert len(await _publicados(fabrica, "negociacion.resultado_enviado")) == 2


async def test_no_avisa_mientras_la_negociacion_no_se_resuelve(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    avisar: Avisar,
    buzon: Any,
) -> None:
    evento, enlaces = await publicar()
    buzon.enviados.clear()  # las invitaciones
    assert await avisar() == 0  # abierto
    await _acordar(cliente, comprador, ofertar, enlaces[0], _linea(evento), "31.00")
    await _acordar(cliente, comprador, ofertar, enlaces[1], _linea(evento), "30.00")
    assert await avisar() == 0  # en evaluación
    assert buzon.enviados == []


async def test_el_aviso_no_revela_ganador_ni_montos(
    adjudicado: Any, avisar: Avisar, buzon: Any
) -> None:
    evento, _ = adjudicado
    await avisar()

    for mensaje in buzon.enviados:
        texto = mensaje.as_string()
        ajeno = "Datos del Sur" if mensaje["To"].startswith("lucia") else "Nube Norte"
        assert ajeno not in texto
        assert "#t=" not in texto and "http" not in texto  # el correo no lleva enlace
        for monto in ("30.00", "31.00", "3000", "3,000", "3100", "60000", "60,000", "62000"):
            assert monto not in texto, monto
        assert evento["folio"] in texto and evento["titulo"] in _cuerpo(mensaje)


async def test_correo_caido_queda_fallido(
    adjudicado: Any,
    avisar: Avisar,
    buzon: Any,
    fabrica: Fabrica,
    caplog: pytest.LogCaptureFixture,
) -> None:
    buzon.falla = True
    with caplog.at_level(logging.WARNING, logger="negociacion.avisos"):
        assert await avisar() == 2

    assert buzon.enviados == []
    enviados = await _publicados(fabrica, "negociacion.resultado_enviado")
    assert {(p["estado"], p["error"]) for p in enviados} == {("fallido", correo.NO_ENTREGADO)}
    assert all(s.resultado_avisado_en is not None for s in await _sesiones(fabrica))
    # El log dice la clase del error, no su mensaje (repite direcciones).
    avisos_log = [r.getMessage() for r in caplog.records if r.name == "negociacion.avisos"]
    assert len(avisos_log) == 2 and all("(OSError)" in aviso for aviso in avisos_log)
    assert "sin servidor de correo" not in caplog.text

    buzon.falla = False
    assert await avisar() == 0  # como una invitación, no se reintenta
    assert buzon.enviados == []


async def test_un_correo_que_no_se_puede_armar_tambien_queda_fallido(
    adjudicado: Any,
    avisar: Avisar,
    fabrica: Fabrica,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def roto(**_: Any) -> EmailMessage:
        raise ValueError("encabezado inválido")

    monkeypatch.setattr(correo, "resultado", roto)
    assert await avisar() == 2
    enviados = await _publicados(fabrica, "negociacion.resultado_enviado")
    assert {p["estado"] for p in enviados} == {"fallido"}
    assert await avisar() == 0


async def test_una_sesion_sin_destinatario_se_marca_sin_correo_ni_evento(
    adjudicado: Any, avisar: Avisar, buzon: Any, fabrica: Fabrica
) -> None:
    _, enlaces = adjudicado
    async with fabrica() as bd:
        await bd.execute(
            update(SesionNegociacion)
            .where(SesionNegociacion.id == uuid.UUID(enlaces[0]["sesion_id"]))
            .values(destinatario="")
        )
        await bd.commit()

    assert await avisar() == 2

    assert [m["To"] for m in buzon.enviados] == ["ventas@datossur.example"]
    assert [
        p["resultado"] for p in await _publicados(fabrica, "negociacion.resultado_enviado")
    ] == ["adjudicada"]
    assert all(s.resultado_avisado_en is not None for s in await _sesiones(fabrica))
    assert await avisar() == 0


async def test_dos_trabajadores_no_envian_dos_veces(
    adjudicado: Any, avisar: Avisar, buzon: Any, fabrica: Fabrica
) -> None:
    async with fabrica() as retenedor, retenedor.begin():  # otro trabajador las tiene tomadas
        await retenedor.execute(select(SesionNegociacion).with_for_update())
        assert await avisar() == 0  # SKIP LOCKED: no espera ni envía
    assert buzon.enviados == []
    assert await avisar() == 2


async def test_avisos_de_una_negociacion_desierta(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    avisar: Avisar,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    _, enlaces = await publicar()
    buzon.enviados.clear()  # las invitaciones
    for enlace in enlaces:
        await _sin_acuerdo(cliente, comprador, enlace)

    assert await avisar() == 2

    assert [DESIERTA in _cuerpo(m) for m in buzon.enviados] == [True, True]
    enviados = await _publicados(fabrica, "negociacion.resultado_enviado")
    assert {p["resultado"] for p in enviados} == {"desierta"}
    assert await avisar() == 0


async def test_el_portal_muestra_el_resultado(
    cliente: httpx.AsyncClient, adjudicado: Any, portal: Any
) -> None:
    _, enlaces = adjudicado
    # El enlace sigue vigente: la fecha límite no ha llegado.
    resultados = [
        (await cliente.get("/portal/sesion", headers=portal(e))).json()["resultado"]
        for e in enlaces
    ]
    assert resultados == ["no_elegida", "adjudicada"]


async def test_el_portal_no_da_resultado_hasta_que_se_decide(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    externos: Any,
    portal: Any,
) -> None:
    async def resultados() -> list[str | None]:
        return [
            (await cliente.get("/portal/sesion", headers=portal(e))).json()["resultado"]
            for e in enlaces
        ]

    evento, enlaces = await publicar()
    assert await resultados() == [None, None]  # abierto
    await _acordar(cliente, comprador, ofertar, enlaces[0], _linea(evento), "31.00")
    await _acordar(cliente, comprador, ofertar, enlaces[1], _linea(evento), "30.00")
    assert await resultados() == [None, None]  # en evaluación
    externos.umbral = D("1000.00")
    propuesta = await _proponer(cliente, comprador, evento, enlaces[1])
    assert propuesta.json()["vigente"]["estado"] == "pendiente", propuesta.text
    assert await resultados() == [None, None]  # pendiente de aprobación
    aprobada = await cliente.post(
        f"/eventos/{evento['id']}/adjudicacion/aprobar",
        json={"adjudicacion_id": propuesta.json()["vigente"]["id"]},
        headers=aprobador,
    )
    assert aprobada.status_code == 200, aprobada.text
    assert await resultados() == ["no_elegida", "adjudicada"]


async def test_el_portal_muestra_la_desierta(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, portal: Any
) -> None:
    _, enlaces = await publicar()
    for enlace in enlaces:
        await _sin_acuerdo(cliente, comprador, enlace)
    for enlace in enlaces:
        vista = (await cliente.get("/portal/sesion", headers=portal(enlace))).json()
        assert vista["resultado"] == "desierta"
