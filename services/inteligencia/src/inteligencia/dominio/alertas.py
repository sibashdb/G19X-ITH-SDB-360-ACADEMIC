"""Alertas: contratos por vencer, precios sobre el mercado y proveedores en riesgo.

Se calculan al consultar; no tienen estado ("atendida") en este sub-proyecto.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from inteligencia.dominio.contratos import ContratoInfo, Linea
from inteligencia.dominio.precios import (
    Banda,
    ahorro_potencial,
    cantidad_mensual,
    meses_restantes,
)

Severidad = Literal["alta", "media", "informativa"]
TipoAlerta = Literal["vencimiento", "sobreprecio", "riesgo"]
ORDEN_SEVERIDAD: dict[str, int] = {"alta": 0, "media": 1, "informativa": 2}
DIAS_VENCIMIENTO: tuple[tuple[int, Severidad], ...] = (
    (30, "alta"),
    (60, "media"),
    (90, "informativa"),
)
CAIDA_RIESGO = 10.0  # puntos en 3 meses
NOMBRES_UNIDAD = {
    "usuario_mes": "usuario al mes",
    "vcpu_mes": "vCPU al mes",
    "gb_mes": "GB al mes",
    "mes": "mes",
    "hora": "hora",
    "ticket": "ticket",
}


@dataclass(frozen=True)
class Alerta:
    id: str
    tipo: TipoAlerta
    severidad: Severidad
    titulo: str
    explicacion: str
    entidad_tipo: Literal["contrato", "proveedor"]
    entidad_id: str
    entidad_nombre: str
    proveedor_id: str
    proveedor_nombre: str
    fecha: date
    ahorro_potencial: Decimal | None = None
    moneda: str | None = None


def _dinero(valor: Decimal | float) -> str:
    return f"{valor:,.2f}"


def vencimiento(contrato: ContratoInfo, hoy: date) -> Alerta | None:
    if not contrato.vigente(hoy):
        return None
    dias = (contrato.fecha_fin - hoy).days
    severidad = next((s for limite, s in DIAS_VENCIMIENTO if dias <= limite), None)
    if severidad is None:
        return None
    cuando = "hoy" if dias == 0 else "mañana" if dias == 1 else f"en {dias} días"
    servicios = ", ".join(linea.servicio for linea in contrato.lineas)
    return Alerta(
        id=f"vencimiento:{contrato.id}",
        tipo="vencimiento",
        severidad=severidad,
        titulo=f"Vence {cuando}: {contrato.folio}",
        explicacion=(
            f"El contrato con {contrato.proveedor} ({servicios}) termina el "
            f"{contrato.fecha_fin:%d/%m/%Y}."
        ),
        entidad_tipo="contrato",
        entidad_id=contrato.id,
        entidad_nombre=contrato.folio,
        proveedor_id=contrato.proveedor_id,
        proveedor_nombre=contrato.proveedor,
        fecha=contrato.fecha_fin,
    )


def sobreprecio(contrato: ContratoInfo, linea: Linea, banda: Banda, hoy: date) -> Alerta | None:
    if float(linea.precio) <= banda.p75:
        return None
    p50 = Decimal(str(round(banda.p50, 4)))
    ahorro = ahorro_potencial(
        linea.precio,
        p50,
        cantidad_mensual(linea.cantidad, linea.unidad, contrato.plazo_meses),
        meses_restantes(hoy, contrato.fecha_fin),
    )
    unidad = NOMBRES_UNIDAD.get(linea.unidad, linea.unidad)
    return Alerta(
        id=f"sobreprecio:{contrato.id}:{linea.codigo}",
        tipo="sobreprecio",
        severidad="media",
        titulo=f"Sobreprecio en {contrato.folio}: {linea.servicio}",
        explicacion=(
            f"Paga {_dinero(linea.precio)} {contrato.moneda} por {unidad}; el mercado paga hasta "
            f"{_dinero(banda.p75)} (P75). Pagando el precio típico ({_dinero(p50)}) ahorraría "
            f"{_dinero(ahorro)} {contrato.moneda} en lo que resta del contrato."
        ),
        entidad_tipo="contrato",
        entidad_id=contrato.id,
        entidad_nombre=contrato.folio,
        proveedor_id=contrato.proveedor_id,
        proveedor_nombre=contrato.proveedor,
        fecha=hoy,
        ahorro_potencial=ahorro,
        moneda=contrato.moneda,
    )


def riesgo(
    proveedor_id: str,
    nombre: str,
    actual: float,
    anterior: float | None,
    umbral: int,
    hoy: date,
) -> Alerta | None:
    if actual < umbral:
        severidad: Severidad = "alta"
        titulo = f"Puntuación baja: {nombre}"
        explicacion = f"Su puntuación es {actual:.0f} de 100, por debajo del umbral de {umbral}."
    elif anterior is not None and anterior - actual > CAIDA_RIESGO:
        severidad = "media"
        titulo = f"Puntuación en caída: {nombre}"
        explicacion = (
            f"Bajó {anterior - actual:.0f} puntos en 3 meses (de {anterior:.0f} a {actual:.0f})."
        )
    else:
        return None
    return Alerta(
        id=f"riesgo:{proveedor_id}",
        tipo="riesgo",
        severidad=severidad,
        titulo=titulo,
        explicacion=explicacion,
        entidad_tipo="proveedor",
        entidad_id=proveedor_id,
        entidad_nombre=nombre,
        proveedor_id=proveedor_id,
        proveedor_nombre=nombre,
        fecha=hoy,
    )


def ordenar(alertas: Iterable[Alerta]) -> list[Alerta]:
    return sorted(alertas, key=lambda a: (ORDEN_SEVERIDAD[a.severidad], a.fecha, a.id))
