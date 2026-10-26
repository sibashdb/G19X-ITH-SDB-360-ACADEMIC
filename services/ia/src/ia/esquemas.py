"""Contrato de `ia` con `negociacion` (spec §3): sin ideales, límites, pesos ni referencias."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Intencion = Literal["oferta", "pregunta", "rechazo", "pide_persona", "otro"]
TipoRespuesta = Literal[
    "contraoferta", "aceptar", "cerrar_sin_acuerdo", "pedir_aclaracion", "respuesta"
]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class LineaEsquema(BaseModel):
    id: str
    nombre: str
    unidad: str


class PalancaEsquema(BaseModel):
    clave: str
    nombre: str
    unidad: str


class InterpretarEntrada(BaseModel):
    texto: Texto
    moneda: str
    lineas: list[LineaEsquema] = Field(min_length=1, max_length=20)
    palancas: list[PalancaEsquema] = []


class Interpretacion(BaseModel):
    intencion: Intencion
    precios: dict[str, Decimal]
    palancas: dict[str, Decimal]
    confianza: float = Field(ge=0, le=1)
    modelo: str
    version_prompt: str


class Cifra(BaseModel):
    nombre: str
    valor: Decimal
    unidad: str


class RedactarEntrada(BaseModel):
    tipo: TipoRespuesta
    estilo: Literal["firme", "balanceado", "flexible"]
    cifras: list[Cifra] = []
    hay_mejor_oferta: bool = False
    ultima_ronda: bool = False
    mensaje_proveedor: Annotated[str, StringConstraints(max_length=2000)] | None = None


class Redaccion(BaseModel):
    texto: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    modelo: str
    version_prompt: str
