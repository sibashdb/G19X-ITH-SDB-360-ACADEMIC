import json
import logging

from comun.logs import (
    CABECERA_CORRELACION,
    FormatoJSON,
    configurar_logs,
    correlation_id,
    middleware_correlacion,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(middleware_correlacion)

    @app.get("/eco")
    async def eco() -> dict[str, str]:
        return {"correlation_id": correlation_id.get()}

    return app


def test_formato_json_incluye_servicio_mensaje_y_correlation_id() -> None:
    token = correlation_id.set("abc-123")
    try:
        registro = logging.LogRecord(
            "prueba", logging.INFO, __file__, 1, "hola %s", ("mundo",), None
        )
        linea = json.loads(FormatoJSON("proveedores").format(registro))
    finally:
        correlation_id.reset(token)
    assert linea["mensaje"] == "hola mundo"
    assert linea["servicio"] == "proveedores"
    assert linea["correlation_id"] == "abc-123"
    assert linea["nivel"] == "INFO"


def test_configurar_logs_instala_un_solo_manejador_json() -> None:
    raiz = logging.getLogger()
    anteriores = raiz.handlers[:]
    try:
        configurar_logs("proveedores", "WARNING")
        assert len(raiz.handlers) == 1
        assert isinstance(raiz.handlers[0].formatter, FormatoJSON)
        assert raiz.level == logging.WARNING
    finally:
        raiz.handlers = anteriores


def test_middleware_reutiliza_el_id_valido_del_gateway() -> None:
    respuesta = TestClient(_app()).get("/eco", headers={CABECERA_CORRELACION: "req-42"})
    assert respuesta.headers[CABECERA_CORRELACION] == "req-42"
    assert respuesta.json() == {"correlation_id": "req-42"}


def test_middleware_reemplaza_un_id_con_caracteres_no_permitidos() -> None:
    malicioso = 'x" {"nivel": "CRITICAL"}'
    respuesta = TestClient(_app()).get("/eco", headers={CABECERA_CORRELACION: malicioso})
    generado = respuesta.headers[CABECERA_CORRELACION]
    assert generado != malicioso
    assert len(generado) == 32
    assert respuesta.json() == {"correlation_id": generado}


def test_middleware_genera_id_si_no_llega() -> None:
    respuesta = TestClient(_app()).get("/eco")
    assert len(respuesta.headers[CABECERA_CORRELACION]) == 32
