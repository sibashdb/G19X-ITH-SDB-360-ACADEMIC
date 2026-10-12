import os
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI
from generador.modelo import DatosSinteticos, generar
from inteligencia.config import Configuracion
from inteligencia.dominio.precios import Observacion, plazo_en_meses
from inteligencia.eventos import aplicar
from inteligencia.main import crear_app
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
CLAVE_APLICACION = "clave-aplicacion-prueba"
TABLAS = (
    "proveedor, servicio, tipo_cambio, contrato, linea_contrato, desempeno, "
    "evento_procesado, modelo_benchmark, outbox"
)
HOY = date(2026, 9, 15)  # dos semanas después del último mes de los datos generados
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
CONFIGURACION_INICIAL = (
    "UPDATE configuracion SET peso_sla = 30, peso_resolucion = 20, peso_incidentes = 20, "
    "peso_entregas = 15, peso_satisfaccion = 15, umbral_riesgo = 40, inflacion_anual = 4.50, "
    "actualizado_en = NULL, actualizado_por = NULL"
)


@pytest.fixture(scope="session")
def urls_bd() -> Iterator[tuple[str, str]]:
    """(URL del dueño, que migra; URL del usuario de la aplicación, con permisos reducidos)."""
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as contenedor:
        # El rol de la aplicación existe antes de migrar, como en infra/postgres/inteligencia.sh.
        resultado = contenedor.exec(
            [
                "psql",
                "-U",
                contenedor.username,
                "-d",
                contenedor.dbname,
                "-c",
                f"CREATE ROLE inteligencia LOGIN PASSWORD '{CLAVE_APLICACION}'",
            ]
        )
        assert resultado.exit_code == 0, resultado.output
        url_dueno = contenedor.get_connection_url()
        os.environ["DATABASE_URL_MIGRACIONES"] = url_dueno
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        url_app = (
            make_url(url_dueno)
            .set(username="inteligencia", password=CLAVE_APLICACION)
            .render_as_string(hide_password=False)
        )
        yield url_dueno, url_app


