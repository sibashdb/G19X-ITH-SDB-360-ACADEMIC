from decimal import Decimal as D

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from negociacion.dominio.motor import BETA, Estado, contraoferta, curva, decidir, u_objetivo
from negociacion.dominio.terminos import (
    PALANCAS,
    PRECISION,
    RANGOS,
    Linea,
    Palanca,
    Rango,
    Terminos,
    Valores,
    es_valida,
    redondear,
    utilidad,
)

# El ejemplo del PRD §3.3: una línea, ideal 30, límite 35, T = 6, β = 0.6.
PRD = Terminos(peso_precio=100, lineas=(Linea("l", "Licencia", D(10), Rango(D(30), D(35))),))


def _oferta(precio: str) -> Valores:
    return Valores({"l": D(precio)}, {})


def test_el_ejemplo_del_prd() -> None:
    anterior: Valores | None = None
    obtenidas: dict[int, D] = {}
    for t in range(1, 7):
        propuesta, _ = contraoferta(PRD, _oferta("40.00"), Estado(t, 6, 0.6, anterior))
        obtenidas[t] = propuesta.precios["l"]
        anterior = propuesta
    assert [obtenidas[t] for t in (2, 4, 5, 6)] == [D("30.80"), D("32.54"), D("33.69"), D("35.00")]


def test_u_objetivo_baja_de_1_a_0() -> None:
    assert u_objetivo(0, 6, 0.6) == 1.0
    assert u_objetivo(6, 6, 0.6) == 0.0
    assert u_objetivo(9, 6, 0.6) == 0.0  # más allá de T se trata como T
    assert u_objetivo(2, 6, 0.6) == pytest.approx(0.8398, abs=1e-4)


def test_con_una_oferta_fuera_de_limite_no_contesta_con_el_limite() -> None:
    propuesta, traza = contraoferta(PRD, _oferta("40.00"), Estado(1, 6, 0.6))
    assert D(30) < propuesta.precios["l"] < D(35)
    assert traza["de_curva"] == ["l"]


def test_acepta_una_oferta_valida_mejor_que_su_contraoferta() -> None:
    decision = decidir(PRD, Estado(4, 6, 0.6), _oferta("32.00"))
    assert decision.accion == "aceptar"
    assert decision.contraoferta is None


def test_contraoferta_una_oferta_valida_pero_cara() -> None:
    decision = decidir(PRD, Estado(1, 6, 0.6), _oferta("34.00"))
    assert decision.accion == "contraofertar"
    assert decision.contraoferta is not None
    assert decision.contraoferta.precios["l"] < D("34.00")


def test_acepta_cuando_el_proveedor_reenvia_la_propuesta_anterior() -> None:
    propuesta, _ = contraoferta(PRD, _oferta("40.00"), Estado(2, 6, 0.6))
    assert decidir(PRD, Estado(3, 6, 0.6, anterior=propuesta), propuesta).accion == "aceptar"


def test_en_la_ultima_ronda_acepta_lo_valido_y_cierra_lo_demas() -> None:
    assert decidir(PRD, Estado(6, 6, 0.6), _oferta("35.00")).accion == "aceptar"
    assert decidir(PRD, Estado(6, 6, 0.6), _oferta("35.01")).accion == "cerrar_sin_acuerdo"


def test_avisa_cuando_la_siguiente_es_la_ultima_ronda() -> None:
    assert decidir(PRD, Estado(5, 6, 0.6), _oferta("40.00")).ultima_ronda
    assert not decidir(PRD, Estado(4, 6, 0.6), _oferta("40.00")).ultima_ronda


def test_pide_aclaracion_ante_un_precio_fuera_de_lo_usual() -> None:
    con_referencia = Terminos(
        100, (Linea("l", "Licencia", D(10), Rango(D(30), D(35)), referencia=D(33)),)
    )
    decision = decidir(con_referencia, Estado(1, 6, 0.6), _oferta("3300.00"))
    assert decision.accion == "pedir_aclaracion"
    assert decision.dudosas == ("l",)
    confirmada = decidir(con_referencia, Estado(1, 6, 0.6), _oferta("3300.00"), True)
    assert confirmada.accion == "contraofertar"
    # Sin referencia, la cordura se mide contra el límite (0.1 x 35 = 3.50).
    assert decidir(PRD, Estado(1, 6, 0.6), _oferta("3.40")).accion == "pedir_aclaracion"


def test_una_palanca_fuera_de_limite_usa_la_curva_propia() -> None:
    terminos = Terminos(80, PRD.lineas, (Palanca("plazo_pago_dias", 20, Rango(D(60), D(30))),))
    oferta = Valores({"l": D("31.00")}, {"plazo_pago_dias": D(15)})
    propuesta, traza = contraoferta(terminos, oferta, Estado(1, 6, 0.6))
    assert D(30) < propuesta.palancas["plazo_pago_dias"] <= D(60)
    assert traza["de_curva"] == ["plazo_pago_dias"]


def test_la_curva_llega_al_limite_solo_en_la_ultima_ronda() -> None:
    rango = Rango(D(30), D(35))
    assert curva("precio", rango, u_objetivo(5, 6, 0.6)) < D(35)
    assert curva("precio", rango, u_objetivo(6, 6, 0.6)) == D(35)


