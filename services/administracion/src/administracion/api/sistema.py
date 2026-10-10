"""Estado de la plataforma y conteos del panel de administración."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from administracion.api import esquemas
from administracion.api.rutas import Admin, Identidad, Sesion
from administracion.estado import comprobar_todo
from administracion.identidad import IdentidadNoDisponible
from administracion.modelos import Actividad, CorreoEnviado

router = APIRouter(tags=["sistema"])


@router.get("/estado")
async def estado_del_sistema(request: Request, _: Admin) -> esquemas.EstadoSistema:
    estado = request.app.state
    servicios = await comprobar_todo(estado.config, estado.fabrica, estado.http)
    return esquemas.EstadoSistema(
        version=estado.config.version_app,
        comprobado_en=datetime.now(UTC),
        servicios=[esquemas.EstadoServicio(**asdict(s)) for s in servicios],
    )


@router.get("/resumen")
async def resumen(sesion: Sesion, identidad: Identidad, _: Admin) -> esquemas.Resumen:
    ahora = datetime.now(UTC)
    try:
        usuarios_activos: int | None = sum(1 for u in await identidad.listar_usuarios() if u.activo)
    except IdentidadNoDisponible:
        usuarios_activos = None  # el panel lo muestra sin dato; el resto sí carga
    fallidos = await sesion.scalar(
        select(func.count())
        .select_from(Actividad)
        .where(Actividad.tipo == "sesion.fallida", Actividad.fecha >= ahora - timedelta(hours=24))
    )
    correos = await sesion.scalar(
        select(func.count())
        .select_from(CorreoEnviado)
        .where(CorreoEnviado.fecha >= ahora - timedelta(days=7))
    )
    return esquemas.Resumen(
        usuarios_activos=usuarios_activos,
        intentos_fallidos_24h=fallidos or 0,
        correos_7d=correos or 0,
    )
