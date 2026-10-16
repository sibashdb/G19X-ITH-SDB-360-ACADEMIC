"""Configuración de la puntuación, modelo de precios y estado de la copia local."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from comun.errores import ErrorDominio
from comun.outbox import registrar_evento
from fastapi import APIRouter, Request
from sqlalchemy import func, select

from inteligencia import consultas
from inteligencia.api import esquemas
from inteligencia.api.dependencias import Admin, Ctx, Interno, Sesion
from inteligencia.contexto import Contexto
from inteligencia.db import Base
from inteligencia.dominio.puntuacion import validar_pesos
from inteligencia.entrenamiento import Entrenador
from inteligencia.modelos import (
    Configuracion,
    Contrato,
    Desempeno,
    EventoProcesado,
    LineaContrato,
    ModeloBenchmark,
    Outbox,
    Proveedor,
    Servicio,
    TipoCambio,
)

router = APIRouter(tags=["configuracion"])

MAX_MODELOS = 50
DOS_DECIMALES = Decimal("0.01")
PESOS_ADJUDICACION = (
    "adjudicacion_costo",
    "adjudicacion_desempeno",
    "adjudicacion_riesgo",
    "adjudicacion_sla",
)
ENTIDADES: dict[str, type[Base]] = {
    "proveedores": Proveedor,
    "servicios": Servicio,
    "contratos": Contrato,
    "lineas_contrato": LineaContrato,
    "desempeno": Desempeno,
    "tipo_cambio": TipoCambio,
}


def pesos_invalidos(campo: str, mensaje: str) -> ErrorDominio:
    return ErrorDominio(
        422,
        "Solicitud inválida",
        "Revise los campos indicados.",
        {"codigo": "pesos_invalidos", "errores": [{"campo": campo, "mensaje": mensaje}]},
    )


def _para_evento(valor: Any) -> Any:
    return f"{valor:.2f}" if isinstance(valor, Decimal) else valor


def _en_uso(contexto: Contexto) -> int | None:
    """La versión que de verdad responde: la promovida puede no cargar (archivo perdido o de otra
    versión de scikit-learn) y entonces se usa la línea base."""
    return None if contexto.modelo is None else contexto.modelo.version


@router.get("/configuracion")
async def leer_configuracion(sesion: Sesion, _: Interno) -> esquemas.ConfiguracionSalida:
    return esquemas.ConfiguracionSalida.model_validate(await consultas.configuracion(sesion))


@router.put("/configuracion")
async def guardar_configuracion(
    datos: esquemas.ConfiguracionEntrada, sesion: Sesion, usuario: Admin
) -> esquemas.ConfiguracionSalida:
    nuevos = datos.model_dump(exclude_none=True)  # None = sin cambio
    nuevos["inflacion_anual"] = nuevos["inflacion_anual"].quantize(DOS_DECIMALES)
    if "umbral_aprobacion" in nuevos:
        nuevos["umbral_aprobacion"] = nuevos["umbral_aprobacion"].quantize(DOS_DECIMALES)
    error = validar_pesos({c: v for c, v in nuevos.items() if c.startswith("peso_")})
    if error is not None:
        raise pesos_invalidos("body.pesos", error)
    if any(c in nuevos for c in PESOS_ADJUDICACION):
        if not all(c in nuevos for c in PESOS_ADJUDICACION):
            raise pesos_invalidos("body.pesos_adjudicacion", "Envíe los cuatro pesos juntos.")
        error = validar_pesos({c: nuevos[c] for c in PESOS_ADJUDICACION})
        if error is not None:
            raise pesos_invalidos("body.pesos_adjudicacion", error)
    async with sesion.begin():
        fila = await sesion.get(Configuracion, 1, with_for_update=True)
        if fila is None:
            raise LookupError("Falta la fila de configuración (la crea la migración 0001)")
        cambios = [
            {
                "campo": campo,
                "anterior": _para_evento(getattr(fila, campo)),
                "nuevo": _para_evento(valor),
            }
            for campo, valor in nuevos.items()
            if getattr(fila, campo) != valor
        ]
        if cambios:
            for campo, valor in nuevos.items():
                setattr(fila, campo, valor)
            fila.actualizado_en = datetime.now(UTC)
            fila.actualizado_por = usuario.nombre
            registrar_evento(
                sesion,
                Outbox,
                "configuracion.actualizada",
                {"cambios": cambios, "actor": {"id": usuario.id, "nombre": usuario.nombre}},
            )
    return esquemas.ConfiguracionSalida.model_validate(fila)


@router.get("/modelos")
async def modelos(
    request: Request, _: Interno, sesion: Sesion, contexto: Ctx
) -> esquemas.RegistroModelos:
    registros = await sesion.scalars(
        select(ModeloBenchmark).order_by(ModeloBenchmark.version.desc()).limit(MAX_MODELOS)
    )
    activo = await consultas.modelo_activo(sesion)
    entrenador: Entrenador = request.app.state.entrenador
    return esquemas.RegistroModelos(
        entrenando=entrenador.entrenando,
        activo=None if activo is None else activo.version,
        en_uso=_en_uso(contexto),
        ultimo_error=entrenador.ultimo_error,
        elementos=[esquemas.ModeloSalida.model_validate(r) for r in registros],
    )


@router.post("/modelos/entrenar", status_code=202)
async def entrenar(request: Request, usuario: Admin) -> esquemas.EntrenamientoIniciado:
    entrenador: Entrenador = request.app.state.entrenador
    if not entrenador.iniciar("manual", {"id": usuario.id, "nombre": usuario.nombre}):
        raise ErrorDominio(
            409,
            "Conflicto",
            "Ya hay un entrenamiento del modelo de precios en curso; espere a que termine.",
            {"codigo": "entrenamiento_en_curso"},
        )
    return esquemas.EntrenamientoIniciado(entrenando=True)


@router.get("/datos")
async def datos(request: Request, _: Admin, sesion: Sesion, contexto: Ctx) -> esquemas.DatosSalida:
    """Lo que llegó a la copia local, para la tarjeta "Datos y modelo" del Panel."""
    fila = (
        await sesion.execute(
            select(
                *(
                    select(func.count()).select_from(modelo).scalar_subquery()
                    for modelo in ENTIDADES.values()
                ),
                select(func.max(EventoProcesado.procesado_en)).scalar_subquery(),
            )
        )
    ).one()
    activo = await consultas.modelo_activo(sesion)
    entrenador: Entrenador = request.app.state.entrenador
    return esquemas.DatosSalida(
        registros=dict(zip(ENTIDADES, fila[:-1], strict=True)),
        ultimo_evento=fila[-1],
        modelo=None if activo is None else esquemas.ModeloSalida.model_validate(activo),
        en_uso=_en_uso(contexto),
        entrenando=entrenador.entrenando,
    )
