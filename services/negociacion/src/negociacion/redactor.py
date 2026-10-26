"""El texto de la respuesta del agente: el del LLM si pasa la verificación; si no, la plantilla.

El LLM recibe solo lo que decidió el motor y, como dato, el mensaje del proveedor; nunca el
ideal, el límite, los pesos ni la utilidad (PRD §3.4, regla 1).
"""

import time
from decimal import Decimal
from typing import Any

from negociacion import textos
from negociacion.dominio.redaccion import texto_verificado
from negociacion.dominio.terminos import Terminos, Valores
from negociacion.integraciones import ClienteIA
from negociacion.modelos import Evento

MIN_REINTENTO_S = 4.0  # sin este margen, el segundo intento no cabría en el presupuesto
INTENTOS = 2


def _cifras(valores: Valores | None, terminos: Terminos, evento: Evento) -> list[dict[str, str]]:
    if valores is None:
        return []
    cifras = [
        {"nombre": linea.nombre, "valor": str(valores.precios[linea.id]), "unidad": evento.moneda}
        for linea in terminos.lineas
        if linea.id in valores.precios
    ]
    for clave, valor in valores.palancas.items():
        nombre, unidad = textos.nombre_y_unidad(clave, evento.moneda)
        cifras.append({"nombre": nombre, "valor": str(valor), "unidad": unidad})
    return cifras


async def redactar_respuesta(
    ia: ClienteIA,
    tipo: str,
    valores: Valores | None,
    terminos: Terminos,
    evento: Evento,
    mensaje_proveedor: str | None,
    hasta: float,
    respaldo: str,
    *,
    hay_mejor_oferta: bool = False,
    ultima_ronda: bool = False,
) -> tuple[str, dict[str, Any]]:
    """(texto, detalle para la bitácora): de dónde salió el texto y, si fue plantilla, por qué."""
    cifras = _cifras(valores, terminos, evento)
    cuerpo = {
        "tipo": tipo,
        "estilo": evento.estilo,
        "cifras": cifras,
        "hay_mejor_oferta": hay_mejor_oferta,
        "ultima_ronda": ultima_ronda,
        "mensaje_proveedor": mensaje_proveedor or None,
    }
    permitidos = [Decimal(cifra["valor"]) for cifra in cifras]
    modelo = version = motivo = None
    for intento in range(INTENTOS):
        restante = hasta - time.monotonic()
        if intento and restante < MIN_REINTENTO_S:
            motivo = "sin_tiempo"
            break
        respuesta = await ia.redactar(cuerpo, restante)
        if respuesta is None:
            motivo = "sin_ia"
            break
        modelo, version = respuesta.get("modelo"), respuesta.get("version_prompt")
        texto = str(respuesta.get("texto", "")).strip()
        if texto and texto_verificado(texto, permitidos):
            return texto, {
                "origen": "llm",
                "modelo": modelo,
                "version_prompt": version,
                "motivo": None,
            }
        motivo = "verificacion"
    return respaldo, {
        "origen": "plantilla",
        "modelo": modelo,
        "version_prompt": version,
        "motivo": motivo,
    }
