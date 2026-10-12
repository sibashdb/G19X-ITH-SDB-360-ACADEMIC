"""Sesión, roles y el contexto del día para las rutas."""

from datetime import date
from typing import Annotated

from comun.auth import ROLES_INTERNOS, Usuario, requiere_rol
from fastapi import Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from inteligencia.contexto import CacheContexto, Contexto
from inteligencia.db import obtener_sesion

Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]
Interno = Annotated[Usuario, Depends(requiere_rol(*ROLES_INTERNOS))]
Admin = Annotated[Usuario, Depends(requiere_rol("admin"))]
CodigoServicio = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{3,30}$")]


async def _contexto(request: Request, sesion: Sesion, _: Interno) -> Contexto:
    """Exige el rol antes de leer la base: sin una sesión válida no se calcula nada."""
    cache: CacheContexto = request.app.state.contexto
    hoy: date = request.app.state.hoy()
    return await cache.obtener(sesion, hoy)


Ctx = Annotated[Contexto, Depends(_contexto)]
