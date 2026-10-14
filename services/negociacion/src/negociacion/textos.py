"""Textos del servicio: nombres de las palancas y mensajes del agente."""

from collections.abc import Mapping

from negociacion.dominio.motor import Decision

CANCELADA = "La negociación se canceló. Gracias por su tiempo."
CONTRAOFERTA = "Gracias por su oferta. Le proponemos los términos que aparecen en la propuesta."
MEJOR_OFERTA = "Hemos recibido propuestas más competitivas."
ULTIMA_RONDA = "La siguiente ronda es la última: envíe su mejor y última oferta."
ACUERDO = (
    "Gracias. Su oferta quedó registrada como acuerdo tentativo; no es vinculante hasta que se "
    "apruebe la adjudicación."
)
SIN_ACUERDO = "Gracias por su tiempo. En esta ocasión no fue posible llegar a un acuerdo."
EN_REVISION = "Una persona del equipo de compras revisará su oferta y le responderá."
ESCALADA = "Avisamos al equipo de compras; una persona le responderá aquí."
PIDE_PERSONA = "Pidió hablar con una persona del equipo de compras."

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


def _unir(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def respuesta_del_agente(decision: Decision, nombres: Mapping[str, str]) -> str:
    """Mensaje del agente (plantillas de N1): nunca lleva límites, pesos, utilidades ni cifras."""
    if decision.accion == "aceptar":
        return ACUERDO
    if decision.accion == "cerrar_sin_acuerdo":
        return SIN_ACUERDO
    if decision.accion == "pedir_aclaracion":
        lineas = [nombres[i] for i in decision.dudosas]
        if len(lineas) == 1:
            return (
                f"El precio de {lineas[0]} parece fuera de lo usual. Si es correcto, márquelo "
                "como confirmado y envíelo de nuevo."
            )
        return (
            f"Los precios de {_unir(lineas)} parecen fuera de lo usual. Si son correctos, "
            "márquelos como confirmados y envíelos de nuevo."
        )
    partes = [CONTRAOFERTA]
    if decision.traza.get("hay_mejor_oferta"):
        partes.append(MEJOR_OFERTA)
    if decision.ultima_ronda:
        partes.append(ULTIMA_RONDA)
    return " ".join(partes)
