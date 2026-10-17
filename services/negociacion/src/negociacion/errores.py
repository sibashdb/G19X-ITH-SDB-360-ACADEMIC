"""Errores de negocio con el formato común de Problem Details (comun.errores)."""

from comun.errores import ErrorDominio

REVISE = "Revise los campos indicados."


def invalidos(errores: list[dict[str, str]], codigo: str) -> ErrorDominio:
    return ErrorDominio(422, "Solicitud inválida", REVISE, {"codigo": codigo, "errores": errores})


def invalido(campo: str, mensaje: str, codigo: str) -> ErrorDominio:
    return invalidos([{"campo": campo, "mensaje": mensaje}], codigo)


def prohibido(detalle: str, codigo: str) -> ErrorDominio:
    return ErrorDominio(403, "Sin permiso", detalle, {"codigo": codigo})


def no_existe(detalle: str) -> ErrorDominio:
    return ErrorDominio(404, "No encontrado", detalle)


def conflicto(detalle: str, codigo: str) -> ErrorDominio:
    return ErrorDominio(409, "Conflicto", detalle, {"codigo": codigo})


SIN_REFERENCIA = "No se pudo consultar la referencia de precios; intente de nuevo."


def no_disponible(detalle: str = SIN_REFERENCIA) -> ErrorDominio:
    return ErrorDominio(
        503, "Servicio no disponible", detalle, {"codigo": "dependencia_no_disponible"}
    )
