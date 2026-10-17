from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import sklearn
from generador.modelo import generar
from generador.salida import escribir
from inteligencia.dominio.adjudicacion import (
    Candidato,
    Entrada,
    PesosAdjudicacion,
    Recomendacion,
    Riesgo,
    recomendar,
)
from inteligencia.dominio.puntuacion import Puntuacion
from inteligencia.modelo import ModeloPrecios, Resultado
from inteligencia.validacion import (
    ResultadoAdjudicacion,
    Validacion,
    _comparar,
    informe,
    principal,
    validar,
    validar_adjudicacion,
)

ADJUDICACION = ResultadoAdjudicacion(200, 0.91, 0.98, 3.4, 4242)


def _validacion(
    *,
    promovido: bool = True,
    mape: float = 0.083,
    cobertura: float = 0.464,
    mape_linea_base: float = 0.093,
    cobertura_linea_base: float = 0.435,
    spearman: float = 0.92,
    adjudicacion: ResultadoAdjudicacion = ADJUDICACION,
) -> Validacion:
    """Una validación armada a mano, sin entrenar: lo que importa son las métricas."""
    modelo = ModeloPrecios(
        version=0,
        tasa_inflacion=0.045,
        categorias={},
        regresores=[],
        version_sklearn=sklearn.__version__,
    )
    resultado = Resultado(
        modelo=modelo if promovido else None,
        observaciones=3553,
        datos_hasta=date(2026, 9, 1),
        mape=mape,
        mape_linea_base=mape_linea_base,
        cobertura=cobertura,
        cobertura_linea_base=cobertura_linea_base,
        pinball=0.1,
    )
    return Validacion(
        semilla=42,
        proveedores=60,
        lineas=3553,
        hasta=date(2026, 9, 1),
        precios=resultado,
        spearman=spearman,
        adjudicacion=adjudicacion,
    )


def test_la_inteligencia_cumple_las_metas_con_el_dataset_por_defecto(tmp_path: Path) -> None:
    escribir(generar(42), tmp_path)
    validacion = validar(tmp_path, tmp_path / "verdad_oculta.json")
    assert (validacion.semilla, validacion.proveedores) == (42, 60)
    assert validacion.cumple_precios, (validacion.mape_en_uso, validacion.cobertura_en_uso)
    assert validacion.cumple_puntuacion, validacion.spearman


def test_escribe_el_informe_y_responde_con_el_resultado(tmp_path: Path) -> None:
    datos = tmp_path / "datos"
    escribir(generar(7, n_proveedores=20), datos)
    salida = tmp_path / "qa" / "validacion.md"
    codigo = principal(["--verdad", str(datos / "verdad_oculta.json"), "--salida", str(salida)])
    texto = salida.read_text(encoding="utf-8")
    assert texto.startswith("# Validación del servicio de inteligencia\n")
    for parte in (
        "MAPE del P50",
        "Cobertura [P25, P75]",
        "Spearman",
        "semilla 7",
        "20 proveedores",
    ):
        assert parte in texto, parte
    # La adjudicación solo se reporta: el código de salida depende de los precios y la puntuación.
    assert codigo == (1 if "**no**" in texto.split("## Adjudicación")[0] else 0)


def test_con_el_modelo_promovido_se_miden_las_metricas_del_modelo() -> None:
    validacion = _validacion(promovido=True, mape=0.05, cobertura=0.50)
    assert (validacion.mape_en_uso, validacion.cobertura_en_uso) == (0.05, 0.50)
    assert validacion.cumple_precios
    assert "En uso: el modelo, porque mejora la línea base" in informe(
        validacion, date(2026, 10, 12)
    )


def test_sin_promocion_se_miden_las_metricas_de_la_linea_base() -> None:
    # El modelo, de haberse usado, cumpliría; la línea base (la que responde) no.
    validacion = _validacion(
        promovido=False,
        mape=0.05,
        cobertura=0.50,
        mape_linea_base=0.12,
        cobertura_linea_base=0.30,
    )
    assert validacion.mape_en_uso == validacion.precios.mape_linea_base == 0.12
    assert validacion.cobertura_en_uso == validacion.precios.cobertura_linea_base == 0.30
    assert not validacion.cumple_precios
    texto = informe(validacion, date(2026, 10, 12))
    assert "la línea base, porque el modelo no la mejoró" in texto
    assert "Cumple: **no**" in texto


