"""Precio justo por línea base: percentiles de los contratos recientes del mismo servicio.

Funciones puras: reciben las observaciones ya cargadas y no hacen E/S.
"""

import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

MIN_OBSERVACIONES = 8
VENTANA_MESES = 24
UNIDADES_MENSUALES = frozenset({"usuario_mes", "vcpu_mes", "gb_mes", "mes"})

Confianza = Literal["normal", "baja"]
Posicion = Literal["bajo_p25", "justo", "sobre_p75"]


@dataclass(frozen=True)
class Observacion:
    """Una línea de contrato vista como precio observado, en la moneda del servicio."""

    servicio: str
    categoria: str
    moneda: str
    fecha: date  # inicio del contrato
    cantidad: float
    precio: float
    plazo_meses: int
    tamano: str | None
    tipo: str


@dataclass(frozen=True)
class Banda:
    p25: float
    p50: float
    p75: float


@dataclass(frozen=True)
class Referencia:
    banda: Banda
    confianza: Confianza
    observaciones: int
    metodo: Literal["linea_base", "modelo"] = "linea_base"
    version: int | None = None


def meses_entre(inicio: date, fin: date) -> int:
    """Meses de calendario de `inicio` a `fin` (del 15 de enero al 1 de marzo son 2)."""
    return (fin.year - inicio.year) * 12 + fin.month - inicio.month


def sumar_meses(fecha: date, meses: int) -> date:
    """El primer día del mes que queda `meses` después (o antes) del mes de `fecha`."""
    indice = fecha.year * 12 + fecha.month - 1 + meses
    return date(indice // 12, indice % 12 + 1, 1)


def plazo_en_meses(inicio: date, fin: date) -> int:
    """Duración del contrato en meses: del 2025-01-01 al 2025-12-31 son 12."""
    return max(1, meses_entre(inicio, fin) + 1)


def meses_restantes(hoy: date, fin: date) -> int:
    """Meses que le quedan al contrato, contando el actual; 0 si ya terminó."""
    return 0 if fin < hoy else meses_entre(hoy, fin) + 1


def ajustar_por_inflacion(precio: float, desde: date, hasta: date, tasa_anual: float) -> float:
    # float(): typeshed tipa float ** float como Any; el valor no cambia.
    return precio * float((1 + tasa_anual) ** (meses_entre(desde, hasta) / 12))


def cuartiles(valores: Sequence[float]) -> Banda:
    if len(valores) == 1:
        return Banda(valores[0], valores[0], valores[0])
    # sorted: el redondeo de punto flotante no debe dejar P25 > P50 con valores casi iguales.
    p25, p50, p75 = sorted(statistics.quantiles(valores, n=4, method="inclusive"))
    return Banda(p25, p50, p75)


def _cortes(cantidades: Sequence[float]) -> tuple[float, float]:
    if len(cantidades) < 3:
        medio = statistics.median(cantidades)
        return medio, medio
    primero, segundo = statistics.quantiles(cantidades, n=3, method="inclusive")
    return primero, segundo


def _tercil(cantidad: float, cortes: tuple[float, float]) -> int:
    return 0 if cantidad <= cortes[0] else 1 if cantidad <= cortes[1] else 2


def linea_base(
    observaciones: Iterable[Observacion],
    servicio: str,
    categoria: str,
    cantidad: float,
    fecha: date,
    tasa_inflacion: float,
) -> Referencia | None:
    """P25/P50/P75 del servicio para esa cantidad a la `fecha`; None sin contratos recientes.

    Usa los contratos de los últimos 24 meses del mismo tercil de cantidad, con los precios llevados
    a la `fecha` por inflación. Con menos de MIN_OBSERVACIONES en el tercil, aplica a la mediana del
    servicio la dispersión relativa de toda su categoría y marca la referencia como de baja
    confianza.
    """
    desde = sumar_meses(fecha, -VENTANA_MESES)
    ventana = [o for o in observaciones if o.categoria == categoria and desde < o.fecha <= fecha]
    propios = [o for o in ventana if o.servicio == servicio]
    if not propios:
        return None

    def ajustado(o: Observacion) -> float:
        return ajustar_por_inflacion(o.precio, o.fecha, fecha, tasa_inflacion)

    cortes = _cortes([o.cantidad for o in propios])
    tercil = _tercil(cantidad, cortes)
    mismos = [ajustado(o) for o in propios if _tercil(o.cantidad, cortes) == tercil]
    if len(mismos) >= MIN_OBSERVACIONES:
        return Referencia(cuartiles(mismos), "normal", len(mismos))
    por_servicio: dict[str, list[float]] = defaultdict(list)
    for o in ventana:
        por_servicio[o.servicio].append(ajustado(o))
    razones: list[float] = []
    for precios in por_servicio.values():
        mediana = statistics.median(precios)
        razones.extend(p / mediana for p in precios)
    base = statistics.median(ajustado(o) for o in propios)
    relativa = cuartiles(razones)
    banda = Banda(relativa.p25 * base, relativa.p50 * base, relativa.p75 * base)
    return Referencia(banda, "baja", len(propios))


def cantidad_mensual(cantidad: Decimal, unidad: str, plazo_meses: int) -> Decimal:
    """Por mes: las unidades mensuales ya lo son; las de consumo (hora, ticket) son del contrato."""
    return cantidad if unidad in UNIDADES_MENSUALES else cantidad / plazo_meses


def posicion(precio: float, banda: Banda) -> Posicion:
    if precio < banda.p25:
        return "bajo_p25"
    return "sobre_p75" if precio > banda.p75 else "justo"


def ahorro_potencial(precio: Decimal, p50: Decimal, cantidad_mes: Decimal, meses: int) -> Decimal:
    """Lo que se ahorraría en `meses` pagando el P50 en vez del precio actual; nunca negativo."""
    ahorro = max(Decimal(0), (precio - p50) * cantidad_mes * meses)
    return ahorro.quantize(Decimal("0.01"))
