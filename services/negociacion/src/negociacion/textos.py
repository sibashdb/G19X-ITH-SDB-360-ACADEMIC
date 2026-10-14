"""Textos del servicio: nombres de las palancas (y, desde la Task 9, mensajes del agente)."""

CANCELADA = "La negociación se canceló. Gracias por su tiempo."

PALANCAS: dict[str, tuple[str, str | None]] = {
    "precio": ("Precio unitario", None),
    "plazo_meses": ("Plazo del contrato", "meses"),
    "plazo_pago_dias": ("Plazo de pago", "días"),
    "sla_disponibilidad": ("Disponibilidad garantizada (SLA)", "%"),
    "tope_aumento_pct": ("Tope de aumento anual", "%"),
    "cuota_implementacion": ("Cuota de implementación", None),
}


def nombre_y_unidad(clave: str, moneda: str) -> tuple[str, str]:
    """El nombre de la palanca y su unidad; los montos se miden en la moneda del evento."""
    nombre, unidad = PALANCAS[clave]
    return nombre, unidad or moneda
