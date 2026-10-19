import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
from comun.errores import ErrorDominio
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI
from negociacion.adjudicacion import evaluar, exigir_estado
from negociacion.modelos import Adjudicacion, Bitacora, Evento, Outbox
from sqlalchemy import event, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]
FECHA_LIMITE_RENOVACION = "2026-10-20T15:00:00+00:00"
SIN_RECOMENDACION = (
    "No se pudo obtener la recomendación de adjudicación. Intente de nuevo en unos minutos."
)


def _linea(evento: dict[str, Any]) -> str:
    return str(evento["lineas"][0]["id"])


async def _evaluacion(
    cliente: httpx.AsyncClient, evento: dict[str, Any], encabezados: dict[str, str], pesos: str = ""
) -> httpx.Response:
    url = f"/eventos/{evento['id']}/evaluacion" + (f"?pesos={pesos}" if pesos else "")
    return await cliente.get(url, headers=encabezados)


@pytest.fixture
async def con_acuerdos(
    evento_con_acuerdos: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return await evento_con_acuerdos()


async def test_la_evaluacion_pide_la_recomendacion_con_los_acuerdos(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    externos: Any,
    acordar: Any,
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    # El primer proveedor acepta la propuesta del agente; con el segundo, el comprador acepta.
    propuesta = (await ofertar(enlaces[0], {linea: "40.00"})).json()["ultima_propuesta"]
    await ofertar(enlaces[0], propuesta["precios"], propuesta["palancas"])
    await acordar(enlaces[1], linea, "31.00")

    respuesta = await _evaluacion(cliente, evento, comprador)

    assert respuesta.status_code == 200, respuesta.text
    [peticion] = externos.recomendaciones()
    assert peticion["moneda"] == "USD"
    assert "pesos" not in peticion  # inteligencia usa los configurados
    candidatos = {c["id"]: c for c in peticion["candidatos"]}
    assert set(candidatos) == {e["sesion_id"] for e in enlaces}
    acordado = {
        enlaces[0]["sesion_id"]: D(propuesta["precios"][linea]),
        enlaces[1]["sesion_id"]: D("31.00"),
    }
    for enlace in enlaces:
        candidato = candidatos[enlace["sesion_id"]]
        assert set(candidato) == {
            "id",
            "proveedor_id",
            "nombre",
            "plazo_meses",
            "cuota_implementacion",
            "sla",
            "lineas",
        }
        assert candidato["nombre"] == enlace["proveedor_nombre"]
        # Sin palancas negociadas en una compra: el plazo del evento, sin cuota y sin SLA.
        assert (candidato["plazo_meses"], D(candidato["cuota_implementacion"])) == (12, 0)
        assert candidato["sla"] is None
        [linea_pedida] = candidato["lineas"]
        assert (linea_pedida["codigo_servicio"], linea_pedida["unidad"]) == (
            "SAAS-CRM-PRO",
            "usuario_mes",
        )
        assert D(linea_pedida["cantidad"]) == 100
        assert D(linea_pedida["precio"]) == acordado[enlace["sesion_id"]]
    cuerpo = respuesta.json()
    recomendacion = cuerpo["recomendacion"]
    ganador = min(acordado, key=lambda sesion: acordado[sesion])
    assert recomendacion["recomendado"] == ganador
    mejor = recomendacion["candidatos"][0]
    assert D(mejor["costo_total_mxn"]) == acordado[ganador] * 100 * D("20.00")  # USD a MXN
    assert D(recomendacion["umbral_aprobacion"]) == D("500000.00")
    assert (cuerpo["vigente"], cuerpo["historial"]) == (None, [])


async def test_candidatos_usan_los_valores_acordados(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    nueva_compra: Any,
    externos: Any,
    acordar: Any,
    sin_acuerdo: Any,
) -> None:
    evento = await nueva_compra()
    palancas = [
        {"clave": "precio", "peso": 50},
        {"clave": "plazo_meses", "peso": 20, "ideal": "36", "limite": "12"},
        {"clave": "sla_disponibilidad", "peso": 15, "ideal": "99.90", "limite": "99.00"},
        {"clave": "cuota_implementacion", "peso": 15, "ideal": "0", "limite": "5000"},
    ]
    editado = await cliente.patch(
        f"/eventos/{evento['id']}", json={"version": 1, "palancas": palancas}, headers=comprador
    )
    assert editado.status_code == 200, editado.text
    publicado = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert publicado.status_code == 200, publicado.text
    [primero, segundo] = publicado.json()["enlaces"]
    acordadas = {"plazo_meses": "24", "sla_disponibilidad": "99.50", "cuota_implementacion": "1500"}
    await acordar(primero, _linea(evento), "31.00", acordadas)
    await sin_acuerdo(segundo)

    respuesta = await _evaluacion(cliente, evento, comprador)

    assert respuesta.status_code == 200, respuesta.text
    [peticion] = externos.recomendaciones()
    [candidato] = peticion["candidatos"]  # el otro proveedor no llegó a un acuerdo
    assert candidato["id"] == primero["sesion_id"]
    assert candidato["plazo_meses"] == 24
    assert D(candidato["sla"]) == D("99.50")
    assert D(candidato["cuota_implementacion"]) == D("1500")
    assert D(candidato["lineas"][0]["precio"]) == D("31.00")


async def test_en_renovacion_el_sla_no_negociado_es_el_del_contrato(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    catalogo: None,
    ids: dict[str, str],
    externos: Any,
    acordar: Any,
) -> None:
    creada = await cliente.post(
        "/eventos",
        json={
            "tipo": "renovacion",
            "titulo": "Renovación del CRM",
            "fecha_limite": FECHA_LIMITE_RENOVACION,
            "proveedor_id": ids["nube_norte"],
            "contrato_id": ids["contrato"],
        },
        headers=comprador,
    )
    assert creada.status_code == 201, creada.text
    evento = creada.json()
    publicado = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert publicado.status_code == 200, publicado.text
    [enlace] = publicado.json()["enlaces"]
    await acordar(enlace, _linea(evento), "31.00")

    respuesta = await _evaluacion(cliente, evento, comprador)

    assert respuesta.status_code == 200, respuesta.text
    [candidato] = externos.recomendaciones()[0]["candidatos"]
    assert D(candidato["sla"]) == D("99.50")  # el del contrato vigente
    assert candidato["plazo_meses"] == 12  # el del contrato vigente


async def test_pesos_propios_van_a_inteligencia(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
) -> None:
    evento, _ = con_acuerdos
    respuesta = await _evaluacion(cliente, evento, comprador, "50,20,15,15")
    assert respuesta.status_code == 200, respuesta.text
    pesos = {"costo": 50, "desempeno": 20, "riesgo": 15, "sla": 15}
    assert externos.recomendaciones()[0]["pesos"] == pesos
    assert respuesta.json()["recomendacion"]["pesos"] == pesos


@pytest.mark.parametrize(
    "pesos",
    [
        "",
        "40,30,15",  # faltan
        "40,30,15,15,0",  # sobran
        "40,30,15,16",  # no suman 100
        "50,50,50,-50",  # negativo
        "101,0,0,-1",  # fuera de rango
        "40,30,15,15.0",  # no entero
        "a,b,c,d",
        "4_0,30,15,15",  # Python lo acepta como 40
        "+40,30,15,15",
        "40, 30,15,15",  # espacios
    ],
)
async def test_pesos_mal_formados_dan_422_sin_llamar_a_inteligencia(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    pesos: str,
) -> None:
    evento, _ = con_acuerdos
    respuesta = await cliente.get(
        f"/eventos/{evento['id']}/evaluacion", params={"pesos": pesos}, headers=comprador
    )
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["codigo"] == "pesos_invalidos"
    assert externos.recomendaciones() == []


async def test_evaluacion_fuera_de_estado(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, externos: Any
) -> None:
    evento, _ = await publicar()  # abierto
    respuesta = await _evaluacion(cliente, evento, comprador)
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["codigo"] == "estado_invalido"
    assert respuesta.json()["detail"] == (
        "La negociación está en estado «abierto»; esta acción solo procede en: en evaluación, "
        "pendiente de aprobación, adjudicado, desierto."
    )
    assert externos.recomendaciones() == []


async def test_una_negociacion_inexistente_da_404(
    cliente: httpx.AsyncClient, comprador: dict[str, str]
) -> None:
    respuesta = await cliente.get(f"/eventos/{uuid.uuid4()}/evaluacion", headers=comprador)
    assert respuesta.status_code == 404


@pytest.mark.parametrize(
    "falla",
    [
        {"caido": "intel"},
        {"estado_intel": 500},
        {"estado_intel": 409, "cuerpo_intel": b'{"codigo": "tipo_cambio_no_disponible"}'},
        {"estado_intel": 422, "cuerpo_intel": b'{"codigo": "pesos_invalidos"}'},
        {"estado_intel": 200, "cuerpo_intel": b"no es json"},
        {"estado_intel": 200, "cuerpo_intel": b"[]"},
        {"estado_intel": 200, "cuerpo_intel": b'{"recomendado": "x", "candidatos": []}'},
        {"usd_mxn": None},  # inteligencia sin tipo de cambio: 409 propio
        {"usd_mxn": D(0)},  # un costo de 0 MXN nunca se acepta
        {"usd_mxn": D("NaN")},
        {"usd_mxn": D("Infinity")},
    ],
    ids=lambda falla: ",".join(f"{k}={v!r}" for k, v in falla.items()),
)
async def test_inteligencia_caida_o_incoherente_responde_503(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    falla: dict[str, Any],
) -> None:
    evento, _ = con_acuerdos
    for campo, valor in falla.items():
        setattr(externos, campo, valor)
    respuesta = await _evaluacion(cliente, evento, comprador)
    assert respuesta.status_code == 503, respuesta.text
    assert respuesta.json()["codigo"] == "dependencia_no_disponible"
    assert respuesta.json()["detail"] == SIN_RECOMENDACION


def _cambia(**cambios: Any) -> Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]:
    """Ajusta la recomendación de inteligencia: cambia campos de la respuesta."""

    async def _ajustar(cuerpo: dict[str, Any]) -> dict[str, Any]:
        return cuerpo | cambios

    return _ajustar


def _cambia_candidato(**cambios: Any) -> Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]:
    """Ajusta la recomendación de inteligencia: cambia campos del primer candidato."""

    async def _ajustar(cuerpo: dict[str, Any]) -> dict[str, Any]:
        [primero, *otros] = cuerpo["candidatos"]
        return cuerpo | {"candidatos": [primero | cambios, *otros]}

    return _ajustar


