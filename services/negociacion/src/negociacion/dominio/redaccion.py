"""Verificación numérica del texto que redacta el LLM (PRD §3.4, regla 2).

Un mensaje del agente solo puede traer números que decidió el motor; si trae otro, se usa la
plantilla. Así el LLM no puede prometer un monto, una ronda o un plazo que nadie decidió.
"""

import re
from collections.abc import Iterable
from decimal import Decimal

# Miles con coma (1,247.25) o un número sin separadores (1247.25, 24); el punto es el decimal.
NUMERO = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def numeros_en(texto: str) -> list[Decimal]:
    return [Decimal(numero.replace(",", "")) for numero in NUMERO.findall(texto)]


def texto_verificado(texto: str, permitidos: Iterable[Decimal]) -> bool:
    """True si cada número del texto es, por valor, uno de los permitidos."""
    validos = {valor.normalize() for valor in permitidos}
    return all(numero.normalize() in validos for numero in numeros_en(texto))
