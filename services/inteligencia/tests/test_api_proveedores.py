import unicodedata
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from generador.modelo import DatosSinteticos, generar
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
Cargar = Callable[[DatosSinteticos], Awaitable[None]]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
IdDe = Callable[[str], str]
Cabeceras = dict[str, str]
KPIS = ["sla", "resolucion", "incidentes", "entregas", "satisfaccion"]


def _sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


async def _lista(
    cliente: httpx.AsyncClient, comprador: Cabeceras, **params: Any
) -> list[dict[str, Any]]:
    cuerpo = (
        await cliente.get("/proveedores", params={"tamano": 100, **params}, headers=comprador)
    ).json()
    assert cuerpo["total"] == len(cuerpo["elementos"])
    return list(cuerpo["elementos"])


@pytest.fixture
async def datos(cargar: Cargar) -> DatosSinteticos:
    generados = generar(42, n_proveedores=15)
    await cargar(generados)
    return generados


async def test_lista_con_puntuacion_gasto_y_alertas(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos, hoy: date
) -> None:
    proveedores = await _lista(cliente, comprador)
    assert len(proveedores) == 15
    assert [p["nombre"] for p in proveedores] == sorted(
        (p["nombre"] for p in proveedores), key=_sin_acentos
    )
    alertas = (await cliente.get("/alertas", params={"limite": 200}, headers=comprador)).json()
    assert alertas["total"] <= 200
    por_proveedor = Counter(a["proveedor_id"] for a in alertas["elementos"])
    folios = {
        (fila["folio"], fila["rfc_proveedor"])
        for fila in datos.contratos
        if date.fromisoformat(fila["fecha_inicio"]) <= hoy <= date.fromisoformat(fila["fecha_fin"])
    }
    vigentes = Counter(rfc for _, rfc in folios)
    for p in proveedores:
        assert p["alertas"] == por_proveedor[p["id"]], p["nombre"]
        assert p["contratos_vigentes"] == vigentes[p["rfc"]], p["nombre"]
        assert 0 <= p["puntuacion"] <= 100
        assert p["confianza"] in {"normal", "baja"}
    tablero = (await cliente.get("/tablero", headers=comprador)).json()
    gasto = sum(Decimal(p["gasto_anual"]) for p in proveedores)
    assert abs(gasto - Decimal(tablero["gasto_anual"])) <= Decimal("0.01") * len(proveedores)


