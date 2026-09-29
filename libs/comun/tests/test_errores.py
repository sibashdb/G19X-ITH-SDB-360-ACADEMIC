from comun.errores import ErrorDominio, registrar_manejadores
from comun.logs import middleware_correlacion
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(middleware_correlacion)
    registrar_manejadores(app)

    @app.get("/dominio")
    async def dominio() -> None:
        raise ErrorDominio(409, "Conflicto", "El folio ya existe", {"folio": "C-1"})

    @app.get("/no-autenticado")
    async def no_autenticado() -> None:
        raise HTTPException(
            401, "Se requiere iniciar sesión", headers={"WWW-Authenticate": "Bearer"}
        )

    @app.get("/numero/{n}")
    async def numero(n: int) -> dict[str, int]:
        return {"n": n}

    @app.get("/falla")
    async def falla() -> None:
        raise RuntimeError("detalle interno secreto")

    return app


cliente = TestClient(_app(), raise_server_exceptions=False)


def test_error_de_dominio_usa_problem_details() -> None:
    respuesta = cliente.get("/dominio", headers={"X-Request-ID": "req-1"})
    assert respuesta.status_code == 409
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.json() == {
        "type": "about:blank",
        "title": "Conflicto",
        "status": 409,
        "detail": "El folio ya existe",
        "instance": "/dominio",
        "correlation_id": "req-1",
        "folio": "C-1",
    }


def test_http_exception_conserva_cabeceras_y_titulo_en_espanol() -> None:
    respuesta = cliente.get("/no-autenticado")
    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
    assert respuesta.json()["title"] == "No autenticado"
    assert respuesta.json()["detail"] == "Se requiere iniciar sesión"


def test_ruta_inexistente_responde_404_en_espanol() -> None:
    respuesta = cliente.get("/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.json()["title"] == "No encontrado"


def test_validacion_lista_los_campos_con_error() -> None:
    respuesta = cliente.get("/numero/abc")
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["title"] == "Solicitud inválida"
    assert cuerpo["errores"][0]["campo"] == "path.n"


def test_error_inesperado_no_filtra_detalles_internos() -> None:
    respuesta = cliente.get("/falla", headers={"X-Request-ID": "req-9"})
    assert respuesta.status_code == 500
    assert "secreto" not in respuesta.text
    assert respuesta.json()["title"] == "Error interno"
    assert respuesta.json()["correlation_id"] == "req-9"
