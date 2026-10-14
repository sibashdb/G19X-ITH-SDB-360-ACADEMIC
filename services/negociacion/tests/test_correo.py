from datetime import UTC, datetime

from negociacion.correo import invitacion
from negociacion.publicacion import enlace


def test_la_invitacion_lleva_el_enlace_y_la_fecha_limite_en_hora_de_mexico() -> None:
    url = enlace("http://localhost:8080/", "abc123")
    assert url == "http://localhost:8080/portal#t=abc123"
    mensaje = invitacion(
        remitente="compras@plataforma.example",
        destinatario="lucia@nubenorte.example",
        contacto="Lucía Pérez",
        titulo="Licencias de CRM 2027",
        folio="NEG-2026-0001",
        fecha_limite=datetime(2026, 10, 20, 15, tzinfo=UTC),
        enlace=url,
    )
    assert mensaje["Subject"] == "Invitación a negociar: Licencias de CRM 2027 (NEG-2026-0001)"
    assert mensaje["To"] == "lucia@nubenorte.example"
    cuerpo = mensaje.get_content()
    assert "Estimado(a) Lucía Pérez:" in cuerpo
    assert url in cuerpo
    assert "20/10/2026 a las 09:00" in cuerpo  # 15:00 UTC son las 09:00 en la Ciudad de México
    assert "El enlace es personal" in cuerpo
