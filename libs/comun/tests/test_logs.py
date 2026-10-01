import json
import logging
import sys
from collections.abc import Iterator

import pytest
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


@pytest.fixture
def estado_logging() -> Iterator[list[logging.Logger]]:
    """Devuelve la raíz y los loggers de uvicorn; al terminar restaura su configuración."""
    registros = [logging.getLogger(n) for n in ("", "uvicorn", "uvicorn.error", "uvicorn.access")]
    guardado = [(r, r.handlers[:], r.propagate, r.level) for r in registros]
    yield registros
    for registro, manejadores, propaga, nivel in guardado:
        registro.handlers = manejadores
        registro.propagate = propaga
        registro.setLevel(nivel)


def test_configurar_logs_instala_un_solo_manejador_json(
    estado_logging: list[logging.Logger],
) -> None:
    raiz = estado_logging[0]
    configurar_logs("proveedores", "WARNING")
    assert len(raiz.handlers) == 1
    assert isinstance(raiz.handlers[0].formatter, FormatoJSON)
    assert raiz.level == logging.WARNING


def test_configurar_logs_encamina_uvicorn_al_manejador_json(
    estado_logging: list[logging.Logger], capsys: pytest.CaptureFixture[str]
) -> None:
    uvicorn = estado_logging[1:]
    # Como hace uvicorn al arrancar: un manejador propio de texto plano y sin propagar.
    for registro in uvicorn:
        registro.handlers = [logging.StreamHandler(sys.stderr)]
        registro.propagate = False
    configurar_logs("proveedores", "INFO")
    assert all(r.handlers == [] and r.propagate for r in uvicorn)

    token = correlation_id.set("req-uvicorn")
    try:
        logging.getLogger("uvicorn.access").info('%s - "%s" %d', "127.0.0.1", "GET /health", 200)
    finally:
        correlation_id.reset(token)
    linea = json.loads(capsys.readouterr().out)
    assert linea["logger"] == "uvicorn.access"
    assert linea["mensaje"] == '127.0.0.1 - "GET /health" 200'
    assert linea["correlation_id"] == "req-uvicorn"


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
