"""Tablero y alertas: lo que cada persona ve al iniciar sesión."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from inteligencia.api import esquemas
from inteligencia.api.dependencias import Ctx
from inteligencia.dominio.tablero import Destacado

router = APIRouter(tags=["tablero"])


def _destacado(destacado: Destacado) -> esquemas.Destacado:
    return esquemas.Destacado(
        proveedor_id=destacado.proveedor_id,
        nombre=destacado.nombre,
        puntuacion=round(destacado.puntuacion, 1),
    )


@router.get("/tablero")
async def tablero(contexto: Ctx) -> esquemas.TableroSalida:
    t = contexto.tablero
    return esquemas.TableroSalida(
        fecha=contexto.hoy,
        gasto_anual=t.gasto_anual,
        variacion_pct=None if t.variacion_pct is None else round(t.variacion_pct, 1),
        por_vencer=t.por_vencer,
        en_riesgo=t.en_riesgo,
        total_proveedores=t.total_proveedores,
        ahorro_potencial=t.ahorro_potencial,
        gasto_por_categoria=[
            esquemas.MontoCategoria(categoria=categoria, monto=monto)
            for categoria, monto in t.gasto_por_categoria.items()
        ],
        gasto_por_mes=[esquemas.MontoMes(mes=mes, monto=monto) for mes, monto in t.gasto_por_mes],
        proximos_vencimientos=[
            esquemas.VencimientoSalida(
                contrato_id=v.contrato.id,
                folio=v.contrato.folio,
                proveedor_id=v.contrato.proveedor_id,
                proveedor=v.contrato.proveedor,
                servicios=[linea.servicio for linea in v.contrato.lineas],
                fecha_fin=v.contrato.fecha_fin,
                dias=v.dias,
                monto_mensual=v.monto_mensual,
            )
            for v in t.proximos_vencimientos
        ],
        alertas_principales=[
            esquemas.AlertaSalida.model_validate(a) for a in t.alertas_principales
        ],
        mejores=[_destacado(d) for d in t.mejores],
        peores=[_destacado(d) for d in t.peores],
        distribucion=[
            esquemas.RangoPuntuacion(rango=rango, proveedores=cuantos)
            for rango, cuantos in t.distribucion
        ],
    )


@router.get("/alertas")
async def alertas(
    contexto: Ctx,
    tipo: Literal["vencimiento", "sobreprecio", "riesgo"] | None = None,
    severidad: Literal["alta", "media", "informativa"] | None = None,
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> esquemas.PaginaAlertas:
    filtradas = [
        a
        for a in contexto.alertas
        if (tipo is None or a.tipo == tipo) and (severidad is None or a.severidad == severidad)
    ]
    visibles = filtradas[(pagina - 1) * limite : pagina * limite]
    return esquemas.PaginaAlertas(
        total=len(filtradas),
        elementos=[esquemas.AlertaSalida.model_validate(a) for a in visibles],
    )
