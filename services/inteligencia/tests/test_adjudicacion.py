from decimal import Decimal

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from inteligencia.dominio.adjudicacion import (
    CRITERIOS,
    Candidato,
    Entrada,
    LineaCandidato,
    PesosAdjudicacion,
    Riesgo,
    concentracion,
    costo_total,
    normalizar,
    puntajes,
    recomendar,
    reescalar,
    riesgo,
    tendencia_incidentes,
)

BAJO = riesgo(0.0, 0.0, 12)


def candidato(
    id: str = "a",
    nombre: str | None = None,
    plazo_meses: int = 12,
    cuota: Decimal = Decimal(0),
    sla: Decimal | None = None,
    lineas: tuple[LineaCandidato, ...] = (),
) -> Candidato:
    return Candidato(id, f"p-{id}", nombre or f"Proveedor {id}", plazo_meses, cuota, sla, lineas)


def entrada(
    id: str,
    costo: str = "1000",
    desempeno: float = 50.0,
    riesgo_: Riesgo = BAJO,
    sla: str | None = None,
    nombre: str | None = None,
) -> Entrada:
    c = candidato(id, nombre, sla=None if sla is None else Decimal(sla))
    return Entrada(c, Decimal(costo), Decimal(costo), desempeno, riesgo_)


def test_costo_total_por_tipo_de_unidad() -> None:
    mensual = LineaCandidato("SAAS-CRM", "usuario_mes", Decimal("10"), Decimal("100.00"))
    consumo = LineaCandidato("CONS-QA", "hora", Decimal("50"), Decimal("500.00"))
    c = candidato(plazo_meses=12, cuota=Decimal("1000.00"), lineas=(mensual, consumo))
    esperado = Decimal("10") * Decimal("100.00") * 12 + Decimal("50") * Decimal("500.00")
    assert costo_total(c) == esperado + Decimal("1000.00")


def test_tendencia_de_incidentes() -> None:
    assert tendencia_incidentes([1, 1, 1, 1, 1, 1]) == 0.0
    assert tendencia_incidentes([2, 2, 2, 3, 3, 3]) == 0.5  # (9 - 6) / 6
    assert tendencia_incidentes([0, 0, 0, 5, 5, 5]) == 1.0  # acotado a 1, divisor max(0, 1)
    assert tendencia_incidentes([3, 3, 3, 1, 1, 1]) == 0.0  # bajar no es riesgo


def test_tendencia_usa_solo_los_ultimos_seis_meses() -> None:
    assert tendencia_incidentes([9, 9, 2, 2, 2, 3, 3, 3]) == 0.5
    assert tendencia_incidentes([]) == 0.0


def test_concentracion() -> None:
    assert concentracion(Decimal("100"), Decimal("1000"), Decimal("100")) == pytest.approx(
        200 / 1100
    )
    assert concentracion(Decimal(0), Decimal(0), Decimal(0)) == 0.0


def test_riesgo_promedia_tres_componentes_y_marca_el_historial_corto() -> None:
    corto = riesgo(0.3, 0.6, 5)
    assert corto.sin_historial and corto.valor == pytest.approx((0.3 + 0.6 + 1) / 3)
    largo = riesgo(0.3, 0.6, 6)
    assert not largo.sin_historial and largo.valor == pytest.approx(0.3)


@pytest.mark.parametrize(
    ("valor", "nivel"),
    [
        (0.0, "bajo"),
        (0.33, "bajo"),
        (0.34, "medio"),
        (0.66, "medio"),
        (0.67, "alto"),
        (1.0, "alto"),
    ],
)
def test_nivel_de_riesgo(valor: float, nivel: str) -> None:
    assert Riesgo(valor, 0.0, 0.0, False).nivel == nivel


def test_normalizar_min_max_e_iguales() -> None:
    assert normalizar([10.0, 20.0, 30.0], mayor_es_mejor=False) == [1.0, 0.5, 0.0]
    assert normalizar([5.0, 5.0], mayor_es_mejor=True) == [1.0, 1.0]
    assert normalizar([None, 99.5, 99.9], mayor_es_mejor=True) == [0.0, 0.0, 1.0]
    assert normalizar([None, None], mayor_es_mejor=True) == [1.0, 1.0]
    assert normalizar([None, 5.0, 5.0], mayor_es_mejor=True) == [0.0, 1.0, 1.0]


def test_un_solo_candidato_se_recomienda() -> None:
    r = recomendar([entrada("a")], PesosAdjudicacion())
    assert r.recomendado == "a" and r.evaluados[0].puntaje == 100.0
    assert r.margen == 0.0
    assert r.explicacion[0] == "Es el único acuerdo tentativo."
    assert all(s.peso_necesario is None for s in r.sensibilidad)
    assert not any("pasara" in t for t in r.explicacion)


def test_sin_candidatos_es_un_error() -> None:
    with pytest.raises(ValueError, match="al menos un candidato"):
        recomendar([], PesosAdjudicacion())


