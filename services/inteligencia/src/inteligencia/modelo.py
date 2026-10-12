"""Modelo de precio justo: tres regresores por cuantiles (P25, P50 y P75) sobre el logaritmo del
precio deflactado.

Antes de entrenar, cada precio se lleva a pesos de una fecha fija (ORIGEN) con la tasa de inflación
configurada; al predecir, se lleva de vuelta a la fecha de la consulta. Un árbol no extrapola una
tendencia a fechas que no vio, por eso el modelo no usa los meses transcurridos como variable.
"""

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import sklearn
from numpy.typing import NDArray
from sklearn.ensemble import HistGradientBoostingRegressor

from inteligencia.dominio.precios import (
    Banda,
    Observacion,
    Referencia,
    linea_base,
    meses_entre,
    sumar_meses,
)

CUANTILES = (0.25, 0.5, 0.75)
MESES_VALIDACION = 6
MIN_OBSERVACIONES_ENTRENAMIENTO = 50
ORIGEN = date(2000, 1, 1)
CATEGORICAS = ("servicio", "categoria", "moneda", "tamano", "tipo")
MASCARA_CATEGORICAS = [True] * len(CATEGORICAS) + [False, False]  # + log(cantidad) y plazo


class DatosInsuficientes(ValueError):
    """No hay suficientes contratos para entrenar y validar."""


@dataclass(frozen=True)
class Consulta:
    servicio: str
    categoria: str
    moneda: str
    cantidad: float
    plazo_meses: int
    fecha: date
    tamano: str | None = None
    tipo: str = "nuevo"


def consulta_de(o: Observacion) -> Consulta:
    return Consulta(
        o.servicio, o.categoria, o.moneda, o.cantidad, o.plazo_meses, o.fecha, o.tamano, o.tipo
    )


def _deflactor(fecha: date, tasa: float) -> float:
    return float((1 + tasa) ** (meses_entre(ORIGEN, fecha) / 12))


def _codigo(valor: str | None, conocidos: list[str]) -> float:
    """El índice del valor entre los conocidos; NaN si el modelo no lo vio (HGB lo admite)."""
    return float(conocidos.index(valor)) if valor in conocidos else math.nan


def _matriz(consultas: Sequence[Consulta], categorias: dict[str, list[str]]) -> NDArray[np.float64]:
    return np.array(
        [
            [_codigo(getattr(c, nombre), categorias[nombre]) for nombre in CATEGORICAS]
            + [math.log(c.cantidad), float(c.plazo_meses)]
            for c in consultas
        ],
        dtype=np.float64,
    )


@dataclass
class ModeloPrecios:
    version: int
    tasa_inflacion: float
    categorias: dict[str, list[str]]
    regresores: list[HistGradientBoostingRegressor]
    # scikit-learn no garantiza que un modelo guardado funcione con otra versión: sin valor por
    # omisión, un artefacto anterior a este campo no lo tiene y se descarta al cargarlo.
    version_sklearn: str

    def conoce(self, servicio: str) -> bool:
        return servicio in self.categorias["servicio"]

    def predecir(self, consultas: Sequence[Consulta]) -> list[Banda]:
        if not consultas:
            return []
        x = _matriz(consultas, self.categorias)
        logaritmos = np.sort(np.vstack([r.predict(x) for r in self.regresores]), axis=0)
        factores = np.array([_deflactor(c.fecha, self.tasa_inflacion) for c in consultas])
        precios = np.exp(logaritmos) * factores
        return [Banda(float(a), float(b), float(c)) for a, b, c in precios.T]


def _categorias(observaciones: Sequence[Observacion]) -> dict[str, list[str]]:
    return {
        nombre: sorted({str(v) for o in observaciones if (v := getattr(o, nombre)) is not None})
        for nombre in CATEGORICAS
    }


def ajustar_modelo(
    observaciones: Sequence[Observacion], tasa_inflacion: float, version: int
) -> ModeloPrecios:
    categorias = _categorias(observaciones)
    x = _matriz([consulta_de(o) for o in observaciones], categorias)
    y = np.array([math.log(o.precio / _deflactor(o.fecha, tasa_inflacion)) for o in observaciones])
    regresores = []
    for cuantil in CUANTILES:
        regresor = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=cuantil,
            categorical_features=MASCARA_CATEGORICAS,
            random_state=0,
        )
        regresor.fit(x, y)
        regresores.append(regresor)
    return ModeloPrecios(version, tasa_inflacion, categorias, regresores, sklearn.__version__)


