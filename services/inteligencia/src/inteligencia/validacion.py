"""Valida el precio justo y la puntuación contra la verdad oculta del generador.

    uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json

Lee los CSV que exporta el generador (en la carpeta de la verdad, o en --datos) y escribe
docs/qa/validacion-inteligencia.md con las métricas y las metas de la especificación (§1). La
verdad oculta solo se lee aquí: nunca se carga a la plataforma.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from scipy.stats import spearmanr

from inteligencia.dominio.precios import Observacion, plazo_en_meses
from inteligencia.dominio.puntuacion import Mes, Pesos, puntuar
from inteligencia.modelo import MESES_VALIDACION, Resultado, entrenar

META_MAPE = 0.15
META_COBERTURA = (0.40, 0.60)
META_SPEARMAN = 0.8
INFLACION = 0.045  # la de la configuración por defecto
SALIDA = Path("docs/qa/validacion-inteligencia.md")


def observaciones_de(
    contratos: Iterable[Mapping[str, str]],
    categorias: Mapping[str, str],
    tamanos: Mapping[str, str],
) -> list[Observacion]:
    """Las filas de contratos (una por línea, como el CSV del ERP) como precios observados.

    `categorias` va del código de servicio a su categoría y `tamanos` del RFC al tamaño.
    """
    resultado = []
    for fila in contratos:
        inicio = date.fromisoformat(fila["fecha_inicio"])
        fin = date.fromisoformat(fila["fecha_fin"])
        resultado.append(
            Observacion(
                servicio=fila["codigo_servicio"],
                categoria=categorias[fila["codigo_servicio"]],
                moneda=fila["moneda"],
                fecha=inicio,
                cantidad=float(fila["cantidad"]),
                precio=float(fila["precio_unitario"]),
                plazo_meses=plazo_en_meses(inicio, fin),
                tamano=tamanos.get(fila["rfc_proveedor"]),
                tipo=fila["tipo"],
            )
        )
    return resultado


def meses_de(desempeno: Iterable[Mapping[str, str]]) -> dict[str, list[Mes]]:
    """El desempeño mensual de cada proveedor, por RFC."""
    meses: dict[str, list[Mes]] = defaultdict(list)
    for fila in desempeno:
        meses[fila["rfc_proveedor"]].append(
            Mes(
                date.fromisoformat(fila["periodo"]),
                sla=float(fila["sla_cumplimiento_pct"]),
                resolucion=float(fila["tiempo_resolucion_h"]),
                incidentes=float(fila["incidentes_criticos"]),
                entregas=float(fila["entregas_a_tiempo_pct"]),
                satisfaccion=float(fila["satisfaccion"]),
            )
        )
    return dict(meses)


@dataclass(frozen=True)
class Validacion:
    semilla: int
    proveedores: int
    lineas: int
    hasta: date
    precios: Resultado
    spearman: float

    @property
    def mape_en_uso(self) -> float:
        return self.precios.mape if self.precios.promovido else self.precios.mape_linea_base

    @property
    def cobertura_en_uso(self) -> float:
        p = self.precios
        return p.cobertura if p.promovido else p.cobertura_linea_base

    @property
    def cumple_precios(self) -> bool:
        minima, maxima = META_COBERTURA
        return self.mape_en_uso <= META_MAPE and minima <= self.cobertura_en_uso <= maxima

    @property
    def cumple_puntuacion(self) -> bool:
        return self.spearman >= META_SPEARMAN


def _leer(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def validar(carpeta: Path, verdad: Path) -> Validacion:
    servicios = _leer(carpeta / "servicios.csv")
    proveedores = _leer(carpeta / "proveedores.csv")
    contratos = _leer(carpeta / "contratos.csv")
    desempeno = meses_de(_leer(carpeta / "desempeno.csv"))
    oculta = json.loads(verdad.read_text(encoding="utf-8"))
    calidad = {p["rfc"]: float(p["calidad"]) for p in oculta["proveedores"]}

    observaciones = observaciones_de(
        contratos,
        {s["codigo"]: s["categoria"] for s in servicios},
        {p["rfc"]: p["tamano"] for p in proveedores},
    )
    precios = entrenar(observaciones, INFLACION, version=0)

    categorias = {p["rfc"]: p["categorias"].split("|")[0] for p in proveedores}
    hasta = max(m.periodo for meses in desempeno.values() for m in meses)
    puntuaciones = puntuar(
        {rfc: meses for rfc, meses in desempeno.items() if rfc in categorias},
        categorias,
        Pesos(),
        hasta,
    )
    rfcs = sorted(puntuaciones)
    correlacion = spearmanr(
        [puntuaciones[rfc].puntuacion for rfc in rfcs], [calidad[rfc] for rfc in rfcs]
    )
    return Validacion(
        semilla=int(oculta["semilla"]),
        proveedores=len(proveedores),
        lineas=len(contratos),
        hasta=hasta,
        precios=precios,
        spearman=float(correlacion.statistic),
    )


def _pct(valor: float) -> str:
    return f"{valor * 100:.1f} %"


def _cumple(si: bool) -> str:
    return "sí" if si else "**no**"


def informe(v: Validacion, generado: date) -> str:
    p = v.precios
    en_uso = (
        "el modelo, porque mejora la línea base"
        if p.promovido
        else "la línea base, porque el modelo no la mejoró"
    )
    minima, maxima = META_COBERTURA
    lineas = [
        "# Validación del servicio de inteligencia",
        "",
        f"Generado el {generado:%d/%m/%Y} con "
        "`uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json`.",
        "",
        f"Datos del generador: semilla {v.semilla}, {v.proveedores} proveedores, "
        f"{v.lineas:,} líneas de contrato y desempeño hasta {v.hasta:%m/%Y}. La verdad oculta "
        "(calidad de cada proveedor) solo se usa aquí, para medir; la plataforma nunca la ve.",
        "",
        "## Precio justo",
        "",
        f"Validación temporal: se entrena con los contratos hasta {MESES_VALIDACION} meses antes "
        "del último y se mide con los posteriores.",
        "",
        "| Método | MAPE del P50 | Cobertura [P25, P75] |",
        "|---|---|---|",
        f"| Línea base | {_pct(p.mape_linea_base)} | {_pct(p.cobertura_linea_base)} |",
        f"| Modelo (gradient boosting por cuantiles) | {_pct(p.mape)} | {_pct(p.cobertura)} |",
        "",
        f"Meta: MAPE del P50 ≤ {_pct(META_MAPE)} y cobertura entre {_pct(minima)} y "
        f"{_pct(maxima)}. En uso: {en_uso}. Cumple: {_cumple(v.cumple_precios)}.",
        "",
        "## Puntuación de proveedores",
        "",
        "| Medida | Valor | Meta |",
        "|---|---|---|",
        f"| Spearman entre la puntuación y la calidad oculta | {v.spearman:.3f} | "
        f"≥ {META_SPEARMAN} |",
        "",
        f"Con los pesos por defecto. Cumple: {_cumple(v.cumple_puntuacion)}.",
        "",
    ]
    return "\n".join(lineas)


def principal(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Valida la inteligencia contra la verdad oculta del generador"
    )
    parser.add_argument("--verdad", type=Path, required=True, help="verdad_oculta.json")
    parser.add_argument(
        "--datos", type=Path, help="carpeta de los CSV; por defecto, la de --verdad"
    )
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args(argumentos)
    validacion = validar(args.datos or args.verdad.parent, args.verdad)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(informe(validacion, date.today()), encoding="utf-8", newline="\n")
    print(
        f"Precio justo: MAPE {_pct(validacion.mape_en_uso)}, "
        f"cobertura {_pct(validacion.cobertura_en_uso)}; "
        f"Spearman {validacion.spearman:.3f} -> {args.salida}"
    )
    return 0 if validacion.cumple_precios and validacion.cumple_puntuacion else 1


if __name__ == "__main__":
    sys.exit(principal())
