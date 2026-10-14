"""Traduce al español los errores de validación de Pydantic."""

import re

from pydantic_core import ErrorDetails

MENSAJES = {
    "missing": "Campo obligatorio",
    "string_pattern_mismatch": "Formato inválido",
    "string_too_long": "Máximo {max_length} caracteres",
    "string_too_short": "No puede estar vacío",
    "too_short": "Debe tener al menos {min_length} elemento(s)",
    "literal_error": "Valor no permitido; opciones: {expected}",
    "enum": "Valor no permitido; opciones: {expected}",
    "greater_than": "Debe ser mayor que {gt}",
    "greater_than_equal": "Debe ser mayor o igual que {ge}",
    "less_than": "Debe ser menor que {lt}",
    "less_than_equal": "Debe ser menor o igual que {le}",
    "decimal_parsing": "Debe ser un número (punto decimal, sin separador de miles)",
    "decimal_max_places": "Máximo {decimal_places} decimales",
    "decimal_max_digits": "Máximo {max_digits} dígitos",
    "decimal_whole_digits": "Demasiados dígitos enteros",
    "int_parsing": "Debe ser un número entero",
    "int_type": "Debe ser un número entero",
    "date_parsing": "Fecha inválida; use AAAA-MM-DD",
    "date_from_datetime_parsing": "Fecha inválida; use AAAA-MM-DD",
    "date_from_datetime_inexact": "Fecha inválida; use AAAA-MM-DD",
    "timezone_aware": "Incluya la zona horaria, por ejemplo 2026-10-20T18:00:00-06:00",
    "datetime_parsing": "Fecha y hora inválidas; use el formato 2026-10-20T18:00:00-06:00",
    "datetime_from_date_parsing": (
        "Fecha y hora inválidas; use el formato 2026-10-20T18:00:00-06:00"
    ),
    "datetime_type": "Fecha y hora inválidas; use el formato 2026-10-20T18:00:00-06:00",
    "finite_number": "Debe ser un número finito",
    "bool_parsing": "Debe ser true o false",
    "bool_type": "Debe ser true o false",
    "uuid_parsing": "Debe ser un UUID válido",
    "uuid_type": "Debe ser un UUID válido",
    "extra_forbidden": "Columna no reconocida",
}


def _unir(elementos: list[str], conjuncion: str) -> str:
    """Une como lo hace Pydantic: "a", "a o b", "a, b o c"."""
    if len(elementos) == 1:
        return elementos[0]
    return f"{', '.join(elementos[:-1])} {conjuncion} {elementos[-1]}"


def _opciones(esperado: str) -> str | None:
    """Traduce el "'a', 'b' or 'c'" de Pydantic; None si no es una lista de cadenas."""
    valores = re.findall(r"'([^']*)'", esperado)
    if not valores or _unir([f"'{valor}'" for valor in valores], "or") != esperado:
        return None
    return _unir(valores, "o")


def traducir_error(error: ErrorDetails) -> str:
    tipo = error["type"]
    contexto = dict(error.get("ctx", {}))
    if tipo in ("literal_error", "enum"):
        opciones = _opciones(str(contexto.get("expected", "")))
        if opciones is None:
            return "Valor no permitido"
        contexto["expected"] = opciones
    plantilla = MENSAJES.get(tipo)
    if plantilla is None:
        return error["msg"].removeprefix("Value error, ")
    try:
        return plantilla.format(**contexto)
    except (KeyError, IndexError):
        return error["msg"]
