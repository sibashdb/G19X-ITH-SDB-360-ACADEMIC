from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from inteligencia.dominio.precios import (
    Banda,
    Observacion,
    ahorro_potencial,
    ajustar_por_inflacion,
    cantidad_mensual,
    cuartiles,
    linea_base,
    meses_restantes,
    plazo_en_meses,
    posicion,
    sumar_meses,
)

HOY = date(2026, 9, 1)
INFLACION = 0.045


def _obs(
    precio: float,
    cantidad: float = 100.0,
    fecha: date = HOY,
    servicio: str = "SAAS-OFI-EMP",
    categoria: str = "licencia_saas",
) -> Observacion:
    return Observacion(
        servicio=servicio,
        categoria=categoria,
        moneda="USD",
        fecha=fecha,
        cantidad=cantidad,
        precio=precio,
        plazo_meses=12,
        tamano="mediana",
        tipo="nuevo",
    )


def test_sin_observaciones_no_hay_referencia() -> None:
    assert linea_base([], "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION) is None
    vieja = _obs(20.0, fecha=date(2024, 8, 1))  # fuera de la ventana de 24 meses
    assert linea_base([vieja], "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION) is None
    otro = _obs(20.0, servicio="SAAS-CRM-PRO")  # la categoría tiene datos, el servicio no
    assert linea_base([otro], "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION) is None


def test_cuartiles_del_tercil_con_suficientes_observaciones() -> None:
    observaciones = [_obs(p) for p in (10.0, 11, 12, 13, 14, 15, 16, 17, 18)]
    referencia = linea_base(observaciones, "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION)
    assert referencia is not None
    assert (referencia.confianza, referencia.observaciones) == ("normal", 9)
    assert referencia.banda == Banda(12.0, 14.0, 16.0)
    assert (referencia.metodo, referencia.version) == ("linea_base", None)


def test_compara_con_contratos_de_cantidad_parecida() -> None:
    chicos = [_obs(20.0 + i * 0.1, cantidad=10) for i in range(9)]
    grandes = [_obs(15.0 + i * 0.1, cantidad=1_000) for i in range(9)]
    medianos = [_obs(17.0 + i * 0.1, cantidad=100) for i in range(9)]
    todas = chicos + medianos + grandes
    grande = linea_base(todas, "SAAS-OFI-EMP", "licencia_saas", 900, HOY, INFLACION)
    chico = linea_base(todas, "SAAS-OFI-EMP", "licencia_saas", 12, HOY, INFLACION)
    assert grande is not None and chico is not None
    assert grande.banda.p50 == pytest.approx(15.4)
    assert chico.banda.p50 == pytest.approx(20.4)


def test_con_pocas_observaciones_usa_la_categoria_con_baja_confianza() -> None:
    propios = [_obs(p) for p in (19.0, 20.0, 21.0)]
    otros = [
        _obs(p, servicio="SAAS-CRM-PRO") for p in (90.0, 95, 100, 100, 100, 100, 105, 110, 100)
    ]
    referencia = linea_base(propios + otros, "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION)
    assert referencia is not None
    assert (referencia.confianza, referencia.observaciones) == ("baja", 3)
    # La mediana del servicio (20) con la dispersión relativa de la categoría.
    assert referencia.banda.p50 == pytest.approx(20.0)
    assert referencia.banda.p25 < 20.0 < referencia.banda.p75
    # 12 razones 0.9, 0.95, 0.95, 1.0 (x6), 1.05, 1.05, 1.1; P25 y P75 por interpolación.
    assert referencia.banda.p25 == pytest.approx(19.75)
    assert referencia.banda.p75 == pytest.approx(20.25)


def test_lleva_los_precios_viejos_a_la_fecha_por_inflacion() -> None:
    assert ajustar_por_inflacion(100.0, date(2025, 9, 1), HOY, INFLACION) == pytest.approx(104.5)
    hace_un_anio = [_obs(100.0, fecha=date(2025, 9, 1)) for _ in range(8)]
    referencia = linea_base(hace_un_anio, "SAAS-OFI-EMP", "licencia_saas", 100, HOY, INFLACION)
    assert referencia is not None
    assert referencia.banda.p50 == pytest.approx(104.5)


def test_fechas_y_cantidades() -> None:
    assert plazo_en_meses(date(2025, 1, 1), date(2025, 12, 31)) == 12
    assert plazo_en_meses(date(2025, 3, 1), date(2025, 8, 31)) == 6
    assert sumar_meses(date(2026, 9, 15), -24) == date(2024, 9, 1)
    assert meses_restantes(date(2026, 10, 10), date(2026, 12, 31)) == 3
    assert meses_restantes(date(2026, 10, 10), date(2026, 9, 30)) == 0
    assert cantidad_mensual(Decimal("250"), "usuario_mes", 12) == Decimal("250")
    # Por consumo, la cantidad es del contrato completo.
    assert cantidad_mensual(Decimal("120"), "hora", 6) == Decimal("20")


def test_posicion_frente_al_mercado() -> None:
    banda = Banda(10.0, 12.0, 14.0)
    assert posicion(9.5, banda) == "bajo_p25"
    assert posicion(12.0, banda) == "justo"
    assert posicion(14.0, banda) == "justo"
    assert posicion(14.5, banda) == "sobre_p75"


def test_ahorro_potencial() -> None:
    # (25 - 20) x 100 al mes x 6 meses.
    assert ahorro_potencial(Decimal("25"), Decimal("20"), Decimal("100"), 6) == Decimal("3000.00")
    assert ahorro_potencial(Decimal("18"), Decimal("20"), Decimal("100"), 6) == Decimal("0.00")


PRECIOS = st.lists(
    st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=40,
)


@given(PRECIOS)
def test_los_cuartiles_siempre_estan_ordenados(valores: list[float]) -> None:
    banda = cuartiles(valores)
    assert banda.p25 <= banda.p50 <= banda.p75


@given(PRECIOS, st.floats(min_value=1, max_value=10_000))
def test_la_referencia_siempre_esta_ordenada(valores: list[float], cantidad: float) -> None:
    observaciones = [_obs(p, cantidad=float(i % 7 + 1) * 10) for i, p in enumerate(valores)]
    referencia = linea_base(
        observaciones, "SAAS-OFI-EMP", "licencia_saas", cantidad, HOY, INFLACION
    )
    assert referencia is not None
    assert referencia.banda.p25 <= referencia.banda.p50 <= referencia.banda.p75


DECIMALES = st.decimals(
    min_value=Decimal("0.0001"), max_value=Decimal("100000"), places=4, allow_nan=False
)


@given(DECIMALES, DECIMALES, DECIMALES, st.integers(min_value=0, max_value=60))
def test_el_ahorro_nunca_es_negativo(
    precio: Decimal, p50: Decimal, cantidad: Decimal, meses: int
) -> None:
    assert ahorro_potencial(precio, p50, cantidad, meses) >= 0
