import asyncio
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
from negociacion.modelos import Bitacora, Oferta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]
SIN_ACCESO = "El enlace no es válido o ya venció."


def _linea(evento: dict[str, Any]) -> str:
    return str(evento["lineas"][0]["id"])


async def test_sin_un_enlace_valido_responde_siempre_lo_mismo(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, portal: Any, reloj: Any
) -> None:
    evento, enlaces = await publicar()
    respuestas = [
        await cliente.get("/portal/sesion"),
        await cliente.get("/portal/sesion", headers={"Authorization": "Invitacion inventado"}),
        await cliente.get("/portal/sesion", headers=comprador),  # un JWT no sirve en el portal
    ]
    reloj.momento = datetime.fromisoformat(evento["fecha_limite"])
    respuestas.append(await cliente.get("/portal/sesion", headers=portal(enlaces[0])))
    for respuesta in respuestas:
        assert respuesta.status_code == 401
        assert respuesta.json()["detail"] == SIN_ACCESO


async def test_un_enlace_reemplazado_o_cancelado_deja_de_servir(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, portal: Any
) -> None:
    evento, enlaces = await publicar()
    await cliente.post(f"/sesiones/{enlaces[0]['sesion_id']}/invitacion", headers=comprador)
    assert (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).status_code == 401
    await cliente.post(
        f"/eventos/{evento['id']}/cancelar", json={"motivo": "Se pospuso"}, headers=comprador
    )
    assert (await cliente.get("/portal/sesion", headers=portal(enlaces[1]))).status_code == 401


async def test_la_vista_muestra_lo_negociable_sin_los_limites(
    cliente: httpx.AsyncClient, publicar: Any, portal: Any
) -> None:
    evento, enlaces = await publicar()
    vista = (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).json()
    assert (vista["folio"], vista["estado"], vista["rondas_restantes"]) == (
        evento["folio"],
        "invitada",
        6,
    )
    assert (vista["atendido_por"], vista["pide_confirmacion"]) == ("agente", False)
    assert [linea["nombre"] for linea in vista["lineas"]] == ["CRM profesional"]
    assert vista["palancas"] == [] and vista["mensajes"] == []
    assert vista["ultima_propuesta"] is None
    texto = json.dumps(vista)
    for prohibido in ('"ideal"', '"limite"', '"peso"', '"utilidad"', '"referencia"', "28.00"):
        assert prohibido not in texto, prohibido


