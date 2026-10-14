import uuid
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
from negociacion.modelos import Bitacora, Evento
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]
FECHA_LIMITE = "2026-10-20T15:00:00+00:00"


def _renovacion(ids: dict[str, str]) -> dict[str, Any]:
    return {
        "tipo": "renovacion",
        "titulo": "Renovación del CRM",
        "fecha_limite": FECHA_LIMITE,
        "proveedor_id": ids["nube_norte"],
        "contrato_id": ids["contrato"],
    }


async def test_crea_una_compra_con_los_valores_sugeridos(
    nueva_compra: Any, externos: Any, comprador: dict[str, str]
) -> None:
    evento = await nueva_compra(
        lineas=[
            {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "100"},
            {"codigo_servicio": "SAAS-CRM-BAS", "cantidad": "40"},
        ]
    )
    assert evento["folio"] == "NEG-2026-0001"
    assert (evento["estado"], evento["moneda"], evento["version"]) == ("borrador", "USD", 1)
    pro, bas = evento["lineas"]
    assert (D(pro["ideal"]), D(pro["limite"])) == (D("28.00"), D("31.50"))
    assert D(pro["referencia"]["p50"]) == D("31.5")
    assert (D(bas["ideal"]), D(bas["limite"])) == (D("12.00"), D("14.00"))
    assert [p["clave"] for p in evento["palancas"]] == [
        "precio",
        "plazo_meses",
        "plazo_pago_dias",
        "sla_disponibilidad",
        "tope_aumento_pct",
        "cuota_implementacion",
    ]
    precio = evento["palancas"][0]
    assert (precio["activa"], precio["peso"], precio["unidad"]) == (True, 100, "USD")
    assert not any(p["activa"] for p in evento["palancas"][1:])
    assert [i["nombre"] for i in evento["invitados"]] == [
        "Nube Norte S.A. de C.V.",
        "Datos del Sur S.A.",
    ]
    assert evento["errores"] == [] and evento["avisos"] == []
    # inteligencia recibió el token del comprador y el plazo del evento.
    primera = externos.peticiones[0]
    assert primera.headers["authorization"] == comprador["Authorization"]
    assert primera.url.path == "/precios/servicios/SAAS-CRM-PRO/referencia"
    assert (primera.url.params["cantidad"], primera.url.params["plazo"]) == ("100", "12")


async def test_una_linea_sin_referencia_queda_sin_sugerencia(nueva_compra: Any) -> None:
    evento = await nueva_compra(lineas=[{"codigo_servicio": "NUBE-VM-STD", "cantidad": "64"}])
    [linea] = evento["lineas"]
    assert linea["referencia"] is None
    assert (linea["ideal"], linea["limite"]) == (None, None)
    assert evento["moneda"] == "MXN"
    assert {e["campo"] for e in evento["errores"]} == {"lineas.0.ideal", "lineas.0.limite"}


async def test_crea_una_renovacion_desde_el_contrato_vigente(
    cliente: httpx.AsyncClient, comprador: dict[str, str], catalogo: None, ids: dict[str, str]
) -> None:
    respuesta = await cliente.post("/eventos", json=_renovacion(ids), headers=comprador)
    assert respuesta.status_code == 201, respuesta.text
    evento = respuesta.json()
    assert (evento["tipo"], evento["moneda"], evento["plazo_meses"]) == ("renovacion", "USD", 12)
    assert evento["contrato_origen_id"] == ids["contrato"]
    assert evento["proveedor_vigente_id"] == ids["nube_norte"]
    [linea] = evento["lineas"]
    assert D(linea["precio_vigente"]) == D(32)
    # ideal = min(P25 28, 32 * 0.95); límite = min(P50 31.50, 32 * 1.05).
    assert (D(linea["ideal"]), D(linea["limite"])) == (D("28.00"), D("31.50"))
    vigentes = {p["clave"]: p["vigente"] for p in evento["palancas"]}
    assert D(vigentes["plazo_pago_dias"]) == 30
    assert D(vigentes["tope_aumento_pct"]) == 5
    assert D(vigentes["plazo_meses"]) == 12
    assert [i["id"] for i in evento["invitados"]] == [ids["nube_norte"]]


async def test_una_renovacion_exige_un_contrato_vigente_del_proveedor(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    catalogo: None,
    ids: dict[str, str],
    externos: Any,
) -> None:
    contrato = externos.contratos[ids["nube_norte"]][0]
    externos.contratos[ids["nube_norte"]] = [contrato | {"fecha_fin": "2026-09-30"}]
    vencido = await cliente.post("/eventos", json=_renovacion(ids), headers=comprador)
    assert vencido.status_code == 422
    assert vencido.json()["codigo"] == "contrato_no_vigente"
    externos.contratos[ids["nube_norte"]] = []
    ajeno = await cliente.post("/eventos", json=_renovacion(ids), headers=comprador)
    assert ajeno.status_code == 422
    assert ajeno.json()["codigo"] == "contrato_inexistente"


