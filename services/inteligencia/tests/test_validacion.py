from datetime import date
from pathlib import Path

import pytest
from generador.modelo import generar
from generador.salida import escribir
from inteligencia.modelo import ModeloPrecios, Resultado
from inteligencia.validacion import Validacion, informe, principal, validar


def _validacion(
    *,
    promovido: bool = True,
    mape: float = 0.083,
    cobertura: float = 0.464,
    mape_linea_base: float = 0.093,
    cobertura_linea_base: float = 0.435,
    spearman: float = 0.92,
) -> Validacion:
    """Una validación armada a mano, sin entrenar: lo que importa son las métricas."""
    modelo = ModeloPrecios(version=0, tasa_inflacion=0.045, categorias={}, regresores=[])
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
    assert codigo == (1 if "**no**" in texto else 0)


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
