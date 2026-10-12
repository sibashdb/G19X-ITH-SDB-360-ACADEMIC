"""Contratos tal como los usan las alertas y el Tablero (ids como texto)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from inteligencia.dominio.precios import cantidad_mensual, plazo_en_meses


@dataclass(frozen=True)
class Linea:
    codigo: str
    servicio: str  # nombre legible
    categoria: str
    unidad: str
    cantidad: Decimal
    precio: Decimal


@dataclass(frozen=True)
class ContratoInfo:
    id: str
    folio: str
    proveedor_id: str
    proveedor: str  # nombre legible
    tipo: str
    fecha_inicio: date
    fecha_fin: date
    moneda: str
    lineas: tuple[Linea, ...]

    @property
    def plazo_meses(self) -> int:
        return plazo_en_meses(self.fecha_inicio, self.fecha_fin)

    def vigente(self, fecha: date) -> bool:
        return self.fecha_inicio <= fecha <= self.fecha_fin

    def valor_mensual(self) -> Decimal:
        """Lo que cuesta al mes, en la moneda del contrato."""
        return sum(
            (
                cantidad_mensual(linea.cantidad, linea.unidad, self.plazo_meses) * linea.precio
                for linea in self.lineas
            ),
            Decimal(0),
        )
