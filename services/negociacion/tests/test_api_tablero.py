"""GET /tablero: las negociaciones por estado y el ahorro logrado (spec del Tablero, §3 y §4).

El catálogo de prueba cotiza SAAS-CRM-PRO en USD y el falso de inteligencia lo lleva a 20 MXN por
dólar. El falso cuenta precio por cantidad sin el plazo: las compras se publican a 1 mes para que
coincida con la regla real de costo total.
"""

from decimal import Decimal as D
from typing import Any

import httpx

ESTADOS = (
    "borrador",
    "abierto",
    "en_evaluacion",
    "pendiente_aprobacion",
    "adjudicado",
    "desierto",
    "cancelado",
)
UMBRAL_BAJO = D("1000.00")  # los acuerdos de prueba lo superan: quedan pendientes de aprobación


async def _tablero(cliente: httpx.AsyncClient, encabezados: dict[str, str]) -> dict[str, Any]:
    respuesta = await cliente.get("/tablero", headers=encabezados)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo: dict[str, Any] = respuesta.json()
    return cuerpo


async def test_sin_negociaciones_todo_vale_cero(
    cliente: httpx.AsyncClient, comprador: dict[str, str]
) -> None:
    tablero = await _tablero(cliente, comprador)

    assert tablero["por_estado"] == dict.fromkeys(ESTADOS, 0)
    assert tablero["ahorro"] == {
        "adjudicadas": 0,
        "primera_oferta_mxn": "0.00",
        "adjudicado_mxn": "0.00",
        "ahorro_mxn": "0.00",
        "ahorro_pct": None,
    }


async def test_cuenta_las_negociaciones_por_estado(
    cliente: httpx.AsyncClient, admin: dict[str, str], nueva_compra: Any, publicar: Any
) -> None:
    await nueva_compra()
    await publicar()

    tablero = await _tablero(cliente, admin)

    assert tablero["por_estado"] == dict.fromkeys(ESTADOS, 0) | {"borrador": 1, "abierto": 1}


async def test_el_ahorro_compara_la_primera_oferta_con_lo_adjudicado(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    acordar: Any,
    proponer: Any,
    ids: dict[str, str],
) -> None:
    # Un solo invitado: con su acuerdo, la negociación pasa a evaluación.
    evento, enlaces = await publicar(plazo_meses=1, proveedores=[ids["nube_norte"]])
    linea = str(evento["lineas"][0]["id"])
    # Sobre el límite (la referencia llega a 36.00 en el P75): el agente contraoferta.
    primera = await ofertar(enlaces[0], {linea: "40.00"})
    assert primera.status_code == 200, primera.text
    await acordar(enlaces[0], linea, "30.00")
    propuesta = await proponer(comprador, evento, enlaces[0])
    assert propuesta.json()["vigente"]["estado"] == "directa", propuesta.text

    tablero = await _tablero(cliente, aprobador)

    assert tablero["ahorro"] == {
        "adjudicadas": 1,
        "primera_oferta_mxn": "80000.00",  # 40.00 por 100 por 20 MXN/USD
        "adjudicado_mxn": "60000.00",
        "ahorro_mxn": "20000.00",
        "ahorro_pct": 25.0,
    }
    assert tablero["por_estado"]["adjudicado"] == 1


async def test_una_propuesta_rechazada_no_se_cuenta_dos_veces(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    externos: Any,
    publicar: Any,
    acordar: Any,
    proponer: Any,
) -> None:
    evento, enlaces = await publicar(plazo_meses=1)
    linea = str(evento["lineas"][0]["id"])
    await acordar(enlaces[0], linea, "31.00")
    await acordar(enlaces[1], linea, "30.00")
    externos.umbral = UMBRAL_BAJO
    ruta = f"/eventos/{evento['id']}/adjudicacion"

    primera = await proponer(comprador, evento, enlaces[1])
    rechazo = await cliente.post(
        f"{ruta}/rechazar",
        json={"adjudicacion_id": primera.json()["vigente"]["id"], "motivo": "No procede."},
        headers=aprobador,
    )
    assert rechazo.status_code == 200, rechazo.text
    segunda = await proponer(
        comprador, evento, enlaces[0], justificacion="Mejor soporte local para la operación."
    )
    aprobada = await cliente.post(
        f"{ruta}/aprobar",
        json={"adjudicacion_id": segunda.json()["vigente"]["id"]},
        headers=aprobador,
    )
    assert aprobada.status_code == 200, aprobada.text

    tablero = await _tablero(cliente, comprador)

    assert tablero["ahorro"] == {
        "adjudicadas": 1,
        "primera_oferta_mxn": "62000.00",  # su única oferta fue la aceptada: 31.00 por 100 por 20
        "adjudicado_mxn": "62000.00",
        "ahorro_mxn": "0.00",
        "ahorro_pct": 0.0,
    }
