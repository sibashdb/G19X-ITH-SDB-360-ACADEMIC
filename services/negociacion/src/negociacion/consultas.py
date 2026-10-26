"""Lecturas que arman las respuestas de la API (y, desde la Task 9, los términos del motor)."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion.api import esquemas
from negociacion.dominio.adjudicacion import Resultado
from negociacion.dominio.configuracion import (
    Banda,
    LineaRevision,
    PalancaRevision,
    Revision,
    avisos,
    errores,
)
from negociacion.dominio.terminos import CLAVES, Rango, Terminos, Valores
from negociacion.dominio.terminos import Linea as LineaTermino
from negociacion.dominio.terminos import Palanca as PalancaTermino
from negociacion.errores import invalido, no_existe
from negociacion.modelos import (
    FINALES,
    Adjudicacion,
    Bitacora,
    Evento,
    Linea,
    Mensaje,
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
    # En orden de secuencia, la última oferta de cada sesión sustituye a las anteriores. (Sin
    # DISTINCT ON: SQLAlchemy 2.1 lo cambió de forma y el piso declarado es 2.0.)
    filas = await bd.execute(
        select(Oferta.sesion_id, Oferta.utilidad)
        .where(Oferta.sesion_id.in_(sesiones), Oferta.autor == "proveedor")
        .order_by(Oferta.secuencia)
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
        motivo_desierta=evento.motivo_desierta,
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


def _rango(ideal: Decimal | None, limite: Decimal | None) -> Rango:
    if ideal is None or limite is None:
        raise RuntimeError("Un evento publicado siempre tiene ideal y límite")
    return Rango(ideal, limite)


async def terminos_de(bd: AsyncSession, evento: Evento) -> Terminos:
    """Los términos del motor a partir de la configuración guardada del evento publicado."""
    lineas = await lineas_de(bd, evento.id)
    palancas = await palancas_de(bd, evento.id)
    return Terminos(
        peso_precio=palancas["precio"].peso,
        lineas=tuple(
            LineaTermino(
                str(linea.id),
                linea.nombre,
                linea.cantidad,
                _rango(linea.ideal, linea.limite),
                None if (banda := banda_de(linea.referencia)) is None else banda.p50,
            )
            for linea in lineas
        ),
        palancas=tuple(
            PalancaTermino(p.clave, p.peso, _rango(p.ideal, p.limite))
            for p in palancas.values()
            if p.clave != "precio"
        ),
    )


async def ultima_contraoferta(bd: AsyncSession, sesion_id: uuid.UUID) -> Valores | None:
    """La última contraoferta de la sesión, del agente o del comprador."""
    fila = await bd.scalar(
        select(Oferta)
        .where(Oferta.sesion_id == sesion_id, Oferta.autor.in_(("agente", "comprador")))
        .order_by(Oferta.secuencia.desc())
        .limit(1)
    )
    return None if fila is None else Valores.de_json(fila.valores)


def valores_salida(valores: Valores) -> esquemas.ValoresSalida:
    return esquemas.ValoresSalida(precios=dict(valores.precios), palancas=dict(valores.palancas))


async def resultado_de(bd: AsyncSession, evento: Evento, sesion_id: uuid.UUID) -> Resultado | None:
    """Lo que el proveedor de esa sesión puede saber del resultado; nulo mientras no se resuelve."""
    if evento.estado == "desierto":
        return "desierta"
    if evento.estado != "adjudicado":
        return None
    ganadora = await bd.scalar(
        select(Adjudicacion.sesion_id).where(
            Adjudicacion.evento_id == evento.id, Adjudicacion.estado.in_(("aprobada", "directa"))
        )
    )
    return "adjudicada" if ganadora == sesion_id else "no_elegida"


async def vista_portal(bd: AsyncSession, sesion_id: uuid.UUID) -> esquemas.VistaPortal:
    """Lo que ve el proveedor de su sesión: nada de ideales, límites, pesos ni referencia."""
    sesion = await bd.get(SesionNegociacion, sesion_id, populate_existing=True)
    if sesion is None:
        raise no_existe("La sesión no existe.")
    evento = await evento_o_404(bd, sesion.evento_id)
    lineas = await lineas_de(bd, evento.id)
    palancas = [p for p in (await palancas_de(bd, evento.id)).values() if p.clave != "precio"]
    # Una fila por mensaje, con su oferta si la lleva (join externo: no todos tienen).
    filas: list[tuple[Mensaje, Oferta | None]] = [
        (mensaje, oferta)
        for mensaje, oferta in await bd.execute(
            select(Mensaje, Oferta)
            .outerjoin(Oferta, Oferta.id == Mensaje.oferta_id)
            .where(Mensaje.sesion_id == sesion.id)
            .order_by(Mensaje.secuencia)
        )
    ]
    en_curso = sesion.estado not in FINALES
    # Los mensajes libres del proveedor y las respuestas del agente a ellos (N2) no son parte del
    # turno de ofertas: no abren ni cierran una aclaración pendiente.
    detalles: Sequence[dict[str, Any]] = (
        await bd.scalars(
            select(Bitacora.detalle).where(
                Bitacora.sesion_id == sesion.id,
                Bitacora.accion.in_(("mensaje.interpretado", "agente.respuesta")),
            )
        )
    ).all()
    libres = {str(detalle.get("mensaje_id")) for detalle in detalles}
    conversacion = [m for m, _ in filas if m.autor != "sistema" and str(m.id) not in libres]
    # Una respuesta del agente sin propuesta, con la sesión en curso, es una aclaración pendiente.
    pide = (
        en_curso
        and bool(conversacion)
        and conversacion[-1].autor == "agente"
        and conversacion[-1].oferta_id is None
    )
    ultima = await ultima_contraoferta(bd, sesion.id) if en_curso else None
    return esquemas.VistaPortal(
        folio=evento.folio,
        titulo=evento.titulo,
        moneda=evento.moneda,
        fecha_limite=evento.fecha_limite,
        rondas_max=evento.rondas_max,
        rondas_restantes=max(evento.rondas_max - sesion.ronda, 0),
        estado=sesion.estado,
        resultado=await resultado_de(bd, evento, sesion.id),
        atendido_por="persona" if sesion.modo == "comprador" else "agente",
        pide_confirmacion=pide,
        lineas=[
            esquemas.LineaPortal(
                id=linea.id,
                codigo_servicio=linea.codigo_servicio,
                nombre=linea.nombre,
                unidad=linea.unidad,
                cantidad=linea.cantidad,
            )
            for linea in lineas
        ],
        palancas=[
            esquemas.PalancaPortal(
                clave=p.clave,
                nombre=nombre_y_unidad(p.clave, evento.moneda)[0],
                unidad=nombre_y_unidad(p.clave, evento.moneda)[1],
            )
            for p in palancas
        ],
        mensajes=[
            esquemas.MensajePortal(
                autor=mensaje.autor,
                texto=mensaje.texto,
                ronda=mensaje.ronda,
                fecha=mensaje.creado_en,
                oferta=None if oferta is None else valores_salida(Valores.de_json(oferta.valores)),
            )
            for mensaje, oferta in filas
        ],
        ultima_propuesta=None if ultima is None else valores_salida(ultima),
    )


async def sesion_detalle(bd: AsyncSession, sesion_id: uuid.UUID) -> esquemas.SesionDetalle:
    """La sesión completa para el comprador: mensajes, ofertas con su utilidad y cada traza."""
    sesion = await bd.get(SesionNegociacion, sesion_id, populate_existing=True)
    if sesion is None:
        raise no_existe("La sesión no existe.")
    evento = await evento_o_404(bd, sesion.evento_id)
    mensajes = (
        await bd.scalars(
            select(Mensaje).where(Mensaje.sesion_id == sesion.id).order_by(Mensaje.secuencia)
        )
    ).all()
    ofertas = (
        await bd.scalars(
            select(Oferta).where(Oferta.sesion_id == sesion.id).order_by(Oferta.secuencia)
        )
    ).all()
    trazas: dict[str, dict[str, Any]] = {}
    interpretaciones: dict[str, dict[str, Any]] = {}
    redacciones: dict[str, dict[str, Any]] = {}
    for fila in await bd.scalars(
        select(Bitacora).where(
            Bitacora.sesion_id == sesion.id,
            Bitacora.accion.in_(("motor.decision", "mensaje.interpretado", "agente.respuesta")),
        )
    ):
        mensaje_id = str(fila.detalle.get("mensaje_id"))
        if fila.accion == "motor.decision":
            trazas[mensaje_id] = fila.detalle
        elif fila.accion == "mensaje.interpretado":
            interpretaciones[mensaje_id] = fila.detalle
        if fila.detalle.get("redaccion"):
            redacciones[mensaje_id] = fila.detalle["redaccion"]
    return esquemas.SesionDetalle(
        id=sesion.id,
        evento_id=evento.id,
        folio=evento.folio,
        titulo=evento.titulo,
        moneda=evento.moneda,
        proveedor_id=sesion.proveedor_id,
        proveedor_nombre=sesion.proveedor_nombre,
        destinatario=sesion.destinatario,
        estado=sesion.estado,
        modo=sesion.modo,
        ronda=sesion.ronda,
        rondas_max=evento.rondas_max,
        fuera_de_limites=sesion.fuera_de_limites,
        correo_estado=sesion.correo_estado,
        correo_error=sesion.correo_error,
        lineas=[
            esquemas.LineaDetalle(
                id=linea.id,
                nombre=linea.nombre,
                unidad=linea.unidad,
                cantidad=linea.cantidad,
                ideal=linea.ideal,
                limite=linea.limite,
            )
            for linea in await lineas_de(bd, evento.id)
        ],
        palancas=[
            esquemas.PalancaDetalle(
                clave=p.clave,
                nombre=nombre_y_unidad(p.clave, evento.moneda)[0],
                unidad=nombre_y_unidad(p.clave, evento.moneda)[1],
                peso=p.peso,
                ideal=p.ideal,
                limite=p.limite,
            )
            for p in (await palancas_de(bd, evento.id)).values()
        ],
        mensajes=[
            esquemas.MensajeDetalle(
                id=m.id,
                autor=m.autor,
                texto=m.texto,
                ronda=m.ronda,
                fecha=m.creado_en,
                oferta_id=m.oferta_id,
                decision=trazas.get(str(m.id)),
                interpretacion=interpretaciones.get(str(m.id)),
                redaccion=redacciones.get(str(m.id)),
            )
            for m in mensajes
        ],
        ofertas=[
            esquemas.OfertaDetalle(
                id=o.id,
                autor=o.autor,
                ronda=o.ronda,
                valores=valores_salida(Valores.de_json(o.valores)),
                utilidad=float(o.utilidad),
                valida=o.valida,
                fuera_de_limites_confirmada=o.fuera_de_limites_confirmada,
                fecha=o.creado_en,
            )
            for o in ofertas
        ],
    )
