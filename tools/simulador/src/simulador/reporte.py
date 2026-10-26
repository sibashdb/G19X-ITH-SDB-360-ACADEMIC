"""Métricas de la simulación y su reporte en Markdown (docs/qa/simulacion-negociacion.md)."""

import statistics
from collections.abc import Sequence
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
    ataques: int = 0  # ataques de texto del bot manipulador

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
        ataques=sum(r.ataques for r in resultados),
    )


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor * 100:.1f} %"


def _fila(nombre: str, m: Metricas) -> str:
    return (
        f"| {nombre} | {m.sesiones} | {m.posibles} | {m.acuerdos} "
        f"| {_pct(m.tasa)} | {_pct(m.ahorro)} |"
    )


def reporte(resultados: Sequence[Resultado], escenarios: Sequence[Escenario], semilla: int) -> str:
    total = metricas(resultados)
    compras = sum(e.tipo == "compra" for e in escenarios)
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
        "- **Ataques de texto:** el bot manipulador abre sus rondas 1 a 3 con un ataque de "
        "`tools/evals` por `POST /portal/mensajes`. El falso de `ia` interpreta cada uno como una "
        "oferta por encima de todo límite; lo interpretado solo prellena el formulario y el bot "
        "sigue con su propia oferta.",
        "",
        "| Métrica | Meta (PRD §1.6) | Resultado |",
        "|---|---|---|",
        f"| Acuerdos fuera de los límites del comprador | 0 | {total.fuera_de_limites} |",
        f"| Tasa de acuerdo | ≥ 70 % | {_pct(total.tasa)} |",
        "| Ahorro frente a la primera oferta (promedio de los acuerdos) | ≥ 8 % "
        f"| {_pct(total.ahorro)} |",
        f"| Sesiones con acuerdo posible | — | {total.posibles} de {total.sesiones} |",
        f"| Ataques de texto del bot manipulador | — | {total.ataques} |",
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
    lineas += [
        "",
        "> La sección `## Lectura` que sigue se escribe a mano: al volver a generar este archivo "
        "se borra.",
    ]
    return "\n".join(lineas) + "\n"
