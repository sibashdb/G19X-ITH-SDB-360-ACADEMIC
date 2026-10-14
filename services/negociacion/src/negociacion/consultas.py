"""Lecturas que arman las respuestas de la API (y, desde la Task 9, los términos del motor)."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion.api import esquemas
from negociacion.dominio.configuracion import (
    Banda,
    LineaRevision,
    PalancaRevision,
    Revision,
    avisos,
    errores,
)
from negociacion.dominio.terminos import CLAVES
from negociacion.errores import invalido, no_existe
from negociacion.modelos import (
    Evento,
    Linea,
    Oferta,
    Palanca,
    Proveedor,
    Servicio,
    SesionNegociacion,
)
from negociacion.textos import nombre_y_unidad

PROVEEDOR_NO_DISPONIBLE = (
    "El proveedor no está disponible para invitar: no existe, está inactivo o no tiene correo "
    "de contacto."
)


def decimal_o_nada(valor: Any) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def banda_de(referencia: dict[str, Any] | None) -> Banda | None:
    if referencia is None:
        return None
    return Banda(
        Decimal(str(referencia["p25"])),
        Decimal(str(referencia["p50"])),
        Decimal(str(referencia["p75"])),
    )


async def evento_o_404(bd: AsyncSession, evento_id: uuid.UUID, bloquear: bool = False) -> Evento:
    # populate_existing: un UPDATE masivo (cerrar_eventos_terminados) no refresca los objetos
    # que la sesión ya tenía cargados.
    evento = await bd.get(Evento, evento_id, with_for_update=bloquear, populate_existing=True)
    if evento is None:
        raise no_existe("La negociación no existe.")
    return evento


async def lineas_de(bd: AsyncSession, evento_id: uuid.UUID) -> list[Linea]:
    consulta = select(Linea).where(Linea.evento_id == evento_id).order_by(Linea.orden)
    return list((await bd.scalars(consulta)).all())


async def palancas_de(bd: AsyncSession, evento_id: uuid.UUID) -> dict[str, Palanca]:
    filas = await bd.scalars(select(Palanca).where(Palanca.evento_id == evento_id))
    return {p.clave: p for p in sorted(filas, key=lambda p: CLAVES.index(p.clave))}


async def servicios_activos(bd: AsyncSession, codigos: Sequence[str]) -> dict[str, Servicio]:
    consulta = select(Servicio).where(Servicio.codigo.in_(codigos), Servicio.activo.is_(True))
    filas = {s.codigo: s for s in await bd.scalars(consulta)}
    for i, codigo in enumerate(codigos):
        if codigo not in filas:
            raise invalido(
                f"lineas.{i}.codigo_servicio",
                f"El servicio {codigo} no existe o está inactivo.",
                "servicio_no_disponible",
            )
    return filas


async def proveedores_invitables(
    bd: AsyncSession, ids: Sequence[uuid.UUID], campos: Sequence[str] | None = None
) -> list[Proveedor]:
    """Los proveedores en el orden dado; cada uno activo y con correo de contacto en la copia."""
    filas = {p.id: p for p in await bd.scalars(select(Proveedor).where(Proveedor.id.in_(ids)))}
    for i, proveedor_id in enumerate(ids):
        proveedor = filas.get(proveedor_id)
        if proveedor is None or not proveedor.activo or not proveedor.contacto_email:
            campo = campos[i] if campos is not None else f"proveedores.{i}"
            raise invalido(campo, PROVEEDOR_NO_DISPONIBLE, "proveedor_no_disponible")
    return [filas[i] for i in ids]


def revision_de(evento: Evento, lineas: list[Linea], palancas: dict[str, Palanca]) -> Revision:
    contrato = evento.foto.get("contrato") or {}
    return Revision(
        tipo=evento.tipo,
        fecha_limite=evento.fecha_limite,
        lineas=tuple(
            LineaRevision(
                linea.nombre,
                linea.ideal,
                linea.limite,
                linea.precio_vigente,
                None if (banda := banda_de(linea.referencia)) is None else banda.p75,
            )
            for linea in lineas
        ),
        palancas=tuple(
            PalancaRevision(p.clave, p.peso, p.ideal, p.limite) for p in palancas.values()
        ),
        invitados=len(evento.invitados),
        tope_pct=decimal_o_nada(contrato.get("tope_aumento_pct")),
    )


async def _utilidades(bd: AsyncSession, sesiones: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    """La utilidad de la última oferta del proveedor en cada sesión."""
    if not sesiones:
        return {}
    filas = await bd.execute(
        select(Oferta.sesion_id, Oferta.utilidad)
        .where(Oferta.sesion_id.in_(sesiones), Oferta.autor == "proveedor")
        .distinct(Oferta.sesion_id)
        .order_by(Oferta.sesion_id, Oferta.secuencia.desc())
    )
    return {sesion_id: float(u) for sesion_id, u in filas}


def _palanca(clave: str, fila: Palanca | None, moneda: str, vigente: Any) -> esquemas.PalancaSalida:
    nombre, unidad = nombre_y_unidad(clave, moneda)
    return esquemas.PalancaSalida(
        clave=clave,
        nombre=nombre,
        unidad=unidad,
        activa=fila is not None,
        peso=0 if fila is None else fila.peso,
        ideal=None if fila is None else fila.ideal,
        limite=None if fila is None else fila.limite,
        vigente=decimal_o_nada(vigente),
    )


async def evento_salida(
    bd: AsyncSession, evento_id: uuid.UUID, ahora: datetime
) -> esquemas.EventoSalida:
    evento = await evento_o_404(bd, evento_id)
    lineas = await lineas_de(bd, evento.id)
    palancas = await palancas_de(bd, evento.id)
    filas_nombres = await bd.execute(
        select(Proveedor.id, Proveedor.nombre).where(Proveedor.id.in_(evento.invitados))
    )
    nombres = {proveedor_id: nombre for proveedor_id, nombre in filas_nombres}
    sesiones = list(
        (
            await bd.scalars(
                select(SesionNegociacion)
                .where(SesionNegociacion.evento_id == evento.id)
                .order_by(SesionNegociacion.proveedor_nombre)
            )
        ).all()
    )
    utilidades = await _utilidades(bd, [s.id for s in sesiones])
    revision = revision_de(evento, lineas, palancas)
    vigentes = evento.foto.get("contrato") or {}
    borrador = evento.estado == "borrador"
    fecha_foto = evento.foto.get("fecha")
    return esquemas.EventoSalida(
        id=evento.id,
        folio=evento.folio,
        tipo=evento.tipo,
        titulo=evento.titulo,
        moneda=evento.moneda,
        plazo_meses=evento.plazo_meses,
        estado=evento.estado,
        fecha_limite=evento.fecha_limite,
        rondas_max=evento.rondas_max,
        estilo=evento.estilo,
        contrato_origen_id=evento.contrato_origen_id,
        proveedor_vigente_id=evento.proveedor_vigente_id,
        invitados=[
            esquemas.Invitado(id=i, nombre=nombres.get(i, "Proveedor sin datos"))
            for i in evento.invitados
        ],
        lineas=[
            esquemas.LineaSalida(
                id=linea.id,
                orden=linea.orden,
                codigo_servicio=linea.codigo_servicio,
                nombre=linea.nombre,
                unidad=linea.unidad,
                cantidad=linea.cantidad,
                precio_vigente=linea.precio_vigente,
                ideal=linea.ideal,
                limite=linea.limite,
                referencia=None
                if linea.referencia is None
                else esquemas.Banda.model_validate(linea.referencia),
            )
            for linea in lineas
        ],
        palancas=[
            _palanca(clave, palancas.get(clave), evento.moneda, vigentes.get(clave))
            for clave in CLAVES
        ],
        referencia_fecha=None if fecha_foto is None else datetime.fromisoformat(fecha_foto),
        creado_por_nombre=evento.creado_por_nombre,
        creado_en=evento.creado_en,
        publicado_en=evento.publicado_en,
        cerrado_en=evento.cerrado_en,
        motivo_cancelacion=evento.motivo_cancelacion,
        version=evento.version,
        errores=[
            esquemas.ProblemaSalida(campo=p.campo, mensaje=p.mensaje)
            for p in errores(revision, ahora)
        ]
        if borrador
        else [],
        avisos=[esquemas.ProblemaSalida(campo=p.campo, mensaje=p.mensaje) for p in avisos(revision)]
        if borrador
        else [],
        sesiones=[
            esquemas.SesionResumen(
                id=s.id,
                proveedor_id=s.proveedor_id,
                proveedor_nombre=s.proveedor_nombre,
                estado=s.estado,
                modo=s.modo,
                ronda=s.ronda,
                utilidad=utilidades.get(s.id),
                correo_estado=s.correo_estado,
                correo_error=s.correo_error,
                fuera_de_limites=s.fuera_de_limites,
                actualizado_en=s.actualizado_en,
            )
            for s in sesiones
        ],
    )
