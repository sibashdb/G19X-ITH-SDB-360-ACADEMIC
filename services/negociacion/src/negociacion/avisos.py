"""Aviso del resultado a los proveedores (spec §4.6), desde la tarea periódica.

Al adjudicarse o declararse desierta una negociación, cada sesión con destinatario recibe un correo
con su resultado. Nunca dice quién ganó ni ningún monto, ni lleva el enlace del portal.
"""

import logging
from datetime import datetime

from comun.outbox import registrar_evento
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from negociacion import consultas, correo
from negociacion.bitacora import SISTEMA, registrar
from negociacion.config import Configuracion
from negociacion.correo import EnviarCorreo
from negociacion.modelos import Evento, Outbox, Proveedor, SesionNegociacion

log = logging.getLogger(__name__)


async def _avisar(
    bd: AsyncSession,
    enviar: EnviarCorreo,
    config: Configuracion,
    evento: Evento,
    sesion: SesionNegociacion,
    momento: datetime,
) -> None:
    """Manda el correo de la sesión y guarda cómo salió, en la transacción en curso."""
    resultado = await consultas.resultado_de(bd, evento, sesion.id)
    if resultado is None:  # el evento ya está adjudicado o desierto: no pasa
        raise RuntimeError("Solo se avisa el resultado de una negociación resuelta")
    proveedor = await bd.get(Proveedor, sesion.proveedor_id)
    contacto = sesion.proveedor_nombre if proveedor is None else proveedor.contacto_nombre
    # Un fallo (armar el correo o mandarlo) no puede dejar sin registrar a las demás sesiones.
    try:
        await enviar(
            correo.resultado(
                remitente=config.smtp_remitente,
                destinatario=sesion.destinatario,
                contacto=contacto,
                titulo=evento.titulo,
                folio=evento.folio,
                resultado=resultado,
            )
        )
        estado, error = "enviado", None
    except Exception as exc:
        # Solo la clase del error: el mensaje de SMTP repite direcciones.
        log.warning(
            "No se pudo enviar el resultado de la sesión %s (%s)", sesion.id, type(exc).__name__
        )
        estado, error = "fallido", correo.NO_ENTREGADO
    registrar_evento(
        bd,
        Outbox,
        "negociacion.resultado_enviado",
        {
            "folio": evento.folio,
            "titulo": evento.titulo,
            "proveedor": sesion.proveedor_nombre,
            "destinatario": sesion.destinatario,
            "estado": estado,
            "error": error,
            "reenvio": False,
            "resultado": resultado,
            "actor": SISTEMA.para_evento(),
        },
    )
    registrar(
        bd,
        "resultado.enviado",
        SISTEMA,
        evento_id=evento.id,
        sesion_id=sesion.id,
        detalle={"estado": estado, "resultado": resultado},
        fecha=momento,
    )


async def enviar_pendientes(
    fabrica: async_sessionmaker[AsyncSession],
    enviar: EnviarCorreo,
    config: Configuracion,
    momento: datetime,
) -> int:
    """Avisa el resultado a las sesiones de los eventos adjudicados o desiertos que aún no lo
    tienen; devuelve cuántas procesó.

    Cada sesión se marca (`resultado_avisado_en`) aunque el correo falle o no haya destinatario:
    como una invitación, no se reintenta.

    ponytail: el correo sale con las filas bloqueadas y antes de confirmar; si el proceso cae a
    mitad, la siguiente vuelta repite los avisos de la tanda. Un commit por sesión si importara.
    """
    async with fabrica() as bd, bd.begin():
        # skip_locked: dos trabajadores a la vez no avisan dos veces a la misma sesión.
        pendientes = (
            await bd.execute(
                select(SesionNegociacion, Evento)
                .join(Evento, Evento.id == SesionNegociacion.evento_id)
                .where(
                    SesionNegociacion.resultado_avisado_en.is_(None),
                    Evento.estado.in_(("adjudicado", "desierto")),
                )
                .order_by(SesionNegociacion.id)
                .with_for_update(of=SesionNegociacion, skip_locked=True)
            )
        ).all()
        for sesion, evento in pendientes:
            sesion.resultado_avisado_en = momento
            if sesion.destinatario:
                await _avisar(bd, enviar, config, evento, sesion, momento)
    return len(pendientes)
