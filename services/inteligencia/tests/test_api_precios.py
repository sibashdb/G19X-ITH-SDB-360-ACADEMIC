import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from generador.modelo import DatosSinteticos, generar
from inteligencia.dominio.precios import Observacion
from inteligencia.modelo import ajustar_modelo, guardar_modelo
from inteligencia.modelos import ModeloBenchmark
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
Cargar = Callable[[DatosSinteticos], Awaitable[None]]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
Cabeceras = dict[str, str]
INICIO_VENTANA = date(2024, 9, 1)  # 24 meses antes de HOY: la ventana empieza después


def _servicio(codigo: str, activo: bool = True) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "codigo": codigo,
        "nombre": f"Servicio {codigo}",
        "categoria": "nube",
        "unidad": "vcpu_mes",
        "moneda": "USD",
        "activo": activo,
    }


async def _mas_visto(cliente: httpx.AsyncClient, comprador: Cabeceras) -> dict[str, Any]:
    servicios = (await cliente.get("/precios/servicios", headers=comprador)).json()
    return max(servicios, key=lambda s: (s["observaciones"], s["codigo"]))


async def _registrar_modelo(fabrica: Fabrica, artefacto: str) -> None:
    async with fabrica() as sesion, sesion.begin():
        sesion.add(
            ModeloBenchmark(
                version=1,
                entrenado_en=datetime.now(UTC),
                origen="manual",
                actor_nombre="admin-1",
                observaciones=100,
                datos_hasta=date(2026, 9, 1),
                mape=Decimal("0.08"),
                mape_linea_base=Decimal("0.09"),
                cobertura=Decimal("0.5"),
                pinball=Decimal("0.02"),
                promovido=True,
                artefacto=artefacto,
            )
        )


async def test_servicios_activos_con_sus_observaciones(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    aplicar_evento: AplicarEvento,
    hoy: date,
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    await aplicar_evento("servicio.actualizado", _servicio("NUEVO-SERV"))
    await aplicar_evento("servicio.actualizado", _servicio("VIEJO-SERV", activo=False))
    lista = (await cliente.get("/precios/servicios", headers=comprador)).json()
    assert [s["nombre"] for s in lista] == sorted(s["nombre"] for s in lista)
    servicios = {s["codigo"]: s for s in lista}
    assert "VIEJO-SERV" not in servicios
    assert servicios["NUEVO-SERV"]["observaciones"] == 0
    assert len(servicios) == len(datos.servicios) + 1
    for codigo in (s.codigo for s in datos.servicios):
        esperadas = sum(
            1
            for fila in datos.contratos
            if fila["codigo_servicio"] == codigo
            and INICIO_VENTANA < date.fromisoformat(fila["fecha_inicio"]) <= hoy
        )
        assert servicios[codigo]["observaciones"] == esperadas, codigo


async def test_referencia_de_un_servicio_sin_contratos(
    cliente: httpx.AsyncClient, comprador: Cabeceras, aplicar_evento: AplicarEvento
) -> None:
    await aplicar_evento("servicio.actualizado", _servicio("NUEVO-SERV"))
    sin_datos = await cliente.get(
        "/precios/servicios/nuevo-serv/referencia", params={"cantidad": "10"}, headers=comprador
    )
    assert (sin_datos.status_code, sin_datos.json()["codigo"]) == (404, "sin_observaciones")
    inexistente = await cliente.get(
        "/precios/servicios/NO-EXISTE/referencia", params={"cantidad": "10"}, headers=comprador
    )
    assert (inexistente.status_code, inexistente.json()["codigo"]) == (
        404,
        "servicio_no_encontrado",
    )


@pytest.mark.parametrize(
    ("ruta", "params"),
    [
        ("/precios/servicios/NUBE-VM/referencia", {"cantidad": "0"}),
        ("/precios/servicios/NUBE-VM/referencia", {"cantidad": "-5"}),
        ("/precios/servicios/NUBE-VM/referencia", {}),
        ("/precios/servicios/NUBE-VM/referencia", {"cantidad": "10", "plazo": "0"}),
        ("/precios/servicios/NUBE-VM/referencia", {"cantidad": "10", "plazo": "121"}),
        ("/precios/servicios/a$/referencia", {"cantidad": "10"}),
        ("/precios/servicios/NUBE-VM/historial", {"cantidad": "0"}),
        ("/precios/sobreprecios", {"codigo": "a$"}),
    ],
)
async def test_los_parametros_se_validan(
    cliente: httpx.AsyncClient, comprador: Cabeceras, ruta: str, params: dict[str, str]
) -> None:
    respuesta = await cliente.get(ruta, params=params, headers=comprador)
    assert respuesta.status_code == 422


async def test_referencia_con_la_linea_base(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=15))
    servicio = await _mas_visto(cliente, comprador)
    respuesta = await cliente.get(
        f"/precios/servicios/{servicio['codigo']}/referencia",
        params={"cantidad": "50", "plazo": "12"},
        headers=comprador,
    )
    assert respuesta.status_code == 200
    ref = respuesta.json()
    assert Decimal(ref["p25"]) <= Decimal(ref["p50"]) <= Decimal(ref["p75"])
    assert (ref["metodo"], ref["version"]) == ("linea_base", None)
    assert (ref["moneda"], ref["unidad"]) == (servicio["moneda"], servicio["unidad"])
    assert (ref["cantidad"], ref["plazo"], ref["fecha"]) == ("50", 12, "2026-09-15")
    assert ref["confianza"] in {"normal", "baja"}
    assert 0 < ref["observaciones"] <= servicio["observaciones"]