def test_el_puntaje_es_la_suma_ponderada_y_ordena() -> None:
    # a: más barato; b: mejor desempeño; mismo riesgo y SLA → con 40/30/15/15 gana a (70 contra 60).
    a = entrada("a", costo="900", desempeno=60.0, sla="99.9")
    b = entrada("b", costo="1100", desempeno=80.0, sla="99.9")
    r = recomendar([b, a], PesosAdjudicacion())
    assert [e.entrada.candidato.id for e in r.evaluados] == ["a", "b"]
    assert [e.lugar for e in r.evaluados] == [1, 2]
    assert [e.puntaje for e in r.evaluados] == pytest.approx([70.0, 60.0])
    assert r.recomendado == "a" and r.margen == pytest.approx(10.0)
    assert r.evaluados[0].normalizados == {
        "costo": 1.0,
        "desempeno": 0.0,
        "riesgo": 1.0,
        "sla": 1.0,
    }
    assert r.evaluados[0].aportes == {"costo": 40.0, "desempeno": 0.0, "riesgo": 15.0, "sla": 15.0}


def test_un_sla_ausente_vale_cero_si_otros_lo_tienen() -> None:
    r = recomendar([entrada("a", sla=None), entrada("b", sla="99.5")], PesosAdjudicacion())
    por_id = {e.entrada.candidato.id: e for e in r.evaluados}
    assert por_id["a"].normalizados["sla"] == 0.0 and por_id["b"].normalizados["sla"] == 1.0


def test_empate_por_menor_costo_luego_desempeno_luego_nombre() -> None:
    # Con 50/50 entre costo y desempeño, a (barato) y b (mejor desempeño) empatan en 50.
    mitad = PesosAdjudicacion(costo=50, desempeno=50, riesgo=0, sla=0)
    a = entrada("a", costo="900", desempeno=60.0)
    b = entrada("b", costo="1100", desempeno=80.0)
    assert recomendar([b, a], mitad).recomendado == "a"  # menor costo

    # Costo igual (no decide) y 50/50 entre desempeño y riesgo: empatan; gana el mejor desempeño.
    desempeno_riesgo = PesosAdjudicacion(costo=0, desempeno=50, riesgo=50, sla=0)
    c = entrada("c", desempeno=80.0, riesgo_=riesgo(0.9, 0.9, 12))
    d = entrada("d", desempeno=60.0, riesgo_=BAJO)
    r = recomendar([d, c], desempeno_riesgo)
    assert r.evaluados[0].puntaje == r.evaluados[1].puntaje == 50.0
    assert r.recomendado == "c"

    # Todo igual salvo el nombre: gana el que va primero alfabéticamente, no el de menor id.
    z = entrada("a", nombre="Beta")
    y = entrada("z", nombre="Alfa")
    assert recomendar([z, y], PesosAdjudicacion()).recomendado == "z"


def test_sensibilidad_encuentra_el_peso_que_cambia_al_ganador() -> None:
    # Con a más barato y b mejor en desempeño, bajar el peso del costo lo bastante hace ganar a b.
    a = entrada("a", costo="900", desempeno=60.0)
    b = entrada("b", costo="1100", desempeno=80.0)
    r = recomendar([a, b], PesosAdjudicacion())
    s = next(x for x in r.sensibilidad if x.criterio == "costo")
    assert s.ganaria == "b" and s.peso_necesario is not None and s.peso_necesario < 40
    assert s.peso_actual == 40

    def ganador(peso_costo: int) -> str:
        # Los demás pesos se reescalan en proporción para seguir sumando 100.
        pesos = reescalar(PesosAdjudicacion().como_dict(), "costo", peso_costo)
        normalizados = [e.normalizados for e in r.evaluados]
        ids = [e.entrada.candidato.id for e in r.evaluados]
        resultado = puntajes(normalizados, pesos)
        return ids[resultado.index(max(resultado))]

    # Es el peso más cercano: un punto más hacia el actual todavía gana a.
    assert ganador(s.peso_necesario) == "b"
    assert ganador(s.peso_necesario + 1) == "a"
    assert any(
        f"pasara de 40 a {s.peso_necesario}, ganaría Proveedor b" in t for t in r.explicacion
    )


def test_sin_peso_que_cambie_al_ganador() -> None:
    # a gana en todo: ningún peso cambia el resultado.
    a = entrada("a", costo="900", desempeno=80.0, sla="99.9")
    b = entrada("b", costo="1100", desempeno=60.0, sla="99.0")
    r = recomendar([a, b], PesosAdjudicacion())
    assert all(s.peso_necesario is None and s.ganaria is None for s in r.sensibilidad)
    assert "Ningún peso del costo cambia al ganador." in r.explicacion


