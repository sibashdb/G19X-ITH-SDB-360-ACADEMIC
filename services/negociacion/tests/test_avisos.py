import logging
import re
import uuid
from collections import Counter
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
# Lo que identifica a cada proveedor: nombre, contacto, correo y dominio.
PROVEEDORES = {
    "lucia@nubenorte.example": (
        "Nube Norte",
        "Lucía Pérez",
        "lucia@nubenorte.example",
        "nubenorte.example",
    ),
    "ventas@datossur.example": (
        "Datos del Sur",
        "Marco Ruiz",
        "ventas@datossur.example",
        "datossur.example",
    ),
}


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
    evento_con_acuerdos: Any, proponer: Any, comprador: dict[str, str], buzon: Any
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Un evento adjudicado al segundo proveedor (Datos del Sur, 30.00; el otro ofreció 31.00).

    El buzón queda vacío: sin las invitaciones, solo recibirá los avisos del resultado.
    """
    evento, enlaces = await evento_con_acuerdos()
    buzon.enviados.clear()
    propuesta = await proponer(comprador, evento, enlaces[1])
    assert propuesta.json()["vigente"]["estado"] == "directa", propuesta.text
    return evento, enlaces


async def test_cerrar_sin_acuerdos_deja_la_negociacion_desierta(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    sin_acuerdo: Any,
    ids: dict[str, str],
    fabrica: Fabrica,
) -> None:
    evento, enlaces = await publicar(proveedores=[ids["nube_norte"]])
    await sin_acuerdo(enlaces[0])

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
    publicar: Any, evento_con_acuerdos: Any, avisar: Avisar, buzon: Any
) -> None:
    await publicar()  # abierto
    await evento_con_acuerdos()  # en evaluación
    buzon.enviados.clear()  # las invitaciones

    assert await avisar() == 0
    assert buzon.enviados == []


async def test_el_aviso_no_revela_ganador_ni_montos(
    adjudicado: Any, avisar: Avisar, buzon: Any
) -> None:
    evento, _ = adjudicado
    await avisar()

    assert len(buzon.enviados) == 2
    for mensaje in buzon.enviados:
        destinatario = str(mensaje["To"])
        cuerpo = _cuerpo(mensaje)  # ya decodificado: con los acentos y sin cortes de línea
        encabezados = "\n".join(f"{nombre}: {valor}" for nombre, valor in mensaje.items())
        visible = f"{encabezados}\n{cuerpo}"
        # Nada del otro proveedor: ni su nombre, ni su contacto, ni su correo ni su dominio.
        ajenos = [d for otro, datos in PROVEEDORES.items() if otro != destinatario for d in datos]
        assert len(ajenos) == 4
        for dato in ajenos:
            assert dato not in visible, dato
        assert f"Estimado(a) {PROVEEDORES[destinatario][1]}:" in cuerpo
        assert "#t=" not in visible and "http" not in visible  # el correo no lleva enlace
        for monto in ("30.00", "31.00", "3000", "3,000", "3100", "60000", "60,000", "62000"):
            assert monto not in visible, monto
        # Los únicos dígitos del cuerpo son los del folio y los del título.
        assert not re.search(
            r"\d", cuerpo.replace(evento["folio"], "").replace(evento["titulo"], "")
        )


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


async def test_un_fallo_al_confirmar_no_repite_los_avisos_ya_confirmados(
    adjudicado: Any,
    avisar: Avisar,
    buzon: Any,
    fabrica: Fabrica,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registrar = avisos.registrar
    llamadas: list[int] = []

    def falla_en_la_segunda(*args: Any, **kwargs: Any) -> Any:
        llamadas.append(1)
        if len(llamadas) == 2:
            raise RuntimeError("base caída")
        return registrar(*args, **kwargs)

    monkeypatch.setattr(avisos, "registrar", falla_en_la_segunda)
    with pytest.raises(RuntimeError, match="base caída"):
        await avisar()
    # Cada sesión confirma por su cuenta: la primera quedó avisada aunque la segunda falló.
    [confirmada] = [s for s in await _sesiones(fabrica) if s.resultado_avisado_en is not None]

    monkeypatch.setattr(avisos, "registrar", registrar)
    assert await avisar() == 1  # solo la que no se confirmó
    enviados = Counter(str(m["To"]) for m in buzon.enviados)
    assert enviados.pop(confirmada.destinatario) == 1  # no se repitió
    assert list(enviados.values()) == [2]  # la no confirmada sí: no se supo si salió


async def test_avisos_de_una_negociacion_desierta(
    publicar: Any,
    sin_acuerdo: Any,
    avisar: Avisar,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    _, enlaces = await publicar()
    buzon.enviados.clear()  # las invitaciones
    for enlace in enlaces:
        await sin_acuerdo(enlace)

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
    evento_con_acuerdos: Any,
    proponer: Any,
    externos: Any,
    portal: Any,
) -> None:
    async def resultados() -> list[str | None]:
        return [
            (await cliente.get("/portal/sesion", headers=portal(e))).json()["resultado"]
            for e in enlaces
        ]

    evento, enlaces = await evento_con_acuerdos()
    assert await resultados() == [None, None]  # en evaluación
    externos.umbral = D("1000.00")
    propuesta = await proponer(comprador, evento, enlaces[1])
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
    cliente: httpx.AsyncClient, publicar: Any, sin_acuerdo: Any, portal: Any
) -> None:
    _, enlaces = await publicar()
    for enlace in enlaces:
        await sin_acuerdo(enlace)
    for enlace in enlaces:
        vista = (await cliente.get("/portal/sesion", headers=portal(enlace))).json()
        assert vista["resultado"] == "desierta"
