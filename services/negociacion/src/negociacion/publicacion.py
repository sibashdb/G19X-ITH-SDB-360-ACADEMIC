"""Publicar, cancelar y reenviar invitaciones (spec §7 y §9.1).

Los correos salen fuera de la transacción: primero se confirman las sesiones y sus tokens, luego se
manda cada correo, y al final otra transacción guarda si salió y lo publica en el outbox. Si el
proceso se cae entre medio, el comprador ve el correo pendiente y usa «Reenviar invitación».
"""

import logging
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime

from comun.outbox import registrar_evento
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion import consultas, correo, textos
from negociacion.bitacora import Actor, registrar
from negociacion.config import Configuracion
from negociacion.dominio.configuracion import errores
from negociacion.errores import conflicto, invalidos, no_existe
from negociacion.modelos import FINALES, Evento, Mensaje, Outbox, Proveedor, SesionNegociacion
from negociacion.tokens import nuevo_token

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Invitacion:
    sesion_id: uuid.UUID
    proveedor_nombre: str
    contacto: str
    destinatario: str
    token: str


@dataclass(frozen=True)
class Envio:
    sesion_id: uuid.UUID
    proveedor_nombre: str
    destinatario: str
    enlace: str
    estado: str  # enviado o fallido
    error: str | None


def enlace(url_publica: str, token: str) -> str:
    """El token va en el fragmento: el navegador no lo manda al servidor ni en el Referer."""
    return f"{url_publica.rstrip('/')}/portal#t={token}"


async def preparar_publicacion(
    bd: AsyncSession, evento_id: uuid.UUID, actor: Actor, momento: datetime
) -> tuple[Evento, list[Invitacion]]:
    """Valida, crea las sesiones con su token y abre el evento, en la transacción en curso."""
    evento = await consultas.evento_o_404(bd, evento_id, bloquear=True)
    if evento.estado != "borrador":
        raise conflicto("La negociación ya se publicó o se canceló.", "no_publicable")
    lineas = await consultas.lineas_de(bd, evento.id)
    palancas = await consultas.palancas_de(bd, evento.id)
    problemas = errores(consultas.revision_de(evento, lineas, palancas), momento)
    if problemas:
        raise invalidos(
            [{"campo": p.campo, "mensaje": p.mensaje} for p in problemas], "evento_incompleto"
        )
    invitaciones: list[Invitacion] = []
    for proveedor in await consultas.proveedores_invitables(bd, evento.invitados):
        token, huella = nuevo_token()
        sesion = SesionNegociacion(
            evento_id=evento.id,
            proveedor_id=proveedor.id,
            proveedor_nombre=proveedor.nombre,
            destinatario=proveedor.contacto_email,
            token_hash=huella,
            actualizado_en=momento,
        )
        bd.add(sesion)
        await bd.flush()
        invitaciones.append(
            Invitacion(
                sesion.id,
                proveedor.nombre,
                proveedor.contacto_nombre,
                proveedor.contacto_email,
                token,
            )
        )
    evento.estado = "abierto"
    evento.publicado_en = momento
    registrar_evento(
        bd,
        Outbox,
        "negociacion.publicada",
        {
            "folio": evento.folio,
            "titulo": evento.titulo,
            "tipo": evento.tipo,
            "proveedores": len(invitaciones),
            "actor": actor.para_evento(),
        },
    )
    registrar(
        bd,
        "evento.publicado",
        actor,
        evento_id=evento.id,
        detalle={"proveedores": len(invitaciones)},
        fecha=momento,
    )
    return evento, invitaciones


async def enviar_invitaciones(
    enviar: correo.EnviarCorreo,
    config: Configuracion,
    evento: Evento,
    invitaciones: list[Invitacion],
) -> list[Envio]:
    envios: list[Envio] = []
    for invitacion in invitaciones:
        url = enlace(config.url_publica, invitacion.token)
        mensaje = correo.invitacion(
            remitente=config.smtp_remitente,
            destinatario=invitacion.destinatario,
            contacto=invitacion.contacto,
            titulo=evento.titulo,
            folio=evento.folio,
            fecha_limite=evento.fecha_limite,
            enlace=url,
        )
        try:
            await enviar(mensaje)
            estado, error = "enviado", None
        except (smtplib.SMTPException, OSError):
            log.warning("No se pudo enviar la invitación de la sesión %s", invitacion.sesion_id)
            estado, error = "fallido", correo.NO_ENTREGADO
        envios.append(
            Envio(
                invitacion.sesion_id,
                invitacion.proveedor_nombre,
                invitacion.destinatario,
                url,
                estado,
                error,
            )
        )
    return envios


