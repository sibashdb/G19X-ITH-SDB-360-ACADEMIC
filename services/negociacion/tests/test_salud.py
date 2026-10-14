import httpx
import pytest

pytestmark = pytest.mark.integracion


async def test_listo_con_postgres(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/salud/listo")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "dependencias": {"postgres": "ok"}}
