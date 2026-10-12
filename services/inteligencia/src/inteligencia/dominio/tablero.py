"""KPIs del Tablero, en MXN: al último tipo de cambio, y al de cada mes en la serie mensual."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from inteligencia.dominio.alertas import Alerta, ordenar
from inteligencia.dominio.contratos import ContratoInfo
from inteligencia.dominio.precios import cantidad_mensual, sumar_meses

MESES_SERIE = 24
DIAS_POR_VENCER = 90
MAX_VENCIMIENTOS = 10
CUANTOS_DESTACADOS = 5
CUANTAS_ALERTAS = 5
RANGOS_PUNTUACION = (
    ("0-19", 0, 20),
    ("20-39", 20, 40),
    ("40-59", 40, 60),
    ("60-79", 60, 80),
    ("80-100", 80, 101),
)
CENTAVOS = Decimal("0.01")


@dataclass(frozen=True)
class Vencimiento:
    contrato: ContratoInfo
    dias: int
    monto_mensual: Decimal  # MXN


@dataclass(frozen=True)
class Destacado:
    proveedor_id: str
    nombre: str
    puntuacion: float


@dataclass(frozen=True)
class Tablero:
    gasto_anual: Decimal
    variacion_pct: float | None
    por_vencer: int
    en_riesgo: int
    total_proveedores: int
    ahorro_potencial: Decimal
    gasto_por_categoria: dict[str, Decimal]
    gasto_por_mes: list[tuple[date, Decimal]]
    proximos_vencimientos: list[Vencimiento]
    alertas_principales: list[Alerta]
    mejores: list[Destacado]
    peores: list[Destacado]
    distribucion: list[tuple[str, int]]


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


def _gasto_anual(
    contratos: Sequence[ContratoInfo], fecha: date, usd_mxn: Decimal | None
) -> Decimal:
    mensual = sum(
        (a_mxn(c.valor_mensual(), c.moneda, usd_mxn) for c in contratos if c.vigente(fecha)),
        Decimal(0),
    )
    return mensual * 12


def _vigente_en_mes(contrato: ContratoInfo, mes: date) -> bool:
    fin_de_mes = sumar_meses(mes, 1) - timedelta(days=1)
    return contrato.fecha_inicio <= fin_de_mes and contrato.fecha_fin >= mes


def calcular(
    contratos: Sequence[ContratoInfo],
    tipos_cambio: Mapping[date, Decimal],
    puntuaciones: Mapping[str, float],
    nombres: Mapping[str, str],
    activos: int,
    alertas: Sequence[Alerta],
    hoy: date,
) -> Tablero:
    ultimo = tipo_cambio_en(tipos_cambio, hoy)
    actual = _gasto_anual(contratos, hoy, ultimo)
    anterior = _gasto_anual(contratos, date(hoy.year - 1, hoy.month, min(hoy.day, 28)), ultimo)
    variacion = float((actual / anterior - 1) * 100) if anterior > 0 else None

    vigentes = [c for c in contratos if c.vigente(hoy)]
    por_categoria: dict[str, Decimal] = defaultdict(Decimal)
    for contrato in vigentes:
        for linea in contrato.lineas:
            mensual = cantidad_mensual(linea.cantidad, linea.unidad, contrato.plazo_meses)
            por_categoria[linea.categoria] += a_mxn(mensual * linea.precio, contrato.moneda, ultimo)
    serie = []
    for atras in range(MESES_SERIE - 1, -1, -1):
        mes = sumar_meses(hoy, -atras)
        cambio = tipo_cambio_en(tipos_cambio, mes)
        total = sum(
            (
                a_mxn(c.valor_mensual(), c.moneda, cambio)
                for c in contratos
                if _vigente_en_mes(c, mes)
            ),
            Decimal(0),
        )
        serie.append((mes, total.quantize(CENTAVOS)))

    proximos = sorted(
        (
            Vencimiento(
                c,
                (c.fecha_fin - hoy).days,
                a_mxn(c.valor_mensual(), c.moneda, ultimo).quantize(CENTAVOS),
            )
            for c in vigentes
            if (c.fecha_fin - hoy).days <= DIAS_POR_VENCER
        ),
        key=lambda v: (v.dias, v.contrato.folio),
    )
    ahorro = sum(
        (
            a_mxn(a.ahorro_potencial, a.moneda or "MXN", ultimo)
            for a in alertas
            if a.tipo == "sobreprecio" and a.ahorro_potencial is not None
        ),
        Decimal(0),
    )
    ranking = sorted(puntuaciones.items(), key=lambda par: (-par[1], nombres.get(par[0], par[0])))
    destacados = [Destacado(pid, nombres.get(pid, pid), valor) for pid, valor in ranking]
    return Tablero(
        gasto_anual=actual.quantize(CENTAVOS),
        variacion_pct=variacion,
        por_vencer=len(proximos),
        en_riesgo=len({a.proveedor_id for a in alertas if a.tipo == "riesgo"}),
        total_proveedores=activos,
        ahorro_potencial=ahorro.quantize(CENTAVOS),
        gasto_por_categoria={
            categoria: (mensual * 12).quantize(CENTAVOS)
            for categoria, mensual in sorted(por_categoria.items())
        },
        gasto_por_mes=serie,
        proximos_vencimientos=proximos[:MAX_VENCIMIENTOS],
        alertas_principales=ordenar(alertas)[:CUANTAS_ALERTAS],
        mejores=destacados[:CUANTOS_DESTACADOS],
        peores=destacados[::-1][:CUANTOS_DESTACADOS],
        distribucion=[
            (rango, sum(1 for _, valor in ranking if bajo <= valor < alto))
            for rango, bajo, alto in RANGOS_PUNTUACION
        ],
    )
