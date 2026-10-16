"""Valida el precio justo y la puntuación contra la verdad oculta del generador.

    uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json

Lee los CSV que exporta el generador (en la carpeta de la verdad, o en --datos) y escribe
docs/qa/validacion-inteligencia.md con las métricas y las metas de la especificación (§1) y la de
la recomendación de adjudicación. La verdad oculta solo se lee aquí: nunca se carga a la
plataforma.
"""

import argparse
import csv
import json
import random
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from scipy.stats import spearmanr

from inteligencia.dominio.adjudicacion import (
    Candidato,
    Entrada,
    LineaCandidato,
    PesosAdjudicacion,
    concentracion,
    costo_total,
    recomendar,
    riesgo,
    tendencia_incidentes,
)
from inteligencia.dominio.monedas import a_mxn, tipo_cambio_en
from inteligencia.dominio.precios import (
    Observacion,
    cantidad_mensual,
    meses_entre,
    plazo_en_meses,
)
from inteligencia.dominio.puntuacion import Mes, Pesos, Puntuacion, puntuar
from inteligencia.modelo import MESES_VALIDACION, Resultado, entrenar

META_MAPE = 0.15
META_COBERTURA = (0.40, 0.60)
META_SPEARMAN = 0.8
META_ADJUDICACION = 0.85
EVENTOS_ADJUDICACION = 200
SEMILLA_ADJUDICACION = 4242
MESES_ANIO = 12  # el plazo de los eventos simulados y el año del gasto anual
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
class ResultadoAdjudicacion:
    eventos: int
    acierto_top1: float  # fracción de eventos en que el recomendado es el mejor verdadero
    acierto_top2: float  # ... y en que el mejor verdadero está entre los dos primeros
    margen_fallos: float | None  # puntos promedio en los fallos; None si no hubo fallos


@dataclass(frozen=True)
class Validacion:
    semilla: int
    proveedores: int
    lineas: int
    hasta: date
    precios: Resultado
    spearman: float
    adjudicacion: ResultadoAdjudicacion

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

    @property
    def cumple_adjudicacion(self) -> bool:
        return self.adjudicacion.acierto_top1 >= META_ADJUDICACION


def _gasto_anual(
    contratos: Sequence[Mapping[str, str]],
    unidades: Mapping[str, str],
    usd_mxn: Decimal,
    hasta: date,
) -> dict[str, Decimal]:
    """Gasto anual en MXN de cada proveedor con las líneas de contrato vigentes en `hasta`."""
    gasto: dict[str, Decimal] = defaultdict(Decimal)
    for fila in contratos:
        inicio = date.fromisoformat(fila["fecha_inicio"])
        fin = date.fromisoformat(fila["fecha_fin"])
        if inicio <= hasta <= fin:
            cantidad = cantidad_mensual(
                Decimal(fila["cantidad"]),
                unidades[fila["codigo_servicio"]],
                plazo_en_meses(inicio, fin),
            )
            mensual = cantidad * Decimal(fila["precio_unitario"])
            gasto[fila["rfc_proveedor"]] += a_mxn(mensual, fila["moneda"], usd_mxn) * MESES_ANIO
    return gasto


