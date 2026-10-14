"""Rutas del comprador para crear, consultar, editar, publicar y cancelar negociaciones."""

import uuid
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion import consultas
from negociacion.api import esquemas
from negociacion.api.dependencias import Bd, Comprador, Integ, Lector, Reloj, TokenUsuario
from negociacion.bitacora import MAX_NOMBRE, de_usuario, registrar
from negociacion.dominio.configuracion import sugerir_precio
from negociacion.errores import conflicto, invalido
from negociacion.integraciones import ContratoVigente, Integraciones
from negociacion.modelos import Evento, Linea, Palanca, SesionNegociacion

router = APIRouter(tags=["eventos"])
ZONA_NEGOCIO = ZoneInfo("America/Mexico_City")  # el "hoy" de los contratos es el del negocio
# (código, nombre, unidad, cantidad, precio vigente) de cada línea nueva.
LineaPorCrear = tuple[str, str, str, Decimal, Decimal | None]


@router.post("/eventos", status_code=201)
async def crear_evento(
    datos: esquemas.EventoNuevo,
    token: TokenUsuario,
    usuario: Comprador,
    bd: Bd,
    integraciones: Integ,
    reloj: Reloj,
) -> esquemas.EventoSalida:
    momento = reloj()
    contrato: ContratoVigente | None = None
    if datos.tipo == "compra":
        async with bd.begin():
            servicios = await consultas.servicios_activos(
                bd, [linea.codigo_servicio for linea in datos.lineas]
            )
            await consultas.proveedores_invitables(bd, datos.proveedores)
        monedas = {s.moneda for s in servicios.values()}
        if len(monedas) > 1:
            raise invalido(
                "lineas", "Todas las líneas deben estar en la misma moneda.", "monedas_distintas"
            )
        moneda, plazo, invitados = monedas.pop(), datos.plazo_meses, list(datos.proveedores)
        nuevas: list[LineaPorCrear] = [
            (
                linea.codigo_servicio,
                servicios[linea.codigo_servicio].nombre,
                servicios[linea.codigo_servicio].unidad,
                linea.cantidad,
                None,
            )
            for linea in datos.lineas
        ]
    else:
        if datos.proveedor_id is None or datos.contrato_id is None:  # lo exige EventoNuevo
            raise RuntimeError("Renovación sin proveedor o contrato")
        contrato = await integraciones.contrato(token, datos.proveedor_id, datos.contrato_id)
        hoy = momento.astimezone(ZONA_NEGOCIO).date()  # como proveedores, que define «vigente»
        if not contrato.fecha_inicio <= hoy <= contrato.fecha_fin:
            raise invalido("contrato_id", "El contrato no está vigente.", "contrato_no_vigente")
        async with bd.begin():
            await consultas.proveedores_invitables(bd, [datos.proveedor_id], ["proveedor_id"])
        moneda, plazo, invitados = contrato.moneda, contrato.plazo_meses, [datos.proveedor_id]
        nuevas = [
            (
                linea.codigo_servicio,
                linea.nombre,
                linea.unidad,
                linea.cantidad,
                linea.precio_unitario,
            )
            for linea in contrato.lineas
        ]
    # ponytail: una consulta por línea, en serie (≤ 20 líneas en la red interna); con muchas
    # más, lanzarlas en paralelo con asyncio.TaskGroup.
    referencias = [
        await integraciones.referencia(token, codigo, cantidad, plazo)
        for codigo, _, _, cantidad, _ in nuevas
    ]
    async with bd.begin():
        numero = int(await bd.scalar(text("SELECT nextval('folio_evento')")) or 0)
        evento = Evento(
            folio=f"NEG-{momento.year}-{numero:04d}",
            tipo=datos.tipo,
            titulo=datos.titulo,
            moneda=moneda,
            plazo_meses=plazo,
            fecha_limite=datos.fecha_limite,
            rondas_max=datos.rondas_max,
            estilo=datos.estilo,
            contrato_origen_id=None if contrato is None else contrato.id,
            proveedor_vigente_id=None if contrato is None else datos.proveedor_id,
            invitados=invitados,
            foto={
                "fecha": momento.isoformat(),
                "contrato": None if contrato is None else contrato.terminos(),
            },
            creado_por_id=usuario.id,
            creado_por_nombre=usuario.nombre[:MAX_NOMBRE],
            creado_en=momento,
        )
        bd.add(evento)
        await bd.flush()
        tope = None if contrato is None else contrato.tope_aumento_pct
        for orden, ((codigo, nombre, unidad, cantidad, vigente), referencia) in enumerate(
            zip(nuevas, referencias, strict=True)
        ):
            ideal, limite = sugerir_precio(
                datos.tipo, consultas.banda_de(referencia), vigente, tope
            )
            bd.add(
                Linea(
                    evento_id=evento.id,
                    orden=orden,
                    codigo_servicio=codigo,
                    nombre=nombre,
                    unidad=unidad,
                    cantidad=cantidad,
                    precio_vigente=vigente,
                    ideal=ideal,
                    limite=limite,
                    referencia=referencia,
                )
            )
        bd.add(Palanca(evento_id=evento.id, clave="precio", peso=100))
        registrar(
            bd,
            "evento.creado",
            de_usuario(usuario),
            evento_id=evento.id,
            detalle={"folio": evento.folio, "tipo": evento.tipo},
            fecha=momento,
        )
    return await consultas.evento_salida(bd, evento.id, momento)


