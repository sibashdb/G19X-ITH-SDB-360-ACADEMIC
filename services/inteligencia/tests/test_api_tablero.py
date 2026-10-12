import uuid
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from generador.modelo import DatosSinteticos, generar

pytestmark = pytest.mark.integracion

Cargar = Callable[[DatosSinteticos], Awaitable[None]]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
Cabeceras = dict[str, str]
SEVERIDADES = {"alta": 0, "media": 1, "informativa": 2}


def _por_vencer(datos: DatosSinteticos, hoy: date) -> set[str]:
    """Folios vigentes que terminan en 90 días o menos, directo de los datos generados."""
    return {
        fila["folio"]
        for fila in datos.contratos
        if date.fromisoformat(fila["fecha_inicio"]) <= hoy <= date.fromisoformat(fila["fecha_fin"])
        and (date.fromisoformat(fila["fecha_fin"]) - hoy).days <= 90
    }


async def test_tablero_sin_datos(cliente: httpx.AsyncClient, comprador: Cabeceras) -> None:
    respuesta = await cliente.get("/tablero", headers=comprador)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["fecha"], cuerpo["moneda"]) == ("2026-09-15", "MXN")
    assert (cuerpo["gasto_anual"], cuerpo["ahorro_potencial"]) == ("0.00", "0.00")
    assert cuerpo["variacion_pct"] is None
    assert (cuerpo["por_vencer"], cuerpo["en_riesgo"], cuerpo["total_proveedores"]) == (0, 0, 0)
    assert len(cuerpo["gasto_por_mes"]) == 24
    assert {mes["monto"] for mes in cuerpo["gasto_por_mes"]} == {"0.00"}
    for lista in (
        "gasto_por_categoria",
        "proximos_vencimientos",
        "alertas_principales",
        "mejores",
        "peores",
    ):
        assert cuerpo[lista] == [], lista


async def test_tablero_con_los_datos_generados(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar, hoy: date
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    cuerpo = (await cliente.get("/tablero", headers=comprador)).json()
    activos = sum(p.activo for p in datos.proveedores)
    assert cuerpo["total_proveedores"] == activos
    assert cuerpo["por_vencer"] == len(_por_vencer(datos, hoy))
    assert Decimal(cuerpo["gasto_anual"]) > 0
    assert Decimal(cuerpo["ahorro_potencial"]) >= 0
    assert cuerpo["gasto_por_mes"][-1]["mes"] == "2026-09-01"
    assert len(cuerpo["mejores"]) == len(cuerpo["peores"]) == 5
    mejores = [d["puntuacion"] for d in cuerpo["mejores"]]
    assert mejores == sorted(mejores, reverse=True)
    # Todos los proveedores generados tienen desempeño en los últimos 12 meses.
    assert sum(rango["proveedores"] for rango in cuerpo["distribucion"]) == activos
    assert len(cuerpo["alertas_principales"]) == 5
    dias = [v["dias"] for v in cuerpo["proximos_vencimientos"]]
    assert dias == sorted(dias)
    assert all(
        v["servicios"] and Decimal(v["monto_mensual"]) > 0 for v in cuerpo["proximos_vencimientos"]
    )


async def test_el_tablero_se_actualiza_al_llegar_un_evento(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    aplicar_evento: AplicarEvento,
    hoy: date,
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    antes = (await cliente.get("/tablero", headers=comprador)).json()
    servicio = datos.servicios[0]
    contrato_id = str(uuid.uuid4())
    await aplicar_evento(
        "contrato.registrado",
        {
            "id": contrato_id,
            "proveedor_id": antes["mejores"][0]["proveedor_id"],
            "folio": "C-PRUEBA",
            "tipo": "nuevo",
            "fecha_inicio": "2026-01-01",
            "fecha_fin": (hoy + timedelta(days=10)).isoformat(),
            "moneda": servicio.moneda,
            "lineas": [
                {
                    "codigo_servicio": servicio.codigo,
                    "categoria": servicio.categoria,
                    "unidad": servicio.unidad,
                    "cantidad": "10",
                    "precio_unitario": "1.0000",
                }
            ],
        },
    )
    despues = (await cliente.get("/tablero", headers=comprador)).json()
    assert despues["por_vencer"] == antes["por_vencer"] + 1
    vencimientos = (
        await cliente.get(
            "/alertas", params={"tipo": "vencimiento", "limite": 200}, headers=comprador
        )
    ).json()
    [alerta] = [a for a in vencimientos["elementos"] if a["entidad_id"] == contrato_id]
    assert (alerta["severidad"], alerta["titulo"]) == ("alta", "Vence en 10 días: C-PRUEBA")


async def test_alertas_filtra_pagina_y_ordena(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=10))
    todas = (await cliente.get("/alertas", params={"limite": 200}, headers=comprador)).json()
    assert 5 < todas["total"] == len(todas["elementos"])
    orden = [(SEVERIDADES[a["severidad"]], a["fecha"]) for a in todas["elementos"]]
    assert orden == sorted(orden)
    for filtro, valor in (("tipo", "vencimiento"), ("tipo", "sobreprecio"), ("severidad", "alta")):
        parcial = (
            await cliente.get("/alertas", params={filtro: valor, "limite": 200}, headers=comprador)
        ).json()
        assert parcial["elementos"] == [a for a in todas["elementos"] if a[filtro] == valor]
    campana = (await cliente.get("/alertas", params={"limite": 5}, headers=comprador)).json()
    assert campana == {"total": todas["total"], "elementos": todas["elementos"][:5]}
    segunda = (
        await cliente.get("/alertas", params={"limite": 5, "pagina": 2}, headers=comprador)
    ).json()
    assert segunda["elementos"] == todas["elementos"][5:10]


@pytest.mark.parametrize(
    "params", [{"tipo": "otro"}, {"severidad": "baja"}, {"limite": "0"}, {"pagina": "0"}]
)
async def test_alertas_valida_los_filtros(
    cliente: httpx.AsyncClient, comprador: Cabeceras, params: dict[str, str]
) -> None:
    respuesta = await cliente.get("/alertas", params=params, headers=comprador)
    assert respuesta.status_code == 422