@pytest.mark.parametrize(
    "ajuste",
    [
        pytest.param(_cambia(recomendado="otra-sesion"), id="recomendado_ajeno"),
        pytest.param(_cambia(candidatos=[]), id="sin_candidatos"),
        pytest.param(_cambia_candidato(id="otra-sesion"), id="candidato_ajeno"),
        pytest.param(_cambia_candidato(costo_total="0"), id="costo_total_cero"),
        pytest.param(_cambia_candidato(costo_total="-5"), id="costo_total_negativo"),
        pytest.param(_cambia_candidato(costo_total="NaN"), id="costo_total_nan"),
        pytest.param(_cambia_candidato(costo_total="no es un numero"), id="costo_total_texto"),
        pytest.param(_cambia_candidato(costo_total_mxn="-5"), id="costo_mxn_negativo"),
        pytest.param(_cambia_candidato(costo_total=None), id="costo_total_nulo"),
        pytest.param(_cambia(umbral_aprobacion="-1"), id="umbral_negativo"),
        pytest.param(_cambia(umbral_aprobacion="NaN"), id="umbral_nan"),
        pytest.param(_cambia(umbral_aprobacion="Infinity"), id="umbral_infinito"),
        pytest.param(_cambia(pesos=[40, 30, 15, 15]), id="pesos_no_es_objeto"),
        pytest.param(_cambia(pesos=None), id="pesos_nulos"),
    ],
)
async def test_una_recomendacion_incoherente_responde_503(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    ajuste: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    evento, _ = con_acuerdos
    externos.ajustar_recomendacion = ajuste
    respuesta = await _evaluacion(cliente, evento, comprador)
    assert respuesta.status_code == 503, respuesta.text
    assert respuesta.json()["codigo"] == "dependencia_no_disponible"
    assert respuesta.json()["detail"] == SIN_RECOMENDACION


async def test_las_otras_consultas_conservan_su_aviso_de_referencia(
    cliente: httpx.AsyncClient, comprador: dict[str, str], cuerpo_compra: Any, externos: Any
) -> None:
    externos.caido = "intel"
    respuesta = await cliente.post("/eventos", json=cuerpo_compra(), headers=comprador)
    assert respuesta.status_code == 503, respuesta.text
    assert respuesta.json()["detail"] == (
        "No se pudo consultar la referencia de precios; intente de nuevo."
    )


async def test_el_aprobador_puede_ver_la_evaluacion(
    cliente: httpx.AsyncClient, aprobador: dict[str, str], con_acuerdos: Any
) -> None:
    evento, _ = con_acuerdos
    respuesta = await _evaluacion(cliente, evento, aprobador)
    assert respuesta.status_code == 200, respuesta.text
    assert len(respuesta.json()["recomendacion"]["candidatos"]) == 2


async def test_sin_acuerdos_no_hay_recomendacion_ni_llamada(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    externos: Any,
    ids: dict[str, str],
    sin_acuerdo: Any,
) -> None:
    evento, [enlace] = await publicar(proveedores=[ids["nube_norte"]])
    await sin_acuerdo(enlace)
    respuesta = await _evaluacion(cliente, evento, comprador)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"recomendacion": None, "vigente": None, "historial": []}
    assert externos.recomendaciones() == []


def _propuesta(evento_id: str, sesion_id: str, estado: str, dia: int, **extra: Any) -> Adjudicacion:
    return Adjudicacion(
        evento_id=uuid.UUID(evento_id),
        sesion_id=uuid.UUID(sesion_id),
        propuesta_por_id="comprador-1",
        propuesta_por_nombre="Comprador Uno",
        propuesta_en=datetime(2026, 10, dia, 12, tzinfo=UTC),
        recomendada_sesion_id=uuid.UUID(sesion_id),
        se_aparta=False,
        costo_total=D("3000.00"),
        costo_total_mxn=D("60000.00"),
        requiere_aprobacion=estado != "directa",
        motivo_aprobacion=[],
        recomendacion={"recomendado": sesion_id, "foto": dia},
        estado=estado,
        **extra,
    )


async def _guardar(fabrica: Fabrica, estado_evento: str, evento_id: str, *filas: Any) -> None:
    async with fabrica() as bd, bd.begin():
        await bd.execute(
            update(Evento).where(Evento.id == uuid.UUID(evento_id)).values(estado=estado_evento)
        )
        bd.add_all(filas)


