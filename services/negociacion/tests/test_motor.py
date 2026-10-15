from collections.abc import Iterator
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
    combinar,
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


def test_la_curva_redondea_hacia_el_ideal_aunque_la_rejilla_sea_gruesa() -> None:
    meses = Rango(D(12), D(36))
    assert curva("plazo_meses", meses, u_objetivo(5, 6, 0.6)) < D(36)
    # Con un solo paso entre el ideal y el límite, el redondeo al más cercano ya tocaba el límite.
    assert curva("plazo_meses", Rango(D(35), D(36)), u_objetivo(5, 6, 0.6)) == D(35)
    assert curva("plazo_meses", Rango(D(36), D(35)), u_objetivo(5, 6, 0.6)) == D(36)
    assert curva("plazo_meses", Rango(D(35), D(36)), u_objetivo(6, 6, 0.6)) == D(36)


def test_no_contesta_con_el_limite_exacto_antes_de_la_ultima_ronda() -> None:
    # El precio ya está en el ideal, así que la oferta acotada alcanza el objetivo (el atajo): aun
    # así, el plazo de pago que cruzaba su límite se contesta con la curva, no con el límite (30).
    terminos = Terminos(80, PRD.lineas, (Palanca("plazo_pago_dias", 20, Rango(D(60), D(30))),))
    oferta = Valores({"l": D("30.00")}, {"plazo_pago_dias": D(25)})
    propuesta, traza = contraoferta(terminos, oferta, Estado(4, 6, 0.6))
    assert D(30) < propuesta.palancas["plazo_pago_dias"] < D(60)
    assert traza["de_curva"] == ["plazo_pago_dias"]
    assert (traza["tramo"], traza["paso"], traza["atajo"]) == ("propia", 1.0, True)


def test_la_biseccion_no_cae_en_el_limite_aunque_el_redondeo_lo_acerque() -> None:
    # U(s') queda justo bajo el objetivo (0.6848 contra 0.6850): la bisección cae casi en s' y el
    # redondeo al más cercano dejaba el plazo de pago, que cruzaba su límite, en 30 (R26).
    terminos = Terminos(80, PRD.lineas, (Palanca("plazo_pago_dias", 20, Rango(D(60), D(30))),))
    oferta = Valores({"l": D("30.72")}, {"plazo_pago_dias": D(25)})
    propuesta, traza = contraoferta(terminos, oferta, Estado(3, 6, 0.6))
    assert traza["atajo"] is False
    assert propuesta.palancas["plazo_pago_dias"] == D(31)  # un paso hacia el ideal (60)
    assert propuesta.precios["l"] == D("30.72")
    # En la última ronda sí contesta con el límite: ahí ya no queda nada que proteger.
    assert contraoferta(terminos, oferta, Estado(6, 6, 0.6))[0].palancas["plazo_pago_dias"] == D(30)


def test_el_empujon_puede_pedir_un_paso_mas_que_la_contraoferta_anterior() -> None:
    # La excepción de «no retrocede» (§6.7): el plazo (2 a 3 meses) cruzaba su límite y el
    # objetivo lo dejaría en él; el paso hacia el ideal vale 0.25 de utilidad, más que el hueco.
    cent = D("0.01")
    terminos = Terminos(
        55,
        (Linea("l", "Licencia", D(1), Rango(cent, 2 * cent)),),
        (
            Palanca("plazo_meses", 25, Rango(D(3), D(2))),
            Palanca("plazo_pago_dias", 1, Rango(D(0), D(1))),
            Palanca("sla_disponibilidad", 19, Rango(5 * cent, D(0))),
        ),
    )

    def oferta(sla: D) -> Valores:
        return Valores(
            {"l": cent}, {"plazo_meses": D(1), "plazo_pago_dias": D(0), "sla_disponibilidad": sla}
        )

    primera = decidir(terminos, Estado(1, 5, 1.0), oferta(D(0)), True).contraoferta
    assert primera is not None
    segunda = decidir(terminos, Estado(2, 5, 1.0, primera), oferta(cent), True).contraoferta
    assert segunda is not None
    assert segunda.palancas["plazo_meses"] == D(3)  # sin el paso habría quedado en el límite (2)
    assert utilidad(terminos, segunda) > utilidad(terminos, primera)


