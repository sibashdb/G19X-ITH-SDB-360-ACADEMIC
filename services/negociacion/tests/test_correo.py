from datetime import UTC, datetime

import pytest
from negociacion import correo
from negociacion.api.esquemas import Resultado
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


@pytest.mark.parametrize(
    ("resultado", "texto"),
    [
        ("adjudicada", "Su oferta fue adjudicada; el equipo de compras se pondrá en contacto."),
        ("no_elegida", "La negociación se adjudicó a otra propuesta."),
        ("desierta", "La negociación se declaró desierta."),
    ],
)
def test_el_resultado_dice_solo_lo_que_le_toca_al_proveedor(
    resultado: Resultado, texto: str
) -> None:
    mensaje = correo.resultado(
        remitente="compras@plataforma.example",
        destinatario="lucia@nubenorte.example",
        contacto="Lucía Pérez",
        titulo="Licencias de CRM 2027",
        folio="NEG-2026-0001",
        resultado=resultado,
    )
    assert mensaje["Subject"] == "Resultado de la negociación NEG-2026-0001"
    assert mensaje["To"] == "lucia@nubenorte.example"
    cuerpo = mensaje.get_content()
    assert "Estimado(a) Lucía Pérez:" in cuerpo
    assert "«Licencias de CRM 2027» (folio NEG-2026-0001)" in cuerpo
    assert texto in cuerpo
    assert "http" not in cuerpo  # sin enlace: el portal ya lo tiene el proveedor
