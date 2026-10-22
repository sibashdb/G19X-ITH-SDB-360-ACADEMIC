from decimal import Decimal as D

from comun.costos import UNIDADES_MENSUALES, costo_total


def test_las_unidades_mensuales_se_cobran_por_el_plazo_y_las_demas_una_vez() -> None:
    lineas = [("usuario_mes", D("100"), D("30.00")), ("ticket", D("10"), D("500.00"))]
    # 100 por 30 por 12 meses, más 10 por 500, más la cuota de 1,000
    assert costo_total(lineas, 12, D("1000.00")) == D("42000.00")


def test_sin_lineas_vale_la_cuota() -> None:
    assert costo_total([], 12, D("250.00")) == D("250.00")


def test_unidades_mensuales() -> None:
    assert frozenset({"usuario_mes", "vcpu_mes", "gb_mes", "mes"}) == UNIDADES_MENSUALES
