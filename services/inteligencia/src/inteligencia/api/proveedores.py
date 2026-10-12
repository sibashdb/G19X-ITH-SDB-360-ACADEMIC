"""Proveedores con su puntuación, su precio frente al mercado y el ranking."""

import statistics
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from comun.errores import ErrorDominio
from fastapi import APIRouter, Query

from inteligencia.api import esquemas
from inteligencia.api.dependencias import Ctx
from inteligencia.api.esquemas import unitario
from inteligencia.contexto import Contexto, LineaMercado
from inteligencia.dominio.monedas import CENTAVOS, a_mxn, tipo_cambio_en
from inteligencia.dominio.puntuacion import KPIS
from inteligencia.modelos import Proveedor

router = APIRouter(tags=["proveedores"])

Orden = Literal["nombre", "puntuacion", "gasto_anual", "contratos_vigentes", "alertas"]


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para que "codigo" encuentre "Código"."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


def _proveedor(contexto: Contexto, proveedor_id: UUID) -> Proveedor:
    proveedor = contexto.proveedores.get(str(proveedor_id))
    if proveedor is None:
        raise ErrorDominio(
            404, "No encontrado", "El proveedor no existe.", {"codigo": "proveedor_no_encontrado"}
        )
    return proveedor


def _redondear(valor: float | None) -> float | None:
    return None if valor is None else round(valor, 1)


def _resumenes(contexto: Contexto) -> list[esquemas.ProveedorResumen]:
    ultimo = tipo_cambio_en(contexto.tipos_cambio, contexto.hoy)
    gasto: dict[str, Decimal] = defaultdict(Decimal)
    vigentes: Counter[str] = Counter()
    for contrato in contexto.contratos:
        if contrato.vigente(contexto.hoy):
            mensual = a_mxn(contrato.valor_mensual(), contrato.moneda, ultimo)
            gasto[contrato.proveedor_id] += mensual * 12
            vigentes[contrato.proveedor_id] += 1
    alertas = Counter(a.proveedor_id for a in contexto.alertas)
    en_riesgo = {a.proveedor_id for a in contexto.alertas if a.tipo == "riesgo"}
    resumenes = []
    for pid, proveedor in contexto.proveedores.items():
        actual = contexto.puntuaciones.get(pid)
        resumenes.append(
            esquemas.ProveedorResumen(
                id=pid,
                rfc=proveedor.rfc,
                nombre=proveedor.nombre,
                tamano=proveedor.tamano,
                categorias=list(proveedor.categorias),
                activo=proveedor.activo,
                puntuacion=None if actual is None else round(actual.puntuacion, 1),
                confianza=None
                if actual is None
                else ("baja" if actual.historial_corto else "normal"),
                tendencia=_redondear(contexto.tendencia(pid)),
                gasto_anual=gasto[pid].quantize(CENTAVOS),
                contratos_vigentes=vigentes[pid],
                alertas=alertas[pid],
                en_riesgo=pid in en_riesgo,
            )
        )
    return resumenes


