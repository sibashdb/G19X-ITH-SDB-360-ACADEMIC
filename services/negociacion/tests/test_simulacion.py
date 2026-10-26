"""Simulación con bots (spec §13): negocian por el portal contra la app real, dentro del proceso."""

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import httpx
import pytest
from comun.pruebas import ClavesPrueba
from generador.modelo import generar
from negociacion.config import Configuracion
from negociacion.eventos import aplicar
from negociacion.main import crear_app
from simulador.escenarios import bandas, contratos_por_proveedor, escenarios
from simulador.orquestador import Contexto, correr
from simulador.reporte import metricas, reporte
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion
HOY = datetime(2026, 9, 15, 15, tzinfo=UTC)  # dos semanas después del último mes generado
SEMILLA = 42  # la misma de `python -m generador`: son los datos de datos/
ESPACIO = uuid.UUID("5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42")


def _id(clave: str) -> str:
    """Un id estable por RFC, código o folio."""
    return str(uuid.uuid5(ESPACIO, clave))


async def test_los_bots_nunca_cierran_fuera_de_limites(
    urls_bd: tuple[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    claves: ClavesPrueba,
) -> None:
    datos = generar(SEMILLA)
    referencias = bandas(datos, HOY.date())
    contratos = contratos_por_proveedor(datos, _id)
    async with fabrica() as bd, bd.begin():
        for s in datos.servicios:
            payload = {
                "id": _id(s.codigo),
                "codigo": s.codigo,
                "nombre": s.nombre,
                "categoria": s.categoria,
                "unidad": s.unidad,
                "moneda": s.moneda,
                "activo": True,
            }
            await aplicar(
                bd,
                {"event_id": str(uuid.uuid4()), "type": "servicio.actualizado", "payload": payload},
            )
        for p in datos.proveedores:
            payload = {
                "id": _id(p.rfc),
                "nombre": p.nombre,
                "categorias": list(p.categorias),
                "contacto_nombre": p.contacto_nombre,
                "contacto_email": p.contacto_email,
                "activo": p.activo,
            }
            await aplicar(
                bd,
                {
                    "event_id": str(uuid.uuid4()),
                    "type": "proveedor.actualizado",
                    "payload": payload,
                },
            )

    interpretados: list[str] = []

    async def externos(peticion: httpx.Request) -> httpx.Response:
        partes = peticion.url.path.strip("/").split("/")
        if peticion.url.host == "ia":
            if partes[0] != "interpretar":  # el agente redacta con sus plantillas
                return httpx.Response(503, json={"codigo": "llm_no_disponible"})
            cuerpo = json.loads(peticion.content)
            interpretados.append(cuerpo["texto"])
            # El peor caso: el intérprete «cree» cada ataque, una oferta por encima de todo límite.
            return httpx.Response(
                200,
                json={
                    "intencion": "oferta",
                    "precios": {linea["id"]: "9999999" for linea in cuerpo["lineas"]},
                    "palancas": {},
                    "confianza": 0.9,
                    "modelo": "falso",
                    "version_prompt": "1",
                },
            )
        if peticion.url.host == "intel":
            banda = referencias.get(partes[2])
            if banda is None:
                return httpx.Response(404, json={"codigo": "sin_observaciones"})
            return httpx.Response(
                200,
                json={
                    "p25": str(banda.p25),
                    "p50": str(banda.p50),
                    "p75": str(banda.p75),
                    "metodo": "linea_base",
                    "version": None,
                    "confianza": "normal",
                    "observaciones": 0,
                },
            )
        return httpx.Response(200, json=contratos.get(partes[1], []))

    async def sin_correo(_mensaje: EmailMessage) -> None:
        return None

    app = crear_app(
        Configuracion(
            database_url=urls_bd[1],
            usar_rabbitmq=False,
            inteligencia_url="http://intel",
            proveedores_url="http://prov",
            ia_url="http://ia",
        ),
        claves.validador(),
        fabrica,
        transporte=httpx.MockTransport(externos),
        enviar_correo=sin_correo,
        reloj=lambda: HOY,
    )

    def comprador() -> dict[str, str]:
        return {"Authorization": f"Bearer {claves.token('comprador', sub='comprador-sim')}"}

    lista = escenarios(datos, HOY.date())
    contexto = Contexto(datos, referencias, _id, HOY + timedelta(days=7))
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        resultados = await correr(cliente, comprador, contexto, lista)
    total = metricas(resultados)
    assert total.sesiones > 50
    assert total.fuera_de_limites == 0  # la meta dura del PRD §1.6
    # El manipulador atacó con texto y cada ataque pasó por el intérprete (spec N2, §4).
    assert total.ataques > 0
    assert total.ataques == len(interpretados)
    ruta = os.environ.get("SIMULACION_REPORTE")
    if ruta:
        Path(ruta).write_text(  # noqa: ASYNC240 - un archivo al final de la prueba
            reporte(resultados, lista, SEMILLA), encoding="utf-8", newline="\n"
        )