@pytest.mark.parametrize(
    ("estado_evento", "estado_vigente"),
    [("pendiente_aprobacion", "pendiente"), ("adjudicado", "aprobada"), ("adjudicado", "directa")],
)
async def test_muestra_la_vigente_y_el_historial_con_la_foto_sin_consultar_inteligencia(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    fabrica: Fabrica,
    externos: Any,
    estado_evento: str,
    estado_vigente: str,
) -> None:
    evento, enlaces = con_acuerdos
    sesion = enlaces[0]["sesion_id"]
    rechazo = {"decidida_por_id": "aprobador-1", "motivo_rechazo": "Falta justificar"}
    await _guardar(
        fabrica,
        estado_evento,
        evento["id"],
        _propuesta(evento["id"], sesion, "rechazada", 12, **rechazo),
        _propuesta(evento["id"], sesion, "rechazada", 14, **rechazo),
        _propuesta(evento["id"], sesion, estado_vigente, 15),
    )

    antes = len(externos.peticiones)

    respuesta = await _evaluacion(cliente, evento, comprador, pesos="25,25,25,25")

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["vigente"]["estado"] == estado_vigente
    assert cuerpo["vigente"]["recomendacion"] == {"recomendado": sesion, "foto": 15}  # la foto
    assert cuerpo["vigente"]["costo_total_mxn"] == "60000.00"
    assert cuerpo["vigente"]["propuesta_por_nombre"] == "Comprador Uno"
    # Las rechazadas, de la más reciente a la más antigua.
    assert [(h["estado"], h["recomendacion"]["foto"]) for h in cuerpo["historial"]] == [
        ("rechazada", 14),
        ("rechazada", 12),
    ]
    assert cuerpo["historial"][0]["motivo_rechazo"] == "Falta justificar"
    # Ya propuesta, la recomendación es la foto guardada (con sus pesos): no se consulta a nadie.
    assert cuerpo["recomendacion"] == cuerpo["vigente"]["recomendacion"]  # y `pesos` se ignora
    assert len(externos.peticiones) == antes


@pytest.mark.parametrize(
    ("estado_evento", "estado_vigente"),
    [("pendiente_aprobacion", "pendiente"), ("adjudicado", "directa")],
)
async def test_con_inteligencia_caida_la_propuesta_siempre_se_ve(
    cliente: httpx.AsyncClient,
    aprobador: dict[str, str],
    con_acuerdos: Any,
    fabrica: Fabrica,
    externos: Any,
    estado_evento: str,
    estado_vigente: str,
) -> None:
    evento, enlaces = con_acuerdos
    await _guardar(
        fabrica,
        estado_evento,
        evento["id"],
        _propuesta(evento["id"], enlaces[0]["sesion_id"], estado_vigente, 15),
    )
    externos.caido = "intel"
    antes = len(externos.peticiones)

    respuesta = await _evaluacion(cliente, evento, aprobador)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["vigente"]["id"]  # el aprobador siempre puede decidir sobre ella
    assert cuerpo["recomendacion"] == {"recomendado": enlaces[0]["sesion_id"], "foto": 15}
    assert len(externos.peticiones) == antes  # ni siquiera se intentó


async def test_un_evento_desierto_no_pide_recomendacion(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    fabrica: Fabrica,
    externos: Any,
) -> None:
    evento, _ = con_acuerdos
    await _guardar(fabrica, "desierto", evento["id"])
    respuesta = await _evaluacion(cliente, evento, comprador)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"recomendacion": None, "vigente": None, "historial": []}
    assert externos.recomendaciones() == []


@pytest.mark.parametrize(
    ("estado", "etiqueta"),
    [
        ("borrador", "borrador"),
        ("abierto", "abierto"),
        ("en_evaluacion", "en evaluación"),
        ("pendiente_aprobacion", "pendiente de aprobación"),
        ("adjudicado", "adjudicado"),
        ("desierto", "desierto"),
        ("cancelado", "cancelado"),
    ],
)
def test_exigir_estado_nombra_el_estado_en_espanol(estado: str, etiqueta: str) -> None:
    permitidos = (
        ("adjudicado", "desierto")
        if estado not in ("adjudicado", "desierto")
        else (
            "borrador",
            "abierto",
        )
    )
    with pytest.raises(ErrorDominio) as error:
        exigir_estado(Evento(estado=estado), *permitidos)
    assert error.value.estado == 409
    assert error.value.extra == {"codigo": "estado_invalido"}
    assert error.value.detalle.startswith(f"La negociación está en estado «{etiqueta}»;")
    assert error.value.detalle.endswith(f"solo procede en: {', '.join(permitidos)}.")
    exigir_estado(Evento(estado=estado), estado)  # en su estado, no hay error


async def test_evaluar_manda_los_pesos_dados_a_inteligencia(
    app: FastAPI, fabrica: Fabrica, con_acuerdos: Any, externos: Any
) -> None:
    evento, enlaces = con_acuerdos
    pesos = {"costo": 70, "desempeno": 10, "riesgo": 10, "sla": 10}
    async with fabrica() as bd:
        fila = await bd.get(Evento, uuid.UUID(evento["id"]))
        assert fila is not None
        recomendacion = await evaluar(bd, app.state.integraciones, "token", fila, pesos)
    assert externos.recomendaciones()[0]["pesos"] == pesos
    assert recomendacion["pesos"] == pesos
    assert {c["id"] for c in recomendacion["candidatos"]} == {e["sesion_id"] for e in enlaces}


async def test_la_consulta_no_retiene_una_transaccion_mientras_espera_a_inteligencia(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    urls_bd: tuple[str, str],
) -> None:
    evento, _ = con_acuerdos
    abiertas: list[Any] = []

    async def _contar(cuerpo: dict[str, Any]) -> dict[str, Any]:
        """Cuenta, desde fuera, las conexiones de la aplicación con una transacción abierta."""
        motor = create_async_engine(urls_bd[0], poolclass=NullPool)
        async with motor.connect() as conexion:
            abiertas.append(
                await conexion.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE usename = 'negociacion' AND state = 'idle in transaction'"
                    )
                )
            )
        await motor.dispose()
        return cuerpo

    externos.ajustar_recomendacion = _contar
    respuesta = await _evaluacion(cliente, evento, comprador)
    assert respuesta.status_code == 200, respuesta.text
    assert abiertas == [0]


# --- Task 8: proponer, aprobar, rechazar y declarar desierta -------------------------------------

JUSTIFICACION = "Mejor tiempo de implementación y soporte local."
UMBRAL_BAJO = D("1000.00")  # los acuerdos de prueba (60,000 MXN o más) lo superan
CONTRATO_ESPERADO = {
    "tipo": "nuevo",
    "moneda": "USD",
    "fecha_inicio": "2026-10-14",  # el día siguiente a las 09:00 del 13 de octubre en México
    "fecha_fin": "2027-10-13",
    "plazo_pago_dias": 30,
    "sla_disponibilidad": None,
    "tope_aumento_pct": None,
    "cuota_implementacion": "0",
}


async def _accion(
    cliente: httpx.AsyncClient,
    encabezados: dict[str, str],
    evento: dict[str, Any],
    ruta: str,
    **cuerpo: Any,
) -> httpx.Response:
    """Aprobar (`adjudicacion/aprobar`), rechazar (`adjudicacion/rechazar`) o declarar desierta."""
    return await cliente.post(
        f"/eventos/{evento['id']}/{ruta}", json=cuerpo or None, headers=encabezados
    )


