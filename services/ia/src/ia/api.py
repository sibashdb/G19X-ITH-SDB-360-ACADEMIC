"""Interpretar el mensaje del proveedor y redactar la respuesta del agente (spec §3 y §4).

Las dos funciones se usan desde el router y, en el mismo proceso, desde los evals.
"""

import json
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, get_args

from comun.errores import ErrorDominio
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ValidationError

from ia import prompts
from ia.esquemas import (
    Intencion,
    Interpretacion,
    InterpretarEntrada,
    Redaccion,
    RedactarEntrada,
)
from ia.llm import ClienteLLM, LLMNoDisponible
from ia.normalizar import palabras_a_numeros

router = APIRouter(tags=["ia"])
MAX_TOKENS_INTERPRETAR = 200
MAX_TOKENS_REDACTAR = 300


class _SalidaInterpretar(BaseModel):
    intencion: Intencion
    precios: dict[str, Any] = {}
    palancas: dict[str, Any] = {}
    confianza: Any = 0


def _positivo(valor: Any) -> Decimal | None:
    """Un número mayor que 0; texto como «1,300» se acepta, lo demás se descarta."""
    try:
        numero = Decimal(str(valor).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    return numero if numero.is_finite() and numero > 0 else None


def _confianza(valor: Any) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0.0
    return numero if 0 <= numero <= 1 else 0.0  # fuera de rango no dice nada: 0


def _esquema_interpretar(entrada: InterpretarEntrada) -> dict[str, Any]:
    def objeto(claves: list[str]) -> dict[str, Any]:
        propiedades = {clave: {"type": "number"} for clave in claves}
        return {"type": "object", "properties": propiedades, "additionalProperties": False}

    return {
        "type": "object",
        "properties": {
            "intencion": {"type": "string", "enum": list(get_args(Intencion))},
            "precios": objeto([linea.id for linea in entrada.lineas]),
            "palancas": objeto([palanca.clave for palanca in entrada.palancas]),
            "confianza": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["intencion", "precios", "palancas", "confianza"],
        "additionalProperties": False,
    }


async def interpretar(entrada: InterpretarEntrada, llm: ClienteLLM) -> Interpretacion:
    esquema = {
        "moneda": entrada.moneda,
        "lineas": [linea.model_dump() for linea in entrada.lineas],
        "palancas": [palanca.model_dump() for palanca in entrada.palancas],
    }
    usuario = (
        f"Esquema de la negociación: {json.dumps(esquema, ensure_ascii=False)}\n"
        f"<mensaje_del_proveedor>{palabras_a_numeros(entrada.texto)}</mensaje_del_proveedor>"
    )
    crudo = await llm.completar_json(
        prompts.INTERPRETAR, usuario, _esquema_interpretar(entrada), MAX_TOKENS_INTERPRETAR
    )
    try:
        salida = _SalidaInterpretar.model_validate(crudo)
    except ValidationError as exc:
        raise LLMNoDisponible("respuesta_invalida") from exc
    lineas = {linea.id for linea in entrada.lineas}
    palancas = {palanca.clave for palanca in entrada.palancas}
    return Interpretacion(
        intencion=salida.intencion,
        precios={
            clave: numero
            for clave, valor in salida.precios.items()
            if clave in lineas and (numero := _positivo(valor)) is not None
        },
        palancas={
            clave: numero
            for clave, valor in salida.palancas.items()
            if clave in palancas and (numero := _positivo(valor)) is not None
        },
        confianza=_confianza(salida.confianza),
        modelo=llm.modelo,
        version_prompt=prompts.VERSION,
    )


def _instrucciones(entrada: RedactarEntrada) -> str:
    """La decisión en palabras. Un modelo pequeño repite lo que ve, así que solo recibe las
    condiciones que se cumplen y nunca el estilo como etiqueta."""
    lineas = [prompts.TIPOS[entrada.tipo], f"Tono: {prompts.TONOS[entrada.estilo]}."]
    if entrada.cifras:
        lineas.append(
            "Cifras: "
            + "; ".join(f"{c.nombre}: {c.valor} {c.unidad}" for c in entrada.cifras)
            + "."
        )
    else:
        lineas.append("No hay cifras: no escriba números.")
    if entrada.hay_mejor_oferta:
        lineas.append(prompts.HAY_MEJOR_OFERTA)
    if entrada.ultima_ronda:
        lineas.append(prompts.ULTIMA_RONDA)
    return "\n".join(lineas)


async def redactar(entrada: RedactarEntrada, llm: ClienteLLM) -> Redaccion:
    usuario = _instrucciones(entrada)
    if entrada.mensaje_proveedor:
        usuario += f"\n<mensaje_del_proveedor>{entrada.mensaje_proveedor}</mensaje_del_proveedor>"
    esquema = {
        "type": "object",
        "properties": {"texto": {"type": "string", "maxLength": 1000}},
        "required": ["texto"],
        "additionalProperties": False,
    }
    crudo = await llm.completar_json(prompts.REDACTAR, usuario, esquema, MAX_TOKENS_REDACTAR)
    try:
        return Redaccion(
            texto=str(crudo.get("texto", "")).strip(),
            modelo=llm.modelo,
            version_prompt=prompts.VERSION,
        )
    except ValidationError as exc:
        raise LLMNoDisponible("respuesta_invalida") from exc


def _llm(request: Request) -> ClienteLLM:
    llm: ClienteLLM = request.app.state.llm
    return llm


LLM = Annotated[ClienteLLM, Depends(_llm)]


def _error(exc: LLMNoDisponible) -> ErrorDominio:
    if exc.motivo == "respuesta_invalida":
        return ErrorDominio(
            502, "Respuesta inválida del LLM", "El LLM no respondió con el formato esperado.",
            {"codigo": "respuesta_invalida"},
        )  # fmt: skip
    return ErrorDominio(
        503, "LLM no disponible", "El LLM está apagado o no respondió a tiempo.",
        {"codigo": "llm_no_disponible"},
    )  # fmt: skip


@router.post("/interpretar")
async def ruta_interpretar(entrada: InterpretarEntrada, llm: LLM) -> Interpretacion:
    try:
        return await interpretar(entrada, llm)
    except LLMNoDisponible as exc:
        raise _error(exc) from exc


@router.post("/redactar")
async def ruta_redactar(entrada: RedactarEntrada, llm: LLM) -> Redaccion:
    try:
        return await redactar(entrada, llm)
    except LLMNoDisponible as exc:
        raise _error(exc) from exc