@pytest.mark.parametrize(
    ("mape", "spearman", "codigo"),
    [
        pytest.param(0.083, 0.92, 0, id="cumple-las-dos"),
        pytest.param(0.083, 0.50, 1, id="solo-falla-la-puntuacion"),
        pytest.param(0.20, 0.92, 1, id="solo-fallan-los-precios"),
        pytest.param(0.20, 0.50, 1, id="fallan-las-dos"),
    ],
)
def test_el_codigo_de_salida_es_cero_solo_si_se_cumplen_las_dos_metas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mape: float, spearman: float, codigo: int
) -> None:
    validacion = _validacion(mape=mape, spearman=spearman)
    monkeypatch.setattr("inteligencia.validacion.validar", lambda carpeta, verdad: validacion)
    salida = tmp_path / "validacion.md"
    argumentos = ["--verdad", str(tmp_path / "verdad_oculta.json"), "--salida", str(salida)]
    assert principal(argumentos) == codigo
    assert salida.exists()


def test_la_validacion_reporta_la_adjudicacion(tmp_path: Path) -> None:
    escribir(generar(42), tmp_path)
    adjudicacion = validar(tmp_path, tmp_path / "verdad_oculta.json").adjudicacion
    assert adjudicacion.eventos == 200
    assert 0.0 <= adjudicacion.acierto_top1 <= adjudicacion.acierto_top2 <= 1.0
    assert adjudicacion.margen_fallos is None or adjudicacion.margen_fallos > 0
    # Piso de regresión, no la meta: con el dataset por defecto el top-1 ronda 85 %, justo en ella.
    assert adjudicacion.acierto_top1 >= 0.75


def test_misma_semilla_mismo_resultado(tmp_path: Path) -> None:
    escribir(generar(7, n_proveedores=20), tmp_path)
    verdad = tmp_path / "verdad_oculta.json"
    assert validar(tmp_path, verdad).adjudicacion == validar(tmp_path, verdad).adjudicacion


def test_la_semilla_y_los_eventos_se_respetan() -> None:
    escenario = {**_escenario(0.1, 0.9), "eventos": 30}
    uno = validar_adjudicacion(**escenario, semilla=1)
    assert validar_adjudicacion(**escenario, semilla=1) == uno
    otro = validar_adjudicacion(**escenario, semilla=2)
    assert otro.margen_fallos != uno.margen_fallos  # otra semilla, otros SLA sorteados
    assert (uno.eventos, uno.semilla, otro.semilla) == (30, 1, 2)
    assert validar_adjudicacion(**{**escenario, "eventos": 10}).eventos == 10


def test_el_informe_incluye_la_seccion_de_adjudicacion() -> None:
    texto = informe(_validacion(), date(2026, 10, 16))
    adjudicacion = texto.split("## Adjudicación")[1]
    partes = ("200 eventos", "semilla 4242", "top-1", "91.0 %", "top-2", "98.0 %", "3.4 puntos")
    for parte in (*partes, "Cumple: sí"):
        assert parte in adjudicacion, parte


def test_el_informe_toma_la_semilla_del_resultado() -> None:
    validacion = _validacion(adjudicacion=ResultadoAdjudicacion(200, 0.91, 0.98, 3.4, 77))
    assert "semilla 77" in informe(validacion, date(2026, 10, 16)).split("## Adjudicación")[1]


