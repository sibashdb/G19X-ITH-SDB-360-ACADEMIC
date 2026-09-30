from datetime import date
from typing import Annotated
from uuid import UUID

from comun.auth import ROLES_INTERNOS, Usuario, requiere_rol
from comun.errores import ErrorDominio
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from proveedores.api import esquemas
from proveedores.db import obtener_sesion
from proveedores.importacion.aplicar import Entidad, ResumenImportacion, importar
from proveedores.importacion.esquemas import Categoria
from proveedores.modelos import (
    Contrato,
    LineaContrato,
    Proveedor,
    RegistroDesempeno,
    ServicioCatalogo,
)

MAX_BYTES_CSV = 10 * 1024 * 1024

Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]
Interno = Annotated[Usuario, Depends(requiere_rol(*ROLES_INTERNOS))]
Admin = Annotated[Usuario, Depends(requiere_rol("admin"))]

router = APIRouter()


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _proveedor_o_404(sesion: AsyncSession, proveedor_id: UUID) -> Proveedor:
    proveedor = await sesion.get(Proveedor, proveedor_id)
    if proveedor is None:
        raise ErrorDominio(404, "No encontrado", "El proveedor no existe")
    return proveedor


@router.get("/proveedores", tags=["proveedores"])
async def listar_proveedores(
    sesion: Sesion,
    _: Interno,
    q: Annotated[str | None, Query(max_length=100)] = None,
    categoria: Categoria | None = None,
    activo: bool | None = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 25,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> esquemas.PaginaProveedores:
    condiciones = []
    if q:
        patron = f"%{_escapar_like(q)}%"
        condiciones.append(
            or_(
                Proveedor.nombre.ilike(patron, escape="\\"),
                Proveedor.rfc.ilike(patron, escape="\\"),
            )
        )
    if categoria:
        condiciones.append(Proveedor.categorias.contains([categoria]))
    if activo is not None:
        condiciones.append(Proveedor.activo.is_(activo))
    total = await sesion.scalar(select(func.count()).select_from(Proveedor).where(*condiciones))
    filas = await sesion.scalars(
        select(Proveedor)
        .where(*condiciones)
        .order_by(Proveedor.nombre)
        .limit(limite)
        .offset(desplazamiento)
    )
    return esquemas.PaginaProveedores(
        total=total or 0,
        elementos=[esquemas.ProveedorResumen.model_validate(p) for p in filas],
    )


@router.get("/proveedores/{proveedor_id}", tags=["proveedores"])
async def obtener_proveedor(
    proveedor_id: UUID, sesion: Sesion, _: Interno
) -> esquemas.ProveedorDetalle:
    proveedor = await _proveedor_o_404(sesion, proveedor_id)
    hoy = date.today()
    vigentes = await sesion.scalar(
        select(func.count())
        .select_from(Contrato)
        .where(
            Contrato.proveedor_id == proveedor_id,
            Contrato.fecha_inicio <= hoy,
            Contrato.fecha_fin >= hoy,
        )
    )
    return esquemas.ProveedorDetalle(
        **esquemas.ProveedorResumen.model_validate(proveedor).model_dump(),
        contacto_nombre=proveedor.contacto_nombre,
        contacto_email=proveedor.contacto_email,
        contratos_vigentes=vigentes or 0,
    )


@router.get("/proveedores/{proveedor_id}/contratos", tags=["proveedores"])
async def contratos_del_proveedor(
    proveedor_id: UUID, sesion: Sesion, _: Interno
) -> list[esquemas.ContratoSalida]:
    await _proveedor_o_404(sesion, proveedor_id)
    contratos = await sesion.scalars(
        select(Contrato)
        .where(Contrato.proveedor_id == proveedor_id)
        .order_by(Contrato.fecha_inicio.desc())
        .options(selectinload(Contrato.lineas).selectinload(LineaContrato.servicio))
    )
    return [
        esquemas.ContratoSalida(
            id=c.id,
            folio=c.folio,
            tipo=c.tipo,
            fecha_inicio=c.fecha_inicio,
            fecha_fin=c.fecha_fin,
            moneda=c.moneda,
            plazo_pago_dias=c.plazo_pago_dias,
            sla_disponibilidad=c.sla_disponibilidad,
            tope_aumento_pct=c.tope_aumento_pct,
            cuota_implementacion=c.cuota_implementacion,
            lineas=[
                esquemas.LineaContratoSalida(
                    codigo_servicio=linea.servicio.codigo,
                    nombre_servicio=linea.servicio.nombre,
                    unidad=linea.servicio.unidad,
                    cantidad=linea.cantidad,
                    precio_unitario=linea.precio_unitario,
                )
                for linea in c.lineas
            ],
        )
        for c in contratos
    ]


@router.get("/proveedores/{proveedor_id}/desempeno", tags=["proveedores"])
async def desempeno_del_proveedor(
    proveedor_id: UUID,
    sesion: Sesion,
    _: Interno,
    meses: Annotated[int, Query(ge=1, le=60)] = 12,
) -> list[esquemas.Desempeno]:
    await _proveedor_o_404(sesion, proveedor_id)
    registros = await sesion.scalars(
        select(RegistroDesempeno)
        .where(RegistroDesempeno.proveedor_id == proveedor_id)
        .order_by(RegistroDesempeno.periodo.desc())
        .limit(meses)
    )
    return [esquemas.Desempeno.model_validate(r) for r in registros]


@router.get("/servicios", tags=["catalogo"])
async def listar_servicios(sesion: Sesion, _: Interno) -> list[esquemas.Servicio]:
    servicios = await sesion.scalars(
        select(ServicioCatalogo).order_by(ServicioCatalogo.categoria, ServicioCatalogo.codigo)
    )
    return [esquemas.Servicio.model_validate(s) for s in servicios]


@router.post("/importaciones/{entidad}", tags=["importacion"])
async def importar_archivo(
    entidad: Entidad,
    archivo: Annotated[UploadFile, File()],
    sesion: Sesion,
    _: Admin,
) -> ResumenImportacion:
    contenido = await archivo.read(MAX_BYTES_CSV + 1)
    if len(contenido) > MAX_BYTES_CSV:
        raise ErrorDominio(413, "Archivo demasiado grande", "El archivo excede el límite de 10 MB")
    try:
        async with sesion.begin():
            return await importar(sesion, entidad, contenido)
    except IntegrityError as error:
        # Dos importaciones simultáneas del mismo folio: la segunda pierde en el commit.
        raise ErrorDominio(
            409,
            "Conflicto",
            "Otra importación modificó los mismos registros al mismo tiempo; intente de nuevo.",
        ) from error