async def test_la_referencia_usa_el_modelo_activo(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    fabrica: Fabrica,
    generadas: list[Observacion],
    tmp_path: Path,
) -> None:
    await cargar(generar(42, n_proveedores=15))
    ruta = tmp_path / "modelo-v1.joblib"
    guardar_modelo(ajustar_modelo(generadas, 0.045, version=1), ruta)
    await _registrar_modelo(fabrica, str(ruta))
    servicio = await _mas_visto(cliente, comprador)
    ref = (
        await cliente.get(
            f"/precios/servicios/{servicio['codigo']}/referencia",
            params={"cantidad": "50"},
            headers=comprador,
        )
    ).json()
    assert (ref["metodo"], ref["version"]) == ("modelo", 1)
    assert Decimal(ref["p25"]) <= Decimal(ref["p50"]) <= Decimal(ref["p75"])


async def test_promover_un_modelo_con_el_contexto_ya_calculado_cambia_la_referencia(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    fabrica: Fabrica,
    generadas: list[Observacion],
    tmp_path: Path,
) -> None:
    await cargar(generar(42, n_proveedores=15))
    servicio = await _mas_visto(cliente, comprador)  # deja el contexto calculado
    ruta_referencia = f"/precios/servicios/{servicio['codigo']}/referencia"
    antes = (
        await cliente.get(ruta_referencia, params={"cantidad": "50"}, headers=comprador)
    ).json()
    assert (antes["metodo"], antes["version"]) == ("linea_base", None)
    ruta = tmp_path / "modelo-v1.joblib"
    guardar_modelo(ajustar_modelo(generadas, 0.045, version=1), ruta)
    await _registrar_modelo(fabrica, str(ruta))
    despues = (
        await cliente.get(ruta_referencia, params={"cantidad": "50"}, headers=comprador)
    ).json()
    assert (despues["metodo"], despues["version"]) == ("modelo", 1)


async def test_un_modelo_sin_artefacto_usa_la_linea_base(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    fabrica: Fabrica,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await cargar(generar(42, n_proveedores=15))
    await _registrar_modelo(fabrica, str(tmp_path / "no-existe.joblib"))
    servicio = await _mas_visto(cliente, comprador)
    respuesta = await cliente.get(
        f"/precios/servicios/{servicio['codigo']}/referencia",
        params={"cantidad": "50"},
        headers=comprador,
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["metodo"] == "linea_base"
    assert "No se pudo cargar el modelo de precios v1" in caplog.text


async def test_historial_de_precios(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=15))
    servicio = await _mas_visto(cliente, comprador)
    ruta = f"/precios/servicios/{servicio['codigo']}/historial"
    cuerpo = (await cliente.get(ruta, headers=comprador)).json()
    assert cuerpo["moneda"] == servicio["moneda"]
    fechas = [p["fecha"] for p in cuerpo["puntos"]]
    assert len(fechas) == servicio["observaciones"]
    assert fechas == sorted(fechas)
    assert "2024-09-01" < fechas[0] and fechas[-1] <= "2026-09-15"
    meses = [b["mes"] for b in cuerpo["bandas"]]
    assert meses == sorted(meses)
    assert 0 < len(meses) <= 24 and meses[-1] == "2026-09-01"
    assert all(
        Decimal(b["p25"]) <= Decimal(b["p50"]) <= Decimal(b["p75"]) for b in cuerpo["bandas"]
    )
    con_cantidad = (await cliente.get(ruta, params={"cantidad": "5"}, headers=comprador)).json()
    assert con_cantidad["cantidad"] == "5"


async def test_sobreprecios(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=15))
    todos = (await cliente.get("/precios/sobreprecios", headers=comprador)).json()
    assert todos
    for fila in todos:
        assert Decimal(fila["precio"]) >= Decimal(fila["p75"])
        assert Decimal(fila["ahorro_potencial"]) >= 0
        assert Decimal(fila["ahorro_potencial_mxn"]) >= 0
    ahorros = [Decimal(fila["ahorro_potencial_mxn"]) for fila in todos]
    assert ahorros == sorted(ahorros, reverse=True)
    codigo = todos[0]["codigo_servicio"]
    del_servicio = (
        await cliente.get(
            "/precios/sobreprecios", params={"codigo": codigo.lower()}, headers=comprador
        )
    ).json()
    assert del_servicio == [fila for fila in todos if fila["codigo_servicio"] == codigo]
    alertas = (
        await cliente.get(
            "/alertas", params={"tipo": "sobreprecio", "limite": 1}, headers=comprador
        )
    ).json()
    assert alertas["total"] == len(todos)
