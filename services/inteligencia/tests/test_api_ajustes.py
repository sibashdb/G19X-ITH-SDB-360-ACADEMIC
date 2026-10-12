import threading
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from generador.modelo import DatosSinteticos, generar
from inteligencia import entrenamiento
from inteligencia.modelo import DatosInsuficientes
from inteligencia.modelos import ModeloBenchmark, Outbox
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
Cargar = Callable[[DatosSinteticos], Awaitable[None]]
Cabeceras = dict[str, str]
INICIAL: dict[str, Any] = {
    "peso_sla": 30,
    "peso_resolucion": 20,
    "peso_incidentes": 20,
    "peso_entregas": 15,
    "peso_satisfaccion": 15,
    "umbral_riesgo": 40,
    "inflacion_anual": "4.50",
}


async def _eventos(fabrica: Fabrica, tipo: str) -> list[dict[str, Any]]:
    async with fabrica() as sesion:
        filas = await sesion.scalars(select(Outbox).where(Outbox.tipo == tipo))
        return [fila.payload for fila in filas]


async def test_leer_la_configuracion(cliente: httpx.AsyncClient, comprador: Cabeceras) -> None:
    respuesta = await cliente.get("/configuracion", headers=comprador)
    assert respuesta.json() == {**INICIAL, "actualizado_en": None, "actualizado_por": None}


async def test_guardar_publica_los_campos_cambiados(
    cliente: httpx.AsyncClient, admin: Cabeceras, fabrica: Fabrica
) -> None:
    nueva = {**INICIAL, "peso_sla": 40, "peso_satisfaccion": 5, "inflacion_anual": "5.2"}
    respuesta = await cliente.put("/configuracion", json=nueva, headers=admin)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["peso_sla"], cuerpo["inflacion_anual"]) == (40, "5.20")
    assert cuerpo["actualizado_por"] == "admin-1" and cuerpo["actualizado_en"] is not None
    assert await _eventos(fabrica, "configuracion.actualizada") == [
        {
            "cambios": [
                {"campo": "peso_sla", "anterior": 30, "nuevo": 40},
                {"campo": "peso_satisfaccion", "anterior": 15, "nuevo": 5},
                {"campo": "inflacion_anual", "anterior": "4.50", "nuevo": "5.20"},
            ],
            "actor": {"id": "admin-1", "nombre": "admin-1"},
        }
    ]
    assert (await cliente.get("/configuracion", headers=admin)).json()["peso_sla"] == 40


async def test_guardar_sin_cambios_no_publica(
    cliente: httpx.AsyncClient, admin: Cabeceras, fabrica: Fabrica
) -> None:
    respuesta = await cliente.put(
        "/configuracion", json={**INICIAL, "inflacion_anual": "4.5"}, headers=admin
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["actualizado_en"] is None
    assert await _eventos(fabrica, "configuracion.actualizada") == []


async def test_pesos_que_no_suman_100(
    cliente: httpx.AsyncClient, admin: Cabeceras, fabrica: Fabrica
) -> None:
    respuesta = await cliente.put("/configuracion", json={**INICIAL, "peso_sla": 20}, headers=admin)
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "pesos_invalidos"
    assert cuerpo["errores"] == [
        {"campo": "body.pesos", "mensaje": "Los pesos deben sumar 100 (suman 90)."}
    ]
    assert (await cliente.get("/configuracion", headers=admin)).json()["peso_sla"] == 30
    assert await _eventos(fabrica, "configuracion.actualizada") == []


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"peso_sla": -10, "peso_resolucion": 60}, "body.peso_sla"),
        ({"umbral_riesgo": 101}, "body.umbral_riesgo"),
        ({"inflacion_anual": "50.01"}, "body.inflacion_anual"),
        ({"inflacion_anual": "4.555"}, "body.inflacion_anual"),
        ({"otro": 1}, "body.otro"),
    ],
)
async def test_valores_fuera_de_rango(
    cliente: httpx.AsyncClient, admin: Cabeceras, cambio: dict[str, Any], campo: str
) -> None:
    respuesta = await cliente.put("/configuracion", json={**INICIAL, **cambio}, headers=admin)
    assert respuesta.status_code == 422
    assert campo in {e["campo"] for e in respuesta.json()["errores"]}


async def test_la_configuracion_cambia_los_calculos(
    cliente: httpx.AsyncClient, comprador: Cabeceras, admin: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=15))
    antes = (await cliente.get("/tablero", headers=comprador)).json()
    assert antes["en_riesgo"] < antes["total_proveedores"]
    await cliente.put("/configuracion", json={**INICIAL, "umbral_riesgo": 100}, headers=admin)
    despues = (await cliente.get("/tablero", headers=comprador)).json()
    assert despues["en_riesgo"] == despues["total_proveedores"]


