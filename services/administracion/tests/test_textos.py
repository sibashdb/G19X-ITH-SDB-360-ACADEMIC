import re
from pathlib import Path

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
