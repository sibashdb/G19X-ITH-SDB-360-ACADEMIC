"""Aplicación FastAPI del servicio de administración."""

from comun.auth import ValidadorJWT, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.logs import configurar_logs, middleware_correlacion
from comun.salud import crear_router_salud
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from administracion.api.rutas import router
from administracion.config import Configuracion
from administracion.identidad import ProveedorIdentidad
from administracion.keycloak import IdentidadKeycloak


def crear_app(
    configuracion: Configuracion | None = None,
    validador: ValidadorJWT | None = None,
    fabrica: async_sessionmaker[AsyncSession] | None = None,
    identidad: ProveedorIdentidad | None = None,
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
    app = FastAPI(title="Servicio de administración", version="0.1.0", root_path=config.root_path)
    app.state.fabrica = sesiones
    app.state.config = config
    app.state.identidad = proveedor
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
    return app