async def test_lista_filtra_ordena_y_pagina(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    todos = await _lista(cliente, comprador)
    azteca = await _lista(cliente, comprador, busqueda="AZTECA")
    assert azteca and all("Azteca" in p["nombre"] for p in azteca)
    rfc = todos[0]["rfc"]
    assert [p["rfc"] for p in await _lista(cliente, comprador, busqueda=rfc.lower())] == [rfc]
    nube = await _lista(cliente, comprador, categoria="nube")
    assert nube and all("nube" in p["categorias"] for p in nube)
    inactivos = await _lista(cliente, comprador, estado="inactivos")
    assert len(inactivos) == sum(not p.activo for p in datos.proveedores)
    en_riesgo = await _lista(cliente, comprador, en_riesgo="true")
    assert all(p["en_riesgo"] for p in en_riesgo)
    por_puntuacion = await _lista(cliente, comprador, orden="puntuacion", direccion="desc")
    puntuaciones = [p["puntuacion"] for p in por_puntuacion]
    assert puntuaciones == sorted(puntuaciones, reverse=True)
    pagina = (
        await cliente.get("/proveedores", params={"pagina": 2, "tamano": 5}, headers=comprador)
    ).json()
    assert pagina == {"total": 15, "elementos": todos[5:10]}


async def test_la_busqueda_ignora_acentos_y_mayusculas(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    [con_acento] = [p for p in datos.proveedores if p.nombre.startswith("Código")]
    for busqueda in ("codigo", "CODIGO", "código", "CÓDIGO azteca"):
        encontrados = await _lista(cliente, comprador, busqueda=busqueda)
        assert [p["rfc"] for p in encontrados] == [con_acento.rfc], busqueda


async def test_un_proveedor_sin_puntuacion_va_al_final_en_las_dos_direcciones(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    datos: DatosSinteticos,
    aplicar_evento: AplicarEvento,
) -> None:
    sin_desempeno = str(uuid.uuid4())
    await aplicar_evento(
        "proveedor.actualizado",
        {
            "id": sin_desempeno,
            "rfc": "AAA010101AAA",
            "nombre": "Aaa Recién Llegado S.A.",  # el primero por nombre, para que el orden cuente
            "tamano": "micro",
            "categorias": ["nube"],
            "activo": True,
        },
    )
    for direccion in ("asc", "desc"):
        lista = await _lista(cliente, comprador, orden="puntuacion", direccion=direccion)
        assert len(lista) == 16, direccion
        ultimo = lista[-1]
        assert ultimo["id"] == sin_desempeno, direccion
        assert (ultimo["puntuacion"], ultimo["confianza"], ultimo["tendencia"]) == (
            None,
            None,
            None,
        )
        puntuaciones = [p["puntuacion"] for p in lista[:-1]]
        assert None not in puntuaciones
        assert puntuaciones == sorted(puntuaciones, reverse=direccion == "desc"), direccion


async def test_en_riesgo_devuelve_a_los_activos_con_puntuacion(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    datos: DatosSinteticos,
    aplicar_evento: AplicarEvento,
    fabrica: Fabrica,
    id_estable: IdDe,
) -> None:
    # Con el umbral en 100, todo proveedor activo con puntuación tiene una alerta de riesgo.
    async with fabrica() as sesion, sesion.begin():
        await sesion.execute(
            text("UPDATE configuracion SET umbral_riesgo = 100, actualizado_en = now()")
        )
    inactivo = datos.proveedores[0]
    await aplicar_evento(
        "proveedor.actualizado",
        {
            "id": id_estable(inactivo.rfc),
            "rfc": inactivo.rfc,
            "nombre": inactivo.nombre,
            "tamano": inactivo.tamano,
            "categorias": list(inactivo.categorias),
            "activo": False,
        },
    )
    sin_desempeno = str(uuid.uuid4())
    await aplicar_evento(
        "proveedor.actualizado",
        {
            "id": sin_desempeno,
            "rfc": "BBB020202BBB",
            "nombre": "Sin Desempeño S.A.",
            "tamano": "micro",
            "categorias": ["soporte"],
            "activo": True,
        },
    )
    todos = await _lista(cliente, comprador)
    esperados = {p["id"] for p in todos if p["activo"] and p["puntuacion"] is not None}
    assert len(esperados) == 14  # 15 menos el inactivo; el nuevo no tiene puntuación
    en_riesgo = await _lista(cliente, comprador, en_riesgo="true")
    assert {p["id"] for p in en_riesgo} == esperados
    assert all(p["en_riesgo"] for p in en_riesgo)
    resto = await _lista(cliente, comprador, en_riesgo="false")
    assert {p["id"] for p in resto} == {id_estable(inactivo.rfc), sin_desempeno}
    assert not any(p["en_riesgo"] for p in resto)


async def test_ordena_por_gasto_anual(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    for direccion in ("asc", "desc"):
        lista = await _lista(cliente, comprador, orden="gasto_anual", direccion=direccion)
        gastos = [Decimal(p["gasto_anual"]) for p in lista]
        assert gastos == sorted(gastos, reverse=direccion == "desc"), direccion
        assert len(set(gastos)) > 1, direccion  # que el orden no sea trivial


@pytest.mark.parametrize(
    "params",
    [{"orden": "rfc"}, {"direccion": "arriba"}, {"tamano": "0"}, {"categoria": "otra"}],
)
async def test_lista_valida_los_parametros(
    cliente: httpx.AsyncClient, comprador: Cabeceras, params: dict[str, str]
) -> None:
    respuesta = await cliente.get("/proveedores", params=params, headers=comprador)
    assert respuesta.status_code == 422


async def test_puntuacion_de_un_proveedor(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    proveedor = (await _lista(cliente, comprador))[0]
    respuesta = await cliente.get(f"/proveedores/{proveedor['id']}/puntuacion", headers=comprador)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["puntuacion"] == proveedor["puntuacion"]
    assert cuerpo["categoria"] == proveedor["categorias"][0]
    assert cuerpo["historial_corto"] == (cuerpo["meses"] < 6)
    assert [c["kpi"] for c in cuerpo["componentes"]] == KPIS
    assert all(0 <= c["percentil"] <= 100 for c in cuerpo["componentes"])
    assert 0 < len(cuerpo["historial"]) <= 12
    assert cuerpo["historial"][-1] == {"mes": "2026-09-01", "puntuacion": cuerpo["puntuacion"]}


async def test_un_proveedor_que_no_existe(cliente: httpx.AsyncClient, comprador: Cabeceras) -> None:
    for ruta in ("puntuacion", "mercado"):
        respuesta = await cliente.get(f"/proveedores/{uuid.uuid4()}/{ruta}", headers=comprador)
        assert (respuesta.status_code, respuesta.json()["codigo"]) == (
            404,
            "proveedor_no_encontrado",
        )
        invalido = await cliente.get(f"/proveedores/no-es-un-id/{ruta}", headers=comprador)
        assert invalido.status_code == 422


async def test_precio_contra_mercado_de_un_proveedor(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    proveedor = max(await _lista(cliente, comprador), key=lambda p: p["contratos_vigentes"])
    lineas = (
        await cliente.get(f"/proveedores/{proveedor['id']}/mercado", headers=comprador)
    ).json()
    assert len({linea["contrato_id"] for linea in lineas}) == proveedor["contratos_vigentes"]
    for linea in lineas:
        if linea["posicion"] is None:
            assert (linea["p50"], linea["ahorro_potencial"]) == (None, "0.00")
            continue
        p25, p50, p75 = (Decimal(linea[k]) for k in ("p25", "p50", "p75"))
        precio = Decimal(linea["precio"])
        assert p25 <= p50 <= p75
        if linea["posicion"] == "sobre_p75":
            assert precio >= p75 and Decimal(linea["ahorro_potencial"]) >= 0
        else:
            assert linea["ahorro_potencial"] == "0.00"
        if linea["posicion"] == "bajo_p25":
            assert precio <= p25


async def test_ranking(
    cliente: httpx.AsyncClient, comprador: Cabeceras, datos: DatosSinteticos
) -> None:
    proveedores = await _lista(cliente, comprador)
    ranking = (await cliente.get("/ranking", headers=comprador)).json()
    assert [f["posicion"] for f in ranking] == list(range(1, len(ranking) + 1))
    puntuaciones = [f["puntuacion"] for f in ranking]
    assert puntuaciones == sorted(puntuaciones, reverse=True)
    assert {f["proveedor_id"] for f in ranking} == {p["id"] for p in proveedores if p["activo"]}
    for fila in ranking:
        assert list(fila["componentes"]) == KPIS
        assert fila["historial_corto"] == (fila["meses"] < 6)
    nube = (await cliente.get("/ranking", params={"categoria": "nube"}, headers=comprador)).json()
    assert {f["proveedor_id"] for f in nube} == {
        p["id"] for p in proveedores if p["activo"] and "nube" in p["categorias"]
    }
    assert [f["posicion"] for f in nube] == list(range(1, len(nube) + 1))
