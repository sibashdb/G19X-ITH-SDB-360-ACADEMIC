from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesdeOrm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProveedorResumen(DesdeOrm):
    id: UUID
    rfc: str
    nombre: str
    tamano: str
    categorias: list[str]
    activo: bool


class PaginaProveedores(BaseModel):
    total: int
    elementos: list[ProveedorResumen]


class ProveedorDetalle(ProveedorResumen):
    contacto_nombre: str
    contacto_email: str
    contratos_vigentes: int


class Servicio(DesdeOrm):
    id: UUID
    codigo: str
    nombre: str
    categoria: str
    unidad: str
    moneda: str


class LineaContratoSalida(BaseModel):
    codigo_servicio: str
    nombre_servicio: str
    unidad: str
    cantidad: Decimal
    precio_unitario: Decimal


class ContratoSalida(BaseModel):
    id: UUID
    folio: str
    tipo: str
    fecha_inicio: date
    fecha_fin: date
    moneda: str
    plazo_pago_dias: int
    sla_disponibilidad: Decimal | None
    tope_aumento_pct: Decimal | None
    cuota_implementacion: Decimal
    lineas: list[LineaContratoSalida]


class Desempeno(DesdeOrm):
    periodo: date
    sla_cumplimiento_pct: Decimal
    tiempo_resolucion_h: Decimal
    incidentes_criticos: int
    entregas_a_tiempo_pct: Decimal
    satisfaccion: Decimal
