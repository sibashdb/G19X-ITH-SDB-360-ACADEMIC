"""Catálogo de servicios: consulta para los roles internos; alta, edición y estado para admin."""

import uuid
from typing import Annotated, Any

from comun.auth import ROLES_INTERNOS, Usuario, requiere_rol
from comun.errores import ErrorDominio
from comun.outbox import registrar_evento
from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from proveedores.api import esquemas
from proveedores.db import obtener_sesion
from proveedores.modelos import LineaContrato, Outbox, ServicioCatalogo

Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]
Interno = Annotated[Usuario, Depends(requiere_rol(*ROLES_INTERNOS))]
Admin = Annotated[Usuario, Depends(requiere_rol("admin"))]
CodigoEnRuta = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{3,30}$")]
CAMPOS_CON_CONTRATOS = ("categoria", "unidad", "moneda")  # los precios históricos dependen de ellos

router = APIRouter(tags=["catalogo"])


def _actor(usuario: Usuario) -> dict[str, str]:
    return {"id": usuario.id, "nombre": usuario.nombre}


async def _con_contratos(sesion: AsyncSession, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    filas = await sesion.scalars(
        select(LineaContrato.servicio_id).where(LineaContrato.servicio_id.in_(ids)).distinct()
    )
    return set(filas)


def _salida(servicio: ServicioCatalogo, tiene_contratos: bool) -> esquemas.Servicio:
    return esquemas.Servicio.model_validate(servicio).model_copy(
        update={"tiene_contratos": tiene_contratos}
    )


def _publicar(
    sesion: AsyncSession,
    servicio: ServicioCatalogo,
    cambio: str,
    actor: dict[str, str],
    campos: list[str] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "id": servicio.id,
        "codigo": servicio.codigo,
        "nombre": servicio.nombre,
        "categoria": servicio.categoria,
        "unidad": servicio.unidad,
        "moneda": servicio.moneda,
        "activo": servicio.activo,
        "cambio": cambio,
        "campos": campos or [],
        "actor": actor,
    }
    registrar_evento(sesion, Outbox, "servicio.actualizado", payload)


def _duplicado() -> ErrorDominio:
    mensaje = "Ya existe un servicio con ese código."
    return ErrorDominio(
        409,
        "Conflicto",
        mensaje,
        {"codigo": "servicio_duplicado", "errores": [{"campo": "codigo", "mensaje": mensaje}]},
    )


@router.get("/servicios")
async def listar_servicios(
    sesion: Sesion, usuario: Interno, incluir_inactivos: bool = False
) -> list[esquemas.Servicio]:
    if incluir_inactivos and "admin" not in usuario.roles:
        raise ErrorDominio(
            403, "Sin permiso", "Solo administración puede ver los servicios inactivos."
        )
    consulta = select(ServicioCatalogo).order_by(
        ServicioCatalogo.categoria, ServicioCatalogo.codigo
    )
    if not incluir_inactivos:
        consulta = consulta.where(ServicioCatalogo.activo.is_(True))
    servicios = list((await sesion.scalars(consulta)).all())
    usados = await _con_contratos(sesion, [s.id for s in servicios])
    return [_salida(s, s.id in usados) for s in servicios]


@router.post("/servicios", status_code=201)
async def crear_servicio(
    datos: esquemas.ServicioNuevo, sesion: Sesion, usuario: Admin
) -> esquemas.Servicio:
    servicio = ServicioCatalogo(id=uuid.uuid4(), activo=True, **datos.model_dump())
    try:
        async with sesion.begin():
            existente = await sesion.scalar(
                select(ServicioCatalogo.id).where(ServicioCatalogo.codigo == datos.codigo)
            )
            if existente is not None:
                raise _duplicado()
            sesion.add(servicio)
            _publicar(sesion, servicio, "creado", _actor(usuario))
    except IntegrityError as error:  # dos altas simultáneas del mismo código
        raise _duplicado() from error
    return _salida(servicio, tiene_contratos=False)


@router.patch("/servicios/{codigo}")
async def editar_servicio(
    codigo: CodigoEnRuta, datos: esquemas.CambioServicio, sesion: Sesion, usuario: Admin
) -> esquemas.Servicio:
    async with sesion.begin():
        servicio = await sesion.scalar(
            select(ServicioCatalogo)
            .where(ServicioCatalogo.codigo == codigo.upper())
            .with_for_update()
        )
        if servicio is None:
            raise ErrorDominio(
                404, "No encontrado", "El servicio no existe.", {"codigo": "servicio_no_encontrado"}
            )
        tiene_contratos = bool(await _con_contratos(sesion, [servicio.id]))
        cambios = {
            campo: valor
            for campo, valor in datos.model_dump(exclude_none=True).items()
            if getattr(servicio, campo) != valor
        }
        bloqueados = [c for c in CAMPOS_CON_CONTRATOS if c in cambios]
        if bloqueados and tiene_contratos:
            raise ErrorDominio(
                409,
                "Conflicto",
                "El servicio ya tiene contratos: su categoría, su unidad y su moneda no se pueden "
                "cambiar.",
                {
                    "codigo": "servicio_con_contratos",
                    "errores": [
                        {
                            "campo": campo,
                            "mensaje": "No se puede cambiar porque el servicio ya tiene contratos.",
                        }
                        for campo in bloqueados
                    ],
                },
            )
        activo = cambios.pop("activo", None)
        actor = _actor(usuario)
        for campo, valor in cambios.items():
            setattr(servicio, campo, valor)
        if cambios:
            _publicar(sesion, servicio, "actualizado", actor, sorted(cambios))
        if activo is not None:
            servicio.activo = activo
            _publicar(sesion, servicio, "activado" if activo else "desactivado", actor)
    return _salida(servicio, tiene_contratos)
