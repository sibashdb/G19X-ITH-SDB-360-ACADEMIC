"""Turnos de una sesión: la oferta del proveedor y la respuesta del agente (spec §8.3).

Cada turno corre en una transacción con la sesión bloqueada (FOR UPDATE): dos ofertas a la vez se
procesan una tras otra y la ronda nunca se salta.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from comun.errores import ErrorDominio
from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion import consultas, textos
from negociacion.api import esquemas
from negociacion.bitacora import AGENTE, SISTEMA, Actor, registrar
from negociacion.dominio.motor import BETA, Estado, decidir
from negociacion.dominio.terminos import Terminos, Valores, es_valida, problema_de_valor, utilidad
from negociacion.errores import conflicto, invalidos, no_existe
from negociacion.modelos import FINALES, Evento, Mensaje, Oferta, SesionNegociacion

LIMITE_POR_MINUTO = 10  # mensajes del proveedor por sesión (spec §8.2)
CUATRO_DECIMALES = Decimal("0.0001")


def actor_proveedor(sesion: SesionNegociacion) -> Actor:
    return Actor("proveedor", str(sesion.proveedor_id), sesion.proveedor_nombre)


async def bloquear(bd: AsyncSession, sesion_id: uuid.UUID) -> tuple[SesionNegociacion, Evento]:
    sesion = await bd.get(
        SesionNegociacion, sesion_id, with_for_update=True, populate_existing=True
    )
    if sesion is None:
        raise no_existe("La sesión no existe.")
    return sesion, await consultas.evento_o_404(bd, sesion.evento_id)


def exigir_en_curso(sesion: SesionNegociacion, evento: Evento, momento: datetime) -> None:
    if evento.estado != "abierto" or sesion.estado in FINALES or momento >= evento.fecha_limite:
        raise conflicto("La negociación terminó.", "negociacion_terminada")


async def exigir_tasa(bd: AsyncSession, sesion_id: uuid.UUID, momento: datetime) -> None:
    recientes = await bd.scalar(
        select(func.count())
        .select_from(Mensaje)
        .where(
            Mensaje.sesion_id == sesion_id,
            Mensaje.autor == "proveedor",
            Mensaje.creado_en > momento - timedelta(minutes=1),
        )
    )
    if (recientes or 0) >= LIMITE_POR_MINUTO:
        raise HTTPException(
            429,
            "Envió demasiados mensajes; espere un minuto e intente de nuevo.",
            headers={"Retry-After": "60"},
        )


async def ya_recibido(bd: AsyncSession, sesion_id: uuid.UUID, clave: str) -> bool:
    consulta = select(Mensaje.id).where(
        Mensaje.sesion_id == sesion_id, Mensaje.clave_idempotencia == clave
    )
    return (await bd.scalar(consulta)) is not None


def valores_de(terminos: Terminos, entrada: esquemas.ValoresEntrada, prefijo: str) -> Valores:
    """Los valores de una oferta, con un error por campo si no cuadran con los términos."""
    precios = {str(k): v for k, v in entrada.precios.items()}
    errores: list[dict[str, str]] = []
    for linea_id in sorted(precios.keys() - {linea.id for linea in terminos.lineas}):
        errores.append(
            {
                "campo": f"{prefijo}.precios.{linea_id}",
                "mensaje": "Esta línea no es parte de la negociación.",
            }
        )
    for clave in sorted(entrada.palancas.keys() - {p.clave for p in terminos.palancas}):
        errores.append(
            {"campo": f"{prefijo}.palancas.{clave}", "mensaje": "Este término no se negocia aquí."}
        )
    for linea in terminos.lineas:
        precio = precios.get(linea.id)
        mensaje = (
            "Indique el precio de esta línea."
            if precio is None
            else problema_de_valor("precio", precio)
        )
        if mensaje is not None:
            errores.append({"campo": f"{prefijo}.precios.{linea.id}", "mensaje": mensaje})
    for palanca in terminos.palancas:
        valor = entrada.palancas.get(palanca.clave)
        mensaje = (
            "Indique este valor." if valor is None else problema_de_valor(palanca.clave, valor)
        )
        if mensaje is not None:
            errores.append({"campo": f"{prefijo}.palancas.{palanca.clave}", "mensaje": mensaje})
    if errores:
        raise invalidos(errores, "oferta_invalida")
    return Valores(
        {linea.id: precios[linea.id] for linea in terminos.lineas},
        {p.clave: entrada.palancas[p.clave] for p in terminos.palancas},
    )


def guardar_oferta(
    bd: AsyncSession,
    sesion_id: uuid.UUID,
    autor: str,
    ronda: int,
    terminos: Terminos,
    valores: Valores,
    momento: datetime,
    confirmada: bool = False,
) -> Oferta:
    oferta = Oferta(
        sesion_id=sesion_id,
        autor=autor,
        ronda=ronda,
        valores=valores.a_json(),
        utilidad=Decimal(repr(utilidad(terminos, valores))).quantize(CUATRO_DECIMALES),
        valida=es_valida(terminos, valores),
        fuera_de_limites_confirmada=confirmada,
        creado_en=momento,
    )
    bd.add(oferta)
    return oferta


async def hay_mejor_oferta(
    bd: AsyncSession, evento_id: uuid.UUID, sesion_id: uuid.UUID, utilidad_oferta: Decimal
) -> bool:
    """Si otra sesión del evento tiene una oferta válida mejor; nunca se dice cuál ni de quién."""
    consulta = (
        select(Oferta.id)
        .join(SesionNegociacion, SesionNegociacion.id == Oferta.sesion_id)
        .where(
            SesionNegociacion.evento_id == evento_id,
            Oferta.sesion_id != sesion_id,
            Oferta.autor == "proveedor",
            Oferta.valida.is_(True),
            Oferta.utilidad > utilidad_oferta,
        )
        .limit(1)
    )
    return (await bd.scalar(consulta)) is not None


async def responder(
    bd: AsyncSession,
    evento: Evento,
    sesion: SesionNegociacion,
    terminos: Terminos,
    oferta: Valores,
    utilidad_oferta: Decimal,
    ronda: int,
    confirmar: bool,
    momento: datetime,
) -> None:
    """El agente decide con el motor y responde; la traza queda en la bitácora."""
    estado = Estado(
        ronda=ronda,
        rondas=evento.rondas_max,
        beta=BETA[evento.estilo],
        anterior=await consultas.ultima_contraoferta(bd, sesion.id),
        hay_mejor_oferta=await hay_mejor_oferta(bd, evento.id, sesion.id, utilidad_oferta),
    )
    decision = decidir(terminos, estado, oferta, confirmar)
    if decision.accion != "pedir_aclaracion":  # la aclaración no consume la ronda
        sesion.ronda = max(sesion.ronda, ronda)
    propuesta_id = None
    if decision.contraoferta is not None:
        propuesta = guardar_oferta(
            bd, sesion.id, "agente", ronda, terminos, decision.contraoferta, momento
        )
        await bd.flush()
        propuesta_id = propuesta.id
    nombres = {linea.id: linea.nombre for linea in terminos.lineas}
    mensaje = Mensaje(
        sesion_id=sesion.id,
        autor="agente",
        texto=textos.respuesta_del_agente(decision, nombres),
        ronda=ronda,
        oferta_id=propuesta_id,
        creado_en=momento,
    )
    bd.add(mensaje)
    await bd.flush()
    registrar(
        bd,
        "motor.decision",
        AGENTE,
        evento_id=evento.id,
        sesion_id=sesion.id,
        detalle=decision.traza | {"mensaje_id": str(mensaje.id)},
        fecha=momento,
    )
    if decision.accion == "aceptar":
        sesion.estado = "acuerdo_tentativo"
    elif decision.accion == "cerrar_sin_acuerdo":
        sesion.estado = "sin_acuerdo"


async def cerrar_eventos_terminados(
    bd: AsyncSession, momento: datetime, evento_id: uuid.UUID | None = None
) -> list[uuid.UUID]:
    """Pasa a evaluación los eventos abiertos sin sesiones en curso o con la fecha límite vencida.

    ponytail: dos turnos que cierran a la vez las dos últimas sesiones no se ven entre sí y ninguno
    cierra el evento; la tarea de la fecha límite (vencimientos.py) lo cierra en menos de un minuto.
    """
    en_curso = (
        select(SesionNegociacion.id)
        .where(SesionNegociacion.evento_id == Evento.id, SesionNegociacion.estado.not_in(FINALES))
        .correlate(Evento)
        .exists()
    )
    consulta = (
        update(Evento)
        .where(Evento.estado == "abierto", or_(~en_curso, Evento.fecha_limite <= momento))
        .values(estado="en_evaluacion", cerrado_en=momento)
        .returning(Evento.id)
        .execution_options(synchronize_session=False)
    )
    if evento_id is not None:
        consulta = consulta.where(Evento.id == evento_id)
    cerrados = list((await bd.scalars(consulta)).all())
    for cerrado in cerrados:
        registrar(bd, "evento.en_evaluacion", SISTEMA, evento_id=cerrado, fecha=momento)
    return cerrados


async def recibir_oferta(
    bd: AsyncSession,
    sesion_id: uuid.UUID,
    entrada: esquemas.OfertaPortal,
    clave: str,
    momento: datetime,
) -> None:
    sesion, evento = await bloquear(bd, sesion_id)
    if await ya_recibido(bd, sesion.id, clave):
        return
    exigir_en_curso(sesion, evento, momento)
    await exigir_tasa(bd, sesion.id, momento)
    terminos = await consultas.terminos_de(bd, evento)
    oferta = valores_de(terminos, entrada.valores, "valores")
    ronda = sesion.ronda + 1
    fila = guardar_oferta(bd, sesion.id, "proveedor", ronda, terminos, oferta, momento)
    await bd.flush()
    bd.add(
        Mensaje(
            sesion_id=sesion.id,
            autor="proveedor",
            texto=entrada.nota,
            ronda=ronda,
            oferta_id=fila.id,
            clave_idempotencia=clave,
            creado_en=momento,
        )
    )
    registrar(
        bd,
        "oferta.recibida",
        actor_proveedor(sesion),
        evento_id=evento.id,
        sesion_id=sesion.id,
        detalle={"ronda": ronda, "utilidad": float(fila.utilidad), "valida": fila.valida},
        fecha=momento,
    )
    if sesion.estado == "invitada":
        sesion.estado = "activa"
    sesion.actualizado_en = momento
    if sesion.modo == "comprador":  # la oferta espera a la persona
        sesion.ronda = ronda
        bd.add(
            Mensaje(
                sesion_id=sesion.id,
                autor="sistema",
                texto=textos.EN_REVISION,
                ronda=ronda,
                creado_en=momento,
            )
        )
    else:
        await responder(
            bd,
            evento,
            sesion,
            terminos,
            oferta,
            fila.utilidad,
            ronda,
            entrada.confirmar_valores,
            momento,
        )
    await cerrar_eventos_terminados(bd, momento, evento.id)


async def escalar(bd: AsyncSession, sesion_id: uuid.UUID, clave: str, momento: datetime) -> None:
    sesion, evento = await bloquear(bd, sesion_id)
    if await ya_recibido(bd, sesion.id, clave):
        return
    exigir_en_curso(sesion, evento, momento)
    await exigir_tasa(bd, sesion.id, momento)
    bd.add(
        Mensaje(
            sesion_id=sesion.id,
            autor="proveedor",
            texto=textos.PIDE_PERSONA,
            ronda=sesion.ronda,
            clave_idempotencia=clave,
            creado_en=momento,
        )
    )
    if sesion.estado == "escalada":
        return
    bd.add(
        Mensaje(
            sesion_id=sesion.id,
            autor="sistema",
            texto=textos.ESCALADA,
            ronda=sesion.ronda,
            creado_en=momento,
        )
    )
    sesion.estado, sesion.modo, sesion.actualizado_en = "escalada", "comprador", momento
    registrar(
        bd,
        "sesion.escalada",
        actor_proveedor(sesion),
        evento_id=evento.id,
        sesion_id=sesion.id,
        fecha=momento,
    )


async def tomar_control(
    bd: AsyncSession, sesion_id: uuid.UUID, actor: Actor, momento: datetime
) -> None:
    sesion, evento = await bloquear(bd, sesion_id)
    exigir_en_curso(sesion, evento, momento)
    if sesion.modo == "comprador":
        return
    sesion.modo, sesion.actualizado_en = "comprador", momento
    registrar(bd, "control.tomado", actor, evento_id=evento.id, sesion_id=sesion.id, fecha=momento)


async def oferta_sin_respuesta(bd: AsyncSession, sesion_id: uuid.UUID) -> Oferta | None:
    """La última oferta del proveedor, si nadie le respondió después."""
    ultimo = await bd.scalar(
        select(Mensaje)
        .where(
            Mensaje.sesion_id == sesion_id,
            Mensaje.autor != "sistema",
            # «Pidió hablar con una persona» no responde ni plantea una oferta: se salta.
            or_(Mensaje.autor != "proveedor", Mensaje.oferta_id.is_not(None)),
        )
        .order_by(Mensaje.secuencia.desc())
        .limit(1)
    )
    if ultimo is None or ultimo.autor != "proveedor" or ultimo.oferta_id is None:
        return None
    return await bd.get(Oferta, ultimo.oferta_id)


async def devolver_control(
    bd: AsyncSession, sesion_id: uuid.UUID, actor: Actor, momento: datetime
) -> None:
    """El agente retoma la sesión y responde la oferta que quedó pendiente."""
    sesion, evento = await bloquear(bd, sesion_id)
    exigir_en_curso(sesion, evento, momento)
    if sesion.modo == "agente":
        return
    sesion.modo, sesion.actualizado_en = "agente", momento
    if sesion.estado == "escalada":
        sesion.estado = "activa"
    registrar(
        bd, "control.devuelto", actor, evento_id=evento.id, sesion_id=sesion.id, fecha=momento
    )
    pendiente = await oferta_sin_respuesta(bd, sesion.id)
    if pendiente is not None:
        terminos = await consultas.terminos_de(bd, evento)
        # La persona ya vio la oferta: no se pide aclaración; la ronda ya se contó al recibirla.
        await responder(
            bd,
            evento,
            sesion,
            terminos,
            Valores.de_json(pendiente.valores),
            pendiente.utilidad,
            sesion.ronda,
            True,
            momento,
        )
        await cerrar_eventos_terminados(bd, momento, evento.id)


async def ultima_oferta_proveedor(bd: AsyncSession, sesion_id: uuid.UUID) -> Oferta | None:
    return await bd.scalar(
        select(Oferta)
        .where(Oferta.sesion_id == sesion_id, Oferta.autor == "proveedor")
        .order_by(Oferta.secuencia.desc())
        .limit(1)
    )


def _fuera_de_limites(detalle: str) -> ErrorDominio:
    return ErrorDominio(422, "Solicitud inválida", detalle, {"codigo": "fuera_de_limites"})


async def responder_a_mano(
    bd: AsyncSession,
    sesion_id: uuid.UUID,
    datos: esquemas.Respuesta,
    actor: Actor,
    clave: str,
    momento: datetime,
) -> None:
    """La respuesta de la persona que tomó el control (spec §7)."""
    sesion, evento = await bloquear(bd, sesion_id)
    if await ya_recibido(bd, sesion.id, clave):
        return
    exigir_en_curso(sesion, evento, momento)
    if sesion.modo != "comprador":
        raise conflicto("Tome el control de la sesión antes de responder.", "sin_control")
    fuera, oferta_id, texto = False, None, datos.texto
    if datos.tipo == "mensaje" and datos.contraoferta is not None:
        terminos = await consultas.terminos_de(bd, evento)
        valores = valores_de(terminos, datos.contraoferta, "contraoferta")
        fuera = not es_valida(terminos, valores)
        if fuera and not datos.confirmar_fuera_de_limites:
            raise _fuera_de_limites(
                "La contraoferta sale de los límites de la negociación; confirme para enviarla."
            )
        fila = guardar_oferta(
            bd, sesion.id, "comprador", sesion.ronda, terminos, valores, momento, fuera
        )
        await bd.flush()
        oferta_id = fila.id
    elif datos.tipo == "aceptar":
        ultima = await ultima_oferta_proveedor(bd, sesion.id)
        if ultima is None:
            raise conflicto("El proveedor todavía no envía una oferta.", "sin_oferta")
        fuera = not ultima.valida
        if fuera and not datos.confirmar_fuera_de_limites:
            raise _fuera_de_limites(
                "La oferta del proveedor sale de los límites de la negociación; confirme para "
                "aceptarla."
            )
        sesion.estado = "acuerdo_tentativo"
        texto = texto or textos.ACUERDO
    elif datos.tipo == "cerrar":
        sesion.estado = "sin_acuerdo"
        texto = texto or textos.SIN_ACUERDO
    if fuera:
        sesion.fuera_de_limites = True  # el aprobador lo verá (incremento 4)
    bd.add(
        Mensaje(
            sesion_id=sesion.id,
            autor="comprador",
            texto=texto,
            ronda=sesion.ronda,
            oferta_id=oferta_id,
            clave_idempotencia=clave,
            creado_en=momento,
        )
    )
    sesion.actualizado_en = momento
    registrar(
        bd,
        "respuesta.manual",
        actor,
        evento_id=evento.id,
        sesion_id=sesion.id,
        detalle={"tipo": datos.tipo, "fuera_de_limites": fuera},
        fecha=momento,
    )
    await cerrar_eventos_terminados(bd, momento, evento.id)
