"""La acción de cada registro de la bitácora en lenguaje llano.

Son los mismos textos que `web/src/actividad.ts`; una prueba verifica que ambos cubren los mismos
tipos.
"""

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal

from administracion.modelos import Actividad

NOMBRES_ROL = {"admin": "Administración", "comprador": "Compras", "aprobador": "Aprobación"}
ERRORES_SESION = {
    "invalid_user_credentials": "contraseña incorrecta",
    "user_not_found": "usuario inexistente",
    "user_disabled": "cuenta desactivada",
    "user_temporarily_disabled": "cuenta bloqueada temporalmente",
}
# Un alta que quedó a medias trae en el detalle qué faltó.
PENDIENTES = {"roles": "; faltó asignar los roles", "contrasena": "; faltó la contraseña"}


def _roles(valor: object) -> str:
    if not isinstance(valor, list):
        return ""
    return ", ".join(NOMBRES_ROL.get(str(r), str(r)) for r in valor)


def _numero(valor: object) -> str:
    """Como toLocaleString("es-MX"): separador de miles con coma."""
    return f"{int(valor):,}" if isinstance(valor, int | float) else "0"


def _sesion_fallida(a: Actividad) -> str:
    motivo = ERRORES_SESION.get(str(a.detalle.get("error", "")))
    return (
        f"Intento fallido de inicio de sesión: {motivo}"
        if motivo
        else "Intento fallido de inicio de sesión"
    )


NOMBRES_AJUSTE = {
    "umbral_riesgo": "umbral de riesgo",
    "inflacion_anual": "inflación anual",
    "adjudicacion_costo": "peso del costo en la adjudicación",
    "adjudicacion_desempeno": "peso del desempeño en la adjudicación",
    "adjudicacion_riesgo": "peso del riesgo en la adjudicación",
    "adjudicacion_sla": "peso del SLA en la adjudicación",
    "umbral_aprobacion": "umbral de aprobación",
}
CONFIGURACION = "Cambió la configuración de la puntuación"


def _ajustes(a: Actividad) -> str:
    """Los campos cambiados en lenguaje llano; los cinco pesos se nombran una vez."""
    cambios = a.detalle.get("cambios")
    nombres: list[str] = []
    for cambio in cambios if isinstance(cambios, list) else []:
        campo = str(cambio.get("campo", "")) if isinstance(cambio, dict) else ""
        nombre = "pesos" if campo.startswith("peso_") else NOMBRES_AJUSTE.get(campo, campo)
        if nombre not in nombres:
            nombres.append(nombre)
    return f"{CONFIGURACION}: {', '.join(nombres)}" if nombres else CONFIGURACION


def _entrenamiento(a: Actividad) -> str:
    mape = a.detalle.get("mape")
    # Medio hacia arriba, como toFixed en la web; f"{x:.1f}" redondea al par (11.25 → 11.2).
    porcentaje = (
        str(Decimal(mape * 100).quantize(Decimal("0.1"), ROUND_HALF_UP))
        if isinstance(mape, int | float)
        else "?"
    )
    resultado = (
        "promovido" if a.detalle.get("promovido") else "no se promovió (no mejoró la línea base)"
    )
    return (
        f"Reentrenó el modelo de precios: versión {a.detalle.get('version', '?')}, "
        f"MAPE {porcentaje} %, {resultado}"
    )


def _proveedores(valor: object) -> str:
    cuantos = valor if isinstance(valor, int) else 0
    return "1 proveedor" if cuantos == 1 else f"{cuantos} proveedores"


def _invitacion(a: Actividad) -> str:
    proveedor = a.detalle.get("proveedor", "")
    if a.detalle.get("estado") == "fallido":
        return f"No se pudo enviar a {proveedor} la invitación a negociar {a.objeto_nombre}"
    accion = "Reenvió" if a.detalle.get("reenvio") else "Envió"
    return f"{accion} a {proveedor} la invitación a negociar {a.objeto_nombre}"


APROBACIONES = {"directa": " (directa)", "aprobada": " (aprobada)"}


