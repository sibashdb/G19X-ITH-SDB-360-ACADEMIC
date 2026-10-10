from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from proveedores.importacion.esquemas import Categoria, Moneda, Unidad

# Pydantic valida el patrón antes de pasar a mayúsculas: se aceptan minúsculas y se normalizan.
CodigoServicio = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9-]{3,30}$"),
]
NombreServicio = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


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
    activo: bool
    tiene_contratos: bool = False


class ServicioNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: CodigoServicio
    nombre: NombreServicio
    categoria: Categoria
    unidad: Unidad
    moneda: Moneda


class CambioServicio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: NombreServicio | None = None
    categoria: Categoria | None = None
    unidad: Unidad | None = None
    moneda: Moneda | None = None
    activo: bool | None = None


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
