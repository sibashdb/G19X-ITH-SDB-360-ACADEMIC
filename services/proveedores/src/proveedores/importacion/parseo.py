"""Convierte el contenido de un CSV en filas validadas y errores por fila. Sin I/O."""

import csv
import io
from collections import Counter
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field

from comun.mensajes import traducir_error
from pydantic import BaseModel, ValidationError

from proveedores.importacion.esquemas import FilaContrato

MAX_FILAS = 50_000


@dataclass(frozen=True)
class ErrorFila:
    fila: int  # 0 = archivo completo, 1 = encabezado, 2+ = registros
    campo: str
    mensaje: str


@dataclass
class ResultadoParseo[M: BaseModel]:
    filas: list[tuple[int, M]] = field(default_factory=list)
    errores: list[ErrorFila] = field(default_factory=list)


def _leer_registros[M: BaseModel](
    texto: str, esquema: type[M], resultado: ResultadoParseo[M]
) -> None:
    primera_linea = texto.split("\n", 1)[0]
    separador = ";" if primera_linea.count(";") > primera_linea.count(",") else ","
    lector = csv.DictReader(io.StringIO(texto, newline=""), delimiter=separador)
    encabezado = [columna.strip() for columna in lector.fieldnames or []]
    lector.fieldnames = encabezado

    columnas = set(encabezado)
    obligatorias = {n for n, campo in esquema.model_fields.items() if campo.is_required()}
    faltantes = sorted(obligatorias - columnas)
    desconocidas = sorted(columnas - set(esquema.model_fields))
    # DictReader se queda con la última columna repetida: se perdería el dato sin avisar.
    duplicadas = sorted(nombre for nombre, veces in Counter(encabezado).items() if veces > 1)
    if faltantes or desconocidas or duplicadas:
        partes = []
        if faltantes:
            partes.append("faltan: " + ", ".join(faltantes))
        if desconocidas:
            partes.append("no reconocidas: " + ", ".join(desconocidas))
        if duplicadas:
            partes.append("duplicadas: " + ", ".join(duplicadas))
        resultado.errores.append(
            ErrorFila(1, "encabezado", "Columnas inválidas; " + "; ".join(partes))
        )
        return

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
                resultado.errores.append(ErrorFila(numero, campo, traducir_error(error)))


def leer_csv[M: BaseModel](contenido: bytes, esquema: type[M]) -> ResultadoParseo[M]:
    resultado: ResultadoParseo[M] = ResultadoParseo()
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        resultado.errores.append(
            ErrorFila(0, "archivo", "El archivo debe estar codificado en UTF-8")
        )
        return resultado
    if "\x00" in texto:
        # PostgreSQL no admite NUL en texto: llegaría como excepción de la BD (HTTP 500).
        resultado.errores.append(
            ErrorFila(0, "archivo", "El archivo contiene caracteres no válidos (byte nulo).")
        )
        return resultado

    try:
        _leer_registros(texto, esquema, resultado)
    except csv.Error:
        # Comillas sin cerrar o campo mayor que el límite de csv (128 KB): nunca debe
        # llegar como excepción (HTTP 500). Se conserva lo leído; el llamador rechaza el archivo.
        resultado.errores.append(
            ErrorFila(
                0,
                "archivo",
                "El archivo CSV está mal formado "
                "(revise comillas sin cerrar o campos demasiado largos)",
            )
        )
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
