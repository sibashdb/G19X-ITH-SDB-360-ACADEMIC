import csv
import io
from datetime import UTC, datetime

import httpx
import pytest
from administracion.bitacora import Actor, Objeto, registrar
from comun.pruebas import ClavesPrueba
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


@pytest.fixture
async def sembrada(fabrica: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica() as sesion:
        # 05:30 UTC del 8 de octubre = 23:30 del 7 de octubre en la Ciudad de México.
        await registrar(
            sesion,
            "sesion.iniciada",
            Actor("ana", "ana"),
            origen="keycloak",
            clave_origen="k:1",
            fecha=datetime(2026, 10, 8, 5, 30, tzinfo=UTC),
        )
        await registrar(
            sesion,
            "usuario.desactivado",
            Actor("admin-1", "admin1"),
            objeto=Objeto("usuario", "ana", "Ana López"),
            fecha=datetime(2026, 10, 8, 18, 0, tzinfo=UTC),
        )
        await sesion.commit()


@pytest.mark.usefixtures("sembrada")
async def test_filtros_y_dia_en_hora_de_mexico(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    del7 = (
        await cliente.get(
            "/actividad", params={"desde": "2026-10-07", "hasta": "2026-10-07"}, headers=admin
        )
    ).json()
    assert [e["tipo"] for e in del7["elementos"]] == ["sesion.iniciada"]
    persona = (await cliente.get("/actividad", params={"persona": "ana"}, headers=admin)).json()
    assert persona["total"] == 2
    usuarios = (await cliente.get("/actividad", params={"tipo": "usuarios"}, headers=admin)).json()
    assert [e["objeto_nombre"] for e in usuarios["elementos"]] == ["Ana López"]


async def test_filtro_de_inteligencia(
    cliente: httpx.AsyncClient, admin: dict[str, str], fabrica: async_sessionmaker[AsyncSession]
) -> None:
    async with fabrica() as sesion:
        await registrar(
            sesion,
            "configuracion.actualizada",
            Actor("admin-1", "admin1"),
            objeto=Objeto("configuracion", "puntuacion", "configuración de la puntuación"),
            origen="inteligencia",
        )
        await registrar(
            sesion,
            "modelo.entrenado",
            Actor(None, "Sistema (automático)"),
            objeto=Objeto("modelo", "1", "modelo de precios v1"),
            detalle={"version": 1, "mape": 0.08, "promovido": True},
            origen="inteligencia",
        )
        await registrar(
            sesion,
            "servicio.creado",
            Actor("admin-1", "admin1"),
            objeto=Objeto("servicio", "SOP-X", "SOP-X"),
            origen="proveedores",
        )
        await sesion.commit()
    cuerpo = (
        await cliente.get("/actividad", params={"tipo": "inteligencia"}, headers=admin)
    ).json()
    assert sorted(e["tipo"] for e in cuerpo["elementos"]) == [
        "configuracion.actualizada",
        "modelo.entrenado",
    ]


async def test_filtro_de_negociacion(
    cliente: httpx.AsyncClient, admin: dict[str, str], fabrica: async_sessionmaker[AsyncSession]
) -> None:
    async with fabrica() as sesion:
        await registrar(
            sesion,
            "negociacion.publicada",
            Actor("c-1", "comprador1"),
            objeto=Objeto("negociacion", "NEG-2026-0001", "NEG-2026-0001 «CRM 2027»"),
            detalle={"proveedores": 2},
            origen="negociacion",
        )
        await registrar(
            sesion,
            "servicio.creado",
            Actor("admin-1", "admin1"),
            objeto=Objeto("servicio", "SOP-X", "SOP-X"),
            origen="proveedores",
        )
        await sesion.commit()
    cuerpo = (await cliente.get("/actividad", params={"tipo": "negociacion"}, headers=admin)).json()
    assert [e["tipo"] for e in cuerpo["elementos"]] == ["negociacion.publicada"]


async def test_rango_invertido(cliente: httpx.AsyncClient, admin: dict[str, str]) -> None:
    respuesta = await cliente.get(
        "/actividad", params={"desde": "2026-10-08", "hasta": "2026-10-01"}, headers=admin
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        {"campo": "hasta", "mensaje": "Debe ser igual o posterior a la fecha inicial"}
    ]


async def test_solo_admin(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    comprador = {"Authorization": f"Bearer {claves.token('comprador')}"}
    assert (await cliente.get("/actividad", headers=comprador)).status_code == 403


@pytest.mark.parametrize(
    ("params", "campo"),
    [({"hasta": "9999-12-31"}, "hasta"), ({"desde": "1999-12-31"}, "desde")],
)
async def test_fechas_fuera_de_rango(
    cliente: httpx.AsyncClient, admin: dict[str, str], params: dict[str, str], campo: str
) -> None:
    for ruta in ("/actividad", "/actividad/exportar"):
        respuesta = await cliente.get(ruta, params=params, headers=admin)
        assert respuesta.status_code == 422, ruta
        assert respuesta.json()["errores"] == [
            {"campo": campo, "mensaje": "Use una fecha entre 2000-01-01 y 2100-12-31."}
        ]


def _filas_csv(respuesta: httpx.Response) -> list[list[str]]:
    assert respuesta.content.startswith(b"\xef\xbb\xbf")  # BOM: Excel lo abre como UTF-8
    return list(csv.reader(io.StringIO(respuesta.content.decode("utf-8-sig"))))


@pytest.mark.usefixtures("sembrada")
async def test_exportar_csv_en_hora_de_mexico(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    respuesta = await cliente.get("/actividad/exportar", headers=admin)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "text/csv; charset=utf-8"
    assert respuesta.headers["content-disposition"] == 'attachment; filename="actividad.csv"'
    assert respuesta.headers["x-total-registros"] == "2"
    assert _filas_csv(respuesta) == [
        ["Fecha", "Persona", "Acción", "Resultado", "IP"],
        ["2026-10-08 12:00", "admin1", "Desactivó a Ana López", "Éxito", ""],
        ["2026-10-07 23:30", "ana", "Inició sesión", "Éxito", ""],
    ]


@pytest.mark.usefixtures("sembrada")
async def test_exportar_respeta_los_filtros(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    respuesta = await cliente.get("/actividad/exportar", params={"tipo": "sesiones"}, headers=admin)
    assert [fila[2] for fila in _filas_csv(respuesta)[1:]] == ["Inició sesión"]


async def test_exportar_neutraliza_formulas(
    cliente: httpx.AsyncClient, admin: dict[str, str], fabrica: async_sessionmaker[AsyncSession]
) -> None:
    async with fabrica() as sesion:
        await registrar(
            sesion,
            "sesion.fallida",
            Actor(None, '=HIPERVINCULO("http://x.example")'),
            detalle={"error": "user_not_found"},
            resultado="fallo",
            origen="keycloak",
            clave_origen="k:formula",
        )
        await sesion.commit()
    [_, fila] = _filas_csv(await cliente.get("/actividad/exportar", headers=admin))
    assert fila[1] == '\'=HIPERVINCULO("http://x.example")'
    assert fila[3] == "Falló"


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("+52 55", "'+52 55"),
        ("-1+1", "'-1+1"),
        ("@SUMA(1)", "'@SUMA(1)"),
        ("\tx", "'\tx"),
        ("\rx", "'\rx"),
        ("ana-lopez", "ana-lopez"),  # solo importa el primer carácter
    ],
)
async def test_exportar_neutraliza_cada_inicio_de_formula(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    fabrica: async_sessionmaker[AsyncSession],
    nombre: str,
    esperado: str,
) -> None:
    async with fabrica() as sesion:
        await registrar(sesion, "sesion.cerrada", Actor(None, nombre), clave_origen="k:celda")
        await sesion.commit()
    [_, fila] = _filas_csv(await cliente.get("/actividad/exportar", headers=admin))
    assert fila[1] == esperado


@pytest.mark.usefixtures("sembrada")
async def test_exportar_hasta_el_limite_con_las_mas_recientes(
    cliente: httpx.AsyncClient, admin: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("administracion.api.rutas.MAX_FILAS_EXPORTACION", 1)
    respuesta = await cliente.get("/actividad/exportar", headers=admin)
    assert respuesta.headers["x-total-registros"] == "2"
    assert [fila[2] for fila in _filas_csv(respuesta)[1:]] == ["Desactivó a Ana López"]
