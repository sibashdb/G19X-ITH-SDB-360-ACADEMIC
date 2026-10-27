import asyncio

import httpx
from fastapi import FastAPI
from ia.config import Configuracion
from ia.main import crear_app


def _app(url: str, transporte: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    return crear_app(Configuracion(llm_url=url), transporte=transporte)


async def _get(app: FastAPI, ruta: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://ia"
    ) as http:
        return await http.get(ruta)


async def test_salud_responde_aunque_no_haya_llm() -> None:
    assert (await _get(_app(""), "/salud/listo")).status_code == 200


async def test_llm_dice_si_esta_disponible() -> None:
    respuesta = await _get(_app(""), "/llm")
    assert respuesta.json() == {"disponible": False, "modelo": "qwen2.5:3b"}


async def test_al_arrancar_precarga_el_modelo() -> None:
    peticiones: list[httpx.Request] = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        return httpx.Response(500)  # una falla no impide arrancar

    app = _app("http://llm/v1", httpx.MockTransport(manejador))
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.05)
        assert (await _get(app, "/salud/vivo")).status_code == 200
    assert [p.url.path for p in peticiones] == ["/v1/chat/completions"]
