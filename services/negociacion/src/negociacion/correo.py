"""Correo de invitación a negociar (SMTP; Mailpit en desarrollo)."""

import asyncio
import smtplib
from collections.abc import Awaitable, Callable
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

EnviarCorreo = Callable[[EmailMessage], Awaitable[None]]
ZONA = ZoneInfo("America/Mexico_City")
TIEMPO_ESPERA_S = 10
NO_ENTREGADO = "No se pudo entregar el correo al servidor de correo."


def invitacion(
    *,
    remitente: str,
    destinatario: str,
    contacto: str,
    titulo: str,
    folio: str,
    fecha_limite: datetime,
    enlace: str,
) -> EmailMessage:
    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = f"Invitación a negociar: {titulo} ({folio})"
    limite = fecha_limite.astimezone(ZONA).strftime("%d/%m/%Y a las %H:%M")
    mensaje.set_content(
        f"Estimado(a) {contacto}:\n\n"
        f"Lo invitamos a presentar su oferta para «{titulo}» (folio {folio}).\n\n"
        f"Puede negociar en línea hasta el {limite} (hora de la Ciudad de México) en este "
        f"enlace:\n{enlace}\n\n"
        "El enlace es personal: no lo comparta. En el portal también puede pedir hablar con una "
        "persona del equipo de compras.\n"
    )
    return mensaje


def enviador_smtp(host: str, puerto: int) -> EnviarCorreo:
    """Manda el correo en un hilo aparte: smtplib es bloqueante."""

    def _enviar(mensaje: EmailMessage) -> None:
        with smtplib.SMTP(host, puerto, timeout=TIEMPO_ESPERA_S) as smtp:
            smtp.send_message(mensaje)

    async def enviar(mensaje: EmailMessage) -> None:
        await asyncio.to_thread(_enviar, mensaje)

    return enviar
