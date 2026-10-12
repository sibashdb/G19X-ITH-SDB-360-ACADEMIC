"""Respuestas de la API: montos como texto decimal y puntuaciones con un decimal."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


def unitario(valor: float) -> Decimal:
    """Un precio unitario calculado, con 4 decimales como los de la base."""
    return Decimal(f"{valor:.4f}")


class AlertaSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tipo: str
    severidad: str
    titulo: str
    explicacion: str
    entidad_tipo: str
    entidad_id: str
    entidad_nombre: str
    proveedor_id: str
    proveedor_nombre: str
    fecha: date
    ahorro_potencial: Decimal | None
    moneda: str | None


class PaginaAlertas(BaseModel):
    total: int
    elementos: list[AlertaSalida]


class MontoCategoria(BaseModel):
    categoria: str
    monto: Decimal


class MontoMes(BaseModel):
    mes: date
    monto: Decimal


class VencimientoSalida(BaseModel):
    contrato_id: str
    folio: str
    proveedor_id: str
    proveedor: str
    servicios: list[str]
    fecha_fin: date
    dias: int
    monto_mensual: Decimal


class Destacado(BaseModel):
    proveedor_id: str
    nombre: str
    puntuacion: float


class RangoPuntuacion(BaseModel):
    rango: str
    proveedores: int


class TableroSalida(BaseModel):
    fecha: date
    moneda: Literal["MXN"] = "MXN"
    gasto_anual: Decimal
    variacion_pct: float | None
    por_vencer: int
    en_riesgo: int
    total_proveedores: int
    ahorro_potencial: Decimal
    gasto_por_categoria: list[MontoCategoria]
    gasto_por_mes: list[MontoMes]
    proximos_vencimientos: list[VencimientoSalida]
    alertas_principales: list[AlertaSalida]
    mejores: list[Destacado]
    peores: list[Destacado]
    distribucion: list[RangoPuntuacion]


class ServicioPrecios(BaseModel):
    codigo: str
    nombre: str
    categoria: str
    unidad: str
    moneda: str
    observaciones: int  # contratos de los últimos 24 meses


class ReferenciaSalida(BaseModel):
    codigo: str
    moneda: str
    unidad: str
    cantidad: Decimal
    plazo: int
    fecha: date
    p25: Decimal
    p50: Decimal
    p75: Decimal
    metodo: Literal["linea_base", "modelo"]
    version: int | None
    confianza: Literal["normal", "baja"]
    observaciones: int


class PuntoPrecio(BaseModel):
    fecha: date
    precio: Decimal
    cantidad: Decimal
    folio: str
    proveedor: str


class BandaMes(BaseModel):
    mes: date
    p25: Decimal
    p50: Decimal
    p75: Decimal


class HistorialPrecios(BaseModel):
    codigo: str
    moneda: str
    cantidad: Decimal  # la de las bandas
    puntos: list[PuntoPrecio]
    bandas: list[BandaMes]


class Sobreprecio(BaseModel):
    contrato_id: str
    folio: str
    proveedor_id: str
    proveedor: str
    codigo_servicio: str
    servicio: str
    moneda: str
    precio: Decimal
    p25: Decimal
    p50: Decimal
    p75: Decimal
    fecha_fin: date
    ahorro_potencial: Decimal  # en la moneda del contrato, por lo que le resta
    ahorro_potencial_mxn: Decimal
