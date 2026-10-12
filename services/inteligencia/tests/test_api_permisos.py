import re

import httpx
import pytest
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI

pytestmark = pytest.mark.integracion

SOLO_ADMIN = {
    ("PUT", "/configuracion"),
    ("POST", "/modelos/entrenar"),
    ("GET", "/datos"),
}


async def test_todas_las_rutas_exigen_su_rol(
    app: FastAPI, cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    externo = {"Authorization": f"Bearer {claves.token('proveedor')}"}
    comprador = {"Authorization": f"Bearer {claves.token('comprador')}"}
    # app.routes no aplana los routers incluidos: se recorre el esquema OpenAPI.
    rutas = [
        (metodo.upper(), ruta)
        for ruta, metodos in app.openapi()["paths"].items()
        if not ruta.startswith("/salud")
        for metodo in metodos
    ]
    assert len(rutas) >= 15  # que el recorrido no quede vacío si cambia cómo se declaran
    assert SOLO_ADMIN <= set(rutas)
    for metodo, plantilla in rutas:
        ruta = re.sub(r"\{[^}]+\}", "x", plantilla)
        sin_token = await cliente.request(metodo, ruta)
        assert sin_token.status_code == 401, (metodo, plantilla)
        de_externo = await cliente.request(metodo, ruta, headers=externo)
        assert de_externo.status_code == 403, (metodo, plantilla)
        if (metodo, plantilla) in SOLO_ADMIN:
            de_comprador = await cliente.request(metodo, ruta, headers=comprador)
            assert de_comprador.status_code == 403, (metodo, plantilla)
