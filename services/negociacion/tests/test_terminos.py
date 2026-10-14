from decimal import Decimal as D

import pytest
from hypothesis import given
from hypothesis import strategies as st
from negociacion.dominio.terminos import (
    CLAVES,
    Linea,
    Palanca,
    Rango,
    Terminos,
    Valores,
    es_valida,
    fuera_de_limite,
    problema_de_valor,
    redondear,
    utilidad,
    utilidades,
)
from negociacion.modelos import CLAVES_PALANCA

TERMINOS = Terminos(
    peso_precio=70,
    lineas=(
        Linea("a", "Licencias", D(100), Rango(D(10), D(20))),
        Linea("b", "Soporte", D(10), Rango(D(100), D(200))),
    ),
    palancas=(Palanca("plazo_pago_dias", 30, Rango(D(60), D(30))),),
)


def test_las_claves_coinciden_con_la_tabla() -> None:
    assert set(CLAVES) == set(CLAVES_PALANCA)


def test_la_utilidad_va_del_limite_al_ideal_en_ambas_direcciones() -> None:
    precio = Rango(D(30), D(35))  # menos es mejor
    assert precio.menos_es_mejor
    assert precio.utilidad(D(30)) == 1.0
    assert precio.utilidad(D(35)) == 0.0
    assert precio.utilidad(D("32.5")) == pytest.approx(0.5)
    assert precio.utilidad(D(28)) == 1.0  # mejor que el ideal
    assert precio.utilidad(D(40)) == 0.0
    assert precio.valido(D(35)) and not precio.valido(D("35.01"))
    assert precio.acotar(D(40)) == D(35) and precio.acotar(D(31)) == D(31)
    pago = Rango(D(60), D(30))  # más días es mejor para el comprador
    assert not pago.menos_es_mejor
    assert pago.utilidad(D(45)) == pytest.approx(0.5)
    assert pago.valido(D(30)) and not pago.valido(D(29))


def test_un_rango_sin_direccion_es_invalido() -> None:
    with pytest.raises(ValueError, match="distintos"):
        Rango(D(30), D("30.00"))


def test_el_precio_pondera_cada_linea_por_cantidad_por_limite() -> None:
    # Pesos de las líneas: a = 100 x 20 = 2,000 y b = 10 x 200 = 2,000: mitad y mitad.
    valores = Valores({"a": D(10), "b": D(200)}, {"plazo_pago_dias": D(60)})
    assert utilidades(TERMINOS, valores) == {"a": 1.0, "b": 0.0, "plazo_pago_dias": 1.0}
    assert utilidad(TERMINOS, valores) == pytest.approx(0.7 * 0.5 + 0.3 * 1.0)


def test_una_oferta_con_un_valor_mas_alla_del_limite_es_invalida() -> None:
    buena = Valores({"a": D(20), "b": D(200)}, {"plazo_pago_dias": D(30)})
    assert es_valida(TERMINOS, buena)
    cara = Valores({"a": D("20.01"), "b": D(200)}, {"plazo_pago_dias": D(29)})
    assert not es_valida(TERMINOS, cara)
    assert fuera_de_limite(TERMINOS, cara) == ["a", "plazo_pago_dias"]


@pytest.mark.parametrize(
    ("clave", "valor", "esperado"),
    [
        ("precio", D("30.125"), D("30.13")),
        ("plazo_meses", D("12.5"), D(13)),
        ("plazo_pago_dias", D("29.4"), D(29)),
        ("sla_disponibilidad", D("99.954"), D("99.95")),
        ("tope_aumento_pct", D("5.25"), D("5.3")),
        ("cuota_implementacion", D("0.005"), D("0.01")),
    ],
)
def test_redondea_a_la_precision_de_cada_termino(clave: str, valor: D, esperado: D) -> None:
    assert redondear(clave, valor) == esperado


@pytest.mark.parametrize(
    ("clave", "valor", "mensaje"),
    [
        ("precio", D(0), "Debe ser mayor que 0."),
        ("precio", D("30.123"), "Use como máximo 2 decimales."),
        ("precio", D("0.001"), "Use como máximo 2 decimales."),
        ("precio", D(20_000_000), "Debe ser como máximo 10,000,000."),
        ("plazo_meses", D(61), "Debe estar entre 1 y 60."),
        ("plazo_meses", D("12.5"), "Use un número entero."),
        ("plazo_pago_dias", D(-1), "Debe estar entre 0 y 180."),
        ("sla_disponibilidad", D("100.5"), "Debe estar entre 0 y 100."),
        ("tope_aumento_pct", D("5.25"), "Use como máximo 1 decimal."),
        ("cuota_implementacion", D(-1), "No puede ser negativo."),
        ("precio", D("30.10"), None),
        ("plazo_meses", D("12.0"), None),
        ("cuota_implementacion", D(0), None),
    ],
)
def test_problema_de_valor(clave: str, valor: D, mensaje: str | None) -> None:
    assert problema_de_valor(clave, valor) == mensaje


def test_valores_ida_y_vuelta_en_json() -> None:
    valores = Valores({"a": D("30.80")}, {"plazo_meses": D(12)})
    assert valores.a_json() == {"precios": {"a": "30.80"}, "palancas": {"plazo_meses": "12"}}
    assert Valores.de_json(valores.a_json()) == valores


@given(st.integers(1, 10**6), st.integers(1, 10**6), st.integers(0, 2 * 10**6))
def test_la_utilidad_siempre_esta_entre_0_y_1(ideal: int, limite: int, valor: int) -> None:
    if ideal == limite:
        return
    rango = Rango(D(ideal) / 100, D(limite) / 100)
    assert 0.0 <= rango.utilidad(D(valor) / 100) <= 1.0
