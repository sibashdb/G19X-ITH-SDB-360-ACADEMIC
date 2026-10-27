"""Verificación del texto que redacta el LLM (PRD §3.4, regla 2).

Un mensaje del agente solo puede traer números que decidió el motor; si trae otro, se usa la
plantilla. Así el LLM no puede prometer un monto, una ronda o un plazo que nadie decidió. Tampoco
puede hablar de otras ofertas ni anunciar la última ronda si la decisión no lo dice: decirle a un
proveedor que no hay mejores ofertas debilita al comprador. Y nunca puede afirmar una aceptación
o una aprobación: esos mensajes siempre son plantillas, así que si el texto lo dice, alguien se lo
dictó al LLM.
"""

import re
from collections.abc import Iterable
from decimal import Decimal

from comun.numeros import palabras_a_numeros

# Miles con coma (1,247.25) o un número sin separadores (1247.25, 24); el punto es el decimal.
NUMERO = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
AFIRMA_ACUERDO = re.compile(
    r"\b(?:aceptamos|aceptad[oa]s?|aprobamos|aprobad[oa]s?|adjudic\w*)\b", re.IGNORECASE
)
OTRAS_OFERTAS = re.compile(
    r"\b(?:otr[oa]s|mejor(?:es)?|más\s+competitiv[oa]s?)\s+"
    r"(?:ofertas?|propuestas?|proveedor(?:es)?|cotizaciones)\b|\bcompetencia\b",
    re.IGNORECASE,
)
ULTIMA_RONDA = re.compile(
    r"\búltim[oa]\s+(?:ronda|oportunidad)\b|\bserá\s+la\s+última\b", re.IGNORECASE
)


def numeros_en(texto: str) -> list[Decimal]:
    """Los números del texto, también los escritos con palabras («mil trescientos»)."""
    return [
        Decimal(numero.replace(",", "")) for numero in NUMERO.findall(palabras_a_numeros(texto))
    ]


def texto_verificado(
    texto: str,
    permitidos: Iterable[Decimal],
    *,
    hay_mejor_oferta: bool = False,
    ultima_ronda: bool = False,
) -> bool:
    """True si cada número del texto es, por valor, uno de los permitidos, si no afirma un
    acuerdo y si solo habla de otras ofertas o de la última ronda cuando la decisión lo dice."""
    # ponytail: busca palabras, no sentido («No hay mejores ofertas» pasa si de verdad las hay);
    # un clasificador haría falta si el LLM redactara también las aceptaciones.
    if AFIRMA_ACUERDO.search(texto):
        return False
    if not hay_mejor_oferta and OTRAS_OFERTAS.search(texto):
        return False
    if not ultima_ronda and ULTIMA_RONDA.search(texto):
        return False
    validos = {valor.normalize() for valor in permitidos}
    return all(numero.normalize() in validos for numero in numeros_en(texto))
