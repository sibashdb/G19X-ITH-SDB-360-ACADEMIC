import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from comun.pruebas import ClavesPrueba
from generador.modelo import DatosSinteticos, generar
from inteligencia.dominio.adjudicacion import tendencia_incidentes

pytestmark = pytest.mark.integracion

Cargar = Callable[[DatosSinteticos], Awaitable[None]]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
IdDe = Callable[[str], str]
Cabeceras = dict[str, str]

RUTA = "/adjudicacion/recomendacion"
CENTAVO = Decimal("0.01")
CUOTA = Decimal("1000.00")
CANTIDAD = Decimal("10")
PLAZO = 12


@pytest.fixture
async def datos(cargar: Cargar) -> DatosSinteticos:
    generados = generar(42, n_proveedores=15)
    await cargar(generados)
    return generados


def candidato(i: int, proveedor_id: str, id_de: IdDe, **cambios: Any) -> dict[str, Any]:
    """Un acuerdo con una línea mensual; el precio sube con `i`, así que el costo también."""
    return {
        "id": id_de(f"sesion-{i}"),
        "proveedor_id": proveedor_id,
        "nombre": f"Proveedor {i}",
        "plazo_meses": PLAZO,
        "cuota_implementacion": str(CUOTA),
        "sla": f"{99.9 - i / 10:.1f}",
        "lineas": [
            {
                "codigo_servicio": "SAAS-OFI-BAS",
                "unidad": "usuario_mes",
                "cantidad": str(CANTIDAD),
                "precio": str(Decimal("100.00") + 10 * i),
            }
        ],
    } | cambios


def cuerpo(
    datos: DatosSinteticos, n: int, id_de: IdDe, moneda: str = "MXN", **cambios: Any
) -> dict[str, Any]:
    return {
        "moneda": moneda,
        "candidatos": [
            candidato(i, id_de(p.rfc), id_de) for i, p in enumerate(datos.proveedores[:n])
        ],
    } | cambios


async def test_recomienda_y_explica(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos, id_estable: IdDe
) -> None:
    r = await cliente.post(RUTA, json=cuerpo(datos, 3, id_estable), headers=comprador)
    assert r.status_code == 200
    c = r.json()
    assert [x["lugar"] for x in c["candidatos"]] == [1, 2, 3]
    assert c["recomendado"] == c["candidatos"][0]["id"]
    assert c["pesos"] == {"costo": 40, "desempeno": 30, "riesgo": 15, "sla": 15}
    assert c["umbral_aprobacion"] == "500000.00" and c["explicacion"][0].startswith(
        "Recomendamos a "
    )
    puntajes = [x["puntaje"] for x in c["candidatos"]]
    assert puntajes == sorted(puntajes, reverse=True)
    assert c["margen"] == pytest.approx(puntajes[0] - puntajes[1])
    assert {s["criterio"] for s in c["sensibilidad"]} == {"costo", "desempeno", "riesgo", "sla"}
    for x in c["candidatos"]:
        assert (
            set(x["normalizados"]) == set(x["aportes"]) == {"costo", "desempeno", "riesgo", "sla"}
        )
        assert x["puntaje"] == pytest.approx(sum(x["aportes"].values()))
        assert x["riesgo"]["nivel"] in {"bajo", "medio", "alto"}
        assert x["costo_total"] == x["costo_total_mxn"]  # en pesos no hay conversión
    assert c["tipo_cambio"]["usd_mxn"]  # el más reciente, aunque el evento sea en pesos


async def test_usa_los_pesos_del_cuerpo(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos, id_estable: IdDe
) -> None:
    pesos = {"costo": 100, "desempeno": 0, "riesgo": 0, "sla": 0}
    r = await cliente.post(RUTA, json=cuerpo(datos, 4, id_estable, pesos=pesos), headers=comprador)
    assert r.status_code == 200
    c = r.json()
    assert c["pesos"] == pesos
    costos = [Decimal(x["costo_total_mxn"]) for x in c["candidatos"]]
    assert costos == sorted(costos)  # solo cuenta el costo: gana el más barato
    assert c["candidatos"][0]["puntaje"] == pytest.approx(100.0)
    assert c["candidatos"][0]["id"] == id_estable("sesion-0")


