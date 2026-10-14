import asyncio
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest
from negociacion import publicacion
from negociacion.modelos import Mensaje, Oferta, Outbox, SesionNegociacion
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _token(enlace: str) -> str:
    return enlace.split("#t=")[1]


async def _outbox(fabrica: Fabrica) -> list[Outbox]:
    async with fabrica() as bd:
        return list((await bd.scalars(select(Outbox).order_by(Outbox.ocurrido_en))).all())


async def test_publica_crea_sesiones_manda_correos_y_eventos(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    nueva_compra: Any,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    evento = await nueva_compra()
    respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["evento"]["estado"] == "abierto"
    assert [s["estado"] for s in cuerpo["evento"]["sesiones"]] == ["invitada", "invitada"]
    enlaces = cuerpo["enlaces"]
    assert [e["proveedor_nombre"] for e in enlaces] == [
        "Nube Norte S.A. de C.V.",
        "Datos del Sur S.A.",
    ]
    assert all(e["enlace"].startswith("http://localhost:8080/portal#t=") for e in enlaces)
    assert {e["correo_estado"] for e in enlaces} == {"enviado"}
    tokens = [_token(e["enlace"]) for e in enlaces]
    assert [m["To"] for m in buzon.enviados] == [
        "lucia@nubenorte.example",
        "ventas@datossur.example",
    ]
    assert buzon.enviados[0]["Subject"] == (
        f"Invitación a negociar: Licencias de CRM 2027 ({evento['folio']})"
    )
    assert enlaces[0]["enlace"] in buzon.enviados[0].get_content()
    async with fabrica() as bd:
        hashes = set((await bd.scalars(select(SesionNegociacion.token_hash))).all())
    assert hashes == {_hash(t) for t in tokens}  # la base solo guarda el hash
    eventos = await _outbox(fabrica)
    assert sorted(e.tipo for e in eventos) == [
        "negociacion.invitacion_enviada",
        "negociacion.invitacion_enviada",
        "negociacion.publicada",
    ]
    assert not any(t in json.dumps(e.payload) for e in eventos for t in tokens)
    publicada = next(e for e in eventos if e.tipo == "negociacion.publicada")
    assert publicada.payload == {
        "folio": evento["folio"],
        "titulo": "Licencias de CRM 2027",
        "tipo": "compra",
        "proveedores": 2,
        "actor": {"id": "comprador-1", "nombre": "comprador-1"},
    }
    invitacion = next(
        e
        for e in eventos
        if e.tipo == "negociacion.invitacion_enviada"
        and e.payload["proveedor"] == "Nube Norte S.A. de C.V."
    )
    assert invitacion.payload | {"actor": None} == {
        "folio": evento["folio"],
        "titulo": "Licencias de CRM 2027",
        "proveedor": "Nube Norte S.A. de C.V.",
        "destinatario": "lucia@nubenorte.example",
        "estado": "enviado",
        "error": None,
        "reenvio": False,
        "actor": None,
    }


async def test_no_publica_un_borrador_incompleto(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, buzon: Any
) -> None:
    evento = await nueva_compra(lineas=[{"codigo_servicio": "NUBE-VM-STD", "cantidad": "64"}])
    respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "evento_incompleto"
    assert {e["campo"] for e in respuesta.json()["errores"]} == {
        "lineas.0.ideal",
        "lineas.0.limite",
    }
    assert buzon.enviados == []


async def test_publicar_dos_veces_a_la_vez_crea_un_solo_juego_de_sesiones(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    nueva_compra: Any,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    evento = await nueva_compra()
    ruta = f"/eventos/{evento['id']}/publicar"
    primera, segunda = await asyncio.gather(
        cliente.post(ruta, headers=comprador), cliente.post(ruta, headers=comprador)
    )
    assert sorted([primera.status_code, segunda.status_code]) == [200, 409]
    assert len(buzon.enviados) == 2
    async with fabrica() as bd:
        assert await bd.scalar(select(func.count()).select_from(SesionNegociacion)) == 2


async def test_si_el_correo_falla_la_sesion_lo_dice_y_el_enlace_se_entrega(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    nueva_compra: Any,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    buzon.falla = True
    evento = await nueva_compra()
    respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert respuesta.status_code == 200
    assert {e["correo_estado"] for e in respuesta.json()["enlaces"]} == {"fallido"}
    sesiones = respuesta.json()["evento"]["sesiones"]
    assert {s["correo_error"] for s in sesiones} == {
        "No se pudo entregar el correo al servidor de correo."
    }
    invitaciones = [e for e in await _outbox(fabrica) if e.tipo.endswith("invitacion_enviada")]
    assert {e.payload["estado"] for e in invitaciones} == {"fallido"}


async def test_si_el_envio_falla_por_cualquier_motivo_la_publicacion_conserva_los_enlaces(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    nueva_compra: Any,
    buzon: Any,
    fabrica: Fabrica,
    caplog: pytest.LogCaptureFixture,
) -> None:
    buzon.falla, buzon.error = True, ValueError  # no es de red: igual no debe perder los enlaces
    evento = await nueva_compra()
    with caplog.at_level(logging.WARNING, logger="negociacion.publicacion"):
        respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["evento"]["estado"] == "abierto"
    assert {e["correo_estado"] for e in cuerpo["enlaces"]} == {"fallido"}
    assert {s["correo_error"] for s in cuerpo["evento"]["sesiones"]} == {
        "No se pudo entregar el correo al servidor de correo."
    }
    invitaciones = [e for e in await _outbox(fabrica) if e.tipo.endswith("invitacion_enviada")]
    assert [e.payload["estado"] for e in invitaciones] == ["fallido", "fallido"]
    # El log dice la clase del error, no su mensaje, y nunca el token.
    avisos = [r.getMessage() for r in caplog.records if r.name == "negociacion.publicacion"]
    assert len(avisos) == 2 and all("(ValueError)" in aviso for aviso in avisos)
    assert "sin servidor de correo" not in caplog.text
    assert not any(_token(e["enlace"]) in caplog.text for e in cuerpo["enlaces"])


async def test_cancelar_revoca_los_enlaces_y_cierra_las_sesiones(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, fabrica: Fabrica
) -> None:
    evento, _ = await publicar()
    ruta = f"/eventos/{evento['id']}/cancelar"
    respuesta = await cliente.post(ruta, json={"motivo": "Se pospuso la compra"}, headers=comprador)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["estado"], cuerpo["motivo_cancelacion"]) == ("cancelado", "Se pospuso la compra")
    assert {s["estado"] for s in cuerpo["sesiones"]} == {"sin_acuerdo"}
    async with fabrica() as bd:
        assert set((await bd.scalars(select(SesionNegociacion.token_hash))).all()) == {None}
        textos = (await bd.scalars(select(Mensaje.texto).where(Mensaje.autor == "sistema"))).all()
    assert list(textos) == ["La negociación se canceló. Gracias por su tiempo."] * 2
    cancelada = next(e for e in await _outbox(fabrica) if e.tipo == "negociacion.cancelada")
    assert cancelada.payload["motivo"] == "Se pospuso la compra"
    otra_vez = await cliente.post(ruta, json={"motivo": "Otra vez"}, headers=comprador)
    assert otra_vez.status_code == 409
    assert otra_vez.json()["codigo"] == "no_cancelable"


async def test_cancelar_un_borrador(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    respuesta = await cliente.post(
        f"/eventos/{evento['id']}/cancelar", json={"motivo": "Ya no se necesita"}, headers=comprador
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "cancelado"


async def test_reenviar_cambia_el_token_y_manda_otro_correo(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    _, enlaces = await publicar()
    sesion_id = enlaces[0]["sesion_id"]
    respuesta = await cliente.post(f"/sesiones/{sesion_id}/invitacion", headers=comprador)
    assert respuesta.status_code == 200, respuesta.text
    nuevo = _token(respuesta.json()["enlace"])
    assert nuevo != _token(enlaces[0]["enlace"])
    async with fabrica() as bd:
        sesion = await bd.get(SesionNegociacion, uuid.UUID(sesion_id))
    assert sesion is not None and sesion.token_hash == _hash(nuevo)
    assert len(buzon.enviados) == 3
    invitaciones = [e for e in await _outbox(fabrica) if e.tipo == "negociacion.invitacion_enviada"]
    assert len(invitaciones) == 3
    assert [e.payload["reenvio"] for e in invitaciones].count(True) == 1


async def test_no_reenvia_en_una_negociacion_cancelada(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    evento, enlaces = await publicar()
    await cliente.post(f"/eventos/{evento['id']}/cancelar", json={"motivo": "x"}, headers=comprador)
    respuesta = await cliente.post(
        f"/sesiones/{enlaces[0]['sesion_id']}/invitacion", headers=comprador
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "no_reenviable"


async def test_la_utilidad_de_la_sesion_es_la_de_la_ultima_oferta_del_proveedor(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    sesion_id = enlaces[0]["sesion_id"]
    async with fabrica() as bd, bd.begin():
        for autor, ronda, utilidad in (
            ("proveedor", 1, "0.5500"),
            ("agente", 1, "0.7000"),
            ("proveedor", 2, "0.4000"),  # la última es menor que una anterior: no es el máximo
        ):
            bd.add(
                Oferta(
                    sesion_id=uuid.UUID(sesion_id),
                    autor=autor,
                    ronda=ronda,
                    valores={},
                    utilidad=Decimal(utilidad),
                    valida=True,
                )
            )
            await bd.flush()  # una por una: la secuencia fija cuál fue la última
    respuesta = await cliente.get(f"/eventos/{evento['id']}", headers=comprador)
    utilidades = {s["id"]: s["utilidad"] for s in respuesta.json()["sesiones"]}
    assert utilidades.pop(sesion_id) == pytest.approx(0.40)
    assert list(utilidades.values()) == [None]


async def test_reenviar_deja_pendiente_y_sin_el_error_del_envio_anterior(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    nueva_compra: Any,
    buzon: Any,
    fabrica: Fabrica,
) -> None:
    buzon.falla = True
    evento = await nueva_compra()
    respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    sesion_id = uuid.UUID(respuesta.json()["enlaces"][0]["sesion_id"])
    async with fabrica() as bd, bd.begin():
        await publicacion.preparar_reenvio(bd, sesion_id, datetime(2026, 10, 13, tzinfo=UTC))
    async with fabrica() as bd:
        sesion = await bd.get(SesionNegociacion, sesion_id)
    assert sesion is not None
    assert (sesion.correo_estado, sesion.correo_error, sesion.correo_en) == (
        "pendiente",
        None,
        None,
    )
