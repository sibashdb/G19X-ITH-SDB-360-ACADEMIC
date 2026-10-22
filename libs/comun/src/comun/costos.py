"""Costo total de un contrato: la regla que comparten la recomendación de adjudicación
(`inteligencia`) y el Tablero (`negociacion`)."""

from collections.abc import Iterable
from decimal import Decimal

UNIDADES_MENSUALES = frozenset({"usuario_mes", "vcpu_mes", "gb_mes", "mes"})


def costo_total(
    lineas: Iterable[tuple[str, Decimal, Decimal]], plazo_meses: int, cuota: Decimal
) -> Decimal:
    """Suma de precio por cantidad de cada línea `(unidad, cantidad, precio)`, por el plazo en las
    unidades mensuales, más la cuota. No redondea."""
    total = cuota
    for unidad, cantidad, precio in lineas:
        meses = plazo_meses if unidad in UNIDADES_MENSUALES else 1
        total += precio * cantidad * meses
    return total
