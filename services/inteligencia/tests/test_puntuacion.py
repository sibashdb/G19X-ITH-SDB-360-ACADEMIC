import statistics
from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st
from inteligencia.dominio.precios import sumar_meses
from inteligencia.dominio.puntuacion import (
    KPIS,
    Mes,
    Pesos,
    Puntuacion,
    contraer,
    historial,
    percentil,
    promedio_ponderado,
    puntuar,
    validar_pesos,
)

HOY = date(2026, 9, 1)


def _mes(periodo: date, nivel: float) -> Mes:
    """Un mes de desempeño de un proveedor con calidad `nivel` (0 malo, 1 excelente)."""
    return Mes(
        periodo=periodo,
        sla=95 + 5 * nivel,
        resolucion=24 - 18 * nivel,
        incidentes=3 * (1 - nivel),
        entregas=80 + 20 * nivel,
        satisfaccion=1.5 + 3.5 * nivel,
    )


def _historia(nivel: float, meses: int = 12, hasta: date = HOY) -> list[Mes]:
    return [_mes(sumar_meses(hasta, -i), nivel) for i in range(meses)]


def test_mejor_desempeno_mejor_puntuacion() -> None:
    desempeno = {"bueno": _historia(0.9), "medio": _historia(0.5), "malo": _historia(0.1)}
    categorias = dict.fromkeys(desempeno, "nube")
    puntuaciones = puntuar(desempeno, categorias, Pesos(), HOY)
    assert (
        puntuaciones["bueno"].puntuacion
        > puntuaciones["medio"].puntuacion
        > puntuaciones["malo"].puntuacion
    )
    # Resolución e incidentes: menos es mejor, así que el bueno queda arriba también ahí.
    assert puntuaciones["bueno"].componentes["resolucion"] == 100
    assert puntuaciones["bueno"].componentes["incidentes"] == 100
    assert puntuaciones["bueno"].meses == 12


def test_percentil_con_empates() -> None:
    assert percentil(5, [1, 5, 5, 9]) == pytest.approx(50.0)
    assert percentil(9, [1, 5, 5, 9]) == pytest.approx(100.0)
    assert percentil(7, [7]) == 50.0


def test_el_desempeno_reciente_pesa_mas() -> None:
    reciente = Mes(HOY, sla=100, resolucion=1, incidentes=0, entregas=100, satisfaccion=5)
    viejo = Mes(
        sumar_meses(HOY, -6), sla=90, resolucion=1, incidentes=0, entregas=100, satisfaccion=5
    )
    resultado = promedio_ponderado([reciente, viejo], HOY)
    assert resultado is not None
    valores, meses = resultado
    # Vida media de 6 meses: el mes de hace 6 pesa la mitad.
    assert valores["sla"] == pytest.approx((100 * 1 + 90 * 0.5) / 1.5)
    assert meses == 2


def test_fuera_de_los_12_meses_no_cuenta() -> None:
    assert promedio_ponderado([_mes(sumar_meses(HOY, -12), 0.5)], HOY) is None


def test_un_historial_corto_se_acerca_a_la_media() -> None:
    desempeno = {f"p{i}": _historia(0.2 + i * 0.05) for i in range(10)}
    desempeno["nuevo"] = _historia(1.0, meses=1)
    categorias = dict.fromkeys(desempeno, "nube")
    puntuaciones = puntuar(desempeno, categorias, Pesos(), HOY)
    nuevo = puntuaciones["nuevo"]
    media = sum(p.sin_ajuste for p in puntuaciones.values()) / len(puntuaciones)
    assert nuevo.historial_corto
    assert media < nuevo.puntuacion < nuevo.sin_ajuste
    assert not puntuaciones["p0"].historial_corto


