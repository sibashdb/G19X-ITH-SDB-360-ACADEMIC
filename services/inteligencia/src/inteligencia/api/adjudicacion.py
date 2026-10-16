"""Recomendación de adjudicación: ordena los acuerdos tentativos de un evento y explica el orden."""

import statistics
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter

from inteligencia import consultas
from inteligencia.api import esquemas
from inteligencia.api.ajustes import pesos_invalidos
from inteligencia.api.dependencias import Ctx, Sesion
from inteligencia.contexto import Contexto
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
from inteligencia.dominio.monedas import CENTAVOS, a_mxn, periodo_cambio, tipo_cambio_en
from inteligencia.dominio.puntuacion import validar_pesos

router = APIRouter(tags=["adjudicacion"])

DESEMPENO_SIN_DATOS = 50.0  # si nadie tiene puntuación, la mitad de la escala
MESES_ANIO = 12


def _gasto_anual(contexto: Contexto, usd_mxn: Decimal | None) -> dict[str, Decimal]:
    """Gasto anual vigente en MXN por proveedor: el «gasto anual contratado» del Tablero."""
    gasto: dict[str, Decimal] = defaultdict(Decimal)
    for contrato in contexto.contratos:
        if contrato.vigente(contexto.hoy):
            gasto[contrato.proveedor_id] += (
                a_mxn(contrato.valor_mensual(), contrato.moneda, usd_mxn) * MESES_ANIO
            )
    return gasto


def _desempeno(contexto: Contexto, pid: str) -> float:
    """La puntuación del proveedor; sin ella, la media de su categoría principal, la de todos si
    esa categoría no tiene ninguna y 50 si nadie tiene."""
    puntuacion = contexto.puntuaciones.get(pid)
    if puntuacion is not None:
        return puntuacion.puntuacion
    proveedor = contexto.proveedores.get(pid)
    categoria = proveedor.categorias[0] if proveedor is not None and proveedor.categorias else None
    puntuadas = [
        (contexto.proveedores[otro].categorias[0], p.puntuacion)
        for otro, p in contexto.puntuaciones.items()
    ]
    valores = [v for c, v in puntuadas if c == categoria] or [v for _, v in puntuadas]
    return statistics.mean(valores) if valores else DESEMPENO_SIN_DATOS


def _entrada(
    datos: esquemas.CandidatoEntrada,
    moneda: str,
    contexto: Contexto,
    usd_mxn: Decimal | None,
    gasto: dict[str, Decimal],
    gasto_total: Decimal,
) -> Entrada:
    pid = str(datos.proveedor_id)
    candidato = Candidato(
        datos.id,
        pid,
        datos.nombre,
        datos.plazo_meses,
        datos.cuota_implementacion,
        datos.sla,
        tuple(
            LineaCandidato(linea.codigo_servicio, linea.unidad, linea.cantidad, linea.precio)
            for linea in datos.lineas
        ),
    )
    costo = costo_total(candidato)
    anual_mxn = a_mxn(
        (costo - candidato.cuota) / candidato.plazo_meses * MESES_ANIO, moneda, usd_mxn
    )
    puntuacion = contexto.puntuaciones.get(pid)
    meses = sorted(contexto.desempeno.get(pid, []), key=lambda mes: mes.periodo)
    return Entrada(
        candidato,
        costo,
        a_mxn(costo, moneda, usd_mxn),
        _desempeno(contexto, pid),
        riesgo(
            concentracion(gasto.get(pid, Decimal(0)), gasto_total, anual_mxn),
            tendencia_incidentes([mes.incidentes for mes in meses]),
            0 if puntuacion is None else puntuacion.meses,
        ),
    )


@router.post("/adjudicacion/recomendacion")
async def recomendacion(
    datos: esquemas.RecomendacionEntrada, sesion: Sesion, contexto: Ctx
) -> esquemas.RecomendacionSalida:
    config = await consultas.configuracion(sesion)
    if datos.pesos is None:
        pesos = PesosAdjudicacion(
            config.adjudicacion_costo,
            config.adjudicacion_desempeno,
            config.adjudicacion_riesgo,
            config.adjudicacion_sla,
        )
    else:
        error = validar_pesos(datos.pesos.model_dump())
        if error is not None:
            raise pesos_invalidos("body.pesos", error)
        pesos = PesosAdjudicacion(**datos.pesos.model_dump())
    usd_mxn = tipo_cambio_en(contexto.tipos_cambio, contexto.hoy)
    periodo = periodo_cambio(contexto.tipos_cambio, contexto.hoy)
    gasto = _gasto_anual(contexto, usd_mxn)
    gasto_total = sum(gasto.values(), Decimal(0))
    resultado = recomendar(
        [
            _entrada(c, datos.moneda, contexto, usd_mxn, gasto, gasto_total)
            for c in datos.candidatos
        ],
        pesos,
    )
    return esquemas.RecomendacionSalida(
        pesos=esquemas.PesosEntrada(**pesos.como_dict()),
        umbral_aprobacion=config.umbral_aprobacion,
        tipo_cambio=None
        if periodo is None or usd_mxn is None
        else esquemas.TipoCambioSalida(periodo=periodo, usd_mxn=usd_mxn),
        candidatos=[
            esquemas.CandidatoSalida(
                id=e.entrada.candidato.id,
                proveedor_id=e.entrada.candidato.proveedor_id,
                nombre=e.entrada.candidato.nombre,
                costo_total=e.entrada.costo_total.quantize(CENTAVOS),
                costo_total_mxn=e.entrada.costo_total_mxn.quantize(CENTAVOS),
                desempeno=e.entrada.desempeno,
                riesgo=esquemas.RiesgoSalida.model_validate(e.entrada.riesgo),
                sla=e.entrada.candidato.sla,
                normalizados=e.normalizados,
                aportes=e.aportes,
                puntaje=e.puntaje,
                lugar=e.lugar,
            )
            for e in resultado.evaluados
        ],
        recomendado=resultado.recomendado,
        margen=resultado.margen,
        explicacion=resultado.explicacion,
        sensibilidad=[
            esquemas.SensibilidadSalida.model_validate(s) for s in resultado.sensibilidad
        ],
    )
