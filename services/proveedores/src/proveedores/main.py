"""Aplicación FastAPI del servicio de proveedores."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.outbox import RelayOutbox
from comun.salud import crear_router_salud
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from proveedores.api.catalogo import router as router_catalogo
from proveedores.api.rutas import router
from proveedores.config import Configuracion
from proveedores.modelos import Outbox


def crear_app(
    configuracion: Configuracion | None = None,
    validador: ValidadorJWT | None = None,
    fabrica: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    config = configuracion or Configuracion()
    configurar_logs(config.nombre_servicio, config.log_level)
    sesiones = fabrica or async_sessionmaker(
        # hide_parameters: que los datos de proveedores no lleguen a los logs en los errores de SQL.
        create_async_engine(config.database_url, pool_pre_ping=True, hide_parameters=True),
        expire_on_commit=False,
    )
    relay = RelayOutbox(sesiones, Outbox, config.rabbitmq_url)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        await relay.conectar()
        tarea = asyncio.create_task(relay.ejecutar())
        yield
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
        await relay.cerrar()

    app = FastAPI(
        title="Servicio de proveedores",
        version="0.1.0",
        root_path=config.root_path,
        lifespan=ciclo_de_vida,
    )
    app.state.fabrica = sesiones
    app.state.validador = validador or validador_desde_jwks(
        config.oidc_issuer, config.oidc_audience, config.oidc_jwks_url
    )
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    async def verificar_postgres() -> None:
        async with sesiones() as sesion:
            await sesion.execute(text("SELECT 1"))

    async def verificar_rabbitmq() -> None:
        if not relay.conectado():
            raise ConnectionError("Sin conexión con RabbitMQ")

    app.include_router(
        crear_router_salud({"postgres": verificar_postgres, "rabbitmq": verificar_rabbitmq})
    )
    app.include_router(router)
    app.include_router(router_catalogo)
    return app
