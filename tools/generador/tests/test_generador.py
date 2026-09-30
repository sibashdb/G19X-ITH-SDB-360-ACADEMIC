import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import pytest
from generador.__main__ import main
from generador.catalogo import SERVICIOS
from generador.modelo import generar
from generador.salida import escribir

ARCHIVOS = (
    "servicios.csv",
    "proveedores.csv",
    "tipo_cambio.csv",
    "contratos.csv",
    "desempeno.csv",
    "verdad_oculta.json",
)
# KPI -> signo de su relación con la calidad (tiempo de resolución e incidentes: negativo).
KPIS = {
    "sla_cumplimiento_pct": 1,
    "tiempo_resolucion_h": -1,
    "incidentes_criticos": -1,
    "entregas_a_tiempo_pct": 1,
    "satisfaccion": 1,
}


def test_misma_semilla_produce_los_mismos_archivos(tmp_path: Path) -> None:
    escribir(generar(7, n_proveedores=10), tmp_path / "a")
    escribir(generar(7, n_proveedores=10), tmp_path / "b")
    escribir(generar(8, n_proveedores=10), tmp_path / "c")
    for nombre in ARCHIVOS:
        assert (tmp_path / "a" / nombre).read_bytes() == (tmp_path / "b" / nombre).read_bytes()
        # Mismos bytes en cualquier sistema operativo: saltos de línea siempre "\n".
        assert b"\r\n" not in (tmp_path / "a" / nombre).read_bytes()
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


def test_kpis_son_senales_imperfectas_pero_informativas() -> None:
    # Spearman del promedio por proveedor de cada KPI contra la calidad oculta (semilla 11:
    # 0.79 a 0.87). Cota superior: si subiera de 0.95 los KPI volverían a ser casi sin ruido.
    datos = generar(11)
    calidad = [p.calidad for p in datos.proveedores]
    for kpi, signo in KPIS.items():
        valores: dict[str, list[float]] = defaultdict(list)
        for fila in datos.desempeno:
            valores[fila["rfc_proveedor"]].append(float(fila[kpi]))
        promedios = [statistics.fmean(valores[p.rfc]) for p in datos.proveedores]
        rho = signo * statistics.correlation(calidad, promedios, method="ranked")
        assert 0.6 < rho < 0.95, f"{kpi}: rho={rho:.3f}"


def test_hay_proveedores_recientes_con_poco_historial() -> None:
    datos = generar(11)
    meses = Counter(fila["rfc_proveedor"] for fila in datos.desempeno)
    assert len(meses) == len(datos.proveedores)
    assert any(n <= 12 for n in meses.values())
    assert any(n >= 48 for n in meses.values())


def test_precios_siguen_el_nivel_de_precio_oculto() -> None:
    # Spearman del promedio por proveedor de (precio / precio base del catálogo) contra
    # nivel_precio (semilla 11: 0.83).
    datos = generar(11)
    base = {s.codigo: float(s.precio_base) for s in SERVICIOS}
    razones: dict[str, list[float]] = defaultdict(list)
    for fila in datos.contratos:
        razon = float(fila["precio_unitario"]) / base[fila["codigo_servicio"]]
        razones[fila["rfc_proveedor"]].append(razon)
    promedios = [statistics.fmean(razones[p.rfc]) for p in datos.proveedores]
    niveles = [p.nivel_precio for p in datos.proveedores]
    assert statistics.correlation(niveles, promedios, method="ranked") > 0.7


def test_verdad_oculta_guarda_la_calidad_verdadera(tmp_path: Path) -> None:
    datos = generar(11, n_proveedores=5)
    escribir(datos, tmp_path)
    verdad = json.loads((tmp_path / "verdad_oculta.json").read_text(encoding="utf-8"))
    assert [(p["rfc"], p["calidad"]) for p in verdad["proveedores"]] == [
        (p.rfc, p.calidad) for p in datos.proveedores
    ]


def test_el_catalogo_no_usa_marcas_reales() -> None:
    marcas = (
        r"\b(Kubernetes|AWS|Azure|Google|Microsoft|Amazon|Salesforce|SAP|Oracle|Zoom|Slack|Jira)\b"
    )
    assert not re.search(marcas, " ".join(s.nombre for s in SERVICIOS), re.IGNORECASE)


@pytest.mark.parametrize("opcion", ["--anios", "--proveedores"])
@pytest.mark.parametrize("valor", ["0", "-3", "abc"])
def test_cli_rechaza_cantidades_no_positivas(
    opcion: str, valor: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as salida:
        main([opcion, valor, "--salida", str(tmp_path)])
    assert salida.value.code == 2
    assert "entero mayor o igual a 1" in capsys.readouterr().err
    assert not any(tmp_path.iterdir())


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
