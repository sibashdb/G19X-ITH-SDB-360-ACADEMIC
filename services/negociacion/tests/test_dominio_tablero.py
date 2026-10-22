from decimal import Decimal as D

from negociacion.dominio.tablero import Adjudicada, Ahorro, ahorro


def test_en_mxn_el_ahorro_es_la_diferencia_contra_la_primera_oferta() -> None:
    assert ahorro([Adjudicada(D("400"), D("300"), D("1"))]) == Ahorro(
        1, D("400.00"), D("300.00"), D("100.00"), 25.0
    )


def test_un_evento_en_usd_se_convierte_con_su_tasa() -> None:
    resultado = ahorro(
        [Adjudicada(D("100"), D("90"), D("18.50")), Adjudicada(D("1000"), D("800"), D("1"))]
    )
    assert resultado.primera_oferta_mxn == D("2850.00")
    assert resultado.adjudicado_mxn == D("2465.00")
    assert resultado.ahorro_mxn == D("385.00")
    assert resultado.ahorro_pct == 13.5


def test_el_ahorro_negativo_se_conserva() -> None:
    resultado = ahorro([Adjudicada(D("300"), D("330"), D("1"))])
    assert resultado.ahorro_mxn == D("-30.00")
    assert resultado.ahorro_pct == -10.0


def test_sin_adjudicadas_no_hay_porcentaje() -> None:
    assert ahorro([]) == Ahorro(0, D("0.00"), D("0.00"), D("0.00"), None)
