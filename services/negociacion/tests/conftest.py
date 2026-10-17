import json
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI
from negociacion.config import Configuracion
from negociacion.eventos import aplicar
from negociacion.main import crear_app
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
CLAVE_APLICACION = "clave-aplicacion-prueba"
TABLAS = (
    "evento, linea, palanca, sesion, oferta, mensaje, bitacora, proveedor, servicio, "
    "evento_procesado, outbox"
)
RUTA_RECOMENDACION = "/adjudicacion/recomendacion"
AHORA = datetime(2026, 10, 13, 15, tzinfo=UTC)
FECHA_LIMITE = AHORA + timedelta(days=7)
Fabrica = async_sessionmaker[AsyncSession]
AplicarEvento = Callable[[str, dict[str, Any]], Awaitable[None]]
Cuerpo = Callable[..., dict[str, Any]]
Compra = Callable[..., Awaitable[dict[str, Any]]]
Publicar = Callable[..., Awaitable[tuple[dict[str, Any], list[dict[str, Any]]]]]
Ofertar = Callable[..., Awaitable[httpx.Response]]


def _id(numero: int) -> str:
    return f"00000000-0000-4000-8000-{numero:012d}"


IDS = {"nube_norte": _id(1), "datos_sur": _id(2), "inactivo": _id(3), "contrato": _id(901)}
SERVICIOS = [
    {
        "id": _id(101),
        "codigo": "SAAS-CRM-PRO",
        "nombre": "CRM profesional",
        "categoria": "licencia_saas",
        "unidad": "usuario_mes",
        "moneda": "USD",
        "activo": True,
    },
    {
        "id": _id(102),
        "codigo": "SAAS-CRM-BAS",
        "nombre": "CRM básico",
        "categoria": "licencia_saas",
        "unidad": "usuario_mes",
        "moneda": "USD",
        "activo": True,
    },
    {
        "id": _id(103),
        "codigo": "NUBE-VM-STD",
        "nombre": "Máquina virtual estándar",
        "categoria": "nube",
        "unidad": "vcpu_mes",
        "moneda": "MXN",
        "activo": True,
    },
    {
        "id": _id(104),
        "codigo": "SOP-VIEJO",
        "nombre": "Soporte descontinuado",
        "categoria": "soporte",
        "unidad": "ticket",
        "moneda": "MXN",
        "activo": False,
    },
]
PROVEEDORES = [
    {
        "id": IDS["nube_norte"],
        "rfc": "NNO010101AB1",
        "nombre": "Nube Norte S.A. de C.V.",
        "tamano": "mediana",
        "categorias": ["licencia_saas", "nube"],
        "contacto_nombre": "Lucía Pérez",
        "contacto_email": "lucia@nubenorte.example",
        "activo": True,
    },
    {
        "id": IDS["datos_sur"],
        "rfc": "DSU020202CD2",
        "nombre": "Datos del Sur S.A.",
        "tamano": "pequena",
        "categorias": ["licencia_saas"],
        "contacto_nombre": "Marco Ruiz",
        "contacto_email": "ventas@datossur.example",
        "activo": True,
    },
    {
        "id": IDS["inactivo"],
        "rfc": "INA030303EF3",
        "nombre": "Inactivo S.A.",
        "tamano": "micro",
        "categorias": ["soporte"],
        "contacto_nombre": "Nadie",
        "contacto_email": "nadie@inactivo.example",
        "activo": False,
    },
]
REFERENCIAS = {
    "SAAS-CRM-PRO": {
        "p25": "28.0000",
        "p50": "31.5000",
        "p75": "36.0000",
        "metodo": "linea_base",
        "version": None,
        "confianza": "normal",
        "observaciones": 57,
    },
    "SAAS-CRM-BAS": {
        "p25": "12.0000",
        "p50": "14.0000",
        "p75": "17.0000",
        "metodo": "modelo",
        "version": 2,
        "confianza": "baja",
        "observaciones": 9,
    },
}
CONTRATO = {
    "id": IDS["contrato"],
    "folio": "C-000901",
    "tipo": "nuevo",
    "fecha_inicio": "2025-11-01",
    "fecha_fin": "2026-10-31",
    "moneda": "USD",
    "plazo_pago_dias": 30,
    "sla_disponibilidad": "99.50",
    "tope_aumento_pct": "5.00",
    "cuota_implementacion": "0",
    "lineas": [
        {
            "codigo_servicio": "SAAS-CRM-PRO",
            "nombre_servicio": "CRM profesional",
            "unidad": "usuario_mes",
            "cantidad": "120.0000",
            "precio_unitario": "32.0000",
        }
    ],
}