@pytest.mark.parametrize(
    ("eventos", "top1", "intervalo"),
    [
        pytest.param(200, 0.85, "80.1 % a 89.9 %", id="en-la-meta"),
        pytest.param(50, 0.99, "96.2 % a 100.0 %", id="se-recorta-en-100"),
        pytest.param(50, 0.01, "0.0 % a 3.8 %", id="se-recorta-en-0"),
    ],
)
def test_el_informe_da_el_intervalo_de_95_por_ciento_del_top_1(
    eventos: int, top1: float, intervalo: str
) -> None:
    validacion = _validacion(adjudicacion=ResultadoAdjudicacion(eventos, top1, 1.0, None, 4242))
    texto = informe(validacion, date(2026, 10, 16)).split("## Adjudicación")[1]
    assert (
        f"Con {eventos} eventos, el intervalo de 95 % del acierto top-1 va de {intervalo}" in texto
    )


@pytest.mark.parametrize(
    ("top1", "cumple"), [(0.85, True), (0.849, False)], ids=["en-la-meta", "bajo-la-meta"]
)
def test_la_meta_de_adjudicacion_es_85_por_ciento(top1: float, cumple: bool) -> None:
    validacion = _validacion(adjudicacion=ResultadoAdjudicacion(200, top1, 1.0, None, 4242))
    assert validacion.cumple_adjudicacion is cumple
    texto = informe(validacion, date(2026, 10, 16)).split("## Adjudicación")[1]
    assert ("Cumple: sí" in texto) is cumple
    assert "sin fallos" in texto


def test_la_adjudicacion_no_cambia_el_codigo_de_salida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    validacion = _validacion(adjudicacion=ResultadoAdjudicacion(200, 0.4, 0.6, 20.0, 4242))
    monkeypatch.setattr("inteligencia.validacion.validar", lambda carpeta, verdad: validacion)
    salida = tmp_path / "validacion.md"
    assert principal(["--verdad", str(tmp_path / "v.json"), "--salida", str(salida)]) == 0
    assert "Cumple: **no**" in salida.read_text(encoding="utf-8").split("## Adjudicación")[1]


def _escenario(calidad_a: float, calidad_b: float) -> dict[str, Any]:
    """Dos proveedores de la misma categoría, con el mismo precio y sin historial de incidentes.

    Con costo y riesgo empatados, solo deciden el desempeño (30 puntos) y el SLA (15 como máximo):
    la puntuación observada es 90 para A y 10 para B.
    """
    hasta = date(2026, 9, 1)
    nombres = {"A": "Alfa", "B": "Beta"}
    return {
        "proveedores": [
            {"rfc": rfc, "nombre": n, "categorias": "soporte", "activo": "true"}
            for rfc, n in nombres.items()
        ],
        "servicios": [{"codigo": "S1", "categoria": "soporte", "unidad": "mes", "moneda": "MXN"}],
        "contratos": [
            {
                "rfc_proveedor": rfc,
                "fecha_inicio": "2026-01-01",
                "fecha_fin": "2026-12-31",
                "moneda": "MXN",
                "codigo_servicio": "S1",
                "cantidad": cantidad,
                "precio_unitario": "1000",
            }
            for rfc in nombres
            for cantidad in ("2", "4")
        ],
        "desempeno": {},
        "puntuaciones": {
            "A": Puntuacion(90.0, 90.0, 12, {}, {}),
            "B": Puntuacion(10.0, 10.0, 12, {}, {}),
        },
        "oculta": {
            "A": {"calidad": calidad_a, "nivel_precio": 1.0},
            "B": {"calidad": calidad_b, "nivel_precio": 1.0},
        },
        "hasta": hasta,
        "eventos": 30,
        "tipos_cambio": {hasta: Decimal("20")},
    }


def test_si_la_puntuacion_coincide_con_la_calidad_se_acierta_siempre() -> None:
    resultado = validar_adjudicacion(**_escenario(0.9, 0.1))
    assert resultado == ResultadoAdjudicacion(30, 1.0, 1.0, None, 4242)


def test_si_la_puntuacion_se_equivoca_siempre_falla_el_top1_y_se_mide_el_margen() -> None:
    resultado = validar_adjudicacion(**_escenario(0.1, 0.9))
    assert (resultado.acierto_top1, resultado.acierto_top2) == (0.0, 1.0)
    # En el ranking verdadero B le gana a A por 30 puntos de desempeño más o menos el SLA (15).
    assert resultado.margen_fallos is not None
    assert 15 <= resultado.margen_fallos <= 45


