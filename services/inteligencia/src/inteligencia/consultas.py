"""Lectura de la copia local para los cálculos de dominio."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inteligencia.dominio.precios import Observacion, plazo_en_meses
from inteligencia.modelos import Configuracion, Contrato, LineaContrato, ModeloBenchmark, Proveedor


async def observaciones(sesion: AsyncSession) -> list[Observacion]:
    """Cada línea de contrato como precio observado (el contrato va en la moneda del servicio)."""
    filas = await sesion.execute(
        select(
            LineaContrato.codigo_servicio,
            LineaContrato.categoria,
            Contrato.moneda,
            Contrato.fecha_inicio,
            Contrato.fecha_fin,
            LineaContrato.cantidad,
            LineaContrato.precio_unitario,
            Proveedor.tamano,
            Contrato.tipo,
        )
        .join(Contrato, LineaContrato.contrato_id == Contrato.id)
        .outerjoin(Proveedor, Proveedor.id == Contrato.proveedor_id)
    )
    return [
        Observacion(
            servicio=servicio,
            categoria=categoria,
            moneda=moneda,
            fecha=inicio,
            cantidad=float(cantidad),
            precio=float(precio),
            plazo_meses=plazo_en_meses(inicio, fin),
            tamano=tamano,
            tipo=tipo,
        )
        for servicio, categoria, moneda, inicio, fin, cantidad, precio, tamano, tipo in filas
    ]


async def configuracion(sesion: AsyncSession) -> Configuracion:
    fila = await sesion.get(Configuracion, 1)
    if fila is None:
        raise LookupError("Falta la fila de configuración (la crea la migración 0001)")
    return fila


async def modelo_activo(sesion: AsyncSession) -> ModeloBenchmark | None:
    return await sesion.scalar(
        select(ModeloBenchmark)
        .where(ModeloBenchmark.promovido)
        .order_by(ModeloBenchmark.version.desc())
        .limit(1)
    )
