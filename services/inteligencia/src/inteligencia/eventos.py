"""Copia local de los datos de proveedores, alimentada por sus eventos.

Cada evento se aplica en una transacción que también registra su event_id: un evento repetido choca
con esa clave y no se aplica dos veces. Los eventos pueden llegar en desorden (un contrato antes que
su proveedor), por eso la copia no tiene llaves foráneas entre entidades.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from typing import Any

from comun.consumidor import Atender, EventoInvalido
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inteligencia.modelos import (
    Contrato,
    Desempeno,
    EventoProcesado,
    LineaContrato,
    Proveedor,
    Servicio,
    TipoCambio,
)


def _uuid(valor: Any) -> uuid.UUID:
    return uuid.UUID(str(valor))


def _fecha(valor: Any) -> date:
    return date.fromisoformat(str(valor))


def _decimal(valor: Any) -> Decimal:
    return Decimal(str(valor))


async def _proveedor(sesion: AsyncSession, p: dict[str, Any]) -> None:
    consulta = insert(Proveedor).values(
        id=_uuid(p["id"]),
        rfc=str(p["rfc"]),
        nombre=str(p["nombre"]),
        tamano=str(p["tamano"]),
        categorias=[str(c) for c in p["categorias"]],
        activo=bool(p["activo"]),
    )
    columnas = ("rfc", "nombre", "tamano", "categorias", "activo")
    await sesion.execute(
        consulta.on_conflict_do_update(
            index_elements=[Proveedor.id], set_={c: consulta.excluded[c] for c in columnas}
        )
    )


async def _servicio(sesion: AsyncSession, p: dict[str, Any]) -> None:
    """La copia de la importación y la edición del catálogo traen los mismos datos del servicio."""
    consulta = insert(Servicio).values(
        id=_uuid(p["id"]),
        codigo=str(p["codigo"]),
        nombre=str(p["nombre"]),
        categoria=str(p["categoria"]),
        unidad=str(p["unidad"]),
        moneda=str(p["moneda"]),
        activo=bool(p["activo"]),
    )
    columnas = ("codigo", "nombre", "categoria", "unidad", "moneda", "activo")
    await sesion.execute(
        consulta.on_conflict_do_update(
            index_elements=[Servicio.id], set_={c: consulta.excluded[c] for c in columnas}
        )
    )


async def _tipo_cambio(sesion: AsyncSession, p: dict[str, Any]) -> None:
    consulta = insert(TipoCambio).values(
        periodo=_fecha(p["periodo"]), usd_mxn=_decimal(p["usd_mxn"])
    )
    await sesion.execute(
        consulta.on_conflict_do_update(
            index_elements=[TipoCambio.periodo], set_={"usd_mxn": consulta.excluded.usd_mxn}
        )
    )


async def _contrato(sesion: AsyncSession, p: dict[str, Any]) -> None:
    """Los contratos no cambian después de importarse: uno repetido (reproceso) no hace nada."""
    contrato_id = _uuid(p["id"])
    lineas = [
        {
            "contrato_id": contrato_id,
            "codigo_servicio": str(linea["codigo_servicio"]),
            "categoria": str(linea["categoria"]),
            "unidad": str(linea["unidad"]),
            "cantidad": _decimal(linea["cantidad"]),
            "precio_unitario": _decimal(linea["precio_unitario"]),
        }
        for linea in p["lineas"]
    ]
    await sesion.execute(
        insert(Contrato)
        .values(
            id=contrato_id,
            folio=str(p["folio"]),
            proveedor_id=_uuid(p["proveedor_id"]),
            tipo=str(p["tipo"]),
            fecha_inicio=_fecha(p["fecha_inicio"]),
            fecha_fin=_fecha(p["fecha_fin"]),
            moneda=str(p["moneda"]),
        )
        .on_conflict_do_nothing(index_elements=[Contrato.id])
    )
    if lineas:
        await sesion.execute(insert(LineaContrato).on_conflict_do_nothing(), lineas)


async def _desempeno(sesion: AsyncSession, p: dict[str, Any]) -> None:
    metricas = {
        "sla_cumplimiento_pct": _decimal(p["sla_cumplimiento_pct"]),
        "tiempo_resolucion_h": _decimal(p["tiempo_resolucion_h"]),
        "incidentes_criticos": int(p["incidentes_criticos"]),
        "entregas_a_tiempo_pct": _decimal(p["entregas_a_tiempo_pct"]),
        "satisfaccion": _decimal(p["satisfaccion"]),
    }
    consulta = insert(Desempeno).values(
        proveedor_id=_uuid(p["proveedor_id"]), periodo=_fecha(p["periodo"]), **metricas
    )
    await sesion.execute(
        consulta.on_conflict_do_update(
            index_elements=[Desempeno.proveedor_id, Desempeno.periodo],
            set_={c: consulta.excluded[c] for c in metricas},
        )
    )


APLICADORES: dict[str, Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]] = {
    "proveedor.actualizado": _proveedor,
    "servicio.actualizado": _servicio,
    "tipo_cambio.registrado": _tipo_cambio,
    "contrato.registrado": _contrato,
    "desempeno.registrado": _desempeno,
}


async def aplicar(sesion: AsyncSession, sobre: dict[str, Any]) -> bool:
    """Aplica el evento en la transacción en curso; False si ese event_id ya se había aplicado."""
    tipo = str(sobre["type"])
    nuevo = await sesion.scalar(
        insert(EventoProcesado)
        .values(event_id=str(sobre["event_id"]), tipo=tipo)
        .on_conflict_do_nothing(index_elements=[EventoProcesado.event_id])
        .returning(EventoProcesado.event_id)
    )
    if nuevo is None:
        return False
    aplicador = APLICADORES.get(tipo)
    if aplicador is not None:
        await aplicador(sesion, sobre["payload"])
    return True


def atendedor(fabrica: async_sessionmaker[AsyncSession]) -> Atender:
    """La función que el consumidor común llama con cada sobre de evento."""

    async def atender(sobre: dict[str, Any]) -> None:
        try:
            async with fabrica() as sesion, sesion.begin():
                await aplicar(sesion, sobre)
        # Un ValueError (fecha o UUID inválidos) ya lo trata el consumidor como evento inválido.
        except (KeyError, TypeError, AttributeError, ArithmeticError) as exc:
            raise EventoInvalido(repr(exc)) from exc

    return atender