def test_con_20_proveedores_compara_dentro_de_la_categoria_y_con_menos_contra_todos() -> None:
    nube = {f"n{i}": _historia(0.8 + i * 0.005) for i in range(20)}
    soporte = {f"s{i}": _historia(0.1 + i * 0.005) for i in range(20)}
    categorias = dict.fromkeys(nube, "nube") | dict.fromkeys(soporte, "soporte")
    muchos = puntuar(nube | soporte, categorias, Pesos(), HOY)
    # El mejor de soporte es el mejor de su categoría aunque sea peor que todos los de nube.
    assert muchos["s19"].sin_ajuste == pytest.approx(100.0)
    pocos = {k: v for k, v in (nube | soporte).items() if int(k[1:]) < 10}
    menos = puntuar(pocos, categorias, Pesos(), HOY)
    assert menos["s9"].sin_ajuste < menos["n0"].sin_ajuste


def test_los_pesos_cambian_la_puntuacion() -> None:
    bueno_en_sla = [
        Mes(
            sumar_meses(HOY, -i),
            sla=100,
            resolucion=24,
            incidentes=3,
            entregas=80,
            satisfaccion=1.5,
        )
        for i in range(12)
    ]
    bueno_en_lo_demas = [
        Mes(sumar_meses(HOY, -i), sla=95, resolucion=6, incidentes=0, entregas=100, satisfaccion=5)
        for i in range(12)
    ]
    desempeno = {"a": bueno_en_sla, "b": bueno_en_lo_demas}
    categorias = dict.fromkeys(desempeno, "nube")
    solo_sla = Pesos(sla=100, resolucion=0, incidentes=0, entregas=0, satisfaccion=0)
    assert puntuar(desempeno, categorias, solo_sla, HOY)["a"].sin_ajuste == 100
    assert puntuar(desempeno, categorias, Pesos(), HOY)["b"].sin_ajuste == 70


def test_validar_pesos() -> None:
    assert validar_pesos(Pesos().como_dict()) is None
    assert validar_pesos(Pesos(sla=25).como_dict()) == "Los pesos deben sumar 100 (suman 95)."
    assert (
        validar_pesos(Pesos(sla=-10, resolucion=60).como_dict())
        == "Los pesos no pueden ser negativos."
    )


def test_historial_de_12_meses() -> None:
    mejora = [_mes(sumar_meses(HOY, -i), 0.9 - i * 0.05) for i in range(24)]
    desempeno = {"mejora": mejora} | {f"p{i}": _historia(0.5, meses=24) for i in range(5)}
    categorias = dict.fromkeys(desempeno, "nube")
    serie = historial(desempeno, categorias, Pesos(), HOY)["mejora"]
    assert [fecha for fecha, _ in serie] == [sumar_meses(HOY, -i) for i in range(11, -1, -1)]
    assert serie[-1][1] > serie[0][1]


@given(
    st.lists(st.floats(min_value=0, max_value=1), min_size=1, max_size=15),
    st.integers(min_value=1, max_value=12),
)
def test_la_puntuacion_esta_entre_0_y_100(niveles: list[float], meses: int) -> None:
    desempeno = {f"p{i}": _historia(nivel, meses) for i, nivel in enumerate(niveles)}
    categorias = dict.fromkeys(desempeno, "nube")
    for p in puntuar(desempeno, categorias, Pesos(), HOY).values():
        assert 0 <= p.sin_ajuste <= 100
        assert 0 <= p.puntuacion <= 100


@given(
    st.floats(min_value=0, max_value=100),
    st.floats(min_value=0, max_value=100),
    st.integers(min_value=1, max_value=12),
)
def test_la_contraccion_acerca_a_la_media_sin_cruzarla(
    puntuacion: float, media: float, meses: int
) -> None:
    ajustada = contraer(puntuacion, media, meses)
    assert min(puntuacion, media) - 1e-9 <= ajustada <= max(puntuacion, media) + 1e-9


@given(st.lists(st.integers(min_value=0, max_value=25), min_size=4, max_size=4))
def test_pesos_no_negativos_que_suman_100_son_validos(cuatro: list[int]) -> None:
    pesos = dict(zip(KPIS, [*cuatro, 100 - sum(cuatro)], strict=True))
    assert validar_pesos(pesos) is None


