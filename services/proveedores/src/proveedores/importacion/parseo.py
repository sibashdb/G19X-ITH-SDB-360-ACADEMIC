"""Convierte el contenido de un CSV en filas validadas y errores por fila. Sin I/O."""

import csv
import io
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from proveedores.importacion.esquemas import FilaContrato

MAX_FILAS = 50_000

MENSAJES = {
    "missing": "Campo obligatorio",
    "string_pattern_mismatch": "Formato inválido",
    "string_too_long": "Máximo {max_length} caracteres",
    "string_too_short": "No puede estar vacío",
    "too_short": "Debe tener al menos {min_length} elemento(s)",
    "literal_error": "Valor no permitido; opciones: {expected}",
    "greater_than": "Debe ser mayor que {gt}",
    "greater_than_equal": "Debe ser mayor o igual que {ge}",
    "less_than": "Debe ser menor que {lt}",
    "less_than_equal": "Debe ser menor o igual que {le}",
    "decimal_parsing": "Debe ser un número (punto decimal, sin separador de miles)",
    "decimal_max_places": "Máximo {decimal_places} decimales",
    "decimal_max_digits": "Máximo {max_digits} dígitos",
    "decimal_whole_digits": "Demasiados dígitos enteros",
    "int_parsing": "Debe ser un número entero",
    "date_parsing": "Fecha inválida; use AAAA-MM-DD",
    "date_from_datetime_parsing": "Fecha inválida; use AAAA-MM-DD",
    "bool_parsing": "Debe ser true o false",
    "extra_forbidden": "Columna no reconocida",
}


@dataclass(frozen=True)
class ErrorFila:
    fila: int  # 0 = archivo completo, 1 = encabezado, 2+ = registros
    campo: str
    mensaje: str


@dataclass
class ResultadoParseo[M: BaseModel]:
    filas: list[tuple[int, M]] = field(default_factory=list)
    errores: list[ErrorFila] = field(default_factory=list)


def _mensaje(error: ErrorDetails) -> str:
    plantilla = MENSAJES.get(error["type"])
    if plantilla is None:
        return error["msg"].removeprefix("Value error, ")
    try:
        return plantilla.format(**error.get("ctx", {}))
    except (KeyError, IndexError):
        return error["msg"]


def leer_csv[M: BaseModel](contenido: bytes, esquema: type[M]) -> ResultadoParseo[M]:
    resultado: ResultadoParseo[M] = ResultadoParseo()
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        resultado.errores.append(
            ErrorFila(0, "archivo", "El archivo debe estar codificado en UTF-8")
        )
        return resultado

    primera_linea = texto.split("\n", 1)[0]
    separador = ";" if primera_linea.count(";") > primera_linea.count(",") else ","
    lector = csv.DictReader(io.StringIO(texto, newline=""), delimiter=separador)
    lector.fieldnames = [columna.strip() for columna in lector.fieldnames or []]

    columnas = set(lector.fieldnames)
    obligatorias = {n for n, campo in esquema.model_fields.items() if campo.is_required()}
    faltantes = sorted(obligatorias - columnas)
    desconocidas = sorted(columnas - set(esquema.model_fields))
    if faltantes or desconocidas:
        partes = []
        if faltantes:
            partes.append("faltan: " + ", ".join(faltantes))
        if desconocidas:
            partes.append("no reconocidas: " + ", ".join(desconocidas))
        resultado.errores.append(
            ErrorFila(1, "encabezado", "Columnas inválidas; " + "; ".join(partes))
        )
        return resultado

    for numero, fila in enumerate(lector, start=2):
        if numero - 1 > MAX_FILAS:
            resultado.errores.append(
                ErrorFila(numero, "archivo", f"El archivo excede {MAX_FILAS} filas")
            )
            break
        if None in fila:
            resultado.errores.append(
                ErrorFila(numero, "fila", "La fila tiene más valores que columnas")
            )
            continue
        try:
            resultado.filas.append((numero, esquema.model_validate(fila)))
        except ValidationError as exc:
            for error in exc.errors():
                campo = ".".join(str(parte) for parte in error["loc"]) or "fila"
                resultado.errores.append(ErrorFila(numero, campo, _mensaje(error)))
    return resultado


def duplicados[M: BaseModel](
    resultado: ResultadoParseo[M], clave: Callable[[M], Hashable], campo: str
) -> list[ErrorFila]:
    vistos: dict[Hashable, int] = {}
    errores: list[ErrorFila] = []
    for numero, fila in resultado.filas:
        valor = clave(fila)
        if valor in vistos:
            errores.append(ErrorFila(numero, campo, f"Duplicado de la fila {vistos[valor]}"))
        else:
            vistos[valor] = numero
    return errores


def agrupar_contratos(
    filas: list[tuple[int, FilaContrato]],
) -> tuple[dict[str, list[tuple[int, FilaContrato]]], list[ErrorFila]]:
    grupos: dict[str, list[tuple[int, FilaContrato]]] = {}
    errores: list[ErrorFila] = []
    for numero, fila in filas:
        grupo = grupos.setdefault(fila.folio, [])
        if grupo:
            numero_primera, primera = grupo[0]
            if fila.cabecera() != primera.cabecera():
                errores.append(
                    ErrorFila(
                        numero,
                        "folio",
                        f"Los datos del contrato {fila.folio} no coinciden "
                        f"con la fila {numero_primera}",
                    )
                )
            if any(otra.codigo_servicio == fila.codigo_servicio for _, otra in grupo):
                errores.append(
                    ErrorFila(
                        numero, "codigo_servicio", f"Servicio repetido en el contrato {fila.folio}"
                    )
                )
        grupo.append((numero, fila))
    return grupos, errores
