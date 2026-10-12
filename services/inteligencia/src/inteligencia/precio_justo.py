"""Precio justo: el modelo promovido si conoce el servicio; si no, la línea base.

Sin contratos del servicio en los últimos 24 meses no hay referencia, aunque haya modelo. Si el
modelo falla al predecir, también se usa la línea base: una predicción no debe tumbar las consultas.
"""

import logging
from collections.abc import Mapping, Sequence

from inteligencia.dominio.precios import Observacion, Referencia, linea_base
from inteligencia.modelo import Consulta, ModeloPrecios

log = logging.getLogger(__name__)


def referencias(
    consultas: Sequence[Consulta],
    por_categoria: Mapping[str, Sequence[Observacion]],
    modelo: ModeloPrecios | None,
    tasa_inflacion: float,
) -> list[Referencia | None]:
    bases = [
        linea_base(
            por_categoria.get(c.categoria, ()),
            c.servicio,
            c.categoria,
            c.cantidad,
            c.fecha,
            tasa_inflacion,
        )
        for c in consultas
    ]
    if modelo is None:
        return bases
    # Una sola predicción para todas las consultas que el modelo puede responder.
    indices = [
        i
        for i, (consulta, base) in enumerate(zip(consultas, bases, strict=True))
        if base is not None and modelo.conoce(consulta.servicio)
    ]
    try:
        bandas = modelo.predecir([consultas[i] for i in indices])
    except Exception:
        log.exception(
            "El modelo de precios v%s falló al predecir; se usa la línea base", modelo.version
        )
        return bases
    resultado = list(bases)
    for i, banda in zip(indices, bandas, strict=True):
        base = bases[i]
        if base is not None:
            resultado[i] = Referencia(
                banda, base.confianza, base.observaciones, "modelo", modelo.version
            )
    return resultado
