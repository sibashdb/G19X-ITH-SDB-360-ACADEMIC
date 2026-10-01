import base64
import time
from typing import Annotated, Any

import jwt
import pytest
from comun.auth import Usuario, requiere_rol, usuario_actual, validador_desde_jwks
from comun.errores import registrar_manejadores
from comun.pruebas import ClavesPrueba
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import Response

claves = ClavesPrueba()


def _token_sin_exp() -> str:
    """Construye un JWT sin el claim 'exp' firmado con la clave privada de prueba."""
    ahora = int(time.time())
    datos = {
        "sub": "usuario-prueba",
        "preferred_username": "usuario-prueba",
        "iss": ClavesPrueba.EMISOR,
        "aud": ClavesPrueba.AUDIENCIA,
        "iat": ahora,
        # exp ausente intencionalmente
        "realm_access": {"roles": ["admin"]},
    }
    return jwt.encode(datos, claves._privada, algorithm="RS256")


def _token_alg_none() -> str:
    """Construye un JWT con algoritmo 'none' en el header."""
    ahora = int(time.time())
    datos = {
        "sub": "usuario-prueba",
        "preferred_username": "usuario-prueba",
        "iss": ClavesPrueba.EMISOR,
        "aud": ClavesPrueba.AUDIENCIA,
        "iat": ahora,
        "exp": ahora + 300,
        "realm_access": {"roles": ["admin"]},
    }
    header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        __import__("json").dumps(datos, separators=(",", ":")).encode()
    ).rstrip(b"=")
    return (header + b"." + payload + b".").decode()


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
    # 60 s: más allá de la tolerancia de reloj de 10 s.
    [{"exp": int(time.time()) - 60}, {"iss": "http://otro-emisor"}, {"aud": "otra-api"}],
    ids=["vencido", "otro-emisor", "otra-audiencia"],
)
def test_token_vencido_o_ajeno_responde_401(extra: dict[str, Any]) -> None:
    assert _get("/yo", claves.token("admin", **extra)).status_code == 401


def test_token_recien_vencido_se_acepta_por_desfase_de_reloj() -> None:
    """Keycloak y el servicio pueden tener relojes desfasados unos segundos."""
    recien_vencido = claves.token("admin", exp=int(time.time()) - 3)
    assert _get("/yo", recien_vencido).status_code == 200


def test_cliente_jwks_tiene_tiempo_de_espera(monkeypatch: pytest.MonkeyPatch) -> None:
    capturado: dict[str, Any] = {}

    class ClienteFalso:
        def __init__(self, url: str, **kwargs: Any) -> None:
            capturado.update(url=url, **kwargs)

    monkeypatch.setattr("comun.auth.jwt.PyJWKClient", ClienteFalso)
    validador_desde_jwks(ClavesPrueba.EMISOR, ClavesPrueba.AUDIENCIA, "http://keycloak/certs")
    assert capturado == {"url": "http://keycloak/certs", "timeout": 5}


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


def test_token_alg_none_responde_401() -> None:
    """Regresión: token con algoritmo 'none' debe rechazarse."""
    respuesta = _get("/yo", _token_alg_none())
    assert respuesta.status_code == 401


def test_token_sin_exp_responde_401() -> None:
    """Regresión: token sin claim 'exp' requerido debe rechazarse."""
    respuesta = _get("/yo", _token_sin_exp())
    assert respuesta.status_code == 401


def test_realm_access_null_devuelve_roles_vacio() -> None:
    """Regresión: realm_access=null no causa AttributeError, devuelve roles vacío."""
    token_con_null = claves.token("comprador", **{"realm_access": None})
    respuesta = _get("/yo", token_con_null)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": "usuario-prueba", "nombre": "usuario-prueba", "roles": []}
