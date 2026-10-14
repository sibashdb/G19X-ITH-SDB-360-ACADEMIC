import re

import httpx
import pytest
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI

pytestmark = pytest.mark.integracion
UUID = "00000000-0000-4000-8000-000000000000"
# Las tareas que agregan rutas del comprador las suman aquí.
ESPERADAS = {
    ("POST", "/eventos"),
    ("GET", "/eventos"),
    ("GET", "/eventos/{evento_id}"),
    ("PATCH", "/eventos/{evento_id}"),
    ("POST", "/eventos/{evento_id}/publicar"),
    ("POST", "/eventos/{evento_id}/cancelar"),
    ("POST", "/sesiones/{sesion_id}/invitacion"),
}


async def test_las_rutas_del_comprador_exigen_su_rol(
    app: FastAPI, cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    externo = {"Authorization": f"Bearer {claves.token('proveedor')}"}
    aprobador = {"Authorization": f"Bearer {claves.token('aprobador')}"}
    # app.routes no aplana los routers incluidos: se recorre el esquema OpenAPI.
    rutas = [
        (metodo.upper(), ruta)
        for ruta, metodos in app.openapi()["paths"].items()
        if not ruta.startswith(("/salud", "/portal"))
        for metodo in metodos
    ]
    assert ESPERADAS <= set(rutas)
    for metodo, plantilla in rutas:
        ruta = re.sub(r"\{[^}]+\}", UUID, plantilla)
        sin_token = await cliente.request(metodo, ruta)
        assert sin_token.status_code == 401, (metodo, plantilla)
        de_externo = await cliente.request(metodo, ruta, headers=externo)
        assert de_externo.status_code == 403, (metodo, plantilla)
        if metodo != "GET":  # aprobador y admin solo consultan
            de_aprobador = await cliente.request(metodo, ruta, headers=aprobador)
            assert de_aprobador.status_code == 403, (metodo, plantilla)


async def test_el_portal_no_acepta_jwt(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    comprador = {"Authorization": f"Bearer {claves.token('comprador')}"}
    for metodo, ruta in (
        ("GET", "/portal/sesion"),
        ("POST", "/portal/ofertas"),
        ("POST", "/portal/escalar"),
    ):
        respuesta = await cliente.request(metodo, ruta, headers=comprador)
        assert respuesta.status_code == 401, ruta