@pytest.mark.parametrize(
    "pesos",
    [
        {"costo": 40, "desempeno": 30, "riesgo": 15, "sla": 10},  # suman 95
        {"costo": 50, "desempeno": 30, "riesgo": 15, "sla": 15},  # suman 110
    ],
)
async def test_pesos_que_no_suman_100(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    datos: DatosSinteticos,
    id_estable: IdDe,
    pesos: dict[str, int],
) -> None:
    r = await cliente.post(RUTA, json=cuerpo(datos, 3, id_estable, pesos=pesos), headers=comprador)
    assert r.status_code == 422
    assert r.json()["codigo"] == "pesos_invalidos"
    assert r.json()["errores"][0]["campo"] == "body.pesos"


async def test_pesos_fuera_de_rango(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos, id_estable: IdDe
) -> None:
    pesos = {"costo": 120, "desempeno": -10, "riesgo": -5, "sla": -5}
    r = await cliente.post(RUTA, json=cuerpo(datos, 3, id_estable, pesos=pesos), headers=comprador)
    assert r.status_code == 422


async def test_candidatos_repetidos_o_vacios(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos, id_estable: IdDe
) -> None:
    repetidos = cuerpo(datos, 3, id_estable)
    repetidos["candidatos"][2]["id"] = repetidos["candidatos"][0]["id"]
    demasiados = {
        "moneda": "MXN",
        "candidatos": [candidato(i, str(uuid.uuid4()), id_estable) for i in range(11)],
    }
    sin_lineas = cuerpo(datos, 2, id_estable)
    sin_lineas["candidatos"][1]["lineas"] = []
    for mal in (
        cuerpo(datos, 0, id_estable),
        repetidos,
        demasiados,
        sin_lineas,
    ):
        r = await cliente.post(RUTA, json=mal, headers=comprador)
        assert r.status_code == 422, mal["candidatos"][:1]


async def test_proveedor_sin_puntuacion_usa_la_media_de_su_categoria(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    datos: DatosSinteticos,
    id_estable: IdDe,
    aplicar_evento: AplicarEvento,
) -> None:
    nuevo = str(
        uuid.uuid4()
    )  # existe en la copia, pero sin desempeño: usa la media de su categoría
    await aplicar_evento(
        "proveedor.actualizado",
        {
            "id": nuevo,
            "rfc": "AAA010101AAA",
            "nombre": "Recién Llegado S.A.",
            "tamano": "micro",
            "categorias": ["nube"],
            "activo": True,
        },
    )
    desconocido = str(
        uuid.uuid4()
    )  # inteligencia no lo conoce: sin categoría, usa la media de todos
    proveedores = (
        await cliente.get("/proveedores", params={"tamano": 100}, headers=comprador)
    ).json()["elementos"]
    con_puntuacion = [p for p in proveedores if p["puntuacion"] is not None]
    media_todos = sum(p["puntuacion"] for p in con_puntuacion) / len(con_puntuacion)
    de_nube = [p["puntuacion"] for p in con_puntuacion if p["categorias"][0] == "nube"]
    media_nube = sum(de_nube) / len(de_nube)
    assert abs(media_nube - media_todos) > 0.5  # que la prueba distinga una media de la otra

    cuerpo_ = cuerpo(datos, 2, id_estable)
    cuerpo_["candidatos"] += [
        candidato(2, nuevo, id_estable),
        candidato(3, desconocido, id_estable),
    ]
    r = await cliente.post(RUTA, json=cuerpo_, headers=comprador)
    assert r.status_code == 200
    por_id = {p["id"]: p for p in proveedores}
    for x in r.json()["candidatos"]:
        if x["proveedor_id"] in (nuevo, desconocido):
            media = media_nube if x["proveedor_id"] == nuevo else media_todos
            assert x["riesgo"]["sin_historial"] is True
        else:
            media = por_id[x["proveedor_id"]]["puntuacion"]
        assert x["desempeno"] == pytest.approx(media, abs=0.1)  # /proveedores redondea a 0.1


