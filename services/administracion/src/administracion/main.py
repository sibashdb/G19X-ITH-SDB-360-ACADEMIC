"""Aplicación FastAPI del servicio de administración."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.salud import crear_router_salud
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from administracion import estado
from administracion.api.rutas import router
from administracion.api.sistema import router as router_sistema
from administracion.config import Configuracion
from administracion.eventos import ConsumidorEventos
from administracion.identidad import ProveedorIdentidad
from administracion.keycloak import IdentidadKeycloak
from administracion.sesiones import ejecutar_periodicamente


def crear_app(
    configuracion: Configuracion | None = None,
    validador: ValidadorJWT | None = None,
    fabrica: async_sessionmaker[AsyncSession] | None = None,
    identidad: ProveedorIdentidad | None = None,
    transporte_estado: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    config = configuracion or Configuracion()
    configurar_logs(config.nombre_servicio, config.log_level)
    sesiones = fabrica or async_sessionmaker(
        create_async_engine(config.database_url, pool_pre_ping=True, hide_parameters=True),
        expire_on_commit=False,
    )
    proveedor = identidad or IdentidadKeycloak(
        config.keycloak_url,
        config.keycloak_realm,
        config.keycloak_cliente,
        config.keycloak_secreto,
        config.url_app,
    )

    consumidor = ConsumidorEventos(sesiones, config.rabbitmq_url)
    http = httpx.AsyncClient(timeout=estado.TIEMPO_LIMITE_S, transport=transporte_estado)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        tareas = [
            asyncio.create_task(
                ejecutar_periodicamente(proveedor, sesiones, config.intervalo_eventos_s)
            )
        ]
        if config.consumir_eventos:
            tareas.append(asyncio.create_task(consumidor.ejecutar()))
        yield
        for tarea in tareas:
            tarea.cancel()
        for tarea in tareas:
            with contextlib.suppress(asyncio.CancelledError):
                await tarea
        await consumidor.cerrar()
        if isinstance(proveedor, IdentidadKeycloak):
            await proveedor.cerrar()
        await http.aclose()

    app = FastAPI(
        title="Servicio de administración",
        version="0.1.0",
        root_path=config.root_path,
        lifespan=ciclo_de_vida,
    )
    app.state.fabrica = sesiones
    app.state.config = config
    app.state.identidad = proveedor
    app.state.consumidor = consumidor
    app.state.http = http
    app.state.validador = validador or validador_desde_jwks(
        config.oidc_issuer, config.oidc_audience, config.oidc_jwks_url
    )
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    async def verificar_postgres() -> None:
        async with sesiones() as sesion:
            await sesion.execute(text("SELECT 1"))

    app.include_router(crear_router_salud({"postgres": verificar_postgres}))
    app.include_router(router)
    app.include_router(router_sistema)
    return app
