"""Escenarios de la simulación a partir del generador: compras y renovaciones con semilla fija."""

import random
import statistics
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from generador.modelo import DatosSinteticos

VENTANA_DIAS = 730  # 24 meses, como el benchmark de inteligencia
CUATRO_DECIMALES = Decimal("0.0001")


@dataclass(frozen=True)
class Banda:
    p25: Decimal
    p50: Decimal
    p75: Decimal


def bandas(datos: DatosSinteticos, hoy: date) -> dict[str, Banda]:
    """P25/P50/P75 del precio unitario de cada servicio en los contratos de los últimos 24 meses."""
    precios: dict[str, list[float]] = defaultdict(list)
    for fila in datos.contratos:
        if 0 <= (hoy - date.fromisoformat(fila["fecha_inicio"])).days <= VENTANA_DIAS:
            precios[fila["codigo_servicio"]].append(float(fila["precio_unitario"]))
    resultado: dict[str, Banda] = {}
    for codigo, valores in precios.items():
        if len(valores) >= 4:
            p25, p50, p75 = statistics.quantiles(valores, n=4, method="inclusive")
            resultado[codigo] = Banda(
                *(Decimal(repr(v)).quantize(CUATRO_DECIMALES) for v in (p25, p50, p75))
            )
    return resultado


@dataclass(frozen=True)
class LineaEscenario:
    codigo: str
    cantidad: Decimal


@dataclass(frozen=True)
class Escenario:
    tipo: str  # compra o renovacion
    titulo: str
    rfcs: tuple[str, ...]
    lineas: tuple[LineaEscenario, ...] = ()  # compra
    folio: str | None = None  # renovación: el contrato vigente
    con_plazo_de_pago: bool = False


def _vigente(fila: dict[str, str], hoy: date) -> bool:
    return date.fromisoformat(fila["fecha_inicio"]) <= hoy <= date.fromisoformat(fila["fecha_fin"])


def escenarios(
    datos: DatosSinteticos,
    hoy: date,
    compras: int = 20,
    renovaciones: int = 10,
    semilla: int = 7,
) -> list[Escenario]:
    rng = random.Random(semilla)  # noqa: S311 - simulación reproducible, no criptografía
    referencias = bandas(datos, hoy)
    servicios = {s.codigo: s for s in datos.servicios}
    activos = [p for p in datos.proveedores if p.activo]
    cantidades: dict[str, list[Decimal]] = defaultdict(list)
    for fila in datos.contratos:
        cantidades[fila["codigo_servicio"]].append(Decimal(fila["cantidad"]))
    resultado: list[Escenario] = []
    categorias = sorted({s.categoria for s in datos.servicios})
    for numero in range(compras):
        categoria = rng.choice(categorias)
        candidatos = [p for p in activos if categoria in p.categorias]
        codigos = sorted(
            c for c, s in servicios.items() if s.categoria == categoria and c in referencias
        )
        if len(candidatos) < 2 or not codigos:
            continue
        moneda = servicios[rng.choice(codigos)].moneda
        codigos = [c for c in codigos if servicios[c].moneda == moneda]
        elegidos = rng.sample(codigos, k=min(len(codigos), rng.randint(1, 3)))
        invitados = rng.sample(candidatos, k=min(len(candidatos), rng.randint(2, 5)))
        resultado.append(
            Escenario(
                "compra",
                f"Compra simulada {numero + 1}",
                tuple(p.rfc for p in invitados),
                tuple(LineaEscenario(c, statistics.median_low(cantidades[c])) for c in elegidos),
                con_plazo_de_pago=numero % 2 == 1,
            )
        )
    rfcs_activos = {p.rfc for p in activos}
    vigentes = sorted(
        {
            fila["folio"]: fila
            for fila in datos.contratos
            if _vigente(fila, hoy) and fila["rfc_proveedor"] in rfcs_activos
        }.items()
    )
    for folio, fila in rng.sample(vigentes, k=min(len(vigentes), renovaciones)):
        resultado.append(
            Escenario(
                "renovacion",
                f"Renovación simulada {folio}",
                (fila["rfc_proveedor"],),
                folio=folio,
                con_plazo_de_pago=True,
            )
        )
    return resultado


def contratos_por_proveedor(
    datos: DatosSinteticos, ids: Callable[[str], str]
) -> dict[str, list[dict[str, Any]]]:
    """Los contratos como los devuelve GET /proveedores/{id}/contratos de proveedores."""
    servicios = {s.codigo: s for s in datos.servicios}
    por_folio: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fila in datos.contratos:
        por_folio[fila["folio"]].append(fila)
    resultado: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for folio, filas in por_folio.items():
        cabecera = filas[0]
        resultado[ids(cabecera["rfc_proveedor"])].append(
            {
                "id": ids(folio),
                "folio": folio,
                "tipo": cabecera["tipo"],
                "fecha_inicio": cabecera["fecha_inicio"],
                "fecha_fin": cabecera["fecha_fin"],
                "moneda": cabecera["moneda"],
                "plazo_pago_dias": int(cabecera["plazo_pago_dias"]),
                "sla_disponibilidad": cabecera["sla_disponibilidad"] or None,
                "tope_aumento_pct": cabecera["tope_aumento_pct"] or None,
                "cuota_implementacion": cabecera["cuota_implementacion"],
                "lineas": [
                    {
                        "codigo_servicio": fila["codigo_servicio"],
                        "nombre_servicio": servicios[fila["codigo_servicio"]].nombre,
                        "unidad": servicios[fila["codigo_servicio"]].unidad,
                        "cantidad": fila["cantidad"],
                        "precio_unitario": fila["precio_unitario"],
                    }
                    for fila in filas
                ],
            }
        )
    return dict(resultado)