def test_no_pide_mas_de_lo_que_el_proveedor_ofrecio_aunque_sea_mejor_que_el_ideal() -> None:
    lineas = tuple(Linea(i, i.upper(), D(1), Rango(D(30), D(35))) for i in "abc")
    terminos = Terminos(80, lineas, (Palanca("plazo_pago_dias", 20, Rango(D(60), D(30))),))
    oferta = Valores(
        {"a": D("25.00"), "b": D("33.00"), "c": D("40.00")}, {"plazo_pago_dias": D(90)}
    )
    propuesta, traza = contraoferta(terminos, oferta, Estado(1, 6, 0.6))
    assert traza["tramo"] == "propia_a_ideal"  # recorre el tramo que antes jalaba hacia el ideal
    assert propuesta.precios["a"] == D("25.00")  # mejor que el ideal: no pide pagar más
    assert propuesta.palancas["plazo_pago_dias"] == D(90)  # ni menos días de pago
    assert propuesta.precios["b"] < D("33.00")  # lo demás sí se acerca al ideal


def test_el_redondeo_va_hacia_el_proveedor_cuando_el_mas_cercano_retrocederia() -> None:
    # Al más cercano saldría (30.02, 1 mes): pediría un centavo menos que la contraoferta anterior
    # (30.03, 1 mes). El motor redondea hacia el proveedor (30.03, 2 meses) y no retrocede.
    terminos = Terminos(
        50,
        (Linea("l", "Licencia", D(1), Rango(D(30), D(35))),),
        (Palanca("plazo_meses", 50, Rango(D(1), D(3))),),
    )
    anterior = Valores({"l": D("30.03")}, {"plazo_meses": D(1)})
    oferta = Valores({"l": D("35.01")}, {"plazo_meses": D(3)})
    decision = decidir(terminos, Estado(1, 6, 0.6, anterior), oferta)
    assert decision.accion == "contraofertar"
    assert decision.traza["redondeo"] == "hacia_proveedor"
    assert decision.contraoferta is not None
    assert utilidad(terminos, decision.contraoferta) <= utilidad(terminos, anterior)


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
        "atajo",
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


def _entre(clave: str, rango: Rango) -> st.SearchStrategy[D]:
    """Valores en la rejilla del término, dentro de [ideal, límite] (los válidos)."""
    paso = PRECISION[clave]
    bajo, alto = sorted((rango.ideal, rango.limite))
    return st.integers(int(bajo / paso), int(alto / paso)).map(lambda n: D(n) * paso)


def _por_termino(terminos: Terminos, a: Valores, b: Valores) -> Iterator[tuple[Rango, D, D]]:
    for linea in terminos.lineas:
        yield linea.rango, a.precios[linea.id], b.precios[linea.id]
    for p in terminos.palancas:
        yield p.rango, a.palancas[p.clave], b.palancas[p.clave]


def _sin_empujon(terminos: Terminos, propuesta: Valores, oferta: Valores) -> Valores:
    """La propuesta con cada término que cruzaba su límite y está a un paso de él, en el límite."""

    def al_limite(clave: str, rango: Rango, valor: D, ofrecido: D) -> D:
        paso = -PRECISION[clave] if rango.menos_es_mejor else PRECISION[clave]
        return (
            rango.limite if not rango.valido(ofrecido) and valor == rango.limite + paso else valor
        )

    return combinar(terminos, propuesta, oferta, al_limite)


# (términos, rondas, β, ofertas del proveedor, contraoferta previa del comprador)
Escenario = tuple[Terminos, int, float, list[Valores], Valores | None]


@st.composite
def _escenario(draw: st.DrawFn) -> Escenario:
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
    # A veces el comprador ya contraofertó antes de la primera oferta (spec §6.4, paso 2).
    del_comprador = (
        Valores(
            {linea.id: draw(_entre("precio", linea.rango)) for linea in lineas},
            {p.clave: draw(_entre(p.clave, p.rango)) for p in palancas},
        )
        if draw(st.booleans())
        else None
    )
    return terminos, rondas, beta, ofertas, del_comprador


@settings(max_examples=200, deadline=None)
@given(_escenario())
def test_propiedades_del_motor(escenario: Escenario) -> None:
    terminos, rondas, beta, ofertas, anterior = escenario
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
        for rango, nueva, ofrecida in _por_termino(terminos, propuesta, oferta):
            # Ningún término favorece más al proveedor que lo que él mismo ofreció.
            assert nueva <= ofrecida if rango.menos_es_mejor else nueva >= ofrecida
            if not rango.valido(ofrecida):
                assert nueva != rango.limite  # antes de T no revela el límite exacto (R26)
        if anterior is not None and not decision.traza["atajo"]:
            # No retrocede, salvo en el atajo (la oferta acotada ya alcanza el objetivo) y, a lo
            # sumo un paso de precisión, en el término que cruzaba su límite y caería en él (§6.7).
            sin_empujon = _sin_empujon(terminos, propuesta, oferta)
            assert utilidad(terminos, sin_empujon) <= utilidad(terminos, anterior) + 1e-12
        anterior = propuesta