def _id_vigente(respuesta: httpx.Response) -> str:
    """El id de la propuesta vigente de la respuesta: la que el aprobador tiene abierta."""
    return str(respuesta.json()["vigente"]["id"])


async def _aprobar(
    cliente: httpx.AsyncClient,
    encabezados: dict[str, str],
    evento: dict[str, Any],
    adjudicacion_id: str,
) -> httpx.Response:
    return await _accion(
        cliente, encabezados, evento, "adjudicacion/aprobar", adjudicacion_id=adjudicacion_id
    )


async def _rechazar(
    cliente: httpx.AsyncClient,
    encabezados: dict[str, str],
    evento: dict[str, Any],
    adjudicacion_id: str,
    motivo: str = "No procede.",
) -> httpx.Response:
    return await _accion(
        cliente,
        encabezados,
        evento,
        "adjudicacion/rechazar",
        adjudicacion_id=adjudicacion_id,
        motivo=motivo,
    )


async def _estado(
    cliente: httpx.AsyncClient, encabezados: dict[str, str], evento: dict[str, Any]
) -> str:
    respuesta = await cliente.get(f"/eventos/{evento['id']}", headers=encabezados)
    return str(respuesta.json()["estado"])


async def _publicados(fabrica: Fabrica, tipo: str) -> list[dict[str, Any]]:
    """Los payloads que quedaron en el Outbox con ese tipo de evento."""
    async with fabrica() as bd:
        consulta = select(Outbox).where(Outbox.tipo == tipo).order_by(Outbox.ocurrido_en)
        return [fila.payload for fila in await bd.scalars(consulta)]


async def _filas(fabrica: Fabrica, evento: dict[str, Any]) -> list[Adjudicacion]:
    async with fabrica() as bd:
        consulta = select(Adjudicacion).where(Adjudicacion.evento_id == uuid.UUID(evento["id"]))
        return list(await bd.scalars(consulta))


async def _bitacora(fabrica: Fabrica, evento: dict[str, Any]) -> list[Bitacora]:
    """Las acciones de la adjudicación en la bitácora del evento."""
    async with fabrica() as bd:
        consulta = select(Bitacora).where(Bitacora.evento_id == uuid.UUID(evento["id"]))
        return [
            fila
            for fila in await bd.scalars(consulta)
            if fila.accion.startswith("adjudicacion.") or fila.accion == "evento.desierto"
        ]


