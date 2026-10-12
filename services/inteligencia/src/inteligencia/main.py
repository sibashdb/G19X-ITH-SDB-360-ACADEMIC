"""Aplicación FastAPI del servicio de inteligencia."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo

from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.consumidor import ConsumidorEventos
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.outbox import RelayOutbox
from comun.salud import crear_router_salud
from comun.topologia import COLA_INTELIGENCIA
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from inteligencia.api import precios, tablero
from inteligencia.config import Configuracion
from inteligencia.contexto import CacheContexto
from inteligencia.entrenamiento import Entrenador
from inteligencia.eventos import atendedor
from inteligencia.modelos import Outbox

ZONA_NEGOCIO = ZoneInfo("America/Mexico_City")  # el "hoy" del negocio


def crear_app(
    configuracion: Configuracion | None = None,
    validador: ValidadorJWT | None = None,
    fabrica: async_sessionmaker[AsyncSession] | None = None,
    hoy: Callable[[], date] | None = None,
) -> FastAPI:
    config = configuracion or Configuracion()
    configurar_logs(config.nombre_servicio, config.log_level)
    sesiones = fabrica or async_sessionmaker(
        create_async_engine(config.database_url, pool_pre_ping=True, hide_parameters=True),
        expire_on_commit=False,
    )
    relay = RelayOutbox(sesiones, Outbox, config.rabbitmq_url)
    consumidor = ConsumidorEventos(config.rabbitmq_url, COLA_INTELIGENCIA, atendedor(sesiones))
    entrenador = Entrenador(sesiones, config.directorio_modelos)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        tareas: list[asyncio.Task[None]] = []
        if config.usar_rabbitmq:
            await relay.conectar()
            tareas.append(asyncio.create_task(relay.ejecutar()))
            tareas.append(asyncio.create_task(consumidor.ejecutar()))
        if config.entrenamiento_automatico:
            tareas.append(asyncio.create_task(entrenador.ejecutar_periodicamente()))
        yield
        for tarea in tareas:
            tarea.cancel()
        for tarea in tareas:
            with contextlib.suppress(asyncio.CancelledError):
                await tarea
        if config.usar_rabbitmq:
            await consumidor.cerrar()
            await relay.cerrar()

    app = FastAPI(
        title="Servicio de inteligencia",
        version="0.1.0",
        root_path=config.root_path,
        lifespan=ciclo_de_vida,
    )
    app.state.fabrica = sesiones
    app.state.config = config
    app.state.hoy = hoy or (lambda: datetime.now(ZONA_NEGOCIO).date())
    app.state.contexto = CacheContexto()
    app.state.consumidor = consumidor
    app.state.entrenador = entrenador
    app.state.validador = validador or validador_desde_jwks(
        config.oidc_issuer, config.oidc_audience, config.oidc_jwks_url
    )
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    async def verificar_postgres() -> None:
        async with sesiones() as sesion:
            await sesion.execute(text("SELECT 1"))

    app.include_router(crear_router_salud({"postgres": verificar_postgres}))
    app.include_router(tablero.router)
    app.include_router(precios.router)
    return app
