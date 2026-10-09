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