async def test_registro_de_modelos_vacio(cliente: httpx.AsyncClient, comprador: Cabeceras) -> None:
    respuesta = await cliente.get("/modelos", headers=comprador)
    assert respuesta.json() == {
        "entrenando": False,
        "activo": None,
        "en_uso": None,
        "ultimo_error": None,
        "elementos": [],
    }


async def test_un_segundo_entrenamiento_mientras_corre_el_primero(
    app: FastAPI,
    cliente: httpx.AsyncClient,
    admin: Cabeceras,
    comprador: Cabeceras,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    liberar = threading.Event()

    def entrenar_lento(*_argumentos: object) -> None:
        liberar.wait(timeout=10)
        raise DatosInsuficientes("prueba")

    monkeypatch.setattr(entrenamiento, "entrenar", entrenar_lento)
    primera = await cliente.post("/modelos/entrenar", headers=admin)
    assert (primera.status_code, primera.json()) == (202, {"entrenando": True})
    segunda = await cliente.post("/modelos/entrenar", headers=admin)
    assert (segunda.status_code, segunda.json()["codigo"]) == (409, "entrenamiento_en_curso")
    assert (await cliente.get("/modelos", headers=comprador)).json()["entrenando"] is True
    liberar.set()
    await app.state.entrenador.esperar()
    assert (await cliente.get("/modelos", headers=comprador)).json()["entrenando"] is False


async def test_entrenar_registra_el_modelo(
    app: FastAPI,
    cliente: httpx.AsyncClient,
    admin: Cabeceras,
    comprador: Cabeceras,
    cargar: Cargar,
) -> None:
    await cargar(generar(42, n_proveedores=15))
    assert (await cliente.post("/modelos/entrenar", headers=admin)).status_code == 202
    await app.state.entrenador.esperar()
    registro = (await cliente.get("/modelos", headers=comprador)).json()
    [modelo] = registro["elementos"]
    assert (modelo["version"], modelo["origen"], modelo["actor_nombre"]) == (1, "manual", "admin-1")
    assert "artefacto" not in modelo
    assert registro["activo"] == (1 if modelo["promovido"] else None)
    assert registro["en_uso"] == registro["activo"]
    assert registro["ultimo_error"] is None


async def test_datos_de_la_copia_local(
    cliente: httpx.AsyncClient, admin: Cabeceras, comprador: Cabeceras, cargar: Cargar
) -> None:
    datos = generar(42, n_proveedores=15)
    await cargar(datos)
    assert (await cliente.get("/datos", headers=comprador)).status_code == 403
    cuerpo = (await cliente.get("/datos", headers=admin)).json()
    assert cuerpo["registros"] == {
        "proveedores": 15,
        "servicios": len(datos.servicios),
        "contratos": len({fila["folio"] for fila in datos.contratos}),
        "lineas_contrato": len(datos.contratos),
        "desempeno": len(datos.desempeno),
        "tipo_cambio": len(datos.tipo_cambio),
    }
    assert cuerpo["ultimo_evento"] is not None
    assert (cuerpo["modelo"], cuerpo["en_uso"], cuerpo["entrenando"]) == (None, None, False)


async def test_un_modelo_que_no_carga_esta_activo_pero_no_en_uso(
    cliente: httpx.AsyncClient,
    admin: Cabeceras,
    comprador: Cabeceras,
    fabrica: Fabrica,
    tmp_path: Path,
) -> None:
    """Si el archivo del modelo promovido se perdió, se usa la línea base y la API lo dice."""
    async with fabrica() as sesion, sesion.begin():
        sesion.add(
            ModeloBenchmark(
                version=1,
                entrenado_en=datetime.now(UTC),
                origen="manual",
                actor_nombre="admin1",
                observaciones=100,
                datos_hasta=date(2026, 9, 30),
                mape=Decimal("0.100000"),
                mape_linea_base=Decimal("0.120000"),
                cobertura=Decimal("0.500000"),
                pinball=Decimal("0.010000"),
                promovido=True,
                artefacto=str(tmp_path / "no-existe.joblib"),
            )
        )
    registro = (await cliente.get("/modelos", headers=comprador)).json()
    assert (registro["activo"], registro["en_uso"]) == (1, None)
    datos = (await cliente.get("/datos", headers=admin)).json()
    assert (datos["modelo"]["version"], datos["en_uso"]) == (1, None)