async def registrar_envios(
    bd: AsyncSession,
    evento: Evento,
    envios: list[Envio],
    actor: Actor,
    momento: datetime,
    reenvio: bool,
) -> None:
    """Guarda si salió cada correo y lo publica (sin el token), en la transacción en curso."""
    for envio in envios:
        sesion = await bd.get(SesionNegociacion, envio.sesion_id)
        if sesion is None:
            raise LookupError(f"La sesión {envio.sesion_id} desapareció")
        sesion.correo_estado, sesion.correo_error, sesion.correo_en = (
            envio.estado,
            envio.error,
            momento,
        )
        registrar_evento(
            bd,
            Outbox,
            "negociacion.invitacion_enviada",
            {
                "folio": evento.folio,
                "titulo": evento.titulo,
                "proveedor": envio.proveedor_nombre,
                "destinatario": envio.destinatario,
                "estado": envio.estado,
                "error": envio.error,
                "reenvio": reenvio,
                "actor": actor.para_evento(),
            },
        )
        registrar(
            bd,
            "invitacion.reenviada" if reenvio else "invitacion.enviada",
            actor,
            evento_id=evento.id,
            sesion_id=sesion.id,
            detalle={"estado": envio.estado},
            fecha=momento,
        )


async def cancelar(
    bd: AsyncSession, evento_id: uuid.UUID, motivo: str, actor: Actor, momento: datetime
) -> None:
    evento = await consultas.evento_o_404(bd, evento_id, bloquear=True)
    if evento.estado not in ("borrador", "abierto"):
        raise conflicto(
            "Solo se puede cancelar una negociación en borrador o abierta.", "no_cancelable"
        )
    sesiones = await bd.scalars(
        select(SesionNegociacion).where(SesionNegociacion.evento_id == evento.id).with_for_update()
    )
    for sesion in sesiones:
        sesion.token_hash = None  # el enlace deja de servir
        if sesion.estado not in FINALES:
            sesion.estado = "sin_acuerdo"
            sesion.actualizado_en = momento
            bd.add(
                Mensaje(
                    sesion_id=sesion.id,
                    autor="sistema",
                    texto=textos.CANCELADA,
                    ronda=sesion.ronda,
                    creado_en=momento,
                )
            )
    evento.estado = "cancelado"
    evento.cerrado_en = momento
    evento.motivo_cancelacion = motivo
    registrar_evento(
        bd,
        Outbox,
        "negociacion.cancelada",
        {
            "folio": evento.folio,
            "titulo": evento.titulo,
            "motivo": motivo,
            "actor": actor.para_evento(),
        },
    )
    registrar(
        bd,
        "evento.cancelado",
        actor,
        evento_id=evento.id,
        detalle={"motivo": motivo},
        fecha=momento,
    )


async def preparar_reenvio(
    bd: AsyncSession, sesion_id: uuid.UUID, momento: datetime
) -> tuple[Evento, Invitacion]:
    """Un token nuevo para la sesión; el anterior deja de servir."""
    sesion = await bd.get(
        SesionNegociacion, sesion_id, with_for_update=True, populate_existing=True
    )
    if sesion is None:
        raise no_existe("La sesión no existe.")
    evento = await consultas.evento_o_404(bd, sesion.evento_id)
    if evento.estado != "abierto" or sesion.estado in FINALES:
        raise conflicto(
            "Solo se puede reenviar la invitación de una sesión en curso.", "no_reenviable"
        )
    proveedor = await bd.get(Proveedor, sesion.proveedor_id)
    if proveedor is not None and proveedor.contacto_email:
        sesion.destinatario = proveedor.contacto_email  # por si cambió el contacto
    contacto = sesion.proveedor_nombre if proveedor is None else proveedor.contacto_nombre
    token, huella = nuevo_token()
    sesion.token_hash = huella
    sesion.correo_estado = "pendiente"
    sesion.actualizado_en = momento
    return evento, Invitacion(
        sesion.id, sesion.proveedor_nombre, contacto, sesion.destinatario, token
    )
