"""Estado de los servicios de la plataforma: cada comprobación con su propio límite de tiempo."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote, urlsplit

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from administracion.config import Configuracion

log = logging.getLogger(__name__)

UMBRAL_LENTO_S = 1.0
TIEMPO_LIMITE_S = 2.0
MAX_MENSAJES_EN_COLA = 100
SUFIJO_FALLIDOS = ".dlq"

Estado = Literal["sano", "con_problemas", "caido"]
Prueba = Callable[[], Awaitable[str | None]]  # devuelve un problema, o None si todo está bien


@dataclass(frozen=True)
class Comprobacion:
    clave: str
    nombre: str
    estado: Estado
    tiempo_ms: int | None
    detalle: str


async def medir(clave: str, nombre: str, prueba: Prueba) -> Comprobacion:
    inicio = time.perf_counter()
    try:
        problema = await asyncio.wait_for(prueba(), TIEMPO_LIMITE_S)
    except TimeoutError:
        return Comprobacion(clave, nombre, "caido", None, f"No respondió en {TIEMPO_LIMITE_S:g} s.")
    except Exception as exc:
        log.warning("La comprobación de %s falló: %s", clave, exc)
        return Comprobacion(clave, nombre, "caido", None, "No responde o respondió con un error.")
    ms = round((time.perf_counter() - inicio) * 1000)
    if problema:
        return Comprobacion(clave, nombre, "con_problemas", ms, problema)
    if ms >= UMBRAL_LENTO_S * 1000:
        return Comprobacion(clave, nombre, "con_problemas", ms, "Responde con lentitud.")
    return Comprobacion(clave, nombre, "sano", ms, "Funciona con normalidad.")


def _credenciales(url_amqp: str) -> tuple[str, str]:
    partes = urlsplit(url_amqp)
    return unquote(partes.username or "guest"), unquote(partes.password or "guest")


async def comprobar_todo(
    config: Configuracion, fabrica: async_sessionmaker[AsyncSession], http: httpx.AsyncClient
) -> list[Comprobacion]:
    async def obtener(url: str, auth: tuple[str, str] | None = None) -> httpx.Response:
        respuesta = await http.get(url, auth=auth)
        respuesta.raise_for_status()
        return respuesta

    async def base_de_datos() -> None:
        async with fabrica() as sesion:
            await sesion.execute(text("SELECT 1"))

    async def proveedores() -> None:
        await obtener(f"{config.proveedores_url}/salud/listo")

    async def inteligencia() -> None:
        await obtener(f"{config.inteligencia_url}/salud/listo")

    async def identidad() -> None:
        await obtener(
            f"{config.keycloak_url}/realms/{config.keycloak_realm}/.well-known/openid-configuration"
        )

    async def mensajeria() -> str | None:
        colas = (
            await obtener(
                f"{config.rabbitmq_api_url}/queues", auth=_credenciales(config.rabbitmq_url)
            )
        ).json()
        atrasadas = [
            f"{c['name']} ({c.get('messages_ready', 0)})"
            for c in colas
            if not c["name"].endswith(SUFIJO_FALLIDOS)
            and c.get("messages_ready", 0) > MAX_MENSAJES_EN_COLA
        ]
        # Un mensaje en una cola de fallidos agotó sus 5 entregas: alguien debe revisarlo.
        fallidas = [
            f"{c['name']} ({c.get('messages', 0)})"
            for c in colas
            if c["name"].endswith(SUFIJO_FALLIDOS) and c.get("messages", 0) > 0
        ]
        problemas = []
        if atrasadas:
            problemas.append(f"Mensajes pendientes en: {', '.join(atrasadas)}.")
        if fallidas:
            problemas.append(f"Mensajes fallidos en: {', '.join(fallidas)}.")
        return " ".join(problemas) or None

    async def correo() -> None:
        await obtener(f"{config.mailpit_url}/readyz")

    pruebas: list[tuple[str, str, Prueba]] = [
        ("base_de_datos", "Base de datos de administración", base_de_datos),
        ("proveedores", "Servicio de proveedores", proveedores),
        ("inteligencia", "Servicio de inteligencia", inteligencia),
        ("identidad", "Identidad (Keycloak)", identidad),
        ("mensajeria", "Mensajería (RabbitMQ)", mensajeria),
        ("correo", "Buzón de correo (Mailpit)", correo),
    ]
    return list(await asyncio.gather(*(medir(c, n, p) for c, n, p in pruebas)))
