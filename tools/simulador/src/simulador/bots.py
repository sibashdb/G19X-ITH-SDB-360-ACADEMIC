"""Bots de proveedor (spec §13): conceden según su estilo hasta su precio de reserva oculto.

El orquestador les da su verdad oculta (lista, reserva y estilo) y hacia dónde le conviene mover
cada término; del portal solo ven lo que vería un proveedor.
"""

import random
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any

PASO = {
    "precio": Decimal("0.01"),
    "plazo_meses": Decimal(1),
    "plazo_pago_dias": Decimal(1),
    "sla_disponibilidad": Decimal("0.01"),
    "tope_aumento_pct": Decimal("0.1"),
    "cuota_implementacion": Decimal("0.01"),
}
RANGOS = {
    "precio": (Decimal("0.01"), Decimal(10_000_000)),
    "plazo_meses": (Decimal(1), Decimal(60)),
    "plazo_pago_dias": (Decimal(0), Decimal(180)),
    "sla_disponibilidad": (Decimal(0), Decimal(100)),
    "tope_aumento_pct": (Decimal(0), Decimal(100)),
    "cuota_implementacion": (Decimal(0), Decimal(10_000_000)),
}
# Estilo → (β de sus concesiones, margen de su primera oferta sobre su precio de lista).
ESTILOS: dict[str, tuple[float, Decimal]] = {
    "duro": (0.4, Decimal("0.15")),
    "flexible": (2.0, Decimal("0.05")),
    "erratico": (1.0, Decimal("0.10")),
    "manipulador": (0.4, Decimal("0.15")),  # sus ataques de texto llegan en N2
}


def cuantizar(clave: str, valor: Decimal, mas_es_mejor: bool) -> Decimal:
    """En la precisión del término, redondeado a favor del bot y dentro del rango que se acepta."""
    minimo, maximo = RANGOS[clave]
    redondeado = valor.quantize(
        PASO[clave], rounding=ROUND_CEILING if mas_es_mejor else ROUND_FLOOR
    )
    return min(maximo, max(minimo, redondeado))


@dataclass(frozen=True)
class Termino:
    """Lo que el bot pide al empezar, lo peor que acepta y si a él le conviene más."""

    clave: str  # "precio" en las líneas
    inicio: Decimal
    reserva: Decimal
    mas_es_mejor: bool

    def en(self, avance: float) -> Decimal:
        """El valor a cierta fracción del camino de su inicio a su reserva."""
        valor = self.inicio + Decimal(repr(avance)) * (self.reserva - self.inicio)
        return cuantizar(self.clave, valor, self.mas_es_mejor)

    def acepta(self, valor: Decimal) -> bool:
        return valor >= self.reserva if self.mas_es_mejor else valor <= self.reserva


@dataclass
class Bot:
    estilo: str
    precios: dict[str, Termino]  # por id de línea
    palancas: dict[str, Termino]
    rng: random.Random
    _avance: float = field(default=0.0, repr=False)

    def oferta(self, k: int, rondas: int) -> dict[str, dict[str, str]]:
        """Su oferta número k; en la última ronda ofrece su reserva (mejor y última)."""
        beta, _ = ESTILOS[self.estilo]
        if self.estilo == "erratico":
            beta = self.rng.uniform(0.3, 2.0)
        avance = 1.0 if k >= rondas else (k / rondas) ** (1 / beta)
        if self.estilo == "erratico" and k < rondas and self.rng.random() < 0.2:
            avance = max(0.0, self._avance - 0.1)  # a veces retrocede
        self._avance = avance
        return {
            "precios": {linea: str(t.en(avance)) for linea, t in self.precios.items()},
            "palancas": {clave: str(t.en(avance)) for clave, t in self.palancas.items()},
        }

    def acepta(self, propuesta: dict[str, Any]) -> bool:
        return all(
            t.acepta(Decimal(str(propuesta["precios"][linea]))) for linea, t in self.precios.items()
        ) and all(
            t.acepta(Decimal(str(propuesta["palancas"][clave])))
            for clave, t in self.palancas.items()
        )