async def test_bajo_el_umbral_el_comprador_adjudica_directo(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    ids: dict[str, str],
    fabrica: Fabrica,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    respuesta = await proponer(comprador, evento, enlaces[1])  # el recomendado

    assert respuesta.status_code == 200, respuesta.text
    vigente = respuesta.json()["vigente"]
    assert (vigente["estado"], vigente["requiere_aprobacion"], vigente["motivo_aprobacion"]) == (
        "directa",
        False,
        [],
    )
    assert (vigente["se_aparta"], vigente["justificacion"]) == (False, None)
    assert vigente["sesion_id"] == vigente["recomendada_sesion_id"] == enlaces[1]["sesion_id"]
    assert D(vigente["costo_total"]) == D("3000")
    assert D(vigente["costo_total_mxn"]) == D("60000")
    assert vigente["decidida_por_nombre"] == vigente["propuesta_por_nombre"] == "comprador-1"
    assert vigente["decidida_en"] is not None
    assert vigente["contrato_folio"] == f"C-{evento['folio']}"
    assert vigente["recomendacion"]["recomendado"] == enlaces[1]["sesion_id"]  # la foto
    assert respuesta.json()["historial"] == []
    assert await _estado(cliente, comprador, evento) == "adjudicado"
    [adjudicada] = await _publicados(fabrica, "negociacion.adjudicada")
    assert adjudicada == {
        "folio": evento["folio"],
        "titulo": evento["titulo"],
        "tipo": "compra",
        "proveedor_id": ids["datos_sur"],
        "proveedor": "Datos del Sur S.A.",
        "costo_total_mxn": "60000.00",
        "aprobacion": "directa",
        "actor": {"id": "comprador-1", "nombre": "comprador-1"},
        "contrato": CONTRATO_ESPERADO
        | {
            "folio": f"C-{evento['folio']}",
            "lineas": [
                {
                    "codigo_servicio": "SAAS-CRM-PRO",
                    "cantidad": "100.0000",
                    "precio_unitario": "30.00",
                }
            ],
        },
    }


async def test_sobre_el_umbral_queda_pendiente_y_el_aprobador_aprueba(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    reloj: Any,
    fabrica: Fabrica,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    externos.umbral = UMBRAL_BAJO

    propuesta = await proponer(comprador, evento, enlaces[1])

    assert propuesta.status_code == 200, propuesta.text
    vigente = propuesta.json()["vigente"]
    assert (vigente["estado"], vigente["requiere_aprobacion"]) == ("pendiente", True)
    assert vigente["motivo_aprobacion"] == ["umbral"]
    assert (vigente["decidida_por_nombre"], vigente["decidida_en"]) == (None, None)
    assert vigente["contrato_folio"] is None
    assert await _estado(cliente, comprador, evento) == "pendiente_aprobacion"
    assert await _publicados(fabrica, "negociacion.adjudicada") == []

    reloj.momento += timedelta(days=3)  # el contrato nace con la fecha de la aprobación
    aprobada = await _aprobar(cliente, aprobador, evento, vigente["id"])

    assert aprobada.status_code == 200, aprobada.text
    vigente = aprobada.json()["vigente"]
    assert (vigente["estado"], vigente["decidida_por_nombre"]) == ("aprobada", "aprobador-1")
    assert vigente["propuesta_por_nombre"] == "comprador-1"
    assert vigente["contrato_folio"] == f"C-{evento['folio']}"
    assert await _estado(cliente, comprador, evento) == "adjudicado"
    [adjudicada] = await _publicados(fabrica, "negociacion.adjudicada")
    assert adjudicada["aprobacion"] == "aprobada"
    assert adjudicada["actor"] == {"id": "aprobador-1", "nombre": "aprobador-1"}
    assert adjudicada["costo_total_mxn"] == "60000.00"
    assert adjudicada["contrato"]["fecha_inicio"] == "2026-10-17"
    assert adjudicada["contrato"]["fecha_fin"] == "2027-10-16"
    assert len(externos.recomendaciones()) == 1  # aprobar usa la propuesta guardada


@pytest.fixture
async def con_una_fuera_de_limites(
    publicar: Any, acordar: Any
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Dos acuerdos bajo el umbral: el primero, a 40.00, aceptado a mano fuera de límites."""
    evento, enlaces = await publicar()
    await acordar(enlaces[0], _linea(evento), "40.00", None, True)
    await acordar(enlaces[1], _linea(evento), "30.00")
    return evento, enlaces


async def test_fuera_de_limites_siempre_pide_aprobacion(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_una_fuera_de_limites: Any,
    proponer: Any,
) -> None:
    evento, enlaces = con_una_fuera_de_limites

    respuesta = await proponer(comprador, evento, enlaces[0], justificacion=JUSTIFICACION)

    assert respuesta.status_code == 200, respuesta.text
    vigente = respuesta.json()["vigente"]
    assert D(vigente["costo_total_mxn"]) == D("80000")  # bajo el umbral de 500,000
    assert (vigente["estado"], vigente["motivo_aprobacion"]) == ("pendiente", ["fuera_de_limites"])
    assert await _estado(cliente, comprador, evento) == "pendiente_aprobacion"


async def test_solo_cuenta_si_la_sesion_elegida_salio_de_limites(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_una_fuera_de_limites: Any,
    proponer: Any,
) -> None:
    evento, enlaces = con_una_fuera_de_limites
    respuesta = await proponer(comprador, evento, enlaces[1])  # la otra sesión
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["vigente"]["estado"] == "directa"


@pytest.mark.parametrize(
    "justificacion",
    [
        pytest.param(None, id="nula"),
        pytest.param("", id="vacia"),
        pytest.param("   \n\t ", id="solo_espacios"),
        pytest.param("corta", id="corta"),
        pytest.param("  nueve car  ", id="nueve_sin_espacios_sobrantes"),
        pytest.param("x" * 1001, id="mas_de_1000"),
    ],
)
async def test_apartarse_de_la_recomendacion_exige_justificacion(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    fabrica: Fabrica,
    justificacion: str | None,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    respuesta = await proponer(
        comprador, evento, enlaces[0], justificacion=justificacion
    )  # no es el recomendado
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["codigo"] == "justificacion_requerida"
    assert respuesta.json()["errores"][0]["campo"] == "justificacion"
    assert await _estado(cliente, comprador, evento) == "en_evaluacion"
    assert await _filas(fabrica, evento) == []


@pytest.mark.parametrize("texto", ["a" * 10, "b" * 1000])
async def test_la_justificacion_acepta_de_10_a_1000_caracteres_sin_espacios_sobrantes(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    texto: str,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    respuesta = await proponer(comprador, evento, enlaces[0], justificacion=f"  {texto}\n")
    assert respuesta.status_code == 200, respuesta.text
    vigente = respuesta.json()["vigente"]
    assert (vigente["se_aparta"], vigente["justificacion"]) == (True, texto)
    assert vigente["sesion_id"] == enlaces[0]["sesion_id"]
    assert vigente["recomendada_sesion_id"] == enlaces[1]["sesion_id"]


@pytest.mark.parametrize(
    ("justificacion", "guardada", "estado"),
    [
        (None, None, 200),
        ("  ", None, 200),  # sin nada que guardar
        (f"  {JUSTIFICACION} ", JUSTIFICACION, 200),
        ("corta", None, 422),  # si se manda, se valida igual
    ],
)
async def test_con_el_recomendado_la_justificacion_es_opcional(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    justificacion: str | None,
    guardada: str | None,
    estado: int,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    respuesta = await proponer(comprador, evento, enlaces[1], justificacion=justificacion)
    assert respuesta.status_code == estado, respuesta.text
    if estado == 200:
        assert respuesta.json()["vigente"]["justificacion"] == guardada
        assert respuesta.json()["vigente"]["se_aparta"] is False
    else:
        assert respuesta.json()["codigo"] == "justificacion_requerida"


async def test_quien_propone_no_aprueba_aunque_tenga_los_dos_roles(
    cliente: httpx.AsyncClient,
    aprobador: dict[str, str],
    claves: ClavesPrueba,
    con_acuerdos: Any,
    externos: Any,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    externos.umbral = UMBRAL_BAJO
    ambos = {"Authorization": f"Bearer {claves.token('comprador', 'aprobador', sub='ambos-1')}"}
    propuesta = await proponer(ambos, evento, enlaces[1])
    assert propuesta.json()["vigente"]["estado"] == "pendiente", propuesta.text
    propuesta_id = _id_vigente(propuesta)

    for ruta, cuerpo in (
        ("adjudicacion/aprobar", {}),
        ("adjudicacion/rechazar", {"motivo": "No."}),
    ):
        respuesta = await _accion(
            cliente, ambos, evento, ruta, adjudicacion_id=propuesta_id, **cuerpo
        )
        assert respuesta.status_code == 403, respuesta.text
        assert respuesta.json()["codigo"] == "misma_persona"
        assert "otra persona" in respuesta.json()["detail"]
    # Con el id de otra propuesta, primero se dice que cambió (409) y no que es la misma persona.
    ajena = await _aprobar(cliente, ambos, evento, str(uuid.uuid4()))
    assert (ajena.status_code, ajena.json()["codigo"]) == (409, "propuesta_distinta")
    assert await _estado(cliente, ambos, evento) == "pendiente_aprobacion"

    otro = await _aprobar(cliente, aprobador, evento, propuesta_id)  # otra persona
    assert otro.status_code == 200, otro.text


async def test_tras_un_rechazo_se_propone_de_nuevo(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    externos.umbral = UMBRAL_BAJO
    propuesta = await proponer(comprador, evento, enlaces[1])

    rechazada = await _rechazar(
        cliente, aprobador, evento, _id_vigente(propuesta), "  Falta un tercer proveedor. "
    )

    assert rechazada.status_code == 200, rechazada.text
    cuerpo = rechazada.json()
    assert cuerpo["vigente"] is None
    [rechazo] = cuerpo["historial"]
    assert (rechazo["estado"], rechazo["motivo_rechazo"]) == (
        "rechazada",
        "Falta un tercer proveedor.",
    )
    assert (rechazo["decidida_por_nombre"], rechazo["contrato_folio"]) == ("aprobador-1", None)
    assert await _estado(cliente, comprador, evento) == "en_evaluacion"

    # Aprobar (o rechazar) lo que ya se rechazó: 409 que dice el estado actual (spec §8).
    for tarde in (
        await _aprobar(cliente, aprobador, evento, rechazo["id"]),
        await _rechazar(cliente, aprobador, evento, rechazo["id"]),
    ):
        assert tarde.status_code == 409, tarde.text
        assert tarde.json()["codigo"] == "estado_invalido"
        assert tarde.json()["detail"].startswith("La negociación está en estado «en evaluación»;")
    assert await _estado(cliente, comprador, evento) == "en_evaluacion"

    de_nuevo = await proponer(comprador, evento, enlaces[0], justificacion=JUSTIFICACION)

    assert de_nuevo.status_code == 200, de_nuevo.text
    assert de_nuevo.json()["vigente"]["sesion_id"] == enlaces[0]["sesion_id"]
    assert [h["id"] for h in de_nuevo.json()["historial"]] == [rechazo["id"]]
    nueva_id = _id_vigente(de_nuevo)
    assert (await _aprobar(cliente, aprobador, evento, nueva_id)).status_code == 200
    segunda = await _aprobar(cliente, aprobador, evento, nueva_id)
    assert segunda.status_code == 409, segunda.text
    assert segunda.json()["codigo"] == "estado_invalido"
    assert await _estado(cliente, comprador, evento) == "adjudicado"


async def test_evento_en_usd_compara_el_umbral_en_mxn(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    externos: Any,
    acordar: Any,
    proponer: Any,
) -> None:
    assert externos.usd_mxn == D("20.00")
    evento, enlaces = await publicar(
        lineas=[{"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "1000"}]
    )
    await acordar(enlaces[0], _linea(evento), "30.00")
    await acordar(enlaces[1], _linea(evento), "31.00")

    respuesta = await proponer(comprador, evento, enlaces[0])

    assert respuesta.status_code == 200, respuesta.text
    vigente = respuesta.json()["vigente"]
    assert D(vigente["costo_total"]) == D("30000")  # bajo el umbral en dólares
    assert D(vigente["costo_total_mxn"]) == D("600000")  # sobre el umbral en pesos
    assert (vigente["estado"], vigente["motivo_aprobacion"]) == ("pendiente", ["umbral"])


async def test_declarar_desierta(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    fabrica: Fabrica,
    externos: Any,
) -> None:
    evento, _ = con_acuerdos
    antes = await cliente.get(f"/eventos/{evento['id']}", headers=comprador)
    assert antes.json()["motivo_desierta"] is None

    respuesta = await _accion(
        cliente, comprador, evento, "desierta", motivo="  Ninguna propuesta es viable. "
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"recomendacion": None, "vigente": None, "historial": []}
    assert await _estado(cliente, comprador, evento) == "desierto"
    despues = await cliente.get(f"/eventos/{evento['id']}", headers=comprador)
    assert despues.json()["motivo_desierta"] == "Ninguna propuesta es viable."
    async with fabrica() as bd:
        fila = await bd.get(Evento, uuid.UUID(evento["id"]))
        assert fila is not None
        assert fila.motivo_desierta == "Ninguna propuesta es viable."
    assert await _publicados(fabrica, "negociacion.desierta") == [
        {
            "folio": evento["folio"],
            "titulo": evento["titulo"],
            "motivo": "Ninguna propuesta es viable.",
            "actor": {"id": "comprador-1", "nombre": "comprador-1"},
        }
    ]
    assert externos.recomendaciones() == []
    assert await _filas(fabrica, evento) == []


@pytest.mark.parametrize("motivo", ["", "   ", "x" * 501])
async def test_el_motivo_de_desierta_y_de_rechazo_va_de_1_a_500_caracteres(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    motivo: str,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    desierta = await _accion(cliente, comprador, evento, "desierta", motivo=motivo)
    assert desierta.status_code == 422, desierta.text
    externos.umbral = UMBRAL_BAJO
    propuesta = await proponer(comprador, evento, enlaces[1])
    rechazo = await _rechazar(cliente, aprobador, evento, _id_vigente(propuesta), motivo)
    assert rechazo.status_code == 422, rechazo.text
    assert await _estado(cliente, comprador, evento) == "pendiente_aprobacion"


async def _intentos(
    proponer: Any,
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    evento: dict[str, Any],
    enlace: dict[str, Any],
    *acciones: str,
) -> list[httpx.Response]:
    """Intenta esas acciones en orden; cada una debe fallar, así que no cambian el estado."""
    pedidos: dict[str, Callable[[], Awaitable[httpx.Response]]] = {
        "proponer": lambda: proponer(comprador, evento, enlace),
        # Cualquier id: el estado se revisa antes que la propuesta.
        "aprobar": lambda: _aprobar(cliente, aprobador, evento, str(uuid.uuid4())),
        "rechazar": lambda: _rechazar(cliente, aprobador, evento, str(uuid.uuid4())),
        "desierta": lambda: _accion(cliente, comprador, evento, "desierta", motivo="Sin ofertas."),
    }
    return [await pedidos[accion]() for accion in acciones]


def _son_409(respuestas: list[httpx.Response], estado: str) -> None:
    for respuesta in respuestas:
        assert respuesta.status_code == 409, respuesta.text
        assert respuesta.json()["codigo"] == "estado_invalido"
        assert respuesta.json()["detail"].startswith(f"La negociación está en estado «{estado}»;")


async def test_transiciones_desde_otro_estado_dan_409(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    publicar: Any,
    externos: Any,
    fabrica: Fabrica,
    evento_con_acuerdos: Any,
    proponer: Any,
) -> None:
    abierto, enlaces_abierto = await publicar()
    todas = ("proponer", "aprobar", "rechazar", "desierta")
    _son_409(
        await _intentos(
            proponer, cliente, comprador, aprobador, abierto, enlaces_abierto[0], *todas
        ),
        "abierto",
    )
    assert externos.recomendaciones() == []

    evento, enlaces = await evento_con_acuerdos()
    _son_409(
        await _intentos(
            proponer, cliente, comprador, aprobador, evento, enlaces[1], "aprobar", "rechazar"
        ),
        "en evaluación",
    )

    externos.umbral = UMBRAL_BAJO
    pendiente = await proponer(comprador, evento, enlaces[1])
    _son_409(
        await _intentos(
            proponer, cliente, comprador, aprobador, evento, enlaces[1], "proponer", "desierta"
        ),
        "pendiente de aprobación",
    )

    await _aprobar(cliente, aprobador, evento, _id_vigente(pendiente))
    _son_409(
        await _intentos(proponer, cliente, comprador, aprobador, evento, enlaces[1], *todas),
        "adjudicado",
    )
    assert len(await _filas(fabrica, evento)) == 1
    assert len(await _publicados(fabrica, "negociacion.adjudicada")) == 1
    assert await _publicados(fabrica, "negociacion.desierta") == []


async def test_un_evento_desierto_no_admite_ninguna_accion(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    con_acuerdos: Any,
    fabrica: Fabrica,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    await _accion(cliente, comprador, evento, "desierta", motivo="Sin propuestas viables.")
    todas = ("proponer", "aprobar", "rechazar", "desierta")
    _son_409(
        await _intentos(proponer, cliente, comprador, aprobador, evento, enlaces[1], *todas),
        "desierto",
    )
    assert len(await _publicados(fabrica, "negociacion.desierta")) == 1
    assert await _filas(fabrica, evento) == []


async def test_solo_el_comprador_propone_y_solo_el_aprobador_aprueba(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    admin: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    externos.umbral = UMBRAL_BAJO
    for quien in (aprobador, admin):
        assert (await proponer(quien, evento, enlaces[1])).status_code == 403
        desierta = await _accion(cliente, quien, evento, "desierta", motivo="Sin propuestas.")
        assert desierta.status_code == 403
    assert externos.recomendaciones() == []
    assert await _estado(cliente, comprador, evento) == "en_evaluacion"

    propuesta = await proponer(comprador, evento, enlaces[1])
    assert propuesta.status_code == 200
    for quien in (comprador, admin):  # pendiente: no es el estado lo que las frena
        aprobada = await _aprobar(cliente, quien, evento, _id_vigente(propuesta))
        assert aprobada.status_code == 403
        rechazada = await _rechazar(cliente, quien, evento, _id_vigente(propuesta))
        assert rechazada.status_code == 403
    assert await _estado(cliente, comprador, evento) == "pendiente_aprobacion"


async def test_una_sesion_que_no_es_candidata_da_422(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    con_acuerdos: Any,
    externos: Any,
    acordar: Any,
    sin_acuerdo: Any,
    evento_con_acuerdos: Any,
    proponer: Any,
) -> None:
    evento, _ = con_acuerdos
    ajeno, enlaces_ajeno = await evento_con_acuerdos()
    # Con otra sesión en acuerdo: si ninguna lo estuviera, el evento ya sería desierto.
    mixto, [enlace_acordada, enlace_sin_acuerdo] = await publicar()
    await acordar(enlace_acordada, _linea(mixto), "31.00")
    await sin_acuerdo(enlace_sin_acuerdo)
    externos.peticiones.clear()

    for evento_pedido, sesion in (
        (evento, {"sesion_id": str(uuid.uuid4())}),  # no existe
        (evento, enlaces_ajeno[0]),  # es de otra negociación
        (mixto, enlace_sin_acuerdo),  # no llegó a un acuerdo
    ):
        respuesta = await proponer(comprador, evento_pedido, sesion)
        assert respuesta.status_code == 422, respuesta.text
        assert respuesta.json()["codigo"] == "sesion_no_candidata"
        assert respuesta.json()["errores"][0]["campo"] == "sesion_id"
    assert externos.recomendaciones() == []
    assert await _estado(cliente, comprador, evento) == "en_evaluacion"
    assert await _estado(cliente, comprador, ajeno) == "en_evaluacion"
    assert await _estado(cliente, comprador, mixto) == "en_evaluacion"


async def test_si_inteligencia_falla_al_proponer_no_se_guarda_nada(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    fabrica: Fabrica,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    externos.caido = "intel"

    respuesta = await proponer(comprador, evento, enlaces[1])

    assert respuesta.status_code == 503, respuesta.text
    assert respuesta.json()["codigo"] == "dependencia_no_disponible"
    assert respuesta.json()["detail"] == SIN_RECOMENDACION
    assert await _estado(cliente, comprador, evento) == "en_evaluacion"
    assert await _filas(fabrica, evento) == []
    assert await _publicados(fabrica, "negociacion.adjudicada") == []
    assert await _bitacora(fabrica, evento) == []

    externos.caido = None  # y al reintentar, procede
    assert (await proponer(comprador, evento, enlaces[1])).status_code == 200


async def test_los_pesos_del_cuerpo_van_a_inteligencia_y_quedan_en_la_foto(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    respuesta = await proponer(comprador, evento, enlaces[1], pesos="50,20,15,15")
    assert respuesta.status_code == 200, respuesta.text
    pesos = {"costo": 50, "desempeno": 20, "riesgo": 15, "sla": 15}
    assert [p["pesos"] for p in externos.recomendaciones()] == [pesos]
    assert respuesta.json()["vigente"]["recomendacion"]["pesos"] == pesos
    assert respuesta.json()["recomendacion"]["pesos"] == pesos


@pytest.mark.parametrize("pesos", ["40,30,15", "40,30,15,16", "a,b,c,d", ""])
async def test_pesos_mal_formados_en_la_propuesta_dan_422_sin_llamar_a_inteligencia(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    pesos: str,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    respuesta = await proponer(comprador, evento, enlaces[1], pesos=pesos)
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["codigo"] == "pesos_invalidos"
    assert externos.recomendaciones() == []


async def test_dos_propuestas_a_la_vez_solo_una_prospera(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    fabrica: Fabrica,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    respuestas = await asyncio.gather(
        proponer(comprador, evento, enlaces[1]),
        proponer(comprador, evento, enlaces[1]),
    )
    assert sorted(r.status_code for r in respuestas) == [200, 409]
    [perdedora] = [r for r in respuestas if r.status_code == 409]
    assert perdedora.json()["codigo"] == "estado_invalido"
    assert len(await _filas(fabrica, evento)) == 1
    assert len(await _publicados(fabrica, "negociacion.adjudicada")) == 1


async def _renovacion_con_acuerdo(
    cliente: httpx.AsyncClient, comprador: dict[str, str], ids: dict[str, str], acordar: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    creada = await cliente.post(
        "/eventos",
        json={
            "tipo": "renovacion",
            "titulo": "Renovación del CRM",
            "fecha_limite": FECHA_LIMITE_RENOVACION,
            "proveedor_id": ids["nube_norte"],
            "contrato_id": ids["contrato"],
        },
        headers=comprador,
    )
    assert creada.status_code == 201, creada.text
    evento = creada.json()
    publicado = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
    assert publicado.status_code == 200, publicado.text
    [enlace] = publicado.json()["enlaces"]
    await acordar(enlace, _linea(evento), "31.00")
    return evento, enlace


async def test_en_una_renovacion_el_contrato_sigue_al_vigente(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    catalogo: None,
    ids: dict[str, str],
    acordar: Any,
    fabrica: Fabrica,
    proponer: Any,
) -> None:
    evento, enlace = await _renovacion_con_acuerdo(cliente, comprador, ids, acordar)

    respuesta = await proponer(comprador, evento, enlace)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["vigente"]["estado"] == "directa"
    [adjudicada] = await _publicados(fabrica, "negociacion.adjudicada")
    assert adjudicada["tipo"] == "renovacion"
    assert adjudicada["contrato"] == {
        "folio": f"C-{evento['folio']}",
        "tipo": "renovacion",
        "moneda": "USD",
        "fecha_inicio": "2026-11-01",  # el día siguiente al fin del contrato vigente
        "fecha_fin": "2027-10-31",
        "plazo_pago_dias": 30,
        "sla_disponibilidad": "99.50",
        "tope_aumento_pct": "5.00",
        "cuota_implementacion": "0",
        "lineas": [
            {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "120.0000", "precio_unitario": "31.00"}
        ],
    }


@pytest.mark.parametrize("umbral", [D("500000.00"), UMBRAL_BAJO], ids=["directa", "pendiente"])
async def test_una_renovacion_sin_contrato_vigente_da_409_y_no_guarda_nada(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    catalogo: None,
    ids: dict[str, str],
    acordar: Any,
    externos: Any,
    fabrica: Fabrica,
    umbral: D,
    proponer: Any,
) -> None:
    evento, enlace = await _renovacion_con_acuerdo(cliente, comprador, ids, acordar)
    async with fabrica() as bd, bd.begin():
        await bd.execute(
            update(Evento)
            .where(Evento.id == uuid.UUID(evento["id"]))
            .values(foto={"fecha": "2026-10-13T15:00:00+00:00", "contrato": None})
        )
    externos.umbral = umbral

    respuesta = await proponer(comprador, evento, enlace)

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["codigo"] == "contrato_vigente_faltante"
    assert "contrato vigente" in respuesta.json()["detail"]
    assert await _estado(cliente, comprador, evento) == "en_evaluacion"
    assert await _filas(fabrica, evento) == []
    assert await _publicados(fabrica, "negociacion.adjudicada") == []


async def test_cada_accion_queda_en_la_bitacora(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    externos: Any,
    fabrica: Fabrica,
    evento_con_acuerdos: Any,
    proponer: Any,
) -> None:
    evento, enlaces = await evento_con_acuerdos()
    externos.umbral = UMBRAL_BAJO
    primera = await proponer(comprador, evento, enlaces[1])
    await _rechazar(cliente, aprobador, evento, _id_vigente(primera), "Falta justificar.")
    segunda = await proponer(comprador, evento, enlaces[0], justificacion=JUSTIFICACION)
    await _aprobar(cliente, aprobador, evento, _id_vigente(segunda))
    filas = await _bitacora(fabrica, evento)
    assert sorted((f.accion, f.actor_tipo, f.actor_id) for f in filas) == [
        ("adjudicacion.aprobada", "aprobador", "aprobador-1"),
        ("adjudicacion.propuesta", "comprador", "comprador-1"),
        ("adjudicacion.propuesta", "comprador", "comprador-1"),
        ("adjudicacion.rechazada", "aprobador", "aprobador-1"),
    ]
    detalles = {f.accion: f.detalle for f in filas}
    assert detalles["adjudicacion.rechazada"]["motivo"] == "Falta justificar."
    assert detalles["adjudicacion.aprobada"]["proveedor"] == "Nube Norte S.A. de C.V."
    assert detalles["adjudicacion.aprobada"]["contrato_folio"] == f"C-{evento['folio']}"

    externos.umbral = D("500000.00")
    directo, enlaces_directo = await evento_con_acuerdos()
    await proponer(comprador, directo, enlaces_directo[1])
    desierto, _ = await evento_con_acuerdos()
    await _accion(cliente, comprador, desierto, "desierta", motivo="Sin propuestas viables.")
    assert [(f.accion, f.actor_tipo) for f in await _bitacora(fabrica, directo)] == [
        ("adjudicacion.directa", "comprador")
    ]
    [fila] = await _bitacora(fabrica, desierto)
    assert (fila.accion, fila.actor_tipo, fila.detalle) == (
        "evento.desierto",
        "comprador",
        {"motivo": "Sin propuestas viables."},
    )


async def test_la_lista_de_eventos_filtra_por_los_estados_nuevos(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    externos: Any,
    evento_con_acuerdos: Any,
    proponer: Any,
) -> None:
    evento, enlaces = await evento_con_acuerdos()
    otro, _ = await evento_con_acuerdos()

    async def _folios(estado: str) -> list[str]:
        respuesta = await cliente.get("/eventos", params={"estado": estado}, headers=comprador)
        assert respuesta.status_code == 200, respuesta.text
        return [e["folio"] for e in respuesta.json()["elementos"]]

    externos.umbral = UMBRAL_BAJO
    propuesta = await proponer(comprador, evento, enlaces[1])
    assert await _folios("pendiente_aprobacion") == [evento["folio"]]
    await _aprobar(cliente, aprobador, evento, _id_vigente(propuesta))
    await _accion(cliente, comprador, otro, "desierta", motivo="Sin propuestas viables.")
    assert await _folios("pendiente_aprobacion") == []
    assert await _folios("adjudicado") == [evento["folio"]]
    assert await _folios("desierto") == [otro["folio"]]


async def test_una_propuesta_nueva_no_se_decide_con_el_id_de_la_anterior(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    claves: ClavesPrueba,
    con_acuerdos: Any,
    externos: Any,
    fabrica: Fabrica,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    externos.umbral = UMBRAL_BAJO
    otro_aprobador = {"Authorization": f"Bearer {claves.token('aprobador', sub='aprobador-2')}"}
    # El aprobador 1 abre la propuesta 1; el aprobador 2 la rechaza; el comprador propone la 2
    # (otro proveedor, otro monto), y el aprobador 1 aprieta «Aprobar» sobre lo que abrió.
    primera = await proponer(comprador, evento, enlaces[1])
    assert (
        await _rechazar(cliente, otro_aprobador, evento, _id_vigente(primera))
    ).status_code == 200
    segunda = await proponer(comprador, evento, enlaces[0], justificacion=JUSTIFICACION)
    assert segunda.status_code == 200, segunda.text
    assert _id_vigente(primera) != _id_vigente(segunda)

    for ajena in (_id_vigente(primera), str(uuid.uuid4())):  # la anterior y una desconocida
        for respuesta in (
            await _aprobar(cliente, aprobador, evento, ajena),
            await _rechazar(cliente, aprobador, evento, ajena),
        ):
            assert respuesta.status_code == 409, respuesta.text
            assert respuesta.json()["codigo"] == "propuesta_distinta"
            assert respuesta.json()["detail"] == (
                "La propuesta cambió desde que usted la abrió. "
                "Revise la propuesta vigente antes de decidir."
            )
    assert await _estado(cliente, comprador, evento) == "pendiente_aprobacion"
    estados = {str(f.id): f.estado for f in await _filas(fabrica, evento)}
    assert estados == {_id_vigente(primera): "rechazada", _id_vigente(segunda): "pendiente"}
    assert await _publicados(fabrica, "negociacion.adjudicada") == []

    decidida = await _aprobar(cliente, aprobador, evento, _id_vigente(segunda))  # la que ve ahora
    assert decidida.status_code == 200, decidida.text
    assert decidida.json()["vigente"]["sesion_id"] == enlaces[0]["sesion_id"]


@pytest.mark.parametrize("ruta", ["adjudicacion/aprobar", "adjudicacion/rechazar"])
@pytest.mark.parametrize("cuerpo", [None, {}, {"adjudicacion_id": "no-es-un-uuid"}], ids=str)
async def test_aprobar_y_rechazar_exigen_el_id_de_la_propuesta(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    aprobador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    ruta: str,
    cuerpo: dict[str, Any] | None,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    externos.umbral = UMBRAL_BAJO
    await proponer(comprador, evento, enlaces[1])
    respuesta = await cliente.post(
        f"/eventos/{evento['id']}/{ruta}",
        json=None if cuerpo is None else cuerpo | {"motivo": "No procede."},
        headers=aprobador,
    )
    assert respuesta.status_code == 422, respuesta.text
    assert await _estado(cliente, comprador, evento) == "pendiente_aprobacion"


@pytest.mark.parametrize(
    ("umbral", "estado"),
    [(D("60000.00"), "directa"), (D("59999.99"), "pendiente")],
    ids=["costo_igual_al_umbral", "un_centavo_sobre_el_umbral"],
)
async def test_el_umbral_se_supera_solo_con_un_costo_mayor(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    umbral: D,
    estado: str,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    externos.umbral = umbral
    respuesta = await proponer(comprador, evento, enlaces[1])  # cuesta 60,000.00 MXN
    assert respuesta.status_code == 200, respuesta.text
    vigente = respuesta.json()["vigente"]
    assert D(vigente["costo_total_mxn"]) == D("60000.00")
    assert vigente["estado"] == estado


async def test_la_directa_se_inserta_ya_decidida_sin_actualizar_la_fila(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    fabrica: Fabrica,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    sentencias: list[str] = []
    motor = fabrica.kw["bind"].sync_engine

    def _anotar(*argumentos: Any) -> None:  # (conexion, cursor, sentencia, parametros, …)
        sentencias.append(str(argumentos[2]))

    event.listen(motor, "before_cursor_execute", _anotar)
    try:
        respuesta = await proponer(comprador, evento, enlaces[1])
    finally:
        event.remove(motor, "before_cursor_execute", _anotar)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["vigente"]["estado"] == "directa"
    assert len([s for s in sentencias if s.startswith("INSERT INTO adjudicacion")]) == 1
    assert [s for s in sentencias if s.startswith("UPDATE adjudicacion")] == []
    [fila] = await _filas(fabrica, evento)
    assert (fila.estado, fila.decidida_por_id, fila.contrato_folio) == (
        "directa",
        "comprador-1",
        f"C-{evento['folio']}",
    )


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("pesos", "1" * 16), ("justificacion", "x" * 2001)],
    ids=["pesos_de_16_caracteres", "justificacion_de_2001_caracteres"],
)
async def test_las_entradas_largas_se_acotan_antes_de_leerlas(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    con_acuerdos: Any,
    externos: Any,
    campo: str,
    valor: str,
    proponer: Any,
) -> None:
    evento, enlaces = con_acuerdos
    respuesta = await proponer(comprador, evento, enlaces[0], **{campo: valor})
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["errores"][0]["campo"] == f"body.{campo}"
    assert externos.recomendaciones() == []
    assert await _estado(cliente, comprador, evento) == "en_evaluacion"


async def test_la_justificacion_se_mide_recortada_aunque_se_lea_hasta_2000(
    cliente: httpx.AsyncClient, comprador: dict[str, str], con_acuerdos: Any, proponer: Any
) -> None:
    evento, enlaces = con_acuerdos
    texto = " " * 500 + "a" * 1000 + " " * 500  # 2,000 caracteres, 1,000 sin los espacios
    respuesta = await proponer(comprador, evento, enlaces[0], justificacion=texto)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["vigente"]["justificacion"] == "a" * 1000