def _desempeno_constante(meses: int) -> list[Mes]:
    return [
        Mes(
            sumar_meses(HOY, -i),
            sla=99,
            resolucion=4,
            incidentes=0,
            entregas=95,
            satisfaccion=4.5,
        )
        for i in range(meses)
    ]


def test_meses_distintos_con_el_mismo_desempeno_puntuan_igual() -> None:
    # Errores de punto flotante no deben separar a proveedores con el mismo desempeño constante.
    desempeno = {f"p{meses}": _desempeno_constante(meses) for meses in range(1, 13)}
    categorias = dict.fromkeys(desempeno, "nube")
    puntuaciones = puntuar(desempeno, categorias, Pesos(), HOY)
    assert len({p.sin_ajuste for p in puntuaciones.values()}) == 1
    for p in puntuaciones.values():
        assert p.componentes == dict.fromkeys(KPIS, 50.0)


def _media_del_grupo(
    proveedor: str, puntuaciones: dict[str, Puntuacion], categorias: dict[str, str]
) -> float:
    """Media de sin_ajuste del grupo de comparación: la categoría si tiene 20, si no todos."""
    de_su_categoria = [q for q in puntuaciones if categorias[q] == categorias[proveedor]]
    grupo = de_su_categoria if len(de_su_categoria) >= 20 else list(puntuaciones)
    return statistics.mean(puntuaciones[q].sin_ajuste for q in grupo)


def test_la_contraccion_usa_la_media_del_grupo_con_que_se_comparo() -> None:
    # Dos categorías de menos de 20: el grupo de comparación son todos los proveedores.
    buenos = {f"b{i}": _historia(0.85 + i * 0.01) for i in range(5)}
    malos = {f"m{i}": _historia(0.1 + i * 0.01) for i in range(5)}
    categorias = dict.fromkeys(buenos, "nube") | dict.fromkeys(malos, "soporte")
    puntuaciones = puntuar(buenos | malos, categorias, Pesos(), HOY)
    for nombre, p in puntuaciones.items():
        media = _media_del_grupo(nombre, puntuaciones, categorias)
        assert p.puntuacion == pytest.approx(contraer(p.sin_ajuste, media, p.meses))
    # Una categoría de 20 o más se compara consigo misma; la de 3 se compara con todos.
    nube = {f"n{i}": _historia(0.8 + i * 0.005) for i in range(20)}
    soporte = {f"s{i}": _historia(0.1 + i * 0.005) for i in range(3)}
    categorias = dict.fromkeys(nube, "nube") | dict.fromkeys(soporte, "soporte")
    puntuaciones = puntuar(nube | soporte, categorias, Pesos(), HOY)
    for nombre, p in puntuaciones.items():
        media = _media_del_grupo(nombre, puntuaciones, categorias)
        assert p.puntuacion == pytest.approx(contraer(p.sin_ajuste, media, p.meses))


def test_contraer_con_k_6() -> None:
    assert contraer(80, 50, 6) == 65
    assert contraer(80, 50, 2) == pytest.approx(57.5)


def test_con_menos_meses_la_puntuacion_se_acerca_mas_a_la_media() -> None:
    desempeno = {f"p{i}": _historia(0.2 + i * 0.1) for i in range(5)}
    desempeno["corto"] = _historia(0.9, meses=2)
    desempeno["largo"] = _historia(0.9, meses=12)
    categorias = dict.fromkeys(desempeno, "nube")
    puntuaciones = puntuar(desempeno, categorias, Pesos(), HOY)
    media = statistics.mean(p.sin_ajuste for p in puntuaciones.values())
    corto, largo = puntuaciones["corto"], puntuaciones["largo"]
    assert corto.sin_ajuste == pytest.approx(largo.sin_ajuste)
    assert abs(corto.puntuacion - media) < abs(largo.puntuacion - media)