@router.get("/eventos/{evento_id}")
async def ver_evento(
    evento_id: uuid.UUID, _: Lector, bd: Bd, reloj: Reloj
) -> esquemas.EventoSalida:
    return await consultas.evento_salida(bd, evento_id, reloj())


@router.get("/eventos")
async def listar_eventos(
    _: Lector,
    bd: Bd,
    estado: esquemas.EstadoEvento | None = None,
    tipo: esquemas.TipoEvento | None = None,
    pagina: Annotated[int, Query(ge=1, le=1000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
) -> esquemas.PaginaEventos:
    filtros = []
    if estado is not None:
        filtros.append(Evento.estado == estado)
    if tipo is not None:
        filtros.append(Evento.tipo == tipo)
    total = await bd.scalar(select(func.count()).select_from(Evento).where(*filtros))
    conteos = (
        select(
            SesionNegociacion.evento_id,
            func.count().label("sesiones"),
            func.count().filter(SesionNegociacion.estado == "acuerdo_tentativo").label("acuerdos"),
            func.count().filter(SesionNegociacion.estado == "escalada").label("escaladas"),
        )
        .group_by(SesionNegociacion.evento_id)
        .subquery()
    )
    filas = await bd.execute(
        select(Evento, conteos.c.sesiones, conteos.c.acuerdos, conteos.c.escaladas)
        .outerjoin(conteos, conteos.c.evento_id == Evento.id)
        .where(*filtros)
        .order_by(Evento.creado_en.desc(), Evento.folio.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return esquemas.PaginaEventos(
        total=total or 0,
        elementos=[
            esquemas.EventoResumen(
                id=evento.id,
                folio=evento.folio,
                tipo=evento.tipo,
                titulo=evento.titulo,
                estado=evento.estado,
                fecha_limite=evento.fecha_limite,
                invitados=len(evento.invitados),
                sesiones=sesiones or 0,
                acuerdos=acuerdos or 0,
                escaladas=escaladas or 0,
                creado_por_nombre=evento.creado_por_nombre,
                creado_en=evento.creado_en,
            )
            for evento, sesiones, acuerdos, escaladas in filas
        ],
    )


NO_EDITABLE_RENOVACION = (
    "En una renovación, las líneas salen del contrato; solo puede cambiar el ideal y el límite."
)


def _ajustar_renovacion(lineas: list[Linea], cambios: list[esquemas.LineaCambio]) -> None:
    actuales = [(linea.codigo_servicio, linea.cantidad) for linea in lineas]
    if actuales != [(c.codigo_servicio, c.cantidad) for c in cambios]:
        raise invalido("lineas", NO_EDITABLE_RENOVACION, "no_editable")
    for linea, cambio in zip(lineas, cambios, strict=True):
        if cambio.ideal is not None or cambio.limite is not None:  # sin ninguno, se conservan
            linea.ideal, linea.limite = cambio.ideal, cambio.limite


async def _reemplazar_lineas(
    bd: AsyncSession,
    evento: Evento,
    cambios: list[esquemas.LineaCambio],
    token: str,
    integraciones: Integraciones,
    plazo_cambio: bool,
) -> None:
    """Las líneas de una compra se reemplazan; las que no cambian conservan su foto."""
    servicios = await consultas.servicios_activos(bd, [c.codigo_servicio for c in cambios])
    monedas = {s.moneda for s in servicios.values()}
    if len(monedas) > 1:
        raise invalido(
            "lineas", "Todas las líneas deben estar en la misma moneda.", "monedas_distintas"
        )
    evento.moneda = monedas.pop()
    previas = {(p.codigo_servicio, p.cantidad): p for p in await consultas.lineas_de(bd, evento.id)}
    nuevas: list[Linea] = []
    for orden, cambio in enumerate(cambios):
        previa = previas.get((cambio.codigo_servicio, cambio.cantidad))
        if previa is None or plazo_cambio:
            referencia = await integraciones.referencia(
                token, cambio.codigo_servicio, cambio.cantidad, evento.plazo_meses
            )
        else:
            referencia = previa.referencia
        if cambio.ideal is not None or cambio.limite is not None:
            ideal, limite = cambio.ideal, cambio.limite
        elif previa is not None:
            ideal, limite = previa.ideal, previa.limite
        else:
            ideal, limite = sugerir_precio("compra", consultas.banda_de(referencia), None, None)
        servicio = servicios[cambio.codigo_servicio]
        nuevas.append(
            Linea(
                evento_id=evento.id,
                orden=orden,
                codigo_servicio=servicio.codigo,
                nombre=servicio.nombre,
                unidad=servicio.unidad,
                cantidad=cambio.cantidad,
                ideal=ideal,
                limite=limite,
                referencia=referencia,
            )
        )
    await bd.execute(delete(Linea).where(Linea.evento_id == evento.id))
    bd.add_all(nuevas)


@router.patch("/eventos/{evento_id}")
async def editar_evento(
    evento_id: uuid.UUID,
    datos: esquemas.EventoCambios,
    token: TokenUsuario,
    usuario: Comprador,
    bd: Bd,
    integraciones: Integ,
    reloj: Reloj,
) -> esquemas.EventoSalida:
    momento = reloj()
    # ponytail: las consultas a inteligencia corren con la fila del evento bloqueada: hasta 20
    # líneas por 5 s = 100 s en el peor caso; basta para borradores que edita una persona a la vez.
    async with bd.begin():
        evento = await consultas.evento_o_404(bd, evento_id, bloquear=True)
        if evento.estado != "borrador":
            raise conflicto("Solo se puede editar una negociación en borrador.", "no_editable")
        if evento.version != datos.version:
            raise conflicto(
                "Otra persona cambió esta negociación; recárguela para ver sus cambios.",
                "version_desactualizada",
            )
        renovacion = evento.tipo == "renovacion"
        cambios: list[str] = []
        for campo in ("titulo", "fecha_limite", "rondas_max", "estilo"):
            valor = getattr(datos, campo)
            if valor is not None and valor != getattr(evento, campo):
                setattr(evento, campo, valor)
                cambios.append(campo)
        if datos.plazo_meses is not None and datos.plazo_meses != evento.plazo_meses:
            if renovacion:
                raise invalido(
                    "plazo_meses", "El plazo de una renovación sale del contrato.", "no_editable"
                )
            evento.plazo_meses = datos.plazo_meses
            # Con otro plazo se consultan de nuevo todas las líneas (con o sin lineas nuevas).
            # Se reasigna el dict: JSONB no detecta los cambios hechos en su sitio.
            evento.foto = {**evento.foto, "fecha": momento.isoformat()}
            cambios.append("plazo_meses")
        if datos.proveedores is not None:
            if renovacion and datos.proveedores != evento.invitados:
                raise invalido(
                    "proveedores",
                    "En una renovación solo participa el proveedor del contrato.",
                    "no_editable",
                )
            await consultas.proveedores_invitables(bd, datos.proveedores)
            if datos.proveedores != evento.invitados:
                evento.invitados = list(datos.proveedores)
                cambios.append("proveedores")
        if datos.lineas is not None:
            if renovacion:
                _ajustar_renovacion(await consultas.lineas_de(bd, evento.id), datos.lineas)
            else:
                await _reemplazar_lineas(
                    bd, evento, datos.lineas, token, integraciones, "plazo_meses" in cambios
                )
            cambios.append("lineas")
        elif "plazo_meses" in cambios:
            for linea in await consultas.lineas_de(bd, evento.id):
                linea.referencia = await integraciones.referencia(
                    token, linea.codigo_servicio, linea.cantidad, evento.plazo_meses
                )
        if datos.palancas is not None:
            await bd.execute(delete(Palanca).where(Palanca.evento_id == evento.id))
            bd.add_all(
                Palanca(
                    evento_id=evento.id,
                    clave=p.clave,
                    peso=p.peso,
                    ideal=None if p.clave == "precio" else p.ideal,
                    limite=None if p.clave == "precio" else p.limite,
                )
                for p in datos.palancas
            )
            cambios.append("palancas")
        if cambios:
            evento.version += 1
            registrar(
                bd,
                "evento.editado",
                de_usuario(usuario),
                evento_id=evento.id,
                detalle={"campos": cambios},
                fecha=momento,
            )
    return await consultas.evento_salida(bd, evento.id, momento)
