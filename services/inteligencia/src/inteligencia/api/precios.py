"""Precio justo por servicio, su historia y los contratos que pagan de más."""

import statistics
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from comun.errores import ErrorDominio
from fastapi import APIRouter, Query

from inteligencia.api import esquemas
from inteligencia.api.dependencias import CodigoServicio, Ctx
from inteligencia.api.esquemas import unitario
from inteligencia.contexto import Contexto
from inteligencia.dominio.precios import VENTANA_MESES, linea_base, sumar_meses
from inteligencia.dominio.tablero import CENTAVOS, a_mxn, tipo_cambio_en
from inteligencia.modelo import Consulta
from inteligencia.modelos import Servicio
from inteligencia.precio_justo import referencias

router = APIRouter(prefix="/precios", tags=["precios"])

Cantidad = Annotated[Decimal, Query(gt=0, le=10_000_000)]


def _servicio(contexto: Contexto, codigo: str) -> Servicio:
    servicio = contexto.servicios.get(codigo.upper())
    if servicio is None:
        raise ErrorDominio(
            404, "No encontrado", "El servicio no existe.", {"codigo": "servicio_no_encontrado"}
        )
    return servicio


@router.get("/servicios")
async def servicios(contexto: Ctx) -> list[esquemas.ServicioPrecios]:
    """Los servicios activos; un servicio inactivo no se cotiza, aunque sus contratos sigan."""
    desde = sumar_meses(contexto.hoy, -VENTANA_MESES)
    recientes = Counter(
        o.servicio
        for observaciones in contexto.por_categoria.values()
        for o in observaciones
        if desde < o.fecha <= contexto.hoy
    )
    return [
        esquemas.ServicioPrecios(
            codigo=s.codigo,
            nombre=s.nombre,
            categoria=s.categoria,
            unidad=s.unidad,
            moneda=s.moneda,
            observaciones=recientes[s.codigo],
        )
        for s in sorted(contexto.servicios.values(), key=lambda s: (s.nombre, s.codigo))
        if s.activo
    ]


@router.get("/servicios/{codigo}/referencia")
async def referencia(
    codigo: CodigoServicio,
    contexto: Ctx,
    cantidad: Cantidad,
    plazo: Annotated[int, Query(ge=1, le=120)] = 12,
) -> esquemas.ReferenciaSalida:
    servicio = _servicio(contexto, codigo)
    consulta = Consulta(
        servicio.codigo,
        servicio.categoria,
        servicio.moneda,
        float(cantidad),
        plazo,
        contexto.hoy,
    )
    [resultado] = referencias(
        [consulta], contexto.por_categoria, contexto.modelo, contexto.tasa_inflacion
    )
    if resultado is None:
        raise ErrorDominio(
            404,
            "No encontrado",
            "No hay contratos de este servicio en los últimos 24 meses: no se puede calcular su "
            "precio justo.",
            {"codigo": "sin_observaciones"},
        )
    return esquemas.ReferenciaSalida(
        codigo=servicio.codigo,
        moneda=servicio.moneda,
        unidad=servicio.unidad,
        cantidad=cantidad,
        plazo=plazo,
        fecha=contexto.hoy,
        p25=unitario(resultado.banda.p25),
        p50=unitario(resultado.banda.p50),
        p75=unitario(resultado.banda.p75),
        metodo=resultado.metodo,
        version=resultado.version,
        confianza=resultado.confianza,
        observaciones=resultado.observaciones,
    )


@router.get("/servicios/{codigo}/historial")
async def historial(
    codigo: CodigoServicio,
    contexto: Ctx,
    cantidad: Annotated[Decimal | None, Query(gt=0, le=10_000_000)] = None,
) -> esquemas.HistorialPrecios:
    servicio = _servicio(contexto, codigo)
    hoy = contexto.hoy
    desde = sumar_meses(hoy, -VENTANA_MESES)
    puntos = sorted(
        (
            (c, linea)
            for c in contexto.contratos
            for linea in c.lineas
            if linea.codigo == servicio.codigo and desde < c.fecha_inicio <= hoy
        ),
        key=lambda par: (par[0].fecha_inicio, par[0].folio),
    )
    if cantidad is None:
        cantidad = (
            statistics.median(linea.cantidad for _, linea in puntos) if puntos else Decimal(1)
        )
    observaciones = contexto.por_categoria.get(servicio.categoria, [])
    bandas = []
    for atras in range(VENTANA_MESES - 1, -1, -1):
        mes = sumar_meses(hoy, -atras)
        cierre = min(sumar_meses(mes, 1) - timedelta(days=1), hoy)
        base = linea_base(
            observaciones,
            servicio.codigo,
            servicio.categoria,
            float(cantidad),
            cierre,
            contexto.tasa_inflacion,
        )
        if base is not None:
            bandas.append(
                esquemas.BandaMes(
                    mes=mes,
                    p25=unitario(base.banda.p25),
                    p50=unitario(base.banda.p50),
                    p75=unitario(base.banda.p75),
                )
            )
    return esquemas.HistorialPrecios(
        codigo=servicio.codigo,
        moneda=servicio.moneda,
        cantidad=cantidad,
        puntos=[
            esquemas.PuntoPrecio(
                fecha=c.fecha_inicio,
                precio=linea.precio,
                cantidad=linea.cantidad,
                folio=c.folio,
                proveedor=c.proveedor,
            )
            for c, linea in puntos
        ],
        bandas=bandas,
    )


@router.get("/sobreprecios")
async def sobreprecios(
    contexto: Ctx,
    codigo: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9-]{3,30}$")] = None,
) -> list[esquemas.Sobreprecio]:
    """Líneas de contratos vigentes sobre P75, de mayor a menor ahorro potencial en MXN."""
    ultimo = tipo_cambio_en(contexto.tipos_cambio, contexto.hoy)
    filas = [
        esquemas.Sobreprecio(
            contrato_id=m.contrato.id,
            folio=m.contrato.folio,
            proveedor_id=m.contrato.proveedor_id,
            proveedor=m.contrato.proveedor,
            codigo_servicio=m.linea.codigo,
            servicio=m.linea.servicio,
            moneda=m.contrato.moneda,
            precio=m.linea.precio,
            p25=unitario(m.referencia.banda.p25),
            p50=unitario(m.referencia.banda.p50),
            p75=unitario(m.referencia.banda.p75),
            fecha_fin=m.contrato.fecha_fin,
            ahorro_potencial=m.ahorro,
            ahorro_potencial_mxn=a_mxn(m.ahorro, m.contrato.moneda, ultimo).quantize(CENTAVOS),
        )
        for m in contexto.mercado
        if m.referencia is not None
        and m.posicion == "sobre_p75"
        and (codigo is None or m.linea.codigo == codigo.upper())
    ]
    return sorted(filas, key=lambda s: (-s.ahorro_potencial_mxn, s.folio, s.codigo_servicio))
