import uuid
from enum import StrEnum
from typing import Literal

from comun.mensajes import traducir_error
from pydantic import BaseModel, ValidationError


class Color(StrEnum):
    ROJO = "rojo"
    AZUL = "azul"


class Modelo(BaseModel):
    id: uuid.UUID | None = None
    color: Color | None = None
    n: Literal[1, 2] | None = None
    fijo: Literal["a"] | None = None
    tope: int | None = None
    activo: bool | None = None


def _mensaje(**datos: object) -> str:
    try:
        Modelo.model_validate(datos)
    except ValidationError as exc:
        [error] = exc.errors()
        return traducir_error(error)
    raise AssertionError("se esperaba un error de validación")


def test_uuid_invalido() -> None:
    assert _mensaje(id="no-es-uuid") == "Debe ser un UUID válido"
    assert _mensaje(id=5) == "Debe ser un UUID válido"


def test_enum_y_literal_listan_las_opciones_en_espanol() -> None:
    assert _mensaje(color="verde") == "Valor no permitido; opciones: rojo o azul"
    assert _mensaje(fijo="b") == "Valor no permitido; opciones: a"
    assert _mensaje(n=3) == "Valor no permitido"


def test_tipos_numericos_y_booleanos() -> None:
    assert _mensaje(tope="abc") == "Debe ser un número entero"
    assert _mensaje(tope=[1]) == "Debe ser un número entero"
    assert _mensaje(activo="quizas") == "Debe ser true o false"
    assert _mensaje(activo=[1]) == "Debe ser true o false"


def test_error_sin_traduccion_conserva_el_mensaje_de_pydantic_sin_prefijo() -> None:
    error = {"type": "value_error", "loc": ("x",), "msg": "Value error, algo falló", "input": 1}
    assert traducir_error(error) == "algo falló"  # type: ignore[arg-type]


def test_plantilla_con_contexto_ausente_usa_el_mensaje_original() -> None:
    error = {"type": "less_than_equal", "loc": ("x",), "msg": "Input should be <= 1", "input": 2}
    assert traducir_error(error) == "Input should be <= 1"  # type: ignore[arg-type]


def test_traduce_los_errores_de_fecha_y_hora() -> None:
    zona = traducir_error(
        {"type": "timezone_aware", "loc": ("body", "fecha_limite"), "msg": "x", "input": "x"}
    )
    assert zona == "Incluya la zona horaria, por ejemplo 2026-10-20T18:00:00-06:00"
    formato = traducir_error(
        {"type": "datetime_from_date_parsing", "loc": ("body",), "msg": "x", "input": "x"}
    )
    assert formato == "Fecha y hora inválidas; use el formato 2026-10-20T18:00:00-06:00"
