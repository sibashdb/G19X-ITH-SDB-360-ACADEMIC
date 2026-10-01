"""Filas de los CSV del ERP simulado. Los nombres de campo son los nombres de columna."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Categoria = Literal["licencia_saas", "nube", "consultoria", "soporte"]
Moneda = Literal["MXN", "USD"]
Unidad = Literal["usuario_mes", "vcpu_mes", "gb_mes", "mes", "hora", "ticket"]
Porcentaje = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Dinero = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)]

RFC = r"^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$"  # [0-9]: \d aceptaría dígitos no ASCII
CORREO = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
CODIGO = r"^[A-Z0-9-]{3,30}$"


def _primer_dia_del_mes(valor: date) -> date:
    if valor.day != 1:
        raise ValueError("El periodo debe ser el primer día del mes")
    return valor


class Fila(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def omitir_vacios(cls, datos: Any) -> Any:
        # Una celda vacía (o solo con espacios) equivale a "sin dato": aplica el valor
        # por defecto o produce el error "Campo obligatorio".
        if isinstance(datos, dict):
            return {
                clave: valor
                for clave, valor in datos.items()
                if valor is not None and not (isinstance(valor, str) and not valor.strip())
            }
        return datos


class FilaServicio(Fila):
    codigo: str = Field(pattern=CODIGO)
    nombre: str = Field(min_length=1, max_length=200)
    categoria: Categoria
    unidad: Unidad
    moneda: Moneda


class FilaProveedor(Fila):
    rfc: str = Field(pattern=RFC)
    nombre: str = Field(min_length=1, max_length=200)
    tamano: Literal["micro", "pequena", "mediana", "grande"]
    categorias: list[Categoria] = Field(min_length=1)
    contacto_nombre: str = Field(min_length=1, max_length=120)
    contacto_email: str = Field(pattern=CORREO, max_length=254)
    activo: bool = True

    @field_validator("categorias", mode="before")
    @classmethod
    def separar_categorias(cls, valor: Any) -> Any:
        if isinstance(valor, str):
            return [parte.strip() for parte in valor.split("|") if parte.strip()]
        return valor


class FilaTipoCambio(Fila):
    periodo: date
    usd_mxn: Decimal = Field(gt=0, lt=100, max_digits=10, decimal_places=4)

    @field_validator("periodo")
    @classmethod
    def validar_periodo(cls, valor: date) -> date:
        return _primer_dia_del_mes(valor)


class FilaDesempeno(Fila):
    rfc_proveedor: str = Field(pattern=RFC)
    periodo: date
    sla_cumplimiento_pct: Porcentaje
    tiempo_resolucion_h: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    incidentes_criticos: int = Field(ge=0, le=1_000_000)
    entregas_a_tiempo_pct: Porcentaje
    satisfaccion: Decimal = Field(ge=1, le=5, max_digits=3, decimal_places=2)

    @field_validator("periodo")
    @classmethod
    def validar_periodo(cls, valor: date) -> date:
        return _primer_dia_del_mes(valor)


class FilaContrato(Fila):
    """Una fila por línea de contrato; las filas con el mismo folio forman un contrato."""

    folio: str = Field(pattern=CODIGO)
    rfc_proveedor: str = Field(pattern=RFC)
    tipo: Literal["nuevo", "renovacion"]
    fecha_inicio: date
    fecha_fin: date
    moneda: Moneda
    plazo_pago_dias: int = Field(ge=0, le=180)
    sla_disponibilidad: Decimal | None = Field(
        default=None, ge=90, le=100, max_digits=5, decimal_places=2
    )
    tope_aumento_pct: Porcentaje | None = None
    cuota_implementacion: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=4)
    codigo_servicio: str = Field(pattern=CODIGO)
    cantidad: Dinero
    precio_unitario: Dinero

    @model_validator(mode="after")
    def validar_vigencia(self) -> "FilaContrato":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self

    def cabecera(self) -> tuple[object, ...]:
        """Datos que deben ser idénticos en todas las líneas de un mismo folio."""
        return (
            self.rfc_proveedor,
            self.tipo,
            self.fecha_inicio,
            self.fecha_fin,
            self.moneda,
            self.plazo_pago_dias,
            self.sla_disponibilidad,
            self.tope_aumento_pct,
            self.cuota_implementacion,
        )
