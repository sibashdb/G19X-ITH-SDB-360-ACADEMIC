"""Formas de entrada y salida de la API; los montos viajan como texto decimal."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, model_validator

Codigo = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{3,30}$")]
Titulo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Cantidad = Annotated[Decimal, Field(gt=0, le=10_000_000, decimal_places=4)]
Estilo = Literal["firme", "balanceado", "flexible"]
TipoEvento = Literal["compra", "renovacion"]
EstadoEvento = Literal["borrador", "abierto", "en_evaluacion", "cancelado"]


class LineaNueva(BaseModel):
    codigo_servicio: Codigo
    cantidad: Cantidad


class EventoNuevo(BaseModel):
    tipo: TipoEvento
    titulo: Titulo
    fecha_limite: AwareDatetime
    rondas_max: int = Field(6, ge=2, le=12)
    estilo: Estilo = "balanceado"
    plazo_meses: int = Field(12, ge=1, le=60)  # en renovación sale del contrato
    lineas: list[LineaNueva] = Field(default_factory=list, max_length=20)
    proveedores: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    proveedor_id: uuid.UUID | None = None
    contrato_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _por_tipo(self) -> Self:
        if self.tipo == "compra":
            if not self.lineas:
                raise ValueError("Una compra necesita al menos una línea.")
            if not self.proveedores:
                raise ValueError("Invite al menos a un proveedor.")
            if len(set(self.proveedores)) != len(self.proveedores):
                raise ValueError("Un proveedor aparece dos veces.")
        elif self.proveedor_id is None or self.contrato_id is None:
            raise ValueError("Una renovación necesita el proveedor y el contrato.")
        return self


class Banda(BaseModel):
    p25: Decimal
    p50: Decimal
    p75: Decimal
    metodo: str
    confianza: str
    observaciones: int


class LineaSalida(BaseModel):
    id: uuid.UUID
    orden: int
    codigo_servicio: str
    nombre: str
    unidad: str
    cantidad: Decimal
    precio_vigente: Decimal | None
    ideal: Decimal | None
    limite: Decimal | None
    referencia: Banda | None


class PalancaSalida(BaseModel):
    clave: str
    nombre: str
    unidad: str
    activa: bool
    peso: int
    ideal: Decimal | None
    limite: Decimal | None
    vigente: Decimal | None  # el valor del contrato, en renovación


class Invitado(BaseModel):
    id: uuid.UUID
    nombre: str


class ProblemaSalida(BaseModel):
    campo: str
    mensaje: str


class SesionResumen(BaseModel):
    id: uuid.UUID
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    estado: str
    modo: str
    ronda: int
    utilidad: float | None  # de la última oferta del proveedor, de 0 a 1
    correo_estado: str
    correo_error: str | None
    fuera_de_limites: bool
    actualizado_en: datetime


class EventoSalida(BaseModel):
    id: uuid.UUID
    folio: str
    tipo: str
    titulo: str
    moneda: str
    plazo_meses: int
    estado: str
    fecha_limite: datetime
    rondas_max: int
    estilo: str
    contrato_origen_id: uuid.UUID | None
    proveedor_vigente_id: uuid.UUID | None
    invitados: list[Invitado]
    lineas: list[LineaSalida]
    palancas: list[PalancaSalida]
    referencia_fecha: datetime | None
    creado_por_nombre: str
    creado_en: datetime
    publicado_en: datetime | None
    cerrado_en: datetime | None
    motivo_cancelacion: str | None
    version: int
    errores: list[ProblemaSalida]  # lo que impide publicar (solo en borrador)
    avisos: list[ProblemaSalida]
    sesiones: list[SesionResumen]


ClavePalanca = Literal[
    "precio",
    "plazo_meses",
    "plazo_pago_dias",
    "sla_disponibilidad",
    "tope_aumento_pct",
    "cuota_implementacion",
]
# Ideal y límite de un término; el rango y la precisión de cada uno se revisan al publicar.
Monto = Annotated[Decimal, Field(ge=0, le=10_000_000, decimal_places=4)]


class LineaCambio(BaseModel):
    codigo_servicio: Codigo
    cantidad: Cantidad
    ideal: Monto | None = None
    limite: Monto | None = None


class PalancaEntrada(BaseModel):
    clave: ClavePalanca
    peso: int = Field(ge=0, le=100)
    ideal: Monto | None = None  # el precio no lleva: va por línea
    limite: Monto | None = None


class EventoCambios(BaseModel):
    version: int
    titulo: Titulo | None = None
    fecha_limite: AwareDatetime | None = None
    rondas_max: int | None = Field(None, ge=2, le=12)
    estilo: Estilo | None = None
    plazo_meses: int | None = Field(None, ge=1, le=60)
    lineas: list[LineaCambio] | None = Field(None, min_length=1, max_length=20)
    proveedores: list[uuid.UUID] | None = Field(None, min_length=1, max_length=10)
    palancas: list[PalancaEntrada] | None = None

    @model_validator(mode="after")
    def _listas(self) -> Self:
        if self.palancas is not None:
            claves = [p.clave for p in self.palancas]
            if len(set(claves)) != len(claves):
                raise ValueError("Una palanca aparece dos veces.")
            if "precio" not in claves:
                raise ValueError("El precio siempre es una palanca activa.")
        if self.proveedores is not None and len(set(self.proveedores)) != len(self.proveedores):
            raise ValueError("Un proveedor aparece dos veces.")
        return self


class EventoResumen(BaseModel):
    id: uuid.UUID
    folio: str
    tipo: str
    titulo: str
    estado: str
    fecha_limite: datetime
    invitados: int
    sesiones: int
    acuerdos: int
    escaladas: int
    creado_por_nombre: str
    creado_en: datetime


class PaginaEventos(BaseModel):
    total: int
    elementos: list[EventoResumen]


class Cancelacion(BaseModel):
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class EnlaceSalida(BaseModel):
    sesion_id: uuid.UUID
    proveedor_nombre: str
    destinatario: str
    enlace: str  # solo se muestra en esta respuesta; la base guarda el hash del token
    correo_estado: str


class Publicacion(BaseModel):
    evento: EventoSalida
    enlaces: list[EnlaceSalida]
