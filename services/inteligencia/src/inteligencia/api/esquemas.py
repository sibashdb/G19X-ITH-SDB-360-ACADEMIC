"""Respuestas de la API: montos como texto decimal y puntuaciones con un decimal."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Categoria = Literal["licencia_saas", "nube", "consultoria", "soporte"]
Confianza = Literal["normal", "baja"]
Peso = Annotated[int, Field(ge=0, le=100)]
Dinero = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]  # como en la base


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


class ProveedorResumen(BaseModel):
    id: str
    rfc: str
    nombre: str
    tamano: str
    categorias: list[str]
    activo: bool
    puntuacion: float | None  # None: sin desempeño registrado
    confianza: Confianza | None  # baja: menos de 6 meses de historial
    tendencia: float | None  # puntos contra hace 3 meses
    gasto_anual: Decimal  # MXN, contratos vigentes
    contratos_vigentes: int
    alertas: int
    en_riesgo: bool


class PaginaProveedores(BaseModel):
    total: int
    elementos: list[ProveedorResumen]


class Componente(BaseModel):
    kpi: str
    valor: float  # promedio ponderado de 12 meses
    mediana_categoria: float
    percentil: float  # 0 a 100, más es mejor


class PuntoPuntuacion(BaseModel):
    mes: date
    puntuacion: float


class PuntuacionSalida(BaseModel):
    proveedor_id: str
    categoria: str | None  # la principal: contra la que se compara
    puntuacion: float | None
    sin_ajuste: float | None
    meses: int
    historial_corto: bool
    tendencia: float | None
    componentes: list[Componente]
    historial: list[PuntoPuntuacion]


class MercadoLinea(BaseModel):
    contrato_id: str
    folio: str
    codigo_servicio: str
    servicio: str
    moneda: str
    precio: Decimal
    posicion: Literal["bajo_p25", "justo", "sobre_p75"] | None  # None: sin referencia
    p25: Decimal | None
    p50: Decimal | None
    p75: Decimal | None
    metodo: Literal["linea_base", "modelo"] | None
    confianza: Confianza | None
    ahorro_potencial: Decimal


class FilaRanking(BaseModel):
    posicion: int
    proveedor_id: str
    nombre: str
    categoria: str
    puntuacion: float
    componentes: dict[str, float]
    meses: int
    historial_corto: bool
    tendencia: float | None


class ConfiguracionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    peso_sla: int
    peso_resolucion: int
    peso_incidentes: int
    peso_entregas: int
    peso_satisfaccion: int
    umbral_riesgo: int
    inflacion_anual: Decimal
    adjudicacion_costo: int
    adjudicacion_desempeno: int
    adjudicacion_riesgo: int
    adjudicacion_sla: int
    umbral_aprobacion: Decimal
    actualizado_en: datetime | None
    actualizado_por: str | None


class ConfiguracionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    peso_sla: Peso
    peso_resolucion: Peso
    peso_incidentes: Peso
    peso_entregas: Peso
    peso_satisfaccion: Peso
    umbral_riesgo: Annotated[int, Field(ge=0, le=100)]
    inflacion_anual: Annotated[Decimal, Field(ge=0, le=50, decimal_places=2)]
    # Opcionales: None = sin cambio (la pantalla de Configuración aún no los envía).
    adjudicacion_costo: Peso | None = None
    adjudicacion_desempeno: Peso | None = None
    adjudicacion_riesgo: Peso | None = None
    adjudicacion_sla: Peso | None = None
    umbral_aprobacion: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)] | None = (
        None
    )


class ModeloSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    entrenado_en: datetime
    origen: str
    actor_nombre: str
    observaciones: int
    datos_hasta: date
    mape: Decimal
    mape_linea_base: Decimal
    cobertura: Decimal
    pinball: Decimal
    promovido: bool


class RegistroModelos(BaseModel):
    entrenando: bool
    activo: int | None  # el último promovido; None: ninguno mejoró la línea base
    en_uso: int | None  # el que responde las consultas; None: se usa la línea base
    ultimo_error: str | None  # por qué falló el último entrenamiento
    elementos: list[ModeloSalida]


class EntrenamientoIniciado(BaseModel):
    entrenando: bool


class DatosSalida(BaseModel):
    registros: dict[str, int]
    ultimo_evento: datetime | None
    modelo: ModeloSalida | None  # el activo (último promovido)
    en_uso: int | None  # el que responde las consultas; None: se usa la línea base
    entrenando: bool


class PesosEntrada(BaseModel):
    """Los pesos de los cuatro criterios de la adjudicación; deben sumar 100."""

    costo: Peso
    desempeno: Peso
    riesgo: Peso
    sla: Peso


class LineaEntrada(BaseModel):
    codigo_servicio: Annotated[str, Field(min_length=1, max_length=30)]
    unidad: Annotated[str, Field(min_length=1, max_length=20)]
    cantidad: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)]
    precio: Dinero


class CandidatoEntrada(BaseModel):
    id: Annotated[str, Field(min_length=1, max_length=64)]  # el de la sesión de negociación
    proveedor_id: UUID
    nombre: Annotated[str, Field(min_length=1, max_length=200)]
    plazo_meses: Annotated[int, Field(ge=1, le=60)]
    cuota_implementacion: Dinero
    sla: Annotated[Decimal, Field(ge=0, le=100)] | None = None
    lineas: Annotated[list[LineaEntrada], Field(min_length=1, max_length=20)]


class RecomendacionEntrada(BaseModel):
    moneda: Literal["MXN", "USD"]
    pesos: PesosEntrada | None = None  # None: los configurados
    candidatos: Annotated[list[CandidatoEntrada], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def _sin_repetidos(self) -> Self:
        ids = [c.id for c in self.candidatos]
        if len(set(ids)) != len(ids):
            raise ValueError("Los candidatos no pueden repetirse.")
        return self


class TipoCambioSalida(BaseModel):
    periodo: date
    usd_mxn: Decimal


class RiesgoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valor: float  # promedio de los tres componentes, de 0 a 1
    nivel: Literal["bajo", "medio", "alto"]
    concentracion: float
    tendencia: float
    sin_historial: bool


class CandidatoSalida(BaseModel):
    id: str
    proveedor_id: str
    nombre: str
    costo_total: Decimal  # en la moneda del evento
    costo_total_mxn: Decimal
    desempeno: float  # puntuación de 0 a 100
    riesgo: RiesgoSalida
    sla: Decimal | None
    normalizados: dict[str, float]  # por criterio, de 0 a 1 (1 es lo mejor)
    aportes: dict[str, float]  # los puntos que suma cada criterio
    puntaje: float
    lugar: int


class SensibilidadSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    criterio: str
    peso_actual: int
    peso_necesario: int | None  # el más cercano al actual con el que gana otro; None si ninguno
    ganaria: str | None  # id del candidato que ganaría


class RecomendacionSalida(BaseModel):
    pesos: PesosEntrada
    umbral_aprobacion: Decimal  # MXN
    tipo_cambio: TipoCambioSalida | None  # el vigente hoy; None: no hay ninguno registrado
    candidatos: list[CandidatoSalida]  # en orden de lugar
    recomendado: str  # id del candidato
    margen: float  # puntos entre el primero y el segundo; 0 si hay uno solo
    explicacion: list[str]
    sensibilidad: list[SensibilidadSalida]
