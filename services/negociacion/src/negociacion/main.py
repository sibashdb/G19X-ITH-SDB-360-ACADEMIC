"""Aplicación FastAPI del servicio de negociación."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.consumidor import ConsumidorEventos
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.outbox import RelayOutbox
from comun.salud import crear_router_salud
from comun.topologia import COLA_NEGOCIACION
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from negociacion import vencimientos
from negociacion.api import adjudicacion, eventos, portal, tablero
from negociacion.api import sesiones as rutas_sesiones  # `sesiones` es la fábrica de sesiones de BD
from negociacion.config import Configuracion
from negociacion.correo import EnviarCorreo, enviador_smtp
from negociacion.eventos import atendedor
from negociacion.integraciones import ClienteIA, Integraciones
from negociacion.modelos import Outbox


def crear_app(
    configuracion: Configuracion | None = None,
    validador: ValidadorJWT | None = None,
    fabrica: async_sessionmaker[AsyncSession] | None = None,
    transporte: httpx.AsyncBaseTransport | None = None,
    reloj: Callable[[], datetime] | None = None,
    enviar_correo: EnviarCorreo | None = None,
) -> FastAPI:
    config = configuracion or Configuracion()
    configurar_logs(config.nombre_servicio, config.log_level)
    sesiones = fabrica or async_sessionmaker(
        create_async_engine(config.database_url, pool_pre_ping=True, hide_parameters=True),
        expire_on_commit=False,
    )
    relay = RelayOutbox(sesiones, Outbox, config.rabbitmq_url)
    consumidor = ConsumidorEventos(config.rabbitmq_url, COLA_NEGOCIACION, atendedor(sesiones))
    http = httpx.AsyncClient(transport=transporte)
    ahora = reloj or (lambda: datetime.now(UTC))
    enviar = enviar_correo or enviador_smtp(config.smtp_host, config.smtp_puerto)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        tareas: list[asyncio.Task[None]] = []
        if config.usar_rabbitmq:
            await relay.conectar()
            tareas.append(asyncio.create_task(relay.ejecutar()))
            tareas.append(asyncio.create_task(consumidor.ejecutar()))
        if config.tareas_periodicas:
            tareas.append(
                asyncio.create_task(
                    vencimientos.ejecutar_periodicamente(sesiones, ahora, enviar, config)
                )
            )
        yield
        for tarea in tareas:
            tarea.cancel()
        for tarea in tareas:
            with contextlib.suppress(asyncio.CancelledError):
                await tarea
        await http.aclose()
        if config.usar_rabbitmq:
            await consumidor.cerrar()
            await relay.cerrar()

    app = FastAPI(
        title="Servicio de negociación",
        version="0.1.0",
        root_path=config.root_path,
        lifespan=ciclo_de_vida,
    )
    app.state.fabrica = sesiones
    app.state.config = config
    app.state.reloj = ahora
    app.state.integraciones = Integraciones(http, config.inteligencia_url, config.proveedores_url)
    app.state.enviar_correo = enviar
    app.state.ia = ClienteIA(http, config.ia_url)
    app.state.validador = validador or validador_desde_jwks(
        config.oidc_issuer, config.oidc_audience, config.oidc_jwks_url
    )
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    async def verificar_postgres() -> None:
        async with sesiones() as bd:
            await bd.execute(text("SELECT 1"))

    app.include_router(crear_router_salud({"postgres": verificar_postgres}))
    app.include_router(eventos.router)
    app.include_router(adjudicacion.router)
    app.include_router(rutas_sesiones.router)
    app.include_router(portal.router)
    app.include_router(tablero.router)
    return app
