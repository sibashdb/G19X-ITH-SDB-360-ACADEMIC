"""Recomendación de adjudicación: puntaje de los acuerdos tentativos y su explicación.

Suma ponderada de cuatro criterios (costo total, desempeño, riesgo y SLA), normalizados entre los
candidatos con min-max. Funciones puras: reciben los datos ya cargados y no hacen E/S.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Literal

from inteligencia.dominio.precios import UNIDADES_MENSUALES
from inteligencia.dominio.puntuacion import MESES_HISTORIAL_CORTO

CRITERIOS = ("costo", "desempeno", "riesgo", "sla")
MESES_TENDENCIA = 3  # la tendencia compara los últimos 3 meses con los 3 anteriores

# Textos de la explicación (en «usted», sin jerga). Los criterios van con su artículo.
NOMBRE_CRITERIO = {"costo": "costo", "desempeno": "desempeño", "riesgo": "riesgo", "sla": "SLA"}
TEXTO_UNICO = "Es el único acuerdo tentativo."
TEXTO_RESUMEN = (
    "Recomendamos a {ganador}: obtiene {puntaje} de 100 contra {puntaje_segundo} de {segundo}, "
    "un margen de {margen} puntos."
)
TEXTO_APORTE = "{dato}; aporta {aporte} de {peso} puntos."
TEXTO_COSTO = "Costo total: {costo} MXN"
TEXTO_DESEMPENO = "Desempeño: puntuación de {puntuacion} de 100"
TEXTO_RIESGO = (
    "Riesgo {nivel}: concentración de {concentracion} %, tendencia de incidentes de "
    "{tendencia} % y {historial}"
)
TEXTO_HISTORIAL = {True: "sin historial suficiente", False: "con historial suficiente"}
TEXTO_SLA = "SLA: {sla} % de disponibilidad"
TEXTO_SIN_SLA = "SLA: no se acordó una disponibilidad"
TEXTO_CAMBIA = "Si el peso del {criterio} pasara de {actual} a {necesario}, ganaría {ganaria}."
TEXTO_NO_CAMBIA = "Ningún peso del {criterio} cambia al ganador."


@dataclass(frozen=True)
class LineaCandidato:
    codigo: str
    unidad: str
    cantidad: Decimal
    precio: Decimal


@dataclass(frozen=True)
class Candidato:
    id: str  # el de la sesión
    proveedor_id: str
    nombre: str
    plazo_meses: int
    cuota: Decimal
    sla: Decimal | None
    lineas: tuple[LineaCandidato, ...]


@dataclass(frozen=True)
class PesosAdjudicacion:
    costo: int = 40
    desempeno: int = 30
    riesgo: int = 15
    sla: int = 15

    def como_dict(self) -> dict[str, int]:
        return {campo.name: getattr(self, campo.name) for campo in fields(self)}


@dataclass(frozen=True)
class Riesgo:
    valor: float  # promedio de los tres componentes, de 0 a 1
    concentracion: float
    tendencia: float
    sin_historial: bool

    @property
    def nivel(self) -> Literal["bajo", "medio", "alto"]:
        return "bajo" if self.valor < 1 / 3 else "medio" if self.valor < 2 / 3 else "alto"


@dataclass(frozen=True)
class Entrada:
    candidato: Candidato
    costo_total: Decimal  # en la moneda del evento
    costo_total_mxn: Decimal
    desempeno: float  # puntuación de 0 a 100
    riesgo: Riesgo


@dataclass(frozen=True)
class Evaluado:
    entrada: Entrada
    normalizados: dict[str, float]  # por criterio, de 0 a 1 (1 es lo mejor)
    aportes: dict[str, float]  # peso por normalizado: los puntos que suma cada criterio
    puntaje: float
    lugar: int


@dataclass(frozen=True)
class Sensibilidad:
    criterio: str
    peso_actual: int
    peso_necesario: int | None  # el más cercano al actual con el que gana otro; None si ninguno
    ganaria: str | None  # id del candidato que ganaría


@dataclass(frozen=True)
class Recomendacion:
    pesos: PesosAdjudicacion
    evaluados: list[Evaluado]  # ordenados por lugar
    recomendado: str  # id del candidato
    margen: float  # puntos entre el primero y el segundo; 0 si hay uno solo
    explicacion: list[str]
    sensibilidad: list[Sensibilidad]


def costo_total(
    candidato: Candidato, unidades_mensuales: frozenset[str] = UNIDADES_MENSUALES
) -> Decimal:
    """Suma de precio por cantidad (por plazo, en las unidades mensuales) más la cuota."""
    total = candidato.cuota
    for linea in candidato.lineas:
        meses = candidato.plazo_meses if linea.unidad in unidades_mensuales else 1
        total += linea.precio * linea.cantidad * meses
    return total


def tendencia_incidentes(incidentes: Sequence[float]) -> float:
    """Aumento relativo de los últimos 3 meses frente a los 3 anteriores, de 0 a 1.

    Recibe los meses en orden cronológico y usa los últimos 6.
    """
    ultimos = incidentes[-2 * MESES_TENDENCIA :]
    recientes = sum(ultimos[-MESES_TENDENCIA:])
    anteriores = sum(ultimos[:-MESES_TENDENCIA])
    return min(1.0, max(0.0, (recientes - anteriores) / max(anteriores, 1)))


def concentracion(
    gasto_proveedor_mxn: Decimal, gasto_total_mxn: Decimal, costo_anual_mxn: Decimal
) -> float:
    """Fracción del gasto anual que tendría el proveedor si se le adjudica."""
    total = gasto_total_mxn + costo_anual_mxn
    return float((gasto_proveedor_mxn + costo_anual_mxn) / total) if total else 0.0


def riesgo(concentracion: float, tendencia: float, meses_historial: int) -> Riesgo:
    sin_historial = meses_historial < MESES_HISTORIAL_CORTO
    valor = (concentracion + tendencia + sin_historial) / 3
    return Riesgo(valor, concentracion, tendencia, sin_historial)


def normalizar(valores: Sequence[float | None], mayor_es_mejor: bool) -> list[float]:
    """Min-max entre los candidatos; 1 es lo mejor. Un valor ausente (None) vale 0.

    Si todos los valores presentes son iguales, valen 1 y el criterio no decide nada; si ninguno
    está presente, el criterio vale 1 para todos.
    """
    presentes = [v for v in valores if v is not None]
    if not presentes:
        return [1.0] * len(valores)
    menor, mayor = min(presentes), max(presentes)
    ancho = mayor - menor
    return [
        0.0
        if v is None
        else 1.0
        if ancho == 0
        else ((v - menor) if mayor_es_mejor else (mayor - v)) / ancho
        for v in valores
    ]


def reescalar(pesos: Mapping[str, float], criterio: str, nuevo: float) -> dict[str, float]:
    """Pone `criterio` en `nuevo` y reescala los demás en proporción para seguir sumando 100.

    Si los demás valen 0, se reparten por igual.
    """
    otros = [c for c in pesos if c != criterio]
    resto = sum(pesos[c] for c in otros)
    sobrante = 100 - nuevo
    reescalados = {
        c: pesos[c] * sobrante / resto if resto else sobrante / len(otros) for c in otros
    }
    return {**reescalados, criterio: nuevo}


def puntajes(
    normalizados: Sequence[Mapping[str, float]], pesos: Mapping[str, float]
) -> list[float]:
    """Suma de peso por normalizado de cada candidato; con pesos que suman 100 va de 0 a 100."""
    # round: la suma en punto flotante deja ruido que rompería los empates exactos.
    return [round(sum(pesos[c] * n[c] for c in CRITERIOS), 9) for n in normalizados]


def _normalizados(entradas: Sequence[Entrada]) -> list[dict[str, float]]:
    columnas = {
        "costo": normalizar([float(e.costo_total_mxn) for e in entradas], mayor_es_mejor=False),
        "desempeno": normalizar([e.desempeno for e in entradas], mayor_es_mejor=True),
        "riesgo": normalizar([e.riesgo.valor for e in entradas], mayor_es_mejor=False),
        "sla": normalizar(
            [None if e.candidato.sla is None else float(e.candidato.sla) for e in entradas],
            mayor_es_mejor=True,
        ),
    }
    return [{c: columnas[c][i] for c in CRITERIOS} for i in range(len(entradas))]


def _orden(
    entradas: Sequence[Entrada],
    normalizados: Sequence[Mapping[str, float]],
    pesos: Mapping[str, float],
) -> list[tuple[int, float]]:
    """(índice, puntaje) por lugar: mayor puntaje, luego menor costo, mayor desempeño y nombre."""
    resultado = list(enumerate(puntajes(normalizados, pesos)))

    def clave(par: tuple[int, float]) -> tuple[float, Decimal, float, str, str]:
        indice, puntaje = par
        e = entradas[indice]
        return (-puntaje, e.costo_total_mxn, -e.desempeno, e.candidato.nombre, e.candidato.id)

    return sorted(resultado, key=clave)


def _sensibilidad(
    entradas: Sequence[Entrada],
    normalizados: Sequence[Mapping[str, float]],
    pesos: PesosAdjudicacion,
    ganador: int,
) -> list[Sensibilidad]:
    """Por criterio, el peso más cercano al actual con el que otro candidato queda primero."""
    actuales = pesos.como_dict()
    resultado = []
    for criterio in CRITERIOS:
        actual = actuales[criterio]
        necesario = ganaria = None
        for peso in sorted(range(101), key=lambda p: (abs(p - actual), p)):
            if peso == actual:
                continue
            primero = _orden(entradas, normalizados, reescalar(actuales, criterio, peso))[0][0]
            if primero != ganador:
                necesario, ganaria = peso, entradas[primero].candidato.id
                break
        resultado.append(Sensibilidad(criterio, actual, necesario, ganaria))
    return resultado


def _explicar(
    evaluados: Sequence[Evaluado], pesos: Mapping[str, int], sensibilidad: Sequence[Sensibilidad]
) -> list[str]:
    primero = evaluados[0]
    e, r = primero.entrada, primero.entrada.riesgo
    if len(evaluados) == 1:
        textos = [TEXTO_UNICO]
    else:
        segundo = evaluados[1]
        textos = [
            TEXTO_RESUMEN.format(
                ganador=e.candidato.nombre,
                puntaje=f"{primero.puntaje:.1f}",
                puntaje_segundo=f"{segundo.puntaje:.1f}",
                segundo=segundo.entrada.candidato.nombre,
                margen=f"{primero.puntaje - segundo.puntaje:.1f}",
            )
        ]
    datos = {
        "costo": TEXTO_COSTO.format(costo=f"${e.costo_total_mxn:,.2f}"),
        "desempeno": TEXTO_DESEMPENO.format(puntuacion=f"{e.desempeno:.1f}"),
        "riesgo": TEXTO_RIESGO.format(
            nivel=r.nivel,
            concentracion=f"{r.concentracion * 100:.0f}",
            tendencia=f"{r.tendencia * 100:.0f}",
            historial=TEXTO_HISTORIAL[r.sin_historial],
        ),
        "sla": TEXTO_SIN_SLA
        if e.candidato.sla is None
        else TEXTO_SLA.format(sla=f"{e.candidato.sla:g}"),
    }
    textos += [
        TEXTO_APORTE.format(dato=datos[c], aporte=f"{primero.aportes[c]:.1f}", peso=pesos[c])
        for c in CRITERIOS
    ]
    if len(evaluados) > 1:
        nombres = {x.entrada.candidato.id: x.entrada.candidato.nombre for x in evaluados}
        for s in sensibilidad:
            criterio = NOMBRE_CRITERIO[s.criterio]
            if s.peso_necesario is None or s.ganaria is None:
                textos.append(TEXTO_NO_CAMBIA.format(criterio=criterio))
            else:
                textos.append(
                    TEXTO_CAMBIA.format(
                        criterio=criterio,
                        actual=s.peso_actual,
                        necesario=s.peso_necesario,
                        ganaria=nombres[s.ganaria],
                    )
                )
    return textos


def recomendar(entradas: Sequence[Entrada], pesos: PesosAdjudicacion) -> Recomendacion:
    if not entradas:
        raise ValueError("Se necesita al menos un candidato.")
    normalizados = _normalizados(entradas)
    actuales = pesos.como_dict()
    orden = _orden(entradas, normalizados, actuales)
    evaluados = [
        Evaluado(
            entradas[indice],
            normalizados[indice],
            {c: actuales[c] * normalizados[indice][c] for c in CRITERIOS},
            puntaje,
            lugar,
        )
        for lugar, (indice, puntaje) in enumerate(orden, 1)
    ]
    margen = round(evaluados[0].puntaje - evaluados[1].puntaje, 9) if len(evaluados) > 1 else 0.0
    sensibilidad = _sensibilidad(entradas, normalizados, pesos, orden[0][0])
    return Recomendacion(
        pesos,
        evaluados,
        evaluados[0].entrada.candidato.id,
        margen,
        _explicar(evaluados, actuales, sensibilidad),
        sensibilidad,
    )
