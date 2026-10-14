"""Términos de una oferta, su utilidad para el comprador y su precisión (spec §6.1 y §6.4).

Cada término (el precio de una línea o una palanca) va del ideal del comprador, que vale 1, a su
límite, que vale 0. La dirección sale de esos dos valores: si el ideal es menor que el límite,
menos es mejor. Un valor más allá del límite hace inválida la oferta completa.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

CLAVES = (
    "precio",
    "plazo_meses",
    "plazo_pago_dias",
    "sla_disponibilidad",
    "tope_aumento_pct",
    "cuota_implementacion",
)
PALANCAS = CLAVES[1:]  # las que no son el precio

CENTAVO = Decimal("0.01")
PRECISION: dict[str, Decimal] = {
    "precio": CENTAVO,
    "plazo_meses": Decimal(1),
    "plazo_pago_dias": Decimal(1),
    "sla_disponibilidad": CENTAVO,
    "tope_aumento_pct": Decimal("0.1"),
    "cuota_implementacion": CENTAVO,
}
MENSAJE_PRECISION: dict[str, str] = {
    "precio": "Use como máximo 2 decimales.",
    "plazo_meses": "Use un número entero.",
    "plazo_pago_dias": "Use un número entero.",
    "sla_disponibilidad": "Use como máximo 2 decimales.",
    "tope_aumento_pct": "Use como máximo 1 decimal.",
    "cuota_implementacion": "Use como máximo 2 decimales.",
}
MAXIMO_MONTO = Decimal(10_000_000)
# El precio además debe ser mayor que 0 (lo revisa problema_de_valor).
RANGOS: dict[str, tuple[Decimal, Decimal]] = {
    "precio": (Decimal(0), MAXIMO_MONTO),
    "plazo_meses": (Decimal(1), Decimal(60)),
    "plazo_pago_dias": (Decimal(0), Decimal(180)),
    "sla_disponibilidad": (Decimal(0), Decimal(100)),
    "tope_aumento_pct": (Decimal(0), Decimal(100)),
    "cuota_implementacion": (Decimal(0), MAXIMO_MONTO),
}


def redondear(clave: str, valor: Decimal, modo: str = ROUND_HALF_UP) -> Decimal:
    return valor.quantize(PRECISION[clave], rounding=modo)


def problema_de_valor(clave: str, valor: Decimal) -> str | None:
    """Por qué no se acepta un valor para ese término (rango o precisión); None si se acepta."""
    minimo, maximo = RANGOS[clave]
    if clave == "precio" and valor <= 0:
        return "Debe ser mayor que 0."
    if clave == "cuota_implementacion" and valor < 0:
        return "No puede ser negativo."
    if valor > maximo and maximo == MAXIMO_MONTO:
        return f"Debe ser como máximo {maximo:,}."
    if not minimo <= valor <= maximo:
        return f"Debe estar entre {minimo} y {maximo}."
    if valor != redondear(clave, valor):
        return MENSAJE_PRECISION[clave]
    return None


@dataclass(frozen=True)
class Rango:
    ideal: Decimal
    limite: Decimal

    def __post_init__(self) -> None:
        if self.ideal == self.limite:
            raise ValueError("El ideal y el límite deben ser distintos")

    @property
    def menos_es_mejor(self) -> bool:
        return self.ideal < self.limite

    def utilidad(self, valor: Decimal) -> float:
        return min(1.0, max(0.0, float((self.limite - valor) / (self.limite - self.ideal))))

    def valido(self, valor: Decimal) -> bool:
        return valor <= self.limite if self.menos_es_mejor else valor >= self.limite

    def acotar(self, valor: Decimal) -> Decimal:
        """El valor, llevado al límite si lo cruzaba."""
        return valor if self.valido(valor) else self.limite


@dataclass(frozen=True)
class Linea:
    id: str
    nombre: str
    cantidad: Decimal
    rango: Rango
    referencia: Decimal | None = None  # P50 de la foto; sin referencia, la cordura usa el límite


@dataclass(frozen=True)
class Palanca:
    clave: str
    peso: int
    rango: Rango


@dataclass(frozen=True)
class Terminos:
    peso_precio: int
    lineas: tuple[Linea, ...]
    palancas: tuple[Palanca, ...] = ()


@dataclass(frozen=True)
class Valores:
    """Los términos de una oferta: precio unitario por línea (por id) y valor por palanca."""

    precios: Mapping[str, Decimal]
    palancas: Mapping[str, Decimal]

    def a_json(self) -> dict[str, dict[str, str]]:
        return {
            "precios": {linea: str(valor) for linea, valor in self.precios.items()},
            "palancas": {clave: str(valor) for clave, valor in self.palancas.items()},
        }

    @classmethod
    def de_json(cls, datos: Mapping[str, Any]) -> "Valores":
        return cls(
            precios={str(k): Decimal(str(v)) for k, v in datos["precios"].items()},
            palancas={str(k): Decimal(str(v)) for k, v in datos["palancas"].items()},
        )


def transformar(
    terminos: Terminos, valores: Valores, f: Callable[[str, Rango, Decimal], Decimal]
) -> Valores:
    """Aplica f(clave, rango, valor) a cada término."""
    return Valores(
        precios={
            linea.id: f("precio", linea.rango, valores.precios[linea.id])
            for linea in terminos.lineas
        },
        palancas={
            p.clave: f(p.clave, p.rango, valores.palancas[p.clave]) for p in terminos.palancas
        },
    )


def combinar(
    terminos: Terminos,
    a: Valores,
    b: Valores,
    f: Callable[[str, Rango, Decimal, Decimal], Decimal],
) -> Valores:
    """Aplica f(clave, rango, valor de a, valor de b) a cada término."""
    return Valores(
        precios={
            linea.id: f("precio", linea.rango, a.precios[linea.id], b.precios[linea.id])
            for linea in terminos.lineas
        },
        palancas={
            p.clave: f(p.clave, p.rango, a.palancas[p.clave], b.palancas[p.clave])
            for p in terminos.palancas
        },
    )


def ideales(terminos: Terminos) -> Valores:
    return Valores(
        {linea.id: linea.rango.ideal for linea in terminos.lineas},
        {p.clave: p.rango.ideal for p in terminos.palancas},
    )


def fuera_de_limite(terminos: Terminos, valores: Valores) -> list[str]:
    """Las líneas (por id) y las palancas (por clave) que cruzan su límite."""
    return [
        linea.id for linea in terminos.lineas if not linea.rango.valido(valores.precios[linea.id])
    ] + [p.clave for p in terminos.palancas if not p.rango.valido(valores.palancas[p.clave])]


def es_valida(terminos: Terminos, valores: Valores) -> bool:
    return not fuera_de_limite(terminos, valores)


def utilidades(terminos: Terminos, valores: Valores) -> dict[str, float]:
    """La utilidad de cada término: por id de línea y por clave de palanca."""
    return {
        linea.id: linea.rango.utilidad(valores.precios[linea.id]) for linea in terminos.lineas
    } | {p.clave: p.rango.utilidad(valores.palancas[p.clave]) for p in terminos.palancas}


def utilidad(terminos: Terminos, valores: Valores) -> float:
    """U = Σ wᵢ·uᵢ; el precio reparte su peso entre las líneas según cantidad x límite."""
    u = utilidades(terminos, valores)
    total = sum(linea.cantidad * linea.rango.limite for linea in terminos.lineas)
    u_precio = sum(
        float(linea.cantidad * linea.rango.limite / total) * u[linea.id]
        for linea in terminos.lineas
    )
    return (
        terminos.peso_precio * u_precio + sum(p.peso * u[p.clave] for p in terminos.palancas)
    ) / 100
