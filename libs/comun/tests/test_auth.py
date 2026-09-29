import time
from typing import Annotated, Any

import pytest
from comun.auth import Usuario, requiere_rol, usuario_actual, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.pruebas import ClavesPrueba
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import Response

claves = ClavesPrueba()


def _app() -> FastAPI:
    app = FastAPI()
    registrar_manejadores(app)
    app.state.validador = claves.validador()

    @app.get("/yo")
    def yo(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> dict[str, Any]:
        return {"id": usuario.id, "nombre": usuario.nombre, "roles": sorted(usuario.roles)}

    @app.get("/solo-admin")
    def solo_admin(usuario: Annotated[Usuario, Depends(requiere_rol("admin"))]) -> dict[str, str]:
        return {"id": usuario.id}

    return app


cliente = TestClient(_app())


def _get(ruta: str, token: str | None = None) -> Response:
    cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.get(ruta, headers=cabeceras)


def test_token_valido_devuelve_usuario_y_roles() -> None:
    respuesta = _get("/yo", claves.token("comprador", sub="u-1"))
    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": "u-1", "nombre": "u-1", "roles": ["comprador"]}


def test_sin_token_responde_401_con_www_authenticate() -> None:
    respuesta = _get("/yo")
    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "extra",
    [{"exp": int(time.time()) - 10}, {"iss": "http://otro-emisor"}, {"aud": "otra-api"}],
    ids=["vencido", "otro-emisor", "otra-audiencia"],
)
def test_token_vencido_o_ajeno_responde_401(extra: dict[str, Any]) -> None:
    assert _get("/yo", claves.token("admin", **extra)).status_code == 401


def test_token_firmado_con_otra_clave_responde_401() -> None:
    assert _get("/yo", ClavesPrueba().token("admin")).status_code == 401


def test_token_basura_responde_401() -> None:
    assert _get("/yo", "no-es-un-jwt").status_code == 401


def test_rol_insuficiente_responde_403() -> None:
    respuesta = _get("/solo-admin", claves.token("comprador"))
    assert respuesta.status_code == 403
    assert respuesta.json()["title"] == "Sin permiso"


def test_rol_suficiente_responde_200() -> None:
    assert _get("/solo-admin", claves.token("admin", sub="a-1")).json() == {"id": "a-1"}


def test_jwks_inaccesible_responde_503() -> None:
    validador = validador_desde_jwks(
        ClavesPrueba.EMISOR, ClavesPrueba.AUDIENCIA, "http://127.0.0.1:9/certs"
    )
    with pytest.raises(HTTPException) as error:
        validador.validar(claves.token("admin"))
    assert error.value.status_code == 503