def test_el_redondeo_va_hacia_el_proveedor_cuando_el_mas_cercano_retrocederia() -> None:
    # Un precio con solo dos valores posibles (0.01 y 0.02): redondear al más cercano devolvería la
    # utilidad por encima de la contraoferta anterior, así que el motor redondea hacia el proveedor.
    terminos = Terminos(
        99,
        (Linea("l", "Licencia", D(1), Rango(D("0.01"), D("0.02"))),),
        (Palanca("plazo_meses", 1, Rango(D(1), D(2))),),
    )
    primera = decidir(terminos, Estado(1, 3, 0.3), Valores({"l": D("0.01")}, {"plazo_meses": D(3)}))
    assert primera.contraoferta is not None
    segunda = decidir(
        terminos,
        Estado(2, 3, 0.3, primera.contraoferta),
        Valores({"l": D("0.03")}, {"plazo_meses": D(1)}),
    )
    assert segunda.traza["redondeo"] == "hacia_proveedor"
    assert segunda.contraoferta is not None
    assert utilidad(terminos, segunda.contraoferta) <= utilidad(terminos, primera.contraoferta)


def test_la_traza_explica_la_decision() -> None:
    traza = decidir(PRD, Estado(2, 6, 0.6), _oferta("40.00")).traza
    assert traza["accion"] == "contraofertar"
    assert {
        "version_motor",
        "t",
        "T",
        "beta",
        "u",
        "utilidad_oferta",
        "valida",
        "hay_mejor_oferta",
        "u_objetivo",
        "objetivo",
        "tramo",
        "paso",
        "de_curva",
        "redondeo",
        "utilidad_contraoferta",
        "contraoferta",
    } <= set(traza)


# Propiedades (spec §6.7) sobre configuraciones y ofertas al azar, en la precisión de cada término.
def _en_rejilla(clave: str) -> st.SearchStrategy[D]:
    paso = PRECISION[clave]
    minimo, maximo = RANGOS[clave]
    if clave in ("precio", "cuota_implementacion"):
        minimo, maximo = (paso if clave == "precio" else minimo), D(100_000)
    return st.integers(int(minimo / paso), int(maximo / paso)).map(lambda n: D(n) * paso)


@st.composite
def _rango(draw: st.DrawFn, clave: str) -> Rango:
    ideal = draw(_en_rejilla(clave))
    limite = draw(_en_rejilla(clave).filter(lambda valor: valor != ideal))
    return Rango(ideal, limite)


@st.composite
def _escenario(draw: st.DrawFn) -> tuple[Terminos, int, float, list[Valores]]:
    lineas = tuple(
        Linea(f"l{i}", f"Línea {i}", D(draw(st.integers(1, 500))), draw(_rango("precio")))
        for i in range(draw(st.integers(1, 3)))
    )
    claves = draw(st.lists(st.sampled_from(PALANCAS), unique=True, max_size=3))
    palancas = tuple(Palanca(c, draw(st.integers(1, 30)), draw(_rango(c))) for c in claves)
    terminos = Terminos(100 - sum(p.peso for p in palancas), lineas, palancas)
    rondas = draw(st.integers(2, 12))
    beta = draw(st.sampled_from(sorted(BETA.values())))
    ofertas = [
        Valores(
            {linea.id: draw(_en_rejilla("precio")) for linea in lineas},
            {p.clave: draw(_en_rejilla(p.clave)) for p in palancas},
        )
        for _ in range(rondas)
    ]
    return terminos, rondas, beta, ofertas


@settings(max_examples=200, deadline=None)
@given(_escenario())
def test_propiedades_del_motor(escenario: tuple[Terminos, int, float, list[Valores]]) -> None:
    terminos, rondas, beta, ofertas = escenario
    anterior: Valores | None = None
    for t, oferta in enumerate(ofertas, start=1):
        decision = decidir(terminos, Estado(t, rondas, beta, anterior), oferta, True)
        if decision.accion == "aceptar":
            assert es_valida(terminos, oferta)  # nunca acepta una oferta inválida
            assert utilidad(terminos, oferta) >= decision.traza["utilidad_contraoferta"]
            return
        if decision.accion == "cerrar_sin_acuerdo":
            assert t >= rondas  # solo cierra en la ronda T
            assert not es_valida(terminos, oferta)
            return
        assert decision.accion == "contraofertar"
        assert t < rondas  # en la ronda T nunca contraoferta
        propuesta = decision.contraoferta
        assert propuesta is not None
        assert es_valida(terminos, propuesta)  # nunca fuera de los límites
        assert not (
            es_valida(terminos, oferta)
            and utilidad(terminos, oferta) >= utilidad(terminos, propuesta)
        )
        for linea in terminos.lineas:  # todo valor en su precisión
            assert propuesta.precios[linea.id] == redondear("precio", propuesta.precios[linea.id])
        for p in terminos.palancas:
            assert propuesta.palancas[p.clave] == redondear(p.clave, propuesta.palancas[p.clave])
        if anterior is not None and decision.traza["tramo"] != "acotada":
            # No retrocede, salvo cuando la oferta acotada ya supera el objetivo (spec §6.7).
            assert utilidad(terminos, propuesta) <= utilidad(terminos, anterior) + 1e-9
        anterior = propuesta