@pytest.fixture
async def fabrica(
    urls_bd: tuple[str, str],
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url_dueno, url_app = urls_bd
    motor = create_async_engine(url_app, poolclass=NullPool)
    yield async_sessionmaker(motor, expire_on_commit=False)
    await motor.dispose()
    # La aplicación no puede borrar: limpia el dueño.
    limpieza = create_async_engine(url_dueno, poolclass=NullPool)
    async with limpieza.begin() as conexion:
        await conexion.execute(text(f"TRUNCATE {TABLAS} CASCADE"))
        await conexion.execute(text(CONFIGURACION_INICIAL))
    await limpieza.dispose()


@pytest.fixture(scope="session")
def claves() -> ClavesPrueba:
    return ClavesPrueba()


@pytest.fixture
def app(
    urls_bd: tuple[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    claves: ClavesPrueba,
    tmp_path: Path,
) -> FastAPI:
    return crear_app(
        Configuracion(
            database_url=urls_bd[1],
            usar_rabbitmq=False,
            entrenamiento_automatico=False,
            directorio_modelos=tmp_path,
        ),
        claves.validador(),
        fabrica,
        hoy=lambda: HOY,
    )


@pytest.fixture
async def cliente(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente


# Datos del generador como observaciones (para el dominio) y como eventos (para la copia local).
ESPACIO = uuid.UUID("0b8f4c1e-7c55-4c5f-9a43-2f6f0a1d3b10")
Cargar = Callable[[DatosSinteticos], Awaitable[None]]


def id_de(clave: str) -> str:
    """Un id estable por RFC, código o folio: el mismo dato da el mismo id en cada prueba."""
    return str(uuid.uuid5(ESPACIO, clave))


def observaciones(datos: DatosSinteticos) -> list[Observacion]:
    servicios = {s.codigo: s for s in datos.servicios}
    tamanos = {p.rfc: p.tamano for p in datos.proveedores}
    resultado = []
    for fila in datos.contratos:
        servicio = servicios[fila["codigo_servicio"]]
        inicio = date.fromisoformat(fila["fecha_inicio"])
        fin = date.fromisoformat(fila["fecha_fin"])
        resultado.append(
            Observacion(
                servicio=servicio.codigo,
                categoria=servicio.categoria,
                moneda=servicio.moneda,
                fecha=inicio,
                cantidad=float(fila["cantidad"]),
                precio=float(fila["precio_unitario"]),
                plazo_meses=plazo_en_meses(inicio, fin),
                tamano=tamanos[fila["rfc_proveedor"]],
                tipo=fila["tipo"],
            )
        )
    return resultado


def sobres(datos: DatosSinteticos) -> list[dict[str, Any]]:
    """Los eventos que publicaría proveedores al importar esos datos, en el orden de carga."""
    eventos: list[tuple[str, dict[str, Any]]] = []
    for s in datos.servicios:
        eventos.append(
            (
                "servicio.actualizado",
                {
                    "id": id_de(s.codigo),
                    "codigo": s.codigo,
                    "nombre": s.nombre,
                    "categoria": s.categoria,
                    "unidad": s.unidad,
                    "moneda": s.moneda,
                    "activo": True,
                },
            )
        )
    for p in datos.proveedores:
        eventos.append(
            (
                "proveedor.actualizado",
                {
                    "id": id_de(p.rfc),
                    "rfc": p.rfc,
                    "nombre": p.nombre,
                    "tamano": p.tamano,
                    "categorias": list(p.categorias),
                    "activo": p.activo,
                },
            )
        )
    eventos += [("tipo_cambio.registrado", dict(fila)) for fila in datos.tipo_cambio]
    servicios = {s.codigo: s for s in datos.servicios}
    por_folio: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fila in datos.contratos:
        por_folio[fila["folio"]].append(fila)
    for folio, lineas in por_folio.items():
        cabecera = lineas[0]
        eventos.append(
            (
                "contrato.registrado",
                {
                    "id": id_de(folio),
                    "proveedor_id": id_de(cabecera["rfc_proveedor"]),
                    "folio": folio,
                    "tipo": cabecera["tipo"],
                    "fecha_inicio": cabecera["fecha_inicio"],
                    "fecha_fin": cabecera["fecha_fin"],
                    "moneda": cabecera["moneda"],
                    "lineas": [
                        {
                            "codigo_servicio": linea["codigo_servicio"],
                            "categoria": servicios[linea["codigo_servicio"]].categoria,
                            "unidad": servicios[linea["codigo_servicio"]].unidad,
                            "cantidad": linea["cantidad"],
                            "precio_unitario": linea["precio_unitario"],
                        }
                        for linea in lineas
                    ],
                },
            )
        )
    for fila in datos.desempeno:
        eventos.append(
            (
                "desempeno.registrado",
                {"proveedor_id": id_de(fila["rfc_proveedor"])}
                | {k: v for k, v in fila.items() if k != "rfc_proveedor"},
            )
        )
    return [
        {"event_id": str(uuid.uuid4()), "type": tipo, "payload": payload}
        for tipo, payload in eventos
    ]


@pytest.fixture(scope="session")
def generadas() -> list[Observacion]:
    """Las líneas de contrato de 30 proveedores generados, como precios observados."""
    return observaciones(generar(42, n_proveedores=30))


@pytest.fixture
def cargar(fabrica: async_sessionmaker[AsyncSession]) -> Cargar:
    """Aplica todos los eventos de los datos en una sola transacción (rápido para las pruebas)."""

    async def _cargar(datos: DatosSinteticos) -> None:
        async with fabrica() as sesion, sesion.begin():
            for sobre in sobres(datos):
                await aplicar(sesion, sobre)

    return _cargar


@pytest.fixture
def hoy() -> date:
    return HOY


@pytest.fixture
def comprador(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('comprador')}"}


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


@pytest.fixture
def aplicar_evento(fabrica: async_sessionmaker[AsyncSession]) -> AplicarEvento:
    """Aplica un evento suelto, como si hubiera llegado por la cola."""

    async def _aplicar(tipo: str, payload: dict[str, Any]) -> None:
        async with fabrica() as sesion, sesion.begin():
            await aplicar(sesion, {"event_id": str(uuid.uuid4()), "type": tipo, "payload": payload})

    return _aplicar