@dataclass
class Externos:
    """Lo que responden inteligencia (host intel) y proveedores (host prov) en las pruebas."""

    referencias: dict[str, dict[str, Any]] = field(default_factory=lambda: dict(REFERENCIAS))
    contratos: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {IDS["nube_norte"]: [CONTRATO]}
    )
    caido: str | None = None  # host que no responde
    estado_intel: int | None = None  # fuerza esta respuesta de inteligencia
    cuerpo_intel: bytes = b""
    usd_mxn: Decimal | None = Decimal("20.00")  # None: inteligencia no tiene tipo de cambio
    umbral: Decimal = Decimal("500000.00")
    peticiones: list[httpx.Request] = field(default_factory=list)

    def recomendaciones(self) -> list[dict[str, Any]]:
        """Los cuerpos de las peticiones de recomendación que recibió inteligencia."""
        return [
            json.loads(p.content)
            for p in self.peticiones
            if p.url.host == "intel" and p.url.path == RUTA_RECOMENDACION
        ]

    def _recomendar(self, cuerpo: dict[str, Any]) -> httpx.Response:
        """Una recomendación determinista: gana el que menos cuesta (ver inteligencia)."""
        usd = cuerpo["moneda"] == "USD"
        if usd and self.usd_mxn is None:
            return httpx.Response(409, json={"codigo": "tipo_cambio_no_disponible"})
        factor = self.usd_mxn if usd and self.usd_mxn is not None else Decimal(1)
        costos = {
            c["id"]: sum(
                (Decimal(linea["precio"]) * Decimal(linea["cantidad"]) for linea in c["lineas"]),
                Decimal(0),
            )
            for c in cuerpo["candidatos"]
        }
        orden = sorted(cuerpo["candidatos"], key=lambda c: (costos[c["id"]], c["id"]))
        return httpx.Response(
            200,
            json={
                "pesos": cuerpo.get("pesos")
                or {"costo": 40, "desempeno": 30, "riesgo": 15, "sla": 15},
                "umbral_aprobacion": str(self.umbral),
                "tipo_cambio": {"periodo": "2026-10-01", "usd_mxn": str(self.usd_mxn)}
                if usd
                else None,
                "candidatos": [
                    {
                        "id": c["id"],
                        "proveedor_id": c["proveedor_id"],
                        "nombre": c["nombre"],
                        "costo_total": str(costos[c["id"]]),
                        "costo_total_mxn": str(costos[c["id"]] * factor),
                        "desempeno": 50.0,
                        "riesgo": {
                            "valor": 0.0,
                            "nivel": "bajo",
                            "concentracion": 0.0,
                            "tendencia": 0.0,
                            "sin_historial": True,
                        },
                        "sla": c["sla"],
                        "normalizados": {},
                        "aportes": {},
                        "puntaje": 100.0 - lugar,
                        "lugar": lugar,
                    }
                    for lugar, c in enumerate(orden, start=1)
                ],
                "recomendado": orden[0]["id"],
                "margen": 0.0,
                "explicacion": ["Gana el que menos cuesta."],
                "sensibilidad": [],
            },
        )

    async def manejar(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        if peticion.url.host == self.caido:
            raise httpx.ConnectError("sin red", request=peticion)
        partes = peticion.url.path.strip("/").split("/")
        if peticion.url.host == "intel":
            if self.estado_intel is not None:
                return httpx.Response(self.estado_intel, content=self.cuerpo_intel)
            if peticion.url.path == RUTA_RECOMENDACION:
                return self._recomendar(json.loads(peticion.content))
            banda = self.referencias.get(partes[2])
            if banda is None:
                return httpx.Response(404, json={"codigo": "sin_observaciones"})
            return httpx.Response(200, json={"codigo": partes[2], **banda})
        if peticion.url.host == "prov":
            contratos = self.contratos.get(partes[1])
            if contratos is None:
                return httpx.Response(404, json={"title": "No encontrado"})
            return httpx.Response(200, json=contratos)
        return httpx.Response(500)


@dataclass
class Reloj:
    momento: datetime = AHORA

    def __call__(self) -> datetime:
        return self.momento


@dataclass
class Buzon:
    """Recoge los correos en lugar de mandarlos; con `falla`, simula un SMTP caído."""

    enviados: list[EmailMessage] = field(default_factory=list)
    falla: bool = False
    error: type[Exception] = OSError  # lo que lanza cuando `falla`

    async def enviar(self, mensaje: EmailMessage) -> None:
        if self.falla:
            raise self.error("sin servidor de correo")
        self.enviados.append(mensaje)


@pytest.fixture(scope="session")
def urls_bd() -> Iterator[tuple[str, str]]:
    """(URL del dueño, que migra; URL del usuario de la aplicación, con permisos reducidos)."""
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as contenedor:
        # El rol de la aplicación existe antes de migrar, como en infra/postgres/negociacion.sh.
        resultado = contenedor.exec(
            [
                "psql",
                "-U",
                contenedor.username,
                "-d",
                contenedor.dbname,
                "-c",
                f"CREATE ROLE negociacion LOGIN PASSWORD '{CLAVE_APLICACION}'",
            ]
        )
        assert resultado.exit_code == 0, resultado.output
        url_dueno = contenedor.get_connection_url()
        os.environ["DATABASE_URL_MIGRACIONES"] = url_dueno
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        url_app = (
            make_url(url_dueno)
            .set(username="negociacion", password=CLAVE_APLICACION)
            .render_as_string(hide_password=False)
        )
        yield url_dueno, url_app


@pytest.fixture
async def fabrica(urls_bd: tuple[str, str]) -> AsyncIterator[Fabrica]:
    url_dueno, url_app = urls_bd
    motor = create_async_engine(url_app, poolclass=NullPool)
    yield async_sessionmaker(motor, expire_on_commit=False)
    await motor.dispose()
    # La aplicación no puede borrar la bitácora ni los mensajes: limpia el dueño.
    limpieza = create_async_engine(url_dueno, poolclass=NullPool)
    async with limpieza.begin() as conexion:
        await conexion.execute(text(f"TRUNCATE {TABLAS} CASCADE"))
        await conexion.execute(text("ALTER SEQUENCE folio_evento RESTART"))
    await limpieza.dispose()


@pytest.fixture(scope="session")
def claves() -> ClavesPrueba:
    return ClavesPrueba()


@pytest.fixture
def externos() -> Externos:
    return Externos()


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def buzon() -> Buzon:
    return Buzon()


@pytest.fixture
def app(
    urls_bd: tuple[str, str],
    fabrica: Fabrica,
    claves: ClavesPrueba,
    externos: Externos,
    reloj: Reloj,
    buzon: Buzon,
) -> FastAPI:
    return crear_app(
        Configuracion(
            database_url=urls_bd[1],
            usar_rabbitmq=False,
            inteligencia_url="http://intel",
            proveedores_url="http://prov",
        ),
        claves.validador(),
        fabrica,
        transporte=httpx.MockTransport(externos.manejar),
        reloj=reloj,
        enviar_correo=buzon.enviar,
    )


@pytest.fixture
async def cliente(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente


@pytest.fixture
def comprador(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('comprador', sub='comprador-1')}"}


@pytest.fixture
def aprobador(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('aprobador', sub='aprobador-1')}"}


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


@pytest.fixture
def aplicar_evento(fabrica: Fabrica) -> AplicarEvento:
    """Aplica un evento suelto, como si hubiera llegado por la cola."""

    async def _aplicar(tipo: str, payload: dict[str, Any]) -> None:
        async with fabrica() as bd, bd.begin():
            await aplicar(bd, {"event_id": str(uuid.uuid4()), "type": tipo, "payload": payload})

    return _aplicar


@pytest.fixture
def ids() -> dict[str, str]:
    return dict(IDS)


@pytest.fixture
async def catalogo(aplicar_evento: AplicarEvento) -> None:
    """Las copias locales de servicios y proveedores, como si hubieran llegado por eventos."""
    for servicio in SERVICIOS:
        await aplicar_evento("servicio.actualizado", servicio)
    for proveedor in PROVEEDORES:
        await aplicar_evento("proveedor.actualizado", proveedor)


@pytest.fixture
def cuerpo_compra(catalogo: None) -> Cuerpo:
    """El cuerpo de una compra lista para publicar; los cambios reemplazan sus campos."""

    def _cuerpo(**cambios: Any) -> dict[str, Any]:
        return {
            "tipo": "compra",
            "titulo": "Licencias de CRM 2027",
            "fecha_limite": FECHA_LIMITE.isoformat(),
            "lineas": [{"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "100"}],
            "proveedores": [IDS["nube_norte"], IDS["datos_sur"]],
        } | cambios

    return _cuerpo


@pytest.fixture
def nueva_compra(
    cliente: httpx.AsyncClient, comprador: dict[str, str], cuerpo_compra: Cuerpo
) -> Compra:
    """Crea una compra por la API y devuelve su respuesta."""

    async def _crear(**cambios: Any) -> dict[str, Any]:
        respuesta = await cliente.post("/eventos", json=cuerpo_compra(**cambios), headers=comprador)
        assert respuesta.status_code == 201, respuesta.text
        return dict(respuesta.json())

    return _crear


@pytest.fixture
def publicar(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Compra
) -> Publicar:
    """Crea una compra (con los cambios dados), la publica y devuelve (evento, enlaces)."""

    async def _publicar(**cambios: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        evento = await nueva_compra(**cambios)
        respuesta = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()["evento"], respuesta.json()["enlaces"]

    return _publicar


def encabezados_portal(enlace: dict[str, Any], clave: str | None = None) -> dict[str, str]:
    token = enlace["enlace"].split("#t=")[1]
    return {"Authorization": f"Invitacion {token}", "Idempotency-Key": clave or uuid.uuid4().hex}


@pytest.fixture
def portal() -> Callable[..., dict[str, str]]:
    return encabezados_portal


@pytest.fixture
def ofertar(cliente: httpx.AsyncClient) -> Ofertar:
    """Manda una oferta por el portal; `clave` fija la Idempotency-Key, `extra` va en el cuerpo."""

    async def _ofertar(
        enlace: dict[str, Any],
        precios: dict[str, str],
        palancas: dict[str, str] | None = None,
        clave: str | None = None,
        **extra: Any,
    ) -> httpx.Response:
        cuerpo = {"valores": {"precios": precios, "palancas": palancas or {}}} | extra
        return await cliente.post(
            "/portal/ofertas", json=cuerpo, headers=encabezados_portal(enlace, clave)
        )

    return _ofertar


@pytest.fixture
def con_plazo_de_pago(
    cliente: httpx.AsyncClient, comprador: dict[str, str], nueva_compra: Compra
) -> Publicar:
    """Publica una compra con la palanca de plazo de pago (peso 20, ideal 60, límite 30)."""

    async def _publicar(**cambios: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        evento = await nueva_compra(**cambios)
        palancas = [
            {"clave": "precio", "peso": 80},
            {"clave": "plazo_pago_dias", "peso": 20, "ideal": "60", "limite": "30"},
        ]
        editado = await cliente.patch(
            f"/eventos/{evento['id']}", json={"version": 1, "palancas": palancas}, headers=comprador
        )
        assert editado.status_code == 200, editado.text
        publicado = await cliente.post(f"/eventos/{evento['id']}/publicar", headers=comprador)
        assert publicado.status_code == 200, publicado.text
        return publicado.json()["evento"], publicado.json()["enlaces"]

    return _publicar
