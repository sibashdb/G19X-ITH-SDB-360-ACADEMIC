import httpx
import pytest
from comun.pruebas import ClavesPrueba

pytestmark = pytest.mark.integracion


async def test_correos_vacio_con_enlace_al_buzon(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await cliente.get(
        "/correos", headers={"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}
    )
    assert respuesta.json() == {"total": 0, "elementos": [], "buzon_url": "http://buzon:8025"}