def validar_adjudicacion(
    proveedores: list[dict[str, str]],
    contratos: list[dict[str, str]],
    desempeno: dict[str, list[Mes]],
    puntuaciones: dict[str, Puntuacion],
    oculta: dict[str, dict[str, Any]],
    hasta: date,
    eventos: int = EVENTOS_ADJUDICACION,
    semilla: int = SEMILLA_ADJUDICACION,
    *,
    servicios: list[dict[str, str]],
    tipos_cambio: Mapping[date, Decimal],
) -> ResultadoAdjudicacion:
    """Mide cuántas veces la recomendación elige al que la verdad oculta dice que es el mejor.

    Cada evento sortea una categoría con al menos 2 proveedores activos y con puntuación, uno de
    sus servicios y de 2 a 5 de esos proveedores. Cada candidato ofrece el P50 del servicio en
    `contratos` por su `nivel_precio` latente, en la cantidad mediana del servicio, a 12 meses,
    sin cuota y con un SLA nulo o de 99.0 a 99.9 %. El recomendado usa la puntuación observada; el
    verdadero repite el cálculo con `calidad` por 100 como desempeño, así que el costo, el riesgo
    y el SLA son los mismos. En la concentración, el gasto de cada proveedor es el anualizado de
    sus líneas vigentes en `hasta`.
    """
    usd_mxn = tipo_cambio_en(tipos_cambio, hasta)
    if usd_mxn is None:
        raise ValueError("Se necesita un tipo de cambio para validar la adjudicación.")
    servicio = {s["codigo"]: s for s in servicios}
    gasto = _gasto_anual(contratos, {c: s["unidad"] for c, s in servicio.items()}, usd_mxn, hasta)
    gasto_total = sum(gasto.values(), Decimal(0))
    precios: dict[str, list[Decimal]] = defaultdict(list)
    cantidades: dict[str, list[Decimal]] = defaultdict(list)
    for fila in contratos:
        precios[fila["codigo_servicio"]].append(Decimal(fila["precio_unitario"]))
        cantidades[fila["codigo_servicio"]].append(Decimal(fila["cantidad"]))
    servicios_de: dict[str, list[str]] = defaultdict(list)
    for codigo in sorted(precios):
        servicios_de[servicio[codigo]["categoria"]].append(codigo)
    elegibles: dict[str, list[str]] = {}
    for categoria in sorted(servicios_de):
        rfcs = sorted(
            p["rfc"]
            for p in proveedores
            if p["activo"] == "true"
            and p["rfc"] in puntuaciones
            and categoria in p["categorias"].split("|")
        )
        if len(rfcs) >= 2:
            elegibles[categoria] = rfcs
    nombres = {p["rfc"]: p["nombre"] for p in proveedores}
    tendencias = {
        rfc: tendencia_incidentes(
            [
                m.incidentes
                for m in sorted(desempeno.get(rfc, []), key=lambda m: m.periodo)
                if meses_entre(m.periodo, hasta) >= 0
            ]
        )
        for rfc in puntuaciones
    }
    pesos = PesosAdjudicacion()
    rng = random.Random(semilla)  # noqa: S311 - eventos simulados reproducibles, no criptografía
    top1 = top2 = 0
    margenes: list[float] = []
    for _ in range(eventos):
        categoria = rng.choice(list(elegibles))
        codigo = rng.choice(servicios_de[categoria])
        unidad, moneda = servicio[codigo]["unidad"], servicio[codigo]["moneda"]
        p50 = statistics.median(precios[codigo])
        cantidad = statistics.median(cantidades[codigo])
        rfcs = rng.sample(elegibles[categoria], rng.randint(2, min(5, len(elegibles[categoria]))))
        entradas = []
        for rfc in rfcs:
            sla = None if rng.random() < 0.5 else Decimal(rng.randrange(990, 1000)) / 10
            precio = p50 * Decimal(str(oculta[rfc]["nivel_precio"]))
            candidato = Candidato(
                rfc,
                rfc,
                nombres[rfc],
                MESES_ANIO,
                Decimal(0),
                sla,
                (LineaCandidato(codigo, unidad, cantidad, precio),),
            )
            costo = costo_total(candidato)
            # El plazo es de un año y no hay cuota: el costo total es el costo anual.
            costo_mxn = a_mxn(costo, moneda, usd_mxn)
            entradas.append(
                Entrada(
                    candidato,
                    costo,
                    costo_mxn,
                    puntuaciones[rfc].puntuacion,
                    riesgo(
                        concentracion(gasto.get(rfc, Decimal(0)), gasto_total, costo_mxn),
                        tendencias[rfc],
                        puntuaciones[rfc].meses,
                    ),
                )
            )
        recomendada = recomendar(entradas, pesos).evaluados
        verdadera = recomendar(
            [
                replace(e, desempeno=float(oculta[e.candidato.id]["calidad"]) * 100)
                for e in entradas
            ],
            pesos,
        )
        elegido, mejor = recomendada[0].entrada.candidato.id, verdadera.recomendado
        top1 += elegido == mejor
        top2 += mejor in [e.entrada.candidato.id for e in recomendada[:2]]
        if elegido != mejor:
            puntos = {e.entrada.candidato.id: e.puntaje for e in verdadera.evaluados}
            margenes.append(puntos[mejor] - puntos[elegido])
    return ResultadoAdjudicacion(
        eventos, top1 / eventos, top2 / eventos, statistics.mean(margenes) if margenes else None
    )


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
    adjudicacion = validar_adjudicacion(
        proveedores,
        contratos,
        desempeno,
        puntuaciones,
        {p["rfc"]: p for p in oculta["proveedores"]},
        hasta,
        servicios=servicios,
        tipos_cambio={
            date.fromisoformat(f["periodo"]): Decimal(f["usd_mxn"])
            for f in _leer(carpeta / "tipo_cambio.csv")
        },
    )
    return Validacion(
        semilla=int(oculta["semilla"]),
        proveedores=len(proveedores),
        lineas=len(contratos),
        hasta=hasta,
        precios=precios,
        spearman=float(correlacion.statistic),
        adjudicacion=adjudicacion,
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
    a = v.adjudicacion
    margen = "sin fallos" if a.margen_fallos is None else f"{a.margen_fallos:.1f} puntos"
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
        "## Adjudicación",
        "",
        f"{a.eventos} eventos simulados (semilla {SEMILLA_ADJUDICACION}): cada uno es una "
        "categoría con 2 a 5 proveedores activos, a 12 meses, con el P50 del servicio por el nivel "
        "de precio latente de cada proveedor y un SLA nulo o de 99.0 a 99.9 %. El recomendado usa "
        "la puntuación observada; el mejor verdadero repite el cálculo con la calidad oculta por "
        "100 como desempeño, con el mismo costo, riesgo y SLA.",
        "",
        "| Medida | Valor | Meta |",
        "|---|---|---|",
        f"| Acierto top-1 (el recomendado es el mejor verdadero) | {_pct(a.acierto_top1)} | "
        f"≥ {_pct(META_ADJUDICACION)} |",
        f"| Acierto top-2 (el mejor verdadero está entre los dos primeros) | "
        f"{_pct(a.acierto_top2)} | |",
        f"| Margen promedio de los fallos | {margen} | |",
        "",
        f"Con los pesos por defecto. Cumple: {_cumple(v.cumple_adjudicacion)}.",
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
        f"Spearman {validacion.spearman:.3f}; "
        f"adjudicación top-1 {_pct(validacion.adjudicacion.acierto_top1)} -> {args.salida}"
    )
    return 0 if validacion.cumple_precios and validacion.cumple_puntuacion else 1


if __name__ == "__main__":
    sys.exit(principal())
