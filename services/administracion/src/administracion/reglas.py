"""Reglas de la gestión de usuarios, independientes de Keycloak y de la base de datos."""

import secrets
import string

from administracion.identidad import UsuarioIdentidad

LONGITUD_TEMPORAL = 16
SIMBOLOS = "!#$%&*+-=?@_"


class ReglaProteccion(Exception):
    """Cambio prohibido para no dejar la plataforma sin administración.

    El mensaje es para la persona.
    """


def generar_contrasena_temporal() -> str:
    """16 caracteres con al menos una mayúscula, una minúscula, un dígito y un símbolo."""
    clases = [string.ascii_uppercase, string.ascii_lowercase, string.digits, SIMBOLOS]
    caracteres = [secrets.choice(clase) for clase in clases]
    todos = "".join(clases)
    caracteres += [secrets.choice(todos) for _ in range(LONGITUD_TEMPORAL - len(clases))]
    secrets.SystemRandom().shuffle(caracteres)
    return "".join(caracteres)


def _admins_activos(usuarios: list[UsuarioIdentidad]) -> set[str]:
    return {u.id for u in usuarios if u.activo and "admin" in u.roles}


def verificar_desactivacion(
    actor_id: str, objetivo: UsuarioIdentidad, usuarios: list[UsuarioIdentidad]
) -> None:
    if objetivo.id == actor_id:
        raise ReglaProteccion("No puede desactivar su propia cuenta.")
    if _admins_activos(usuarios) == {objetivo.id}:
        raise ReglaProteccion("Debe quedar al menos un administrador activo.")


def verificar_cambio_de_roles(
    actor_id: str,
    objetivo: UsuarioIdentidad,
    roles_nuevos: frozenset[str],
    usuarios: list[UsuarioIdentidad],
) -> None:
    if "admin" in roles_nuevos or "admin" not in objetivo.roles:
        return
    if objetivo.id == actor_id:
        raise ReglaProteccion("No puede quitarse el rol de administrador.")
    if _admins_activos(usuarios) == {objetivo.id}:
        raise ReglaProteccion("Debe quedar al menos un administrador activo.")
