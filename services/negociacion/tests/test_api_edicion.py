import uuid
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
from negociacion.modelos import Evento, SesionNegociacion
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]


async def _editar(
    cliente: httpx.AsyncClient, comprador: dict[str, str], evento: dict[str, Any], **cambios: Any
) -> httpx.Response:
    return await cliente.patch(f"/eventos/{evento['id']}", json=cambios, headers=comprador)


async def test_edita_el_borrador_y_sube_la_version(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    respuesta = await _editar(
        cliente, comprador, evento, version=1, titulo="CRM 2027", rondas_max=4, estilo="firme"
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["titulo"], cuerpo["rondas_max"], cuerpo["estilo"]) == ("CRM 2027", 4, "firme")
    assert cuerpo["version"] == 2


async def test_una_version_vieja_da_409(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    assert (await _editar(cliente, comprador, evento, version=1, titulo="A")).status_code == 200
    vieja = await _editar(cliente, comprador, evento, version=1, titulo="B")
    assert vieja.status_code == 409
    assert vieja.json()["codigo"] == "version_desactualizada"


async def test_solo_se_edita_un_borrador(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, fabrica: Fabrica
) -> None:
    evento = await nueva_compra()
    async with fabrica() as bd:
        await bd.execute(update(Evento).values(estado="abierto"))
        await bd.commit()
    respuesta = await _editar(cliente, comprador, evento, version=1, titulo="Otro")
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "no_editable"


async def test_reemplazar_lineas_solo_consulta_las_nuevas(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, externos: Any
) -> None:
    evento = await nueva_compra()
    antes = len(externos.peticiones)
    lineas = [
        {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "100", "ideal": "27.50", "limite": "31"},
        {"codigo_servicio": "SAAS-CRM-BAS", "cantidad": "40"},
    ]
    respuesta = await _editar(cliente, comprador, evento, version=1, lineas=lineas)
    assert respuesta.status_code == 200, respuesta.text
    pro, bas = respuesta.json()["lineas"]
    assert (D(pro["ideal"]), D(pro["limite"])) == (D("27.50"), D(31))
    assert D(pro["referencia"]["p50"]) == D("31.5")  # la foto de la línea que no cambió se queda
    assert (D(bas["ideal"]), D(bas["limite"])) == (D(12), D(14))  # sugeridos para la nueva
    assert [p.url.path for p in externos.peticiones[antes:]] == [
        "/precios/servicios/SAAS-CRM-BAS/referencia"
    ]


async def test_cambiar_el_plazo_vuelve_a_consultar_las_referencias(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, externos: Any
) -> None:
    evento = await nueva_compra()
    antes = len(externos.peticiones)
    respuesta = await _editar(cliente, comprador, evento, version=1, plazo_meses=24)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["plazo_meses"] == 24
    assert [p.url.params["plazo"] for p in externos.peticiones[antes:]] == ["24"]
    assert D(respuesta.json()["lineas"][0]["ideal"]) == D(28)  # lo que fijó el comprador se queda


async def test_las_lineas_no_mezclan_monedas(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    lineas = [
        {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "100"},
        {"codigo_servicio": "NUBE-VM-STD", "cantidad": "8"},
    ]
    respuesta = await _editar(cliente, comprador, evento, version=1, lineas=lineas)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "monedas_distintas"


async def test_activa_palancas_y_avisa_lo_que_falta(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    palancas = [
        {"clave": "precio", "peso": 70},
        {"clave": "plazo_pago_dias", "peso": 20, "ideal": "60", "limite": "30"},
    ]
    respuesta = await _editar(cliente, comprador, evento, version=1, palancas=palancas)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    activas = {p["clave"]: p for p in cuerpo["palancas"] if p["activa"]}
    assert set(activas) == {"precio", "plazo_pago_dias"}
    assert (activas["plazo_pago_dias"]["unidad"], D(activas["plazo_pago_dias"]["ideal"])) == (
        "días",
        D(60),
    )
    assert cuerpo["errores"] == [
        {"campo": "palancas", "mensaje": "Los pesos deben sumar 100; ahora suman 90."}
    ]


async def test_el_precio_siempre_es_una_palanca_activa(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    palancas = [{"clave": "plazo_meses", "peso": 100, "ideal": "12", "limite": "36"}]
    respuesta = await _editar(cliente, comprador, evento, version=1, palancas=palancas)
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"][0]["mensaje"] == "El precio siempre es una palanca activa."


async def test_en_renovacion_solo_cambian_el_ideal_y_el_limite(
    cliente: httpx.AsyncClient, comprador: dict[str, str], catalogo: None, ids: dict[str, str]
) -> None:
    creada = await cliente.post(
        "/eventos",
        json={
            "tipo": "renovacion",
            "titulo": "Renovación del CRM",
            "fecha_limite": "2026-10-20T15:00:00+00:00",
            "proveedor_id": ids["nube_norte"],
            "contrato_id": ids["contrato"],
        },
        headers=comprador,
    )
    evento = creada.json()
    misma = [{"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "120", "ideal": "29", "limite": "32"}]
    respuesta = await _editar(cliente, comprador, evento, version=1, lineas=misma)
    assert respuesta.status_code == 200, respuesta.text
    assert D(respuesta.json()["lineas"][0]["limite"]) == D(32)
    otra = [{"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "150", "ideal": "29", "limite": "32"}]
    for cambios in ({"lineas": otra}, {"plazo_meses": 24}, {"proveedores": [ids["datos_sur"]]}):
        rechazo = await _editar(cliente, comprador, evento, version=2, **cambios)
        assert rechazo.status_code == 422, cambios
        assert rechazo.json()["codigo"] == "no_editable"


async def test_lista_con_filtros_paginas_y_conteos(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    nueva_compra: Any,
    fabrica: Fabrica,
    ids: dict[str, str],
) -> None:
    await nueva_compra()
    segunda = await nueva_compra(titulo="Otra compra")
    evento_id = uuid.UUID(segunda["id"])
    async with fabrica() as bd:
        await bd.execute(update(Evento).where(Evento.id == evento_id).values(estado="abierto"))
        for proveedor, estado in (
            (ids["nube_norte"], "acuerdo_tentativo"),
            (ids["datos_sur"], "escalada"),
        ):
            bd.add(
                SesionNegociacion(
                    evento_id=evento_id,
                    proveedor_id=uuid.UUID(proveedor),
                    proveedor_nombre="Proveedor",
                    destinatario="ventas@proveedor.example",
                    estado=estado,
                )
            )
        await bd.commit()
    pagina = (await cliente.get("/eventos", headers=aprobador)).json()
    assert pagina["total"] == 2
    assert [e["folio"] for e in pagina["elementos"]] == ["NEG-2026-0002", "NEG-2026-0001"]
    primero = pagina["elementos"][0]
    assert (primero["sesiones"], primero["acuerdos"], primero["escaladas"]) == (2, 1, 1)
    assert primero["invitados"] == 2
    abiertos = (
        await cliente.get("/eventos", params={"estado": "abierto"}, headers=comprador)
    ).json()
    assert [e["folio"] for e in abiertos["elementos"]] == ["NEG-2026-0002"]
    otra_pagina = (
        await cliente.get("/eventos", params={"tamano": 1, "pagina": 2}, headers=comprador)
    ).json()
    assert [e["folio"] for e in otra_pagina["elementos"]] == ["NEG-2026-0001"]
