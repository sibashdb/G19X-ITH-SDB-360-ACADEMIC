"""Copias locales de proveedores y del catálogo, alimentadas por sus eventos.

Igual que en inteligencia: cada evento se aplica en una transacción que también registra su
event_id, así que uno repetido no se aplica dos veces.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from comun.consumidor import Atender, EventoInvalido
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from negociacion.modelos import EventoProcesado, Proveedor, Servicio


def _uuid(valor: Any) -> uuid.UUID:
    return uuid.UUID(str(valor))


async def _proveedor(bd: AsyncSession, p: dict[str, Any]) -> None:
    consulta = insert(Proveedor).values(
        id=_uuid(p["id"]),
        nombre=str(p["nombre"]),
        categorias=[str(c) for c in p["categorias"]],
        contacto_nombre=str(p["contacto_nombre"]),
        contacto_email=str(p["contacto_email"]),
        activo=bool(p["activo"]),
    )
    columnas = ("nombre", "categorias", "contacto_nombre", "contacto_email", "activo")
    await bd.execute(
        consulta.on_conflict_do_update(
            index_elements=[Proveedor.id],
            set_={c: consulta.excluded[c] for c in columnas}
            | {"actualizado_en": consulta.excluded.actualizado_en},
        )
    )


async def _servicio(bd: AsyncSession, p: dict[str, Any]) -> None:
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
    await bd.execute(
        consulta.on_conflict_do_update(
            index_elements=[Servicio.id], set_={c: consulta.excluded[c] for c in columnas}
        )
    )


APLICADORES: dict[str, Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]] = {
    "proveedor.actualizado": _proveedor,
    "servicio.actualizado": _servicio,
}


async def aplicar(bd: AsyncSession, sobre: dict[str, Any]) -> bool:
    """Aplica el evento en la transacción en curso; False si ese event_id ya se había aplicado."""
    tipo = str(sobre["type"])
    nuevo = await bd.scalar(
        insert(EventoProcesado)
        .values(event_id=str(sobre["event_id"]), tipo=tipo)
        .on_conflict_do_nothing(index_elements=[EventoProcesado.event_id])
        .returning(EventoProcesado.event_id)
    )
    if nuevo is None:
        return False
    aplicador = APLICADORES.get(tipo)
    if aplicador is not None:
        await aplicador(bd, sobre["payload"])
    return True


def atendedor(fabrica: async_sessionmaker[AsyncSession]) -> Atender:
    """La función que el consumidor común llama con cada sobre de evento."""

    async def atender(sobre: dict[str, Any]) -> None:
        try:
            async with fabrica() as bd, bd.begin():
                await aplicar(bd, sobre)
        # Un ValueError (UUID inválido) ya lo trata el consumidor como evento inválido.
        except (KeyError, TypeError, AttributeError) as exc:
            raise EventoInvalido(repr(exc)) from exc

    return atender
