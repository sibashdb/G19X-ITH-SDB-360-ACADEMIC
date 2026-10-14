"""Rutas del comprador para crear, consultar, editar, publicar y cancelar negociaciones."""

import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import text

from negociacion import consultas
from negociacion.api import esquemas
from negociacion.api.dependencias import Bd, Comprador, Integ, Lector, Reloj, TokenUsuario
from negociacion.bitacora import MAX_NOMBRE, de_usuario, registrar
from negociacion.dominio.configuracion import sugerir_precio
from negociacion.errores import invalido
from negociacion.integraciones import ContratoVigente
from negociacion.modelos import Evento, Linea, Palanca

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