@router.get("/proveedores")
async def listar(
    contexto: Ctx,
    busqueda: Annotated[str | None, Query(max_length=100)] = None,
    categoria: esquemas.Categoria | None = None,
    estado: Literal["activos", "inactivos"] | None = None,
    en_riesgo: bool | None = None,
    orden: Orden = "nombre",
    direccion: Literal["asc", "desc"] = "asc",
    pagina: Annotated[int, Query(ge=1, le=1000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
) -> esquemas.PaginaProveedores:
    texto = _normalizar((busqueda or "").strip())
    filas = [
        r
        for r in _resumenes(contexto)
        if (not texto or texto in _normalizar(f"{r.nombre} {r.rfc}"))
        and (categoria is None or categoria in r.categorias)
        and (estado is None or r.activo == (estado == "activos"))
        and (en_riesgo is None or r.en_riesgo == en_riesgo)
    ]
    filas.sort(key=lambda r: (_normalizar(r.nombre), r.id))
    if orden == "nombre":
        if direccion == "desc":
            filas.reverse()
    else:
        # Un proveedor sin puntuación (sin desempeño) va al final en las dos direcciones.
        con_valor = [r for r in filas if getattr(r, orden) is not None]
        con_valor.sort(key=lambda r: getattr(r, orden), reverse=direccion == "desc")
        filas = con_valor + [r for r in filas if getattr(r, orden) is None]
    return esquemas.PaginaProveedores(
        total=len(filas), elementos=filas[(pagina - 1) * tamano : pagina * tamano]
    )


@router.get("/proveedores/{proveedor_id}/puntuacion")
async def puntuacion(proveedor_id: UUID, contexto: Ctx) -> esquemas.PuntuacionSalida:
    proveedor = _proveedor(contexto, proveedor_id)
    pid = str(proveedor_id)
    categoria = proveedor.categorias[0] if proveedor.categorias else None
    actual = contexto.puntuaciones.get(pid)
    if actual is None:
        return esquemas.PuntuacionSalida(
            proveedor_id=pid,
            categoria=categoria,
            puntuacion=None,
            sin_ajuste=None,
            meses=0,
            historial_corto=True,
            tendencia=None,
            componentes=[],
            historial=[],
        )
    # Todo proveedor puntuado tiene categoría (contexto.construir lo garantiza).
    de_su_categoria = [
        p
        for otro, p in contexto.puntuaciones.items()
        if contexto.proveedores[otro].categorias[0] == categoria
    ]
    return esquemas.PuntuacionSalida(
        proveedor_id=pid,
        categoria=categoria,
        puntuacion=round(actual.puntuacion, 1),
        sin_ajuste=round(actual.sin_ajuste, 1),
        meses=actual.meses,
        historial_corto=actual.historial_corto,
        tendencia=_redondear(contexto.tendencia(pid)),
        componentes=[
            esquemas.Componente(
                kpi=kpi,
                valor=round(actual.valores[kpi], 2),
                mediana_categoria=round(
                    statistics.median(p.valores[kpi] for p in de_su_categoria), 2
                ),
                percentil=round(actual.componentes[kpi], 1),
            )
            for kpi in KPIS
        ],
        historial=[
            esquemas.PuntoPuntuacion(mes=mes, puntuacion=round(valor, 1))
            for mes, valor in contexto.historial.get(pid, [])
        ],
    )


def _linea(m: LineaMercado) -> esquemas.MercadoLinea:
    ref = m.referencia
    return esquemas.MercadoLinea(
        contrato_id=m.contrato.id,
        folio=m.contrato.folio,
        codigo_servicio=m.linea.codigo,
        servicio=m.linea.servicio,
        moneda=m.contrato.moneda,
        precio=m.linea.precio,
        posicion=m.posicion,
        p25=None if ref is None else unitario(ref.banda.p25),
        p50=None if ref is None else unitario(ref.banda.p50),
        p75=None if ref is None else unitario(ref.banda.p75),
        metodo=None if ref is None else ref.metodo,
        confianza=None if ref is None else ref.confianza,
        ahorro_potencial=m.ahorro,
    )


@router.get("/proveedores/{proveedor_id}/mercado")
async def mercado(proveedor_id: UUID, contexto: Ctx) -> list[esquemas.MercadoLinea]:
    """Cada línea de sus contratos vigentes frente al precio justo de su servicio."""
    _proveedor(contexto, proveedor_id)
    pid = str(proveedor_id)
    propias = [m for m in contexto.mercado if m.contrato.proveedor_id == pid]
    return [_linea(m) for m in sorted(propias, key=lambda m: (m.contrato.folio, m.linea.codigo))]


@router.get("/ranking")
async def ranking(
    contexto: Ctx, categoria: esquemas.Categoria | None = None
) -> list[esquemas.FilaRanking]:
    candidatos = [
        (pid, p)
        for pid, p in contexto.puntuaciones.items()
        if contexto.proveedores[pid].activo
        and (categoria is None or categoria in contexto.proveedores[pid].categorias)
    ]
    candidatos.sort(
        key=lambda par: (-par[1].puntuacion, _normalizar(contexto.proveedores[par[0]].nombre))
    )
    return [
        esquemas.FilaRanking(
            posicion=posicion,
            proveedor_id=pid,
            nombre=contexto.proveedores[pid].nombre,
            categoria=contexto.proveedores[pid].categorias[0],
            puntuacion=round(p.puntuacion, 1),
            componentes={kpi: round(p.componentes[kpi], 1) for kpi in KPIS},
            meses=p.meses,
            historial_corto=p.historial_corto,
            tendencia=_redondear(contexto.tendencia(pid)),
        )
        for posicion, (pid, p) in enumerate(candidatos, start=1)
    ]