def test_sin_tipo_de_cambio_no_se_puede_validar() -> None:
    with pytest.raises(ValueError, match="tipo de cambio"):
        validar_adjudicacion(**{**_escenario(0.9, 0.1), "tipos_cambio": {}})


def test_solo_participan_los_activos_con_puntuacion_y_de_la_categoria(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    escenario = _escenario(0.9, 0.1)
    # C tiene la categoría en segundo lugar (sí participa); D está inactivo, E no tiene puntuación
    # y F es de otra categoría (no participan).
    otros = {"C": ("nube|soporte", "true"), "D": ("soporte", "false"), "E": ("soporte", "true")}
    otros["F"] = ("nube", "true")
    escenario["proveedores"] += [
        {"rfc": rfc, "nombre": rfc, "categorias": categorias, "activo": activo}
        for rfc, (categorias, activo) in otros.items()
    ]
    escenario["puntuaciones"] |= {r: Puntuacion(50.0, 50.0, 12, {}, {}) for r in "CDF"}
    escenario["oculta"] |= {r: {"calidad": 0.5, "nivel_precio": 1.0} for r in "CDEF"}
    vistos: set[str] = set()

    def espia(entradas: Sequence[Entrada], pesos: PesosAdjudicacion) -> Recomendacion:
        vistos.update(e.candidato.id for e in entradas)
        return recomendar(entradas, pesos)

    monkeypatch.setattr("inteligencia.validacion.recomendar", espia)
    validar_adjudicacion(**escenario)
    assert vistos == {"A", "B", "C"}


def test_sin_eventos_no_hay_nada_que_medir() -> None:
    with pytest.raises(ValueError, match="al menos un evento"):
        validar_adjudicacion(**{**_escenario(0.9, 0.1), "eventos": 0})


def test_sin_una_categoria_con_dos_proveedores_elegibles_no_se_puede_validar() -> None:
    escenario = _escenario(0.9, 0.1)
    escenario["proveedores"][1]["activo"] = "false"
    with pytest.raises(ValueError, match="al menos 2 proveedores"):
        validar_adjudicacion(**escenario)


def _empatada(rfc: str, desempeno: float) -> Entrada:
    """Una entrada con costo, riesgo y SLA iguales a los de las demás: solo decide el desempeño."""
    candidato = Candidato(rfc, rfc, rfc, 12, Decimal(0), None, ())
    return Entrada(candidato, Decimal(1000), Decimal(1000), desempeno, Riesgo(0.0, 0.0, 0.0, False))


@pytest.mark.parametrize(
    ("calidades", "esperado"),
    [
        # Observado: A 100, B 88.75, C 70. Verdadero: A 100, B 88.75, C 70. Coinciden.
        pytest.param((0.9, 0.6, 0.1), (True, True, 0.0), id="acierta"),
        # Verdadero: B 100, A 85, C 70. El verdadero es el segundo del observado (en el observado
        # su ventaja sobre A sería 11.25, no 15).
        pytest.param((0.5, 0.9, 0.1), (False, True, 15.0), id="falla-el-top-1-y-acierta-el-top-2"),
        # Verdadero: C 100, A 85, B 70. El verdadero es el tercero del observado (en el observado
        # su ventaja sobre A sería 30, no 15).
        pytest.param((0.5, 0.1, 0.9), (False, False, 15.0), id="falla-los-dos"),
    ],
)
def test_comparar_mide_el_top_1_el_top_2_y_el_margen_del_ranking_verdadero(
    calidades: tuple[float, float, float], esperado: tuple[bool, bool, float]
) -> None:
    entradas = [_empatada("A", 90.0), _empatada("B", 60.0), _empatada("C", 10.0)]
    oculta = {rfc: {"calidad": c} for rfc, c in zip("ABC", calidades, strict=True)}
    top1, top2, ventaja = _comparar(entradas, oculta, PesosAdjudicacion())
    assert (top1, top2) == esperado[:2]
    assert ventaja == pytest.approx(esperado[2])