async def test_sin_nadie_con_puntuacion_el_desempeno_es_50(
    cliente: httpx.AsyncClient, comprador: Cabeceras, id_estable: IdDe
) -> None:
    desconocido = [candidato(i, str(uuid.uuid4()), id_estable) for i in range(2)]
    r = await cliente.post(
        RUTA, json={"moneda": "MXN", "candidatos": desconocido}, headers=comprador
    )
    assert r.status_code == 200
    c = r.json()
    assert [x["desempeno"] for x in c["candidatos"]] == [50.0, 50.0]
    assert c["tipo_cambio"] is None  # sin tipos de cambio registrados


async def test_en_usd_convierte_el_costo_a_mxn(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    datos: DatosSinteticos,
    id_estable: IdDe,
    hoy: date,
) -> None:
    r = await cliente.post(RUTA, json=cuerpo(datos, 3, id_estable, moneda="USD"), headers=comprador)
    assert r.status_code == 200
    c = r.json()
    ultimo = max(
        (f for f in datos.tipo_cambio if date.fromisoformat(f["periodo"]) <= hoy),
        key=lambda f: f["periodo"],
    )
    assert c["tipo_cambio"] == {"periodo": ultimo["periodo"], "usd_mxn": ultimo["usd_mxn"]}
    for x in c["candidatos"]:
        precio = Decimal("100.00") + 10 * int(x["nombre"].split()[-1])
        costo = CANTIDAD * precio * PLAZO + CUOTA
        assert Decimal(x["costo_total"]) == costo
        assert abs(Decimal(x["costo_total_mxn"]) - costo * Decimal(ultimo["usd_mxn"])) <= CENTAVO


async def test_el_riesgo_usa_el_gasto_vigente_y_los_incidentes(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos, id_estable: IdDe
) -> None:
    proveedores = (
        await cliente.get("/proveedores", params={"tamano": 100}, headers=comprador)
    ).json()["elementos"]
    por_id = {p["id"]: p for p in proveedores}
    gasto_total = sum(Decimal(p["gasto_anual"]) for p in proveedores)
    r = await cliente.post(RUTA, json=cuerpo(datos, 10, id_estable), headers=comprador)
    assert r.status_code == 200
    for x in r.json()["candidatos"]:
        proveedor = por_id[x["proveedor_id"]]
        # costo anual del candidato: (costo total - cuota) / plazo * 12, en pesos
        anual = (Decimal(x["costo_total_mxn"]) - CUOTA) / PLAZO * 12
        esperada = float((Decimal(proveedor["gasto_anual"]) + anual) / (gasto_total + anual))
        assert x["riesgo"]["concentracion"] == pytest.approx(esperada, abs=1e-6), proveedor[
            "nombre"
        ]
        rfc = proveedor["rfc"]
        filas = sorted(
            (f for f in datos.desempeno if f["rfc_proveedor"] == rfc), key=lambda f: f["periodo"]
        )
        assert x["riesgo"]["tendencia"] == tendencia_incidentes(
            [float(f["incidentes_criticos"]) for f in filas]
        )
        assert x["riesgo"]["sin_historial"] is (proveedor["confianza"] == "baja")
        assert x["riesgo"]["valor"] == pytest.approx(
            (x["riesgo"]["concentracion"] + x["riesgo"]["tendencia"] + x["riesgo"]["sin_historial"])
            / 3
        )


async def test_sin_token_401_y_proveedor_externo_no_entra(
    cliente: httpx.AsyncClient, claves: ClavesPrueba, id_estable: IdDe
) -> None:
    mal = {"moneda": "MXN", "candidatos": [candidato(0, str(uuid.uuid4()), id_estable)]}
    assert (await cliente.post(RUTA, json=mal)).status_code == 401
    externo = {"Authorization": f"Bearer {claves.token('proveedor')}"}
    assert (await cliente.post(RUTA, json=mal, headers=externo)).status_code == 403