async def test_una_oferta_cara_recibe_una_contraoferta(
    publicar: Any, ofertar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    respuesta = await ofertar(enlaces[0], {linea: "40.00"}, nota="Es nuestro precio de lista")
    assert respuesta.status_code == 200, respuesta.text
    vista = respuesta.json()
    assert (vista["estado"], vista["rondas_restantes"]) == ("activa", 5)
    assert [(m["autor"], m["ronda"]) for m in vista["mensajes"]] == [
        ("proveedor", 1),
        ("agente", 1),
    ]
    assert vista["mensajes"][0]["texto"] == "Es nuestro precio de lista"
    assert vista["mensajes"][1]["texto"].startswith("Gracias por su oferta.")
    propuesta = D(vista["ultima_propuesta"]["precios"][linea])
    assert D("28.00") < propuesta < D("31.50")
    async with fabrica() as bd:
        decision = await bd.scalar(select(Bitacora).where(Bitacora.accion == "motor.decision"))
    assert decision is not None
    assert decision.detalle["accion"] == "contraofertar"
    assert decision.detalle["mensaje_id"]


async def test_aceptar_la_propuesta_deja_un_acuerdo_tentativo(
    cliente: httpx.AsyncClient, publicar: Any, ofertar: Any, portal: Any
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    propuesta = (await ofertar(enlaces[0], {linea: "40.00"})).json()["ultima_propuesta"]
    vista = (await ofertar(enlaces[0], propuesta["precios"], propuesta["palancas"])).json()
    assert vista["estado"] == "acuerdo_tentativo"
    assert vista["mensajes"][-1]["texto"].startswith(
        "Gracias. Su oferta quedó registrada como acuerdo tentativo"
    )
    assert vista["ultima_propuesta"] is None
    despues = await ofertar(enlaces[0], {linea: "30.00"})
    assert despues.status_code == 409
    assert despues.json()["codigo"] == "negociacion_terminada"
    assert (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).status_code == 200


async def test_la_misma_clave_no_se_procesa_dos_veces(
    publicar: Any, ofertar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    primera = await ofertar(enlaces[0], {linea: "40.00"}, clave="clave-fija-0001")
    segunda = await ofertar(enlaces[0], {linea: "39.00"}, clave="clave-fija-0001")
    assert segunda.status_code == 200
    assert segunda.json() == primera.json()
    async with fabrica() as bd:
        propias = select(func.count()).select_from(Oferta).where(Oferta.autor == "proveedor")
        assert await bd.scalar(propias) == 1


async def test_limita_a_10_mensajes_por_minuto(publicar: Any, ofertar: Any, reloj: Any) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    for _ in range(10):  # precios fuera de lo usual: piden aclaración y no consumen ronda
        assert (await ofertar(enlaces[0], {linea: "9999.00"})).status_code == 200
    excedida = await ofertar(enlaces[0], {linea: "9999.00"})
    assert excedida.status_code == 429
    assert excedida.headers["retry-after"] == "60"
    reloj.momento += timedelta(seconds=61)
    assert (await ofertar(enlaces[0], {linea: "9999.00"})).status_code == 200


async def test_pide_aclaracion_y_procesa_al_confirmar(publicar: Any, ofertar: Any) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    vista = (await ofertar(enlaces[0], {linea: "3150.00"})).json()
    assert (vista["pide_confirmacion"], vista["rondas_restantes"]) == (True, 6)
    assert vista["mensajes"][-1]["texto"] == (
        "El precio de CRM profesional parece fuera de lo usual. Si es correcto, márquelo como "
        "confirmado y envíelo de nuevo."
    )
    confirmada = (await ofertar(enlaces[0], {linea: "3150.00"}, confirmar_valores=True)).json()
    assert (confirmada["pide_confirmacion"], confirmada["rondas_restantes"]) == (False, 5)


async def test_una_oferta_con_forma_equivocada_da_422_por_campo(
    publicar: Any, ofertar: Any
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    ajena = str(uuid.uuid4())
    mala = await ofertar(enlaces[0], {linea: "30.123", ajena: "10.00"}, {"plazo_meses": "12"})
    assert mala.status_code == 422
    assert mala.json()["codigo"] == "oferta_invalida"
    assert mala.json()["errores"] == [
        {
            "campo": f"valores.precios.{ajena}",
            "mensaje": "Esta línea no es parte de la negociación.",
        },
        {"campo": "valores.palancas.plazo_meses", "mensaje": "Este término no se negocia aquí."},
        {"campo": f"valores.precios.{linea}", "mensaje": "Use como máximo 2 decimales."},
    ]
    sin_precio = await ofertar(enlaces[0], {})
    assert sin_precio.json()["errores"] == [
        {"campo": f"valores.precios.{linea}", "mensaje": "Indique el precio de esta línea."}
    ]
    cero = await ofertar(enlaces[0], {linea: "0"})
    assert cero.json()["errores"][0]["mensaje"] == "Debe ser mayor que 0."
    no_numero = await ofertar(enlaces[0], {linea: "NaN"})
    assert no_numero.status_code == 422


async def test_las_palancas_se_negocian_y_se_exigen(
    cliente: httpx.AsyncClient, con_plazo_de_pago: Any, ofertar: Any, portal: Any
) -> None:
    evento, enlaces = await con_plazo_de_pago()
    linea = _linea(evento)
    vista = (await cliente.get("/portal/sesion", headers=portal(enlaces[0]))).json()
    assert vista["palancas"] == [
        {"clave": "plazo_pago_dias", "nombre": "Plazo de pago", "unidad": "días"}
    ]
    falta = await ofertar(enlaces[0], {linea: "31.00"})
    assert falta.json()["errores"] == [
        {"campo": "valores.palancas.plazo_pago_dias", "mensaje": "Indique este valor."}
    ]
    vista = (await ofertar(enlaces[0], {linea: "31.00"}, {"plazo_pago_dias": "15"})).json()
    pago = D(vista["ultima_propuesta"]["palancas"]["plazo_pago_dias"])
    assert (
        D(30) < pago <= D(60)
    )  # pidió 15 días (más allá del límite) y no se le contesta el límite


async def test_los_valores_con_exponente_se_guardan_en_la_precision_del_termino(
    con_plazo_de_pago: Any, ofertar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await con_plazo_de_pago()
    linea = _linea(evento)
    respuesta = await ofertar(enlaces[0], {linea: "3.1E+1"}, {"plazo_pago_dias": "4E+1"})
    assert respuesta.status_code == 200, respuesta.text
    async with fabrica() as bd:
        guardada = await bd.scalar(select(Oferta.valores).where(Oferta.autor == "proveedor"))
    assert guardada == {"precios": {linea: "31.00"}, "palancas": {"plazo_pago_dias": "40"}}


async def test_escalar_pasa_la_sesion_a_una_persona(
    cliente: httpx.AsyncClient, publicar: Any, ofertar: Any, portal: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    vista = (await cliente.post("/portal/escalar", headers=portal(enlaces[0]))).json()
    assert (vista["estado"], vista["atendido_por"]) == ("escalada", "persona")
    assert [m["autor"] for m in vista["mensajes"]] == ["proveedor", "sistema"]
    despues = (await ofertar(enlaces[0], {linea: "35.00"})).json()
    assert despues["rondas_restantes"] == 5
    assert (despues["mensajes"][-1]["autor"], despues["mensajes"][-1]["texto"]) == (
        "sistema",
        "Una persona del equipo de compras revisará su oferta y le responderá.",
    )
    async with fabrica() as bd:
        decisiones = select(func.count()).where(Bitacora.accion == "motor.decision")
        assert await bd.scalar(decisiones) == 0


async def test_avisa_si_otro_proveedor_ofrece_mejor(publicar: Any, ofertar: Any) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    await ofertar(enlaces[0], {linea: "30.00"})  # válida y mejor
    vista = (await ofertar(enlaces[1], {linea: "31.00"})).json()
    assert "Hemos recibido propuestas más competitivas." in vista["mensajes"][-1]["texto"]


async def test_en_la_ultima_ronda_cierra_y_el_evento_pasa_a_evaluacion(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    ids: dict[str, str],
) -> None:
    evento, enlaces = await publicar(rondas_max=2, proveedores=[ids["nube_norte"]])
    linea = _linea(evento)
    primera = (await ofertar(enlaces[0], {linea: "40.00"})).json()
    assert "La siguiente ronda es la última" in primera["mensajes"][-1]["texto"]
    segunda = (await ofertar(enlaces[0], {linea: "40.00"})).json()
    assert segunda["estado"] == "sin_acuerdo"
    assert segunda["mensajes"][-1]["texto"] == (
        "Gracias por su tiempo. En esta ocasión no fue posible llegar a un acuerdo."
    )
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    assert detalle["estado"] == "en_evaluacion"


async def test_dos_ofertas_a_la_vez_se_procesan_una_tras_otra(
    publicar: Any, ofertar: Any, fabrica: Fabrica
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    primera, segunda = await asyncio.gather(
        ofertar(enlaces[0], {linea: "40.00"}), ofertar(enlaces[0], {linea: "39.00"})
    )
    assert (primera.status_code, segunda.status_code) == (200, 200)
    async with fabrica() as bd:
        consulta = select(Oferta.ronda).where(Oferta.autor == "proveedor")
        assert sorted((await bd.scalars(consulta)).all()) == [1, 2]


async def test_ninguna_respuesta_del_portal_revela_limites_pesos_ni_referencia(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Any, portal: Any
) -> None:
    borrador = await nueva_compra()
    cambios = {
        "version": 1,
        "lineas": [
            {
                "codigo_servicio": "SAAS-CRM-PRO",
                "cantidad": "100",
                "ideal": "27.13",
                "limite": "31.17",
            }
        ],
        "palancas": [
            {"clave": "precio", "peso": 80},
            {"clave": "plazo_pago_dias", "peso": 20, "ideal": "57", "limite": "33"},
        ],
    }
    editado = await cliente.patch(f"/eventos/{borrador['id']}", json=cambios, headers=comprador)
    assert editado.status_code == 200, editado.text
    publicado = (
        await cliente.post(f"/eventos/{borrador['id']}/publicar", headers=comprador)
    ).json()
    linea = _linea(publicado["evento"])  # al reemplazar las líneas cambió su id
    enlace = publicado["enlaces"][0]
    textos = [(await cliente.get("/portal/sesion", headers=portal(enlace))).text]
    for precio, pago in (("40.00", "20"), ("35.00", "25"), ("33.00", "30")):
        cuerpo = {"valores": {"precios": {linea: precio}, "palancas": {"plazo_pago_dias": pago}}}
        respuesta = await cliente.post("/portal/ofertas", json=cuerpo, headers=portal(enlace))
        assert respuesta.status_code == 200, respuesta.text
        textos.append(respuesta.text)
    texto = " ".join(textos)
    for prohibido in (
        "27.13",
        "31.17",
        '"57"',
        '"33"',
        "28.0000",
        "31.5000",
        "36.0000",
        '"ideal"',
        '"limite"',
        '"peso"',
        '"utilidad"',
        '"referencia"',
    ):
        assert prohibido not in texto, prohibido
