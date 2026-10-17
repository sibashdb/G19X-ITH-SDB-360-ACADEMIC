import uuid
from datetime import UTC, datetime
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
from negociacion.modelos import Adjudicacion, Evento
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
Fabrica = async_sessionmaker[AsyncSession]
FECHA_LIMITE_RENOVACION = "2026-10-20T15:00:00+00:00"


def _linea(evento: dict[str, Any]) -> str:
    return str(evento["lineas"][0]["id"])


async def _acordar(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    ofertar: Any,
    enlace: dict[str, Any],
    linea: str,
    precio: str,
    palancas: dict[str, str] | None = None,
) -> None:
    """Deja la sesión en acuerdo tentativo: el comprador toma el control y acepta la oferta."""
    sesion = enlace["sesion_id"]
    tomada = await cliente.post(
        f"/sesiones/{sesion}/control", json={"accion": "tomar"}, headers=comprador
    )
    assert tomada.status_code == 200, tomada.text
    ofrecida = await ofertar(enlace, {linea: precio}, palancas)
    assert ofrecida.status_code == 200, ofrecida.text
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


async def _evaluacion(
    cliente: httpx.AsyncClient, evento: dict[str, Any], encabezados: dict[str, str], pesos: str = ""
) -> httpx.Response:
    url = f"/eventos/{evento['id']}/evaluacion" + (f"?pesos={pesos}" if pesos else "")
    return await cliente.get(url, headers=encabezados)


@pytest.fixture
async def con_acuerdos(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, ofertar: Any
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Un evento en evaluación con dos acuerdos tentativos: a 31.00 y a 30.00."""
    evento, enlaces = await publicar()
    await _acordar(cliente, comprador, ofertar, enlaces[0], _linea(evento), "31.00")
    await _acordar(cliente, comprador, ofertar, enlaces[1], _linea(evento), "30.00")
    return evento, enlaces


async def test_la_evaluacion_pide_la_recomendacion_con_los_acuerdos(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    externos: Any,
) -> None:
    evento, enlaces = await publicar()
    linea = _linea(evento)
    # El primer proveedor acepta la propuesta del agente; con el segundo, el comprador acepta.
    propuesta = (await ofertar(enlaces[0], {linea: "40.00"})).json()["ultima_propuesta"]
    await ofertar(enlaces[0], propuesta["precios"], propuesta["palancas"])
    await _acordar(cliente, comprador, ofertar, enlaces[1], linea, "31.00")

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
    ofertar: Any,
    externos: Any,
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
    await _acordar(cliente, comprador, ofertar, primero, _linea(evento), "31.00", acordadas)
    await _sin_acuerdo(cliente, comprador, segundo)

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
    ofertar: Any,
    externos: Any,
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
    await _acordar(cliente, comprador, ofertar, enlace, _linea(evento), "31.00")

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
    assert "abierto" in respuesta.json()["detail"]
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
) -> None:
    evento, [enlace] = await publicar(proveedores=[ids["nube_norte"]])
    await _sin_acuerdo(cliente, comprador, enlace)
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
async def test_muestra_la_vigente_y_el_historial_y_recalcula_la_recomendacion(
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

    respuesta = await _evaluacion(cliente, evento, comprador)

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
    # La recomendación se calcula de nuevo; la foto de la propuesta vive en `vigente`.
    assert len(externos.recomendaciones()) == 1
    assert len(cuerpo["recomendacion"]["candidatos"]) == 2


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
