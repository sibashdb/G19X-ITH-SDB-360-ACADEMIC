"""La acción de cada registro de la bitácora en lenguaje llano.

Son los mismos textos que `web/src/actividad.ts`; una prueba verifica que ambos cubren los mismos
tipos.
"""

from collections.abc import Callable

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
}


def describir(actividad: Actividad) -> str:
    """La acción en lenguaje llano; un tipo desconocido se muestra tal cual."""
    texto = TEXTOS.get(actividad.tipo)
    if texto is None:
        return actividad.tipo
    return texto(actividad) + PENDIENTES.get(str(actividad.detalle.get("pendiente")), "")
