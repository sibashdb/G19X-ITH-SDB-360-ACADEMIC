"""Ahorro logrado del Tablero: lo adjudicado frente a la primera oferta (spec del Tablero, §3)."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

CENTAVOS = Decimal("0.01")


@dataclass(frozen=True)
class Adjudicada:
    primera: Decimal  # costo total de la primera oferta, en la moneda del evento
    adjudicado: Decimal  # costo total adjudicado, en la moneda del evento
    tasa: Decimal  # MXN por unidad de la moneda del evento; 1 en MXN


@dataclass(frozen=True)
class Ahorro:
    adjudicadas: int
    primera_oferta_mxn: Decimal
    adjudicado_mxn: Decimal
    ahorro_mxn: Decimal  # negativo si la primera oferta costaba menos
    ahorro_pct: float | None  # None sin adjudicadas o si la primera oferta suma 0


def ahorro(adjudicadas: Sequence[Adjudicada]) -> Ahorro:
    """Cada costo se lleva a MXN con su tasa y se redondea a centavos antes de sumar."""
    primera = sum(((a.primera * a.tasa).quantize(CENTAVOS) for a in adjudicadas), Decimal("0.00"))
    adjudicado = sum(
        ((a.adjudicado * a.tasa).quantize(CENTAVOS) for a in adjudicadas), Decimal("0.00")
    )
    diferencia = primera - adjudicado
    pct = round(float(diferencia / primera * 100), 1) if primera else None
    return Ahorro(len(adjudicadas), primera, adjudicado, diferencia, pct)