@dataclass(frozen=True)
class Resultado:
    modelo: ModeloPrecios | None  # solo si se promovió; reentrenado con todos los datos
    observaciones: int
    datos_hasta: date
    mape: float
    mape_linea_base: float
    cobertura: float  # del modelo
    cobertura_linea_base: float
    pinball: float

    @property
    def promovido(self) -> bool:
        return self.modelo is not None


def _pinball(reales: NDArray[np.float64], bandas: Sequence[Banda]) -> float:
    """Pérdida pinball promedio de los tres cuantiles, sobre el logaritmo del precio."""
    perdidas = []
    for cuantil, predichos in zip(
        CUANTILES,
        ([b.p25 for b in bandas], [b.p50 for b in bandas], [b.p75 for b in bandas]),
        strict=True,
    ):
        diferencia = np.log(reales) - np.log(np.array(predichos))
        perdidas.append(np.mean(np.maximum(cuantil * diferencia, (cuantil - 1) * diferencia)))
    return float(np.mean(perdidas))


def entrenar(
    observaciones: Sequence[Observacion], tasa_inflacion: float, version: int
) -> Resultado:
    """Valida con los últimos 6 meses y promueve el modelo solo si su MAPE mejora la línea base."""
    if len(observaciones) < MIN_OBSERVACIONES_ENTRENAMIENTO:
        raise DatosInsuficientes(f"Solo hay {len(observaciones)} líneas de contrato.")
    datos_hasta = max(o.fecha for o in observaciones)
    corte = sumar_meses(datos_hasta, -MESES_VALIDACION)
    entrenamiento = [o for o in observaciones if o.fecha <= corte]
    prueba = [o for o in observaciones if o.fecha > corte]
    if len(entrenamiento) < MIN_OBSERVACIONES_ENTRENAMIENTO or not prueba:
        raise DatosInsuficientes(
            "Faltan contratos anteriores o posteriores al corte de validación."
        )
    por_categoria: dict[str, list[Observacion]] = defaultdict(list)
    for o in entrenamiento:
        por_categoria[o.categoria].append(o)
    pares: list[tuple[Observacion, Referencia]] = []
    for o in prueba:
        referencia = linea_base(
            por_categoria[o.categoria], o.servicio, o.categoria, o.cantidad, o.fecha, tasa_inflacion
        )
        if referencia is not None:
            pares.append((o, referencia))
    if not pares:
        raise DatosInsuficientes("Ningún contrato reciente tiene con qué compararse.")

    candidato = ajustar_modelo(entrenamiento, tasa_inflacion, version)
    bandas = candidato.predecir([consulta_de(o) for o, _ in pares])
    reales = np.array([o.precio for o, _ in pares], dtype=np.float64)
    del_modelo = np.array([b.p50 for b in bandas])
    de_la_base = np.array([r.banda.p50 for _, r in pares])
    mape = float(np.mean(np.abs(del_modelo - reales) / reales))
    mape_linea_base = float(np.mean(np.abs(de_la_base - reales) / reales))
    cobertura = float(
        np.mean([b.p25 <= o.precio <= b.p75 for (o, _), b in zip(pares, bandas, strict=True)])
    )
    cobertura_linea_base = float(
        np.mean([r.banda.p25 <= o.precio <= r.banda.p75 for o, r in pares])
    )
    modelo = (
        ajustar_modelo(observaciones, tasa_inflacion, version) if mape < mape_linea_base else None
    )
    return Resultado(
        modelo=modelo,
        observaciones=len(observaciones),
        datos_hasta=datos_hasta,
        mape=mape,
        mape_linea_base=mape_linea_base,
        cobertura=cobertura,
        cobertura_linea_base=cobertura_linea_base,
        pinball=_pinball(reales, bandas),
    )


def guardar_modelo(modelo: ModeloPrecios, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, ruta)


def cargar_modelo(ruta: Path) -> ModeloPrecios:
    modelo = joblib.load(ruta)
    if not isinstance(modelo, ModeloPrecios):
        raise TypeError(f"{ruta} no contiene un modelo de precios")
    return modelo
