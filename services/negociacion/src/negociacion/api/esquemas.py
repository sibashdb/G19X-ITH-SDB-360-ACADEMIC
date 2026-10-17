"""Formas de entrada y salida de la API; los montos viajan como texto decimal."""

import unicodedata
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

# Categorías Zl y Zp (no empiezan con «C»): también parten una línea.
SEPARADORES_DE_LINEA = "\N{LINE SEPARATOR}\N{PARAGRAPH SEPARATOR}"


def _sin_control(titulo: str) -> str:
    """El título va en el asunto del correo: un salto de línea ahí no puede entrar."""
    if any(unicodedata.category(c).startswith("C") or c in SEPARADORES_DE_LINEA for c in titulo):
        raise ValueError("El título no puede tener saltos de línea ni caracteres de control.")
    return titulo


Codigo = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{3,30}$")]
Titulo = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    AfterValidator(_sin_control),
]
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


class ValoresEntrada(BaseModel):
    precios: dict[uuid.UUID, Decimal]  # id de línea → precio unitario
    palancas: dict[str, Decimal] = Field(default_factory=dict)


class ValoresSalida(BaseModel):
    precios: dict[str, Decimal]
    palancas: dict[str, Decimal]


Nota = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class OfertaPortal(BaseModel):
    valores: ValoresEntrada
    nota: Nota = ""  # el comprador la ve tal cual; nadie la interpreta hasta N2
    confirmar_valores: bool = False


class LineaPortal(BaseModel):
    id: uuid.UUID
    codigo_servicio: str
    nombre: str
    unidad: str
    cantidad: Decimal


class PalancaPortal(BaseModel):
    clave: str
    nombre: str
    unidad: str


class MensajePortal(BaseModel):
    autor: str
    texto: str
    ronda: int
    fecha: datetime
    oferta: ValoresSalida | None


class VistaPortal(BaseModel):
    """Lo que ve el proveedor: nunca ideales, límites, pesos, utilidades ni la referencia."""

    folio: str
    titulo: str
    moneda: str
    fecha_limite: datetime
    rondas_max: int
    rondas_restantes: int
    estado: str
    atendido_por: Literal["agente", "persona"]
    pide_confirmacion: bool
    lineas: list[LineaPortal]
    palancas: list[PalancaPortal]
    mensajes: list[MensajePortal]
    ultima_propuesta: ValoresSalida | None


class Control(BaseModel):
    accion: Literal["tomar", "devolver"]


class Respuesta(BaseModel):
    tipo: Literal["mensaje", "aceptar", "cerrar"]
    texto: Nota = ""
    contraoferta: ValoresEntrada | None = None
    confirmar_fuera_de_limites: bool = False

    @model_validator(mode="after")
    def _segun_tipo(self) -> Self:
        if self.tipo == "mensaje" and not self.texto:
            raise ValueError("Escriba el mensaje para el proveedor.")
        if self.tipo != "mensaje" and self.contraoferta is not None:
            raise ValueError("Solo un mensaje puede llevar contraoferta.")
        return self


class LineaDetalle(BaseModel):
    id: uuid.UUID
    nombre: str
    unidad: str
    cantidad: Decimal
    ideal: Decimal | None
    limite: Decimal | None


class PalancaDetalle(BaseModel):
    clave: str
    nombre: str
    unidad: str
    peso: int
    ideal: Decimal | None
    limite: Decimal | None


class OfertaDetalle(BaseModel):
    id: uuid.UUID
    autor: str
    ronda: int
    valores: ValoresSalida
    utilidad: float
    valida: bool
    fuera_de_limites_confirmada: bool
    fecha: datetime


class MensajeDetalle(BaseModel):
    id: uuid.UUID
    autor: str
    texto: str
    ronda: int
    fecha: datetime
    oferta_id: uuid.UUID | None
    decision: dict[str, Any] | None  # la traza del motor en las respuestas del agente


class SesionDetalle(BaseModel):
    id: uuid.UUID
    evento_id: uuid.UUID
    folio: str
    titulo: str
    moneda: str
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    destinatario: str
    estado: str
    modo: str
    ronda: int
    rondas_max: int
    fuera_de_limites: bool
    correo_estado: str
    correo_error: str | None
    lineas: list[LineaDetalle]
    palancas: list[PalancaDetalle]
    mensajes: list[MensajeDetalle]
    ofertas: list[OfertaDetalle]


class AdjudicacionSalida(BaseModel):
    """Una propuesta de adjudicación; `recomendacion` es la foto de inteligencia al proponer."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sesion_id: uuid.UUID  # la elegida
    propuesta_por_id: str
    propuesta_por_nombre: str
    propuesta_en: datetime
    recomendada_sesion_id: uuid.UUID
    se_aparta: bool
    justificacion: str | None
    costo_total: Decimal  # en la moneda del evento
    costo_total_mxn: Decimal
    requiere_aprobacion: bool
    motivo_aprobacion: list[str]
    recomendacion: dict[str, Any]
    estado: str
    decidida_por_nombre: str | None
    decidida_en: datetime | None
    motivo_rechazo: str | None
    contrato_folio: str | None


class Evaluacion(BaseModel):
    """Los acuerdos evaluados: la recomendación de hoy, la propuesta vigente y las rechazadas."""

    recomendacion: dict[str, Any] | None  # la respuesta de inteligencia; None sin acuerdos
    vigente: AdjudicacionSalida | None  # pendiente, aprobada o directa
    historial: list[AdjudicacionSalida]  # las rechazadas, de la más reciente a la más antigua
