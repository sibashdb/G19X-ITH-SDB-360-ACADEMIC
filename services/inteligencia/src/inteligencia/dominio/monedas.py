"""Conversión de montos a MXN con el tipo de cambio vigente."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

CENTAVOS = Decimal("0.01")


def tipo_cambio_en(tipos: Mapping[date, Decimal], fecha: date) -> Decimal | None:
    """El tipo de cambio vigente en `fecha` (o el más viejo si `fecha` es anterior a todos)."""
    if not tipos:
        return None
    anteriores = [periodo for periodo in tipos if periodo <= fecha]
    return tipos[max(anteriores)] if anteriores else tipos[min(tipos)]


def a_mxn(monto: Decimal, moneda: str, usd_mxn: Decimal | None) -> Decimal:
    if moneda == "MXN":
        return monto
    # ponytail: sin tipo de cambio registrado, los montos en USD no se pueden convertir y no
    # cuentan; con el ERP de verdad siempre hay al menos un periodo.
    return monto * usd_mxn if usd_mxn is not None else Decimal(0)