def _adjudicada(a: Actividad) -> str:
    proveedor = a.detalle.get("proveedor", "")
    aprobacion = APROBACIONES.get(str(a.detalle.get("aprobacion")), "")
    return f"Adjudicó la negociación {a.objeto_nombre} a {proveedor}{aprobacion}"


def _desierta(a: Actividad) -> str:
    motivo = a.detalle.get("motivo")
    # La automática la publica el sistema (sin actor_id); un comprador puede escribir lo mismo.
    if motivo == "sin_acuerdos" and a.actor_id is None:
        return (
            f"La negociación {a.objeto_nombre} quedó desierta: ningún proveedor llegó a un acuerdo"
        )
    texto = f"Declaró desierta la negociación {a.objeto_nombre}"
    return f"{texto}: {motivo}" if motivo else texto


def _resultado(a: Actividad) -> str:
    proveedor = a.detalle.get("proveedor", "")
    if a.detalle.get("estado") == "fallido":
        return f"No se pudo enviar a {proveedor} el resultado de la negociación {a.objeto_nombre}"
    return f"Envió a {proveedor} el resultado de la negociación {a.objeto_nombre}"


TEXTOS: dict[str, Callable[[Actividad], str]] = {
    "sesion.iniciada": lambda a: "Inició sesión",
    "sesion.fallida": _sesion_fallida,
    "sesion.cerrada": lambda a: "Cerró sesión",
    "usuario.creado": lambda a: f"Dio de alta a {a.objeto_nombre}",
    "usuario.actualizado": lambda a: f"Editó los datos de {a.objeto_nombre}",
    "usuario.roles_cambiados": lambda a: (
        f"Cambió los roles de {a.objeto_nombre}: "
        f"{_roles(a.detalle.get('antes'))} → {_roles(a.detalle.get('despues'))}"
    ),
    "usuario.desactivado": lambda a: f"Desactivó a {a.objeto_nombre}",
    "usuario.activado": lambda a: f"Activó a {a.objeto_nombre}",
    "usuario.correo_contrasena": lambda a: (
        f"Envió a {a.objeto_nombre} un correo para definir su contraseña"
    ),
    "usuario.contrasena_temporal": lambda a: f"Asignó una contraseña temporal a {a.objeto_nombre}",
    "usuario.sesiones_cerradas": lambda a: f"Cerró las sesiones de {a.objeto_nombre}",
    "importacion.completada": lambda a: (
        f"Importó {_numero(a.detalle.get('registros'))} {a.objeto_nombre}"
    ),
    "importacion.rechazada": lambda a: (
        f"Intentó importar {a.objeto_nombre}; el archivo tenía "
        f"{_numero(a.detalle.get('errores'))} errores"
    ),
    "servicio.creado": lambda a: f"Dio de alta el servicio {a.objeto_nombre}",
    "servicio.actualizado": lambda a: f"Editó el servicio {a.objeto_nombre}",
    "servicio.desactivado": lambda a: f"Desactivó el servicio {a.objeto_nombre}",
    "servicio.activado": lambda a: f"Activó el servicio {a.objeto_nombre}",
    "configuracion.actualizada": _ajustes,
    "modelo.entrenado": _entrenamiento,
    "negociacion.publicada": lambda a: (
        f"Publicó la negociación {a.objeto_nombre} con {_proveedores(a.detalle.get('proveedores'))}"
    ),
    "negociacion.cancelada": lambda a: (
        f"Canceló la negociación {a.objeto_nombre}: {a.detalle.get('motivo', '')}"
    ),
    "negociacion.invitacion_enviada": _invitacion,
    "negociacion.adjudicada": _adjudicada,
    "negociacion.desierta": _desierta,
    "negociacion.resultado_enviado": _resultado,
}


def describir(actividad: Actividad) -> str:
    """La acción en lenguaje llano; un tipo desconocido se muestra tal cual."""
    texto = TEXTOS.get(actividad.tipo)
    if texto is None:
        return actividad.tipo
    return texto(actividad) + PENDIENTES.get(str(actividad.detalle.get("pendiente")), "")
