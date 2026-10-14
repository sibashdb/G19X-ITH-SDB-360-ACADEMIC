from decimal import Decimal as D
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integracion


def _linea(evento: dict[str, Any]) -> str:
    return str(evento["lineas"][0]["id"])


async def _control(
    cliente: httpx.AsyncClient, comprador: dict[str, str], sesion: str, accion: str
) -> httpx.Response:
    return await cliente.post(
        f"/sesiones/{sesion}/control", json={"accion": accion}, headers=comprador
    )


async def _responder(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    sesion: str,
    clave: str = "respuesta-0001",
    **cuerpo: Any,
) -> httpx.Response:
    return await cliente.post(
        f"/sesiones/{sesion}/respuestas",
        json=cuerpo,
        headers=comprador | {"Idempotency-Key": clave},
    )


async def test_la_sesion_muestra_la_traza_de_cada_respuesta_del_agente(
    cliente: httpx.AsyncClient, aprobador: dict[str, str], publicar: Any, ofertar: Any
) -> None:
    evento, enlaces = await publicar()
    await ofertar(enlaces[0], {_linea(evento): "40.00"})
    respuesta = await cliente.get(f"/sesiones/{enlaces[0]['sesion_id']}", headers=aprobador)
    assert respuesta.status_code == 200, respuesta.text
    detalle = respuesta.json()
    assert [m["autor"] for m in detalle["mensajes"]] == ["proveedor", "agente"]
    assert detalle["mensajes"][0]["decision"] is None
    traza = detalle["mensajes"][1]["decision"]
    assert (traza["accion"], traza["t"], traza["T"]) == ("contraofertar", 1, 6)
    assert [o["autor"] for o in detalle["ofertas"]] == ["proveedor", "agente"]
    assert detalle["ofertas"][0]["valida"] is False  # 40.00 cruza el límite de 31.50
    assert D(detalle["lineas"][0]["limite"]) == D("31.50")


async def test_con_el_control_el_comprador_responde_y_el_agente_espera(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    portal: Any,
) -> None:
    evento, enlaces = await publicar()
    linea, sesion = _linea(evento), enlaces[0]["sesion_id"]
    tomada = await _control(cliente, comprador, sesion, "tomar")
    assert tomada.json()["modo"] == "comprador"
    vista = (await ofertar(enlaces[0], {linea: "33.00"})).json()
    assert vista["atendido_por"] == "persona"
    assert vista["mensajes"][-1]["autor"] == "sistema"
    respuesta = await _responder(
        cliente,
        comprador,
        sesion,
        tipo="mensaje",
        texto="¿Puede llegar a 30?",
        contraoferta={"precios": {linea: "30.00"}},
    )
    assert respuesta.status_code == 200, respuesta.text
    vista = (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).json()
    assert (vista["mensajes"][-1]["autor"], vista["mensajes"][-1]["texto"]) == (
        "comprador",
        "¿Puede llegar a 30?",
    )
    assert D(vista["ultima_propuesta"]["precios"][linea]) == D(30)