@pytest.mark.parametrize("falla", ["caida", "error", "basura"])
async def test_si_inteligencia_falla_responde_503_sin_crear_nada(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    cuerpo_compra: Any,
    externos: Any,
    fabrica: Fabrica,
    falla: str,
) -> None:
    if falla == "caida":
        externos.caido = "intel"
    elif falla == "error":
        externos.estado_intel = 500
    else:
        externos.estado_intel, externos.cuerpo_intel = 200, b"<html>no es JSON</html>"
    respuesta = await cliente.post("/eventos", json=cuerpo_compra(), headers=comprador)
    assert respuesta.status_code == 503
    assert respuesta.json()["detail"] == (
        "No se pudo consultar la referencia de precios; intente de nuevo."
    )
    async with fabrica() as bd:
        assert await bd.scalar(select(func.count()).select_from(Evento)) == 0


async def test_valida_servicios_proveedores_y_moneda(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    cuerpo_compra: Any,
    ids: dict[str, str],
) -> None:
    sin_copia = "00000000-0000-4000-8000-000000000999"  # recién importado: aún no llega la copia
    casos = [
        (
            cuerpo_compra(lineas=[{"codigo_servicio": "NO-EXISTE", "cantidad": "1"}]),
            "lineas.0.codigo_servicio",
            "servicio_no_disponible",
        ),
        (
            cuerpo_compra(lineas=[{"codigo_servicio": "SOP-VIEJO", "cantidad": "1"}]),
            "lineas.0.codigo_servicio",
            "servicio_no_disponible",
        ),
        (
            cuerpo_compra(proveedores=[ids["nube_norte"], ids["inactivo"]]),
            "proveedores.1",
            "proveedor_no_disponible",
        ),
        (cuerpo_compra(proveedores=[sin_copia]), "proveedores.0", "proveedor_no_disponible"),
        (
            cuerpo_compra(
                lineas=[
                    {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "1"},
                    {"codigo_servicio": "NUBE-VM-STD", "cantidad": "1"},
                ]
            ),
            "lineas",
            "monedas_distintas",
        ),
    ]
    for cuerpo, campo, codigo in casos:
        respuesta = await cliente.post("/eventos", json=cuerpo, headers=comprador)
        assert respuesta.status_code == 422, respuesta.text
        assert respuesta.json()["codigo"] == codigo
        assert respuesta.json()["errores"][0]["campo"] == campo


async def test_la_fecha_limite_debe_traer_zona_horaria(
    cliente: httpx.AsyncClient, comprador: dict[str, str], cuerpo_compra: Any
) -> None:
    respuesta = await cliente.post(
        "/eventos", json=cuerpo_compra(fecha_limite="2026-10-20T18:00:00"), headers=comprador
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        {
            "campo": "body.fecha_limite",
            "mensaje": "Incluya la zona horaria, por ejemplo 2026-10-20T18:00:00-06:00",
        }
    ]


async def test_una_compra_necesita_lineas_y_proveedores_sin_repetir(
    cliente: httpx.AsyncClient, comprador: dict[str, str], cuerpo_compra: Any, ids: dict[str, str]
) -> None:
    sin_lineas = await cliente.post("/eventos", json=cuerpo_compra(lineas=[]), headers=comprador)
    assert sin_lineas.json()["errores"][0]["mensaje"] == "Una compra necesita al menos una línea."
    repetido = await cliente.post(
        "/eventos", json=cuerpo_compra(proveedores=[ids["nube_norte"]] * 2), headers=comprador
    )
    assert repetido.json()["errores"][0]["mensaje"] == "Un proveedor aparece dos veces."


async def test_los_folios_son_consecutivos(nueva_compra: Any) -> None:
    assert (await nueva_compra())["folio"] == "NEG-2026-0001"
    assert (await nueva_compra())["folio"] == "NEG-2026-0002"


async def test_el_aprobador_consulta_pero_no_crea(
    cliente: httpx.AsyncClient, aprobador: dict[str, str], cuerpo_compra: Any, nueva_compra: Any
) -> None:
    evento = await nueva_compra()
    creado = await cliente.post("/eventos", json=cuerpo_compra(), headers=aprobador)
    assert creado.status_code == 403
    respuesta = await cliente.get(f"/eventos/{evento['id']}", headers=aprobador)
    assert respuesta.status_code == 200
    assert respuesta.json()["folio"] == evento["folio"]


async def test_una_negociacion_inexistente_da_404(
    cliente: httpx.AsyncClient, comprador: dict[str, str]
) -> None:
    respuesta = await cliente.get(f"/eventos/{uuid.uuid4()}", headers=comprador)
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "La negociación no existe."


async def test_la_bitacora_registra_quien_creo_la_negociacion(
    nueva_compra: Any, fabrica: Fabrica
) -> None:
    evento = await nueva_compra()
    async with fabrica() as bd:
        fila = await bd.scalar(
            select(Bitacora).where(Bitacora.evento_id == uuid.UUID(evento["id"]))
        )
    assert fila is not None
    assert (fila.accion, fila.actor_tipo, fila.actor_id) == (
        "evento.creado",
        "comprador",
        "comprador-1",
    )
