"""Puntuación de proveedores (0 a 100) a partir de su desempeño mensual.

1. Cada KPI se promedia en los últimos 12 meses con decaimiento exponencial (vida media 6 meses).
2. Se convierte en percentil (0 a 100, más es mejor; resolución e incidentes se invierten) frente a
   los proveedores de su categoría principal si esa categoría tiene al menos
   MIN_PROVEEDORES_CATEGORIA proveedores con desempeño; si tiene menos, frente a todos (con pocos
   proveedores, los percentiles quedan muy gruesos y la puntuación pierde orden).
3. Los percentiles se combinan con los pesos (que suman 100).
4. Contracción bayesiana hacia la media del grupo con que se comparó: su categoría o, con menos
   de 20, todos. Con pocos meses de historia, la puntuación se acerca a esa media en vez de quedar
   en un extremo.
"""

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import date

from inteligencia.dominio.precios import meses_entre, sumar_meses

KPIS = ("sla", "resolucion", "incidentes", "entregas", "satisfaccion")
INVERSOS = frozenset({"resolucion", "incidentes"})  # menos es mejor
VENTANA_MESES = 12
VIDA_MEDIA_MESES = 6
K_CONTRACCION = 6
MIN_PROVEEDORES_CATEGORIA = 20
MESES_HISTORIAL_CORTO = 6
MESES_TENDENCIA = 3


@dataclass(frozen=True)
class Mes:
    periodo: date
    sla: float
    resolucion: float
    incidentes: float
    entregas: float
    satisfaccion: float


@dataclass(frozen=True)
class Pesos:
    sla: int = 30
    resolucion: int = 20
    incidentes: int = 20
    entregas: int = 15
    satisfaccion: int = 15

    def como_dict(self) -> dict[str, int]:
        return {campo.name: getattr(self, campo.name) for campo in fields(self)}


def validar_pesos(pesos: Mapping[str, int]) -> str | None:
    if any(valor < 0 for valor in pesos.values()):
        return "Los pesos no pueden ser negativos."
    total = sum(pesos.values())
    return None if total == 100 else f"Los pesos deben sumar 100 (suman {total})."


@dataclass(frozen=True)
class Puntuacion:
    puntuacion: float  # ajustada por la contracción; la que se muestra
    sin_ajuste: float
    meses: int  # meses con desempeño dentro de la ventana
    componentes: dict[str, float]  # percentil de cada KPI, más es mejor
    valores: dict[str, float]  # promedio ponderado de cada KPI

    @property
    def historial_corto(self) -> bool:
        return self.meses < MESES_HISTORIAL_CORTO


def promedio_ponderado(meses: Sequence[Mes], hasta: date) -> tuple[dict[str, float], int] | None:
    sumas = dict.fromkeys(KPIS, 0.0)
    peso_total = 0.0
    contados = 0
    for mes in meses:
        antiguedad = meses_entre(mes.periodo, hasta)
        if 0 <= antiguedad < VENTANA_MESES:
            peso = 0.5 ** (antiguedad / VIDA_MEDIA_MESES)
            peso_total += peso
            contados += 1
            for kpi in KPIS:
                sumas[kpi] += peso * getattr(mes, kpi)
    if contados == 0:
        return None
    # Redondear: el promedio con meses distintos deja ruido de punto flotante que rompe los empates.
    return {kpi: round(suma / peso_total, 9) for kpi, suma in sumas.items()}, contados


def percentil(valor: float, todos: Sequence[float]) -> float:
    """Rango percentil de 0 a 100; los empates comparten el promedio de sus posiciones."""
    if len(todos) <= 1:
        return 50.0
    menores = sum(1 for v in todos if v < valor)
    iguales = sum(1 for v in todos if v == valor)
    return 100 * (menores + (iguales - 1) / 2) / (len(todos) - 1)


def contraer(puntuacion: float, media: float, meses: int) -> float:
    return (meses * puntuacion + K_CONTRACCION * media) / (meses + K_CONTRACCION)


def puntuar(
    desempeno: Mapping[str, Sequence[Mes]],
    categorias: Mapping[str, str],
    pesos: Pesos,
    hasta: date,
) -> dict[str, Puntuacion]:
    resumen: dict[str, tuple[dict[str, float], int]] = {}
    for proveedor, meses in desempeno.items():
        promedio = promedio_ponderado(meses, hasta)
        if promedio is not None:
            resumen[proveedor] = promedio
    por_categoria: dict[str, list[str]] = defaultdict(list)
    for proveedor in resumen:
        por_categoria[categorias[proveedor]].append(proveedor)
    # Grupo con que se compara cada categoría: ella misma si tiene al menos MIN; si no, todos.
    grupos = {
        categoria: proveedores if len(proveedores) >= MIN_PROVEEDORES_CATEGORIA else list(resumen)
        for categoria, proveedores in por_categoria.items()
    }
    pesos_kpi = pesos.como_dict()
    componentes: dict[str, dict[str, float]] = {}
    crudas: dict[str, float] = {}
    for proveedor, (valores, _) in resumen.items():
        pares = grupos[categorias[proveedor]]
        propios: dict[str, float] = {}
        for kpi in KPIS:
            valor = percentil(valores[kpi], [resumen[otro][0][kpi] for otro in pares])
            propios[kpi] = 100 - valor if kpi in INVERSOS else valor
        componentes[proveedor] = propios
        crudas[proveedor] = sum(pesos_kpi[kpi] * propios[kpi] for kpi in KPIS) / 100
    # La contracción va hacia la media de sin_ajuste del mismo grupo que dio los percentiles.
    medias = {
        categoria: statistics.mean(crudas[p] for p in grupo) for categoria, grupo in grupos.items()
    }
    return {
        proveedor: Puntuacion(
            puntuacion=contraer(crudas[proveedor], medias[categorias[proveedor]], meses),
            sin_ajuste=crudas[proveedor],
            meses=meses,
            componentes=componentes[proveedor],
            valores=valores,
        )
        for proveedor, (valores, meses) in resumen.items()
    }


def historial(
    desempeno: Mapping[str, Sequence[Mes]],
    categorias: Mapping[str, str],
    pesos: Pesos,
    hasta: date,
    meses: int = 12,
) -> dict[str, list[tuple[date, float]]]:
    """La puntuación de cada proveedor al inicio de cada uno de los últimos `meses` meses."""
    serie: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for atras in range(meses - 1, -1, -1):
        fecha = sumar_meses(hasta, -atras)
        for proveedor, p in puntuar(desempeno, categorias, pesos, fecha).items():
            serie[proveedor].append((fecha, p.puntuacion))
    return dict(serie)
