"""Lectura de la copia local para los cálculos de dominio."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from inteligencia.dominio.precios import Observacion, plazo_en_meses
from inteligencia.modelos import (
    Configuracion,
    Contrato,
    Desempeno,
    EventoProcesado,
    LineaContrato,
    ModeloBenchmark,
    Proveedor,
    Servicio,
    TipoCambio,
)


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


async def proveedores(sesion: AsyncSession) -> list[Proveedor]:
    return list((await sesion.scalars(select(Proveedor))).all())


async def servicios(sesion: AsyncSession) -> list[Servicio]:
    return list((await sesion.scalars(select(Servicio))).all())


async def contratos(sesion: AsyncSession) -> list[Contrato]:
    """Con sus líneas (las carga la relación `selectin`)."""
    return list((await sesion.scalars(select(Contrato))).all())


async def tipos_cambio(sesion: AsyncSession) -> dict[date, Decimal]:
    filas = await sesion.execute(select(TipoCambio.periodo, TipoCambio.usd_mxn))
    return {periodo: usd_mxn for periodo, usd_mxn in filas}


async def desempeno(sesion: AsyncSession) -> list[Desempeno]:
    return list((await sesion.scalars(select(Desempeno))).all())


async def clave_datos(sesion: AsyncSession) -> tuple[object, ...]:
    """Cambia cuando se aplica un evento, se guarda la configuración o se promueve un modelo.

    El conteo, además del máximo, detecta un evento que confirmó tarde con una hora anterior.
    """
    # ponytail: cuenta evento_procesado completo en cada consulta (~1 ms con 10,000 eventos); un
    # contador propio si la tabla llega a millones.
    fila = (
        await sesion.execute(
            select(
                select(func.count()).select_from(EventoProcesado).scalar_subquery(),
                select(func.max(EventoProcesado.procesado_en)).scalar_subquery(),
                select(Configuracion.actualizado_en).scalar_subquery(),
                select(func.max(ModeloBenchmark.version))
                .where(ModeloBenchmark.promovido)
                .scalar_subquery(),
            )
        )
    ).one()
    return tuple(fila)
