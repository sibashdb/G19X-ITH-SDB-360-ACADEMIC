import uuid
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from generador.modelo import DatosSinteticos, generar
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
Cargar = Callable[[DatosSinteticos], Awaitable[None]]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
IdDe = Callable[[str], str]
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


async def test_alertas_filtra_por_proveedor(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=10))
    todas = (await cliente.get("/alertas", params={"limite": 200}, headers=comprador)).json()
    proveedor = todas["elementos"][0]["proveedor_id"]
    suyas = (
        await cliente.get(
            "/alertas", params={"proveedor": proveedor, "limite": 200}, headers=comprador
        )
    ).json()
    esperadas = [a for a in todas["elementos"] if a["proveedor_id"] == proveedor]
    assert suyas == {"total": len(esperadas), "elementos": esperadas}


@pytest.mark.parametrize(
    "params",
    [
        {"tipo": "otro"},
        {"severidad": "baja"},
        {"limite": "0"},
        {"pagina": "0"},
        {"proveedor": "no-es-un-uuid"},
    ],
)
async def test_alertas_valida_los_filtros(
    cliente: httpx.AsyncClient, comprador: Cabeceras, params: dict[str, str]
) -> None:
    respuesta = await cliente.get("/alertas", params=params, headers=comprador)
    assert respuesta.status_code == 422


async def test_el_tablero_se_recalcula_al_cambiar_el_dia(
    app: FastAPI, cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=10))
    antes = (await cliente.get("/tablero", headers=comprador)).json()
    assert antes["fecha"] == "2026-09-15"
    app.state.hoy = lambda: date(2026, 9, 16)
    despues = (await cliente.get("/tablero", headers=comprador)).json()
    assert despues["fecha"] == "2026-09-16"


def _con_contrato_vigente(datos: DatosSinteticos, hoy: date) -> set[str]:
    """RFC de los proveedores con algún contrato vigente en `hoy`, de los datos generados."""
    return {
        fila["rfc_proveedor"]
        for fila in datos.contratos
        if date.fromisoformat(fila["fecha_inicio"]) <= hoy <= date.fromisoformat(fila["fecha_fin"])
    }


async def _con_alerta_de_riesgo(cliente: httpx.AsyncClient, cabeceras: Cabeceras) -> set[str]:
    pagina = (
        await cliente.get("/alertas", params={"tipo": "riesgo", "limite": 200}, headers=cabeceras)
    ).json()
    return {a["proveedor_id"] for a in pagina["elementos"]}


async def test_un_proveedor_inactivo_sale_de_las_listas_pero_su_gasto_sigue(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    aplicar_evento: AplicarEvento,
    fabrica: Fabrica,
    id_estable: IdDe,
    hoy: date,
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    # Con el umbral en 100, todo proveedor activo con puntuación tiene una alerta de riesgo.
    async with fabrica() as sesion, sesion.begin():
        await sesion.execute(
            text("UPDATE configuracion SET umbral_riesgo = 100, actualizado_en = now()")
        )
    antes = (await cliente.get("/tablero", headers=comprador)).json()
    assert Decimal(antes["gasto_anual"]) > 0
    assert (
        sum(rango["proveedores"] for rango in antes["distribucion"]) == antes["total_proveedores"]
    )
    destacados = {d["proveedor_id"] for d in antes["mejores"] + antes["peores"]}
    con_contrato = _con_contrato_vigente(datos, hoy)
    proveedor = next(
        (
            p
            for p in datos.proveedores
            if p.activo and p.rfc in con_contrato and id_estable(p.rfc) in destacados
        ),
        None,
    )
    assert proveedor is not None
    id_proveedor = id_estable(proveedor.rfc)
    assert id_proveedor in await _con_alerta_de_riesgo(cliente, comprador)

    await aplicar_evento(
        "proveedor.actualizado",
        {
            "id": id_proveedor,
            "rfc": proveedor.rfc,
            "nombre": proveedor.nombre,
            "tamano": proveedor.tamano,
            "categorias": list(proveedor.categorias),
            "activo": False,
        },
    )

    despues = (await cliente.get("/tablero", headers=comprador)).json()
    assert despues["total_proveedores"] == antes["total_proveedores"] - 1
    assert id_proveedor not in {d["proveedor_id"] for d in despues["mejores"] + despues["peores"]}
    assert sum(r["proveedores"] for r in despues["distribucion"]) == despues["total_proveedores"]
    assert id_proveedor not in await _con_alerta_de_riesgo(cliente, comprador)
    assert despues["gasto_anual"] == antes["gasto_anual"]


async def test_un_servicio_inactivo_no_se_cotiza_pero_sus_contratos_siguen_contando(
    cliente: httpx.AsyncClient,
    comprador: Cabeceras,
    cargar: Cargar,
    aplicar_evento: AplicarEvento,
    id_estable: IdDe,
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    antes = (await cliente.get("/tablero", headers=comprador)).json()
    sobreprecios = (await cliente.get("/precios/sobreprecios", headers=comprador)).json()
    assert Decimal(antes["gasto_anual"]) > 0 and sobreprecios
    codigo = sobreprecios[0]["codigo_servicio"]
    servicio = next(s for s in datos.servicios if s.codigo == codigo)
    catalogo = (await cliente.get("/precios/servicios", headers=comprador)).json()
    assert codigo in {s["codigo"] for s in catalogo}
    filtro = {"tipo": "sobreprecio", "limite": 1}
    alertas = (await cliente.get("/alertas", params=filtro, headers=comprador)).json()

    await aplicar_evento(
        "servicio.actualizado",
        {
            "id": id_estable(codigo),
            "codigo": codigo,
            "nombre": servicio.nombre,
            "categoria": servicio.categoria,
            "unidad": servicio.unidad,
            "moneda": servicio.moneda,
            "activo": False,
        },
    )

    despues = (await cliente.get("/tablero", headers=comprador)).json()
    assert despues["gasto_anual"] == antes["gasto_anual"]
    assert despues["ahorro_potencial"] == antes["ahorro_potencial"]
    catalogo = (await cliente.get("/precios/servicios", headers=comprador)).json()
    assert codigo not in {s["codigo"] for s in catalogo}
    del_servicio = (
        await cliente.get("/precios/sobreprecios", params={"codigo": codigo}, headers=comprador)
    ).json()
    assert del_servicio == [f for f in sobreprecios if f["codigo_servicio"] == codigo]
    alertas_despues = (await cliente.get("/alertas", params=filtro, headers=comprador)).json()
    assert alertas_despues["total"] == alertas["total"]
