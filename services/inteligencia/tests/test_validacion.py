from pathlib import Path

from generador.modelo import generar
from generador.salida import escribir
from inteligencia.validacion import principal, validar


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