async def test_una_contraoferta_fuera_de_limites_exige_confirmacion_y_queda_marcada(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    evento, enlaces = await publicar()
    linea, sesion = _linea(evento), enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    cuerpo = {
        "tipo": "mensaje",
        "texto": "Última propuesta",
        "contraoferta": {"precios": {linea: "32.00"}},
    }
    sin_confirmar = await _responder(cliente, comprador, sesion, "respuesta-0001", **cuerpo)
    assert sin_confirmar.status_code == 422
    assert sin_confirmar.json()["codigo"] == "fuera_de_limites"
    confirmada = await _responder(
        cliente, comprador, sesion, "respuesta-0002", confirmar_fuera_de_limites=True, **cuerpo
    )
    assert confirmada.status_code == 200, confirmada.text
    detalle = confirmada.json()
    assert detalle["fuera_de_limites"] is True
    assert detalle["ofertas"][-1]["fuera_de_limites_confirmada"] is True


async def test_responder_sin_el_control_da_409(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    _, enlaces = await publicar()
    respuesta = await _responder(
        cliente, comprador, enlaces[0]["sesion_id"], tipo="mensaje", texto="Hola"
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "sin_control"


async def test_aceptar_la_ultima_oferta_cierra_la_sesion_y_el_evento(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    ids: dict[str, str],
) -> None:
    evento, enlaces = await publicar(proveedores=[ids["nube_norte"]])
    sesion = enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    await ofertar(enlaces[0], {_linea(evento): "31.00"})
    aceptada = await _responder(cliente, comprador, sesion, tipo="aceptar")
    assert aceptada.status_code == 200, aceptada.text
    assert aceptada.json()["estado"] == "acuerdo_tentativo"
    assert aceptada.json()["mensajes"][-1]["texto"].startswith(
        "Gracias. Su oferta quedó registrada"
    )
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "en_evaluacion"


async def test_cerrar_sin_acuerdo(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    _, enlaces = await publicar()
    sesion = enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    cerrada = await _responder(cliente, comprador, sesion, tipo="cerrar")
    assert cerrada.json()["estado"] == "sin_acuerdo"
    assert cerrada.json()["mensajes"][-1]["texto"] == (
        "Gracias por su tiempo. En esta ocasión no fue posible llegar a un acuerdo."
    )


async def test_al_devolver_el_control_el_agente_responde_sin_retroceder(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, ofertar: Any
) -> None:
    evento, enlaces = await publicar()
    linea, sesion = _linea(evento), enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    await _responder(
        cliente,
        comprador,
        sesion,
        tipo="mensaje",
        texto="Le propongo 29",
        contraoferta={"precios": {linea: "29.00"}},
    )
    await ofertar(enlaces[0], {linea: "40.00"})  # queda pendiente: atiende una persona
    devuelta = await _control(cliente, comprador, sesion, "devolver")
    assert devuelta.status_code == 200, devuelta.text
    detalle = devuelta.json()
    assert detalle["modo"] == "agente"
    agente = [o for o in detalle["ofertas"] if o["autor"] == "agente"]
    assert len(agente) == 1
    # El comprador ya había ofrecido 29: el agente no vuelve a pedir menos.
    assert D(agente[0]["valores"]["precios"][linea]) >= D("29.00")


async def test_pedir_a_una_persona_no_deja_sin_respuesta_la_oferta_pendiente(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    portal: Any,
) -> None:
    evento, enlaces = await publicar()
    linea, sesion = _linea(evento), enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    await ofertar(enlaces[0], {linea: "40.00"})
    await cliente.post("/portal/escalar", headers=portal(enlaces[0]))  # tras su oferta
    detalle = (await _control(cliente, comprador, sesion, "devolver")).json()
    # El «pidió hablar con una persona» no es una respuesta: el agente contesta la oferta.
    assert [o["autor"] for o in detalle["ofertas"]] == ["proveedor", "agente"]


async def test_devolver_una_sesion_escalada_la_reactiva(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, portal: Any
) -> None:
    _, enlaces = await publicar()
    await cliente.post("/portal/escalar", headers=portal(enlaces[0]))
    devuelta = await _control(cliente, comprador, enlaces[0]["sesion_id"], "devolver")
    assert (devuelta.json()["estado"], devuelta.json()["modo"]) == ("activa", "agente")


async def test_la_misma_clave_de_respuesta_no_se_aplica_dos_veces(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any
) -> None:
    _, enlaces = await publicar()
    sesion = enlaces[0]["sesion_id"]
    await _control(cliente, comprador, sesion, "tomar")
    for _ in range(2):
        respuesta = await _responder(
            cliente, comprador, sesion, "misma-clave-01", tipo="mensaje", texto="Hola"
        )
    assert [m["autor"] for m in respuesta.json()["mensajes"]] == ["comprador"]
