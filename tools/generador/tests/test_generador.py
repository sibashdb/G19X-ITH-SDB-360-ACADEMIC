import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from generador.__main__ import main
from generador.catalogo import SERVICIOS
from generador.modelo import generar
from generador.salida import escribir


def test_misma_semilla_produce_los_mismos_archivos(tmp_path: Path) -> None:
    escribir(generar(7, n_proveedores=10), tmp_path / "a")
    escribir(generar(7, n_proveedores=10), tmp_path / "b")
    escribir(generar(8, n_proveedores=10), tmp_path / "c")
    for nombre in ("proveedores.csv", "contratos.csv", "desempeno.csv", "tipo_cambio.csv"):
        assert (tmp_path / "a" / nombre).read_bytes() == (tmp_path / "b" / nombre).read_bytes()
    contratos_a = (tmp_path / "a" / "contratos.csv").read_bytes()
    assert contratos_a != (tmp_path / "c" / "contratos.csv").read_bytes()


def test_volumen_por_defecto() -> None:
    datos = generar()
    folios = {fila["folio"] for fila in datos.contratos}
    assert len(SERVICIOS) == 40
    assert len(datos.proveedores) == 60
    assert len({p.rfc for p in datos.proveedores}) == 60
    assert len({p.nombre for p in datos.proveedores}) == 60
    assert 1_500 <= len(folios) <= 2_500
    assert len(datos.desempeno) > 1_500


def test_integridad_referencial_y_reglas_de_negocio() -> None:
    datos = generar(3, n_proveedores=15)
    rfcs = {p.rfc for p in datos.proveedores}
    monedas = {s.codigo: s.moneda for s in SERVICIOS}
    for fila in datos.contratos:
        assert fila["rfc_proveedor"] in rfcs
        assert fila["moneda"] == monedas[fila["codigo_servicio"]]
        assert fila["fecha_fin"] > fila["fecha_inicio"]
        assert float(fila["precio_unitario"]) > 0
        assert float(fila["cantidad"]) > 0


def test_kpis_reflejan_la_calidad_oculta() -> None:
    datos = generar(11)
    satisfaccion: dict[str, list[float]] = defaultdict(list)
    for fila in datos.desempeno:
        satisfaccion[fila["rfc_proveedor"]].append(float(fila["satisfaccion"]))
    calidad = [p.calidad for p in datos.proveedores]
    promedio = [statistics.fmean(satisfaccion[p.rfc]) for p in datos.proveedores]
    assert statistics.correlation(calidad, promedio, method="ranked") > 0.8


def test_cli_escribe_los_seis_archivos(tmp_path: Path) -> None:
    main(["--semilla", "5", "--proveedores", "5", "--salida", str(tmp_path)])
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "contratos.csv",
        "desempeno.csv",
        "proveedores.csv",
        "servicios.csv",
        "tipo_cambio.csv",
        "verdad_oculta.json",
    ]
    verdad = json.loads((tmp_path / "verdad_oculta.json").read_text(encoding="utf-8"))
    assert len(verdad["proveedores"]) == 5
    with (tmp_path / "proveedores.csv").open(encoding="utf-8", newline="") as archivo:
        assert next(csv.reader(archivo)) == [
            "rfc",
            "nombre",
            "tamano",
            "categorias",
            "contacto_nombre",
            "contacto_email",
            "activo",
        ]
