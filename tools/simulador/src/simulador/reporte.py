"""Métricas de la simulación y su reporte en Markdown (docs/qa/simulacion-negociacion.md)."""

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from simulador.escenarios import Escenario
from simulador.orquestador import Resultado


@dataclass(frozen=True)
class Metricas:
    sesiones: int
    posibles: int
    acuerdos: int
    fuera_de_limites: int
    ahorro: float | None  # promedio sobre los acuerdos

    @property
    def tasa(self) -> float:
        return self.acuerdos / self.sesiones if self.sesiones else 0.0


def metricas(resultados: Sequence[Resultado]) -> Metricas:
    acuerdos = [r for r in resultados if r.estado == "acuerdo_tentativo"]
    ahorros = [r.ahorro for r in acuerdos if r.ahorro is not None]
    return Metricas(
        sesiones=len(resultados),
        posibles=sum(r.posible for r in resultados),
        acuerdos=len(acuerdos),
        fuera_de_limites=sum(r.fuera_de_limites for r in resultados),
        ahorro=statistics.fmean(ahorros) if ahorros else None,
    )


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor * 100:.1f} %"


def _fila(nombre: str, m: Metricas) -> str:
    return (
        f"| {nombre} | {m.sesiones} | {m.posibles} | {m.acuerdos} "
        f"| {_pct(m.tasa)} | {_pct(m.ahorro)} |"
    )


def reporte(
    resultados: Sequence[Resultado],
    escenarios: Sequence[Escenario],
    semilla: int,
    omitidos: Mapping[str, str] | None = None,
) -> str:
    """`escenarios` son los que se simularon; `omitidos`, los que no se pudieron publicar."""
    total = metricas(resultados)
    compras = sum(e.tipo == "compra" for e in escenarios)
    sin_simular = (
        [
            f"- **Escenarios sin simular:** {len(omitidos)}, porque sus valores sugeridos no se "
            "pueden publicar tal cual: " + "; ".join(f"{t} ({m})" for t, m in omitidos.items()),
        ]
        if omitidos
        else []
    )
    lineas = [
        "# Simulación de negociación con bots (N1)",
        "",
        f"- **Escenarios:** {compras} compras y {len(escenarios) - compras} renovaciones; "
        f"{total.sesiones} sesiones.",
        f"- **Datos:** `generador.modelo.generar({semilla})`, los mismos que escribe "
        "`python -m generador` en `datos/`.",
        "- **Cómo se corrió:** `SIMULACION_REPORTE=docs/qa/simulacion-negociacion.md uv run pytest "
        "services/negociacion/tests/test_simulacion.py`.",
        "- **Acuerdo posible:** la reserva del bot cabe en los límites del comprador. Sin ese "
        "traslape no hay acuerdo y lo correcto es cerrar sin acuerdo.",
        *sin_simular,
        "",
        "| Métrica | Meta (PRD §1.6) | Resultado |",
        "|---|---|---|",
        f"| Acuerdos fuera de los límites del comprador | 0 | {total.fuera_de_limites} |",
        f"| Tasa de acuerdo | ≥ 70 % | {_pct(total.tasa)} |",
        "| Ahorro frente a la primera oferta (promedio de los acuerdos) | ≥ 8 % "
        f"| {_pct(total.ahorro)} |",
        f"| Sesiones con acuerdo posible | — | {total.posibles} de {total.sesiones} |",
        "",
        "## Por estilo de proveedor",
        "",
        "| Estilo | Sesiones | Acuerdo posible | Acuerdos | Tasa | Ahorro |",
        "|---|---|---|---|---|---|",
    ]
    for estilo in sorted({r.estilo for r in resultados}):
        lineas.append(_fila(estilo, metricas([r for r in resultados if r.estilo == estilo])))
    lineas += [
        "",
        "## Por tipo de negociación",
        "",
        "| Tipo | Sesiones | Acuerdo posible | Acuerdos | Tasa | Ahorro |",
        "|---|---|---|---|---|---|",
    ]
    for tipo in ("compra", "renovacion"):
        lineas.append(_fila(tipo, metricas([r for r in resultados if r.tipo == tipo])))
    return "\n".join(lineas) + "\n"
