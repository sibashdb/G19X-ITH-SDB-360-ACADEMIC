from collections.abc import Awaitable, Callable

import pytest
from comun.config import ConfiguracionBase
from comun.salud import crear_router_salud
from fastapi import FastAPI
from fastapi.testclient import TestClient


async def sana() -> None:
    return None


async def caida() -> None:
    raise ConnectionError("sin conexión")


def _cliente(verificaciones: dict[str, Callable[[], Awaitable[None]]]) -> TestClient:
    app = FastAPI()
    app.include_router(crear_router_salud(verificaciones))
    return TestClient(app)


def test_vivo_responde_ok_aunque_falle_una_dependencia() -> None:
    respuesta = _cliente({"postgres": caida}).get("/salud/vivo")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_listo_con_dependencias_sanas() -> None:
    respuesta = _cliente({"postgres": sana, "rabbitmq": sana}).get("/salud/listo")
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "estado": "ok",
        "dependencias": {"postgres": "ok", "rabbitmq": "ok"},
    }


def test_listo_con_una_dependencia_caida_responde_503() -> None:
    respuesta = _cliente({"postgres": sana, "rabbitmq": caida}).get("/salud/listo")
    assert respuesta.status_code == 503
    assert respuesta.json() == {
        "estado": "degradado",
        "dependencias": {"postgres": "ok", "rabbitmq": "error"},
    }


def test_configuracion_lee_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOMBRE_SERVICIO", "prueba")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/bd")
    configuracion = ConfiguracionBase()  # type: ignore[call-arg]
    assert configuracion.nombre_servicio == "prueba"
    assert configuracion.database_url.endswith("/bd")
    assert configuracion.oidc_audience == "plataforma-api"