def test_un_criterio_plano_no_cambia_al_ganador_ni_se_explica() -> None:
    # Nadie negoció SLA y el riesgo es igual: todos valen lo mismo en esos criterios. Con peso 100
    # solo decidiría el desempate (b es el más barato), pero eso no es un cambio por el criterio.
    pesos = PesosAdjudicacion(costo=20, desempeno=50, riesgo=15, sla=15)
    r = recomendar([entrada("a", costo="1100", desempeno=90.0), entrada("b", costo="900")], pesos)

    assert r.recomendado == "a"
    por_criterio = {s.criterio: s for s in r.sensibilidad}
    for plano in ("riesgo", "sla"):
        assert por_criterio[plano].peso_necesario is None and por_criterio[plano].ganaria is None
    assert por_criterio["costo"].ganaria == "b" and por_criterio["desempeno"].ganaria == "b"
    frases = [t for t in r.explicacion if "pasara" in t or "Ningún peso" in t]
    assert len(frases) == 2  # solo el costo y el desempeño
    assert not any("riesgo" in t or "SLA" in t for t in frases)


def test_la_sensibilidad_reparte_por_igual_si_los_demas_pesos_son_cero() -> None:
    a = entrada("a", costo="900", desempeno=60.0)
    b = entrada("b", costo="1100", desempeno=80.0)
    solo_costo = PesosAdjudicacion(costo=100, desempeno=0, riesgo=0, sla=0)
    s = next(x for x in recomendar([a, b], solo_costo).sensibilidad if x.criterio == "costo")
    assert s.ganaria == "b" and s.peso_necesario is not None and s.peso_necesario < 100


def test_la_explicacion_nombra_margen_y_aportes() -> None:
    a = entrada("a", costo="1234567.50", desempeno=85.26, sla="99.9", riesgo_=riesgo(0.18, 0.0, 12))
    b = entrada("b", costo="2000000", desempeno=70.0, sla="99.0")
    r = recomendar([a, b], PesosAdjudicacion())
    texto = "\n".join(r.explicacion)
    assert r.explicacion[0].startswith("Recomendamos a Proveedor a: obtiene ")
    assert "contra" in r.explicacion[0] and "Proveedor b" in r.explicacion[0]
    assert "un margen de" in r.explicacion[0]
    assert "$1,234,567.50 MXN" in texto
    assert "85.3 de 100" in texto
    assert "Riesgo bajo" in texto and "concentración de 18 %" in texto
    assert "99.9 %" in texto


def test_el_riesgo_se_describe_como_bajo_medio_o_alto() -> None:
    a = entrada("a", riesgo_=riesgo(0.9, 0.9, 3))
    r = recomendar([a], PesosAdjudicacion())
    assert "Riesgo alto" in "\n".join(r.explicacion)
    assert "sin historial suficiente" in "\n".join(r.explicacion)


# --- Propiedades ---------------------------------------------------------------------------------


@st.composite
def _entradas(draw: st.DrawFn) -> list[Entrada]:
    n = draw(st.integers(2, 5))
    resultado = []
    for i in range(n):
        costo = Decimal(draw(st.integers(1, 10_000_000)))
        sla = draw(st.none() | st.integers(900, 1000).map(lambda x: Decimal(x) / 10))
        r = riesgo(draw(st.floats(0, 1)), draw(st.floats(0, 1)), draw(st.integers(0, 24)))
        c = Candidato(str(i), f"p{i}", draw(st.sampled_from("ABC")), 12, Decimal(0), sla, ())
        resultado.append(Entrada(c, costo, costo, draw(st.floats(0, 100)), r))
    return resultado


@st.composite
def _pesos(draw: st.DrawFn) -> PesosAdjudicacion:
    cortes = sorted(draw(st.lists(st.integers(0, 100), min_size=3, max_size=3)))
    a, b, c = cortes
    return PesosAdjudicacion(a, b - a, c - b, 100 - c)


@given(_entradas(), _pesos())
def test_propiedad_puntajes_entre_0_y_100(
    entradas: list[Entrada], pesos: PesosAdjudicacion
) -> None:
    r = recomendar(entradas, pesos)
    assert all(0.0 <= e.puntaje <= 100.0 for e in r.evaluados)
    assert [e.lugar for e in r.evaluados] == list(range(1, len(entradas) + 1))


@given(_entradas(), _pesos())
def test_propiedad_el_recomendado_tiene_el_maximo(
    entradas: list[Entrada], pesos: PesosAdjudicacion
) -> None:
    r = recomendar(entradas, pesos)
    assert r.evaluados[0].entrada.candidato.id == r.recomendado
    assert r.evaluados[0].puntaje == max(e.puntaje for e in r.evaluados)
    assert r.margen >= 0


@given(_entradas(), _pesos(), st.sampled_from(CRITERIOS), st.integers(0, 100))
def test_propiedad_subir_un_peso_no_baja_al_mejor_en_ese_criterio(
    entradas: list[Entrada], pesos: PesosAdjudicacion, criterio: str, nuevo: int
) -> None:
    actual = pesos.como_dict()
    assume(nuevo >= actual[criterio])
    normalizados = [e.normalizados for e in recomendar(entradas, pesos).evaluados]
    antes = puntajes(normalizados, actual)
    despues = puntajes(normalizados, reescalar(actual, criterio, nuevo))
    for n, a, d in zip(normalizados, antes, despues, strict=True):
        if n[criterio] == 1.0:
            assert d >= a - 1e-6
