import re
from pathlib import Path

import pytest
from administracion.modelos import Actividad
from administracion.textos import TEXTOS, describir

WEB = Path(__file__).resolve().parents[3] / "web" / "src" / "actividad.ts"


def _actividad(tipo: str, **campos: object) -> Actividad:
    return Actividad(
        tipo=tipo,
        actor_nombre="admin1",
        objeto_nombre=campos.pop("objeto_nombre", "Ana López"),
        detalle=campos.pop("detalle", {}),
    )


def test_los_mismos_tipos_que_la_web() -> None:
    bloque = re.search(
        r"TIPOS_ACTIVIDAD = \[(.*?)\] as const", WEB.read_text(encoding="utf-8"), re.S
    )
    assert bloque is not None
    assert set(re.findall(r'"([a-z_.]+)"', bloque.group(1))) == set(TEXTOS)


def test_textos_en_lenguaje_llano() -> None:
    assert describir(_actividad("sesion.fallida", detalle={"error": "user_disabled"})) == (
        "Intento fallido de inicio de sesión: cuenta desactivada"
    )
    assert describir(
        _actividad(
            "usuario.roles_cambiados", detalle={"antes": ["comprador"], "despues": ["admin"]}
        )
    ) == ("Cambió los roles de Ana López: Compras → Administración")
    assert describir(
        _actividad("importacion.completada", objeto_nombre="contratos", detalle={"registros": 1250})
    ) == ("Importó 1,250 contratos")
    assert describir(
        _actividad("importacion.rechazada", objeto_nombre="proveedores", detalle={"errores": 3})
    ) == ("Intentó importar proveedores; el archivo tenía 3 errores")
    assert describir(_actividad("usuario.creado", detalle={"pendiente": "roles"})) == (
        "Dio de alta a Ana López; faltó asignar los roles"
    )
    assert describir(_actividad("servicio.desactivado", objeto_nombre="SOP-MESA-TK")) == (
        "Desactivó el servicio SOP-MESA-TK"
    )
    assert describir(_actividad("tipo.desconocido")) == "tipo.desconocido"


SESION_FALLIDA = "Intento fallido de inicio de sesión"
# (tipo, objeto_nombre, detalle, texto): cada texto copiado de web/src/actividad.ts.
CASOS: list[tuple[str, str, dict[str, object], str]] = [
    ("sesion.iniciada", "", {}, "Inició sesión"),
    ("sesion.fallida", "", {}, SESION_FALLIDA),
    (
        "sesion.fallida",
        "",
        {"error": "invalid_user_credentials"},
        f"{SESION_FALLIDA}: contraseña incorrecta",
    ),
    ("sesion.fallida", "", {"error": "user_not_found"}, f"{SESION_FALLIDA}: usuario inexistente"),
    (
        "sesion.fallida",
        "",
        {"error": "user_temporarily_disabled"},
        f"{SESION_FALLIDA}: cuenta bloqueada temporalmente",
    ),
    ("sesion.fallida", "", {"error": "otro_error"}, SESION_FALLIDA),
    ("sesion.cerrada", "", {}, "Cerró sesión"),
    ("usuario.creado", "Ana López", {}, "Dio de alta a Ana López"),
    (
        "usuario.creado",
        "Ana López",
        {"pendiente": "contrasena"},
        "Dio de alta a Ana López; faltó la contraseña",
    ),
    ("usuario.actualizado", "Ana López", {}, "Editó los datos de Ana López"),
    (
        "usuario.roles_cambiados",
        "Ana López",
        {"antes": ["aprobador", "comprador"], "despues": ["admin", "rol_nuevo"]},
        "Cambió los roles de Ana López: Aprobación, Compras → Administración, rol_nuevo",
    ),
    ("usuario.desactivado", "Ana López", {}, "Desactivó a Ana López"),
    ("usuario.activado", "Ana López", {}, "Activó a Ana López"),
    (
        "usuario.correo_contrasena",
        "Ana López",
        {},
        "Envió a Ana López un correo para definir su contraseña",
    ),
    (
        "usuario.contrasena_temporal",
        "Ana López",
        {},
        "Asignó una contraseña temporal a Ana López",
    ),
    ("usuario.sesiones_cerradas", "Ana López", {}, "Cerró las sesiones de Ana López"),
    ("importacion.completada", "proveedores", {"registros": 7}, "Importó 7 proveedores"),
    ("importacion.completada", "proveedores", {}, "Importó 0 proveedores"),
    (
        "importacion.rechazada",
        "contratos",
        {"errores": 1},
        "Intentó importar contratos; el archivo tenía 1 errores",
    ),
    ("servicio.creado", "SOP-CRM-LIC", {}, "Dio de alta el servicio SOP-CRM-LIC"),
    ("servicio.actualizado", "SOP-CRM-LIC", {}, "Editó el servicio SOP-CRM-LIC"),
    ("servicio.desactivado", "SOP-CRM-LIC", {}, "Desactivó el servicio SOP-CRM-LIC"),
    ("servicio.activado", "SOP-CRM-LIC", {}, "Activó el servicio SOP-CRM-LIC"),
    (
        "configuracion.actualizada",
        "configuración de la puntuación",
        {
            "cambios": [
                {"campo": "peso_sla", "anterior": 30, "nuevo": 40},
                {"campo": "peso_satisfaccion", "anterior": 15, "nuevo": 5},
                {"campo": "umbral_riesgo", "anterior": 40, "nuevo": 35},
                {"campo": "inflacion_anual", "anterior": "4.50", "nuevo": "5.20"},
            ]
        },
        "Cambió la configuración de la puntuación: pesos, umbral de riesgo, inflación anual",
    ),
    (
        "configuracion.actualizada",
        "configuración de la puntuación",
        {},
        "Cambió la configuración de la puntuación",
    ),
    (
        "modelo.entrenado",
        "modelo de precios v4",
        {"version": 4, "mape": 0.112, "promovido": True},
        "Reentrenó el modelo de precios: versión 4, MAPE 11.2 %, promovido",
    ),
    (
        "modelo.entrenado",
        "modelo de precios v5",
        {"version": 5, "mape": 0.0934, "promovido": False},
        "Reentrenó el modelo de precios: versión 5, MAPE 9.3 %, no se promovió "
        "(no mejoró la línea base)",
    ),
    # Un empate exacto (11.25) sube, como toFixed en la web; el redondeo de Python lo bajaría.
    (
        "modelo.entrenado",
        "modelo de precios v6",
        {"version": 6, "mape": 0.1125, "promovido": True},
        "Reentrenó el modelo de precios: versión 6, MAPE 11.3 %, promovido",
    ),
]


def test_la_tabla_cubre_todos_los_tipos() -> None:
    assert {tipo for tipo, *_ in CASOS} == set(TEXTOS)


@pytest.mark.parametrize(
    ("tipo", "objeto", "detalle", "esperado"), CASOS, ids=[caso[0] for caso in CASOS]
)
def test_cada_texto_igual_al_de_la_web(
    tipo: str, objeto: str, detalle: dict[str, object], esperado: str
) -> None:
    assert describir(_actividad(tipo, objeto_nombre=objeto, detalle=detalle)) == esperado
