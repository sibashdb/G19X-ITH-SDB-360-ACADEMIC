import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
from ia.llm import ClienteLLM, LLMNoDisponible

URL = "http://llm/v1"
ESQUEMA: dict[str, Any] = {"type": "object"}
Manejador = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


def respuesta(contenido: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": contenido}}]})


def cliente(manejador: Manejador, url: str = URL, espera_s: float = 1.0) -> ClienteLLM:
    http = httpx.AsyncClient(transport=httpx.MockTransport(manejador))
    return ClienteLLM(http, url, "llama3.2:3b", espera_s)


async def test_la_espera_en_la_cola_cuenta_dentro_del_tope() -> None:
    """Ninguna petición vive más que la espera desde que llega, ni haciendo fila (revisión, I5)."""

    async def lento(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.3)
        return respuesta("{}")

    llm = cliente(lento, espera_s=0.45)
    primera, segunda = await asyncio.gather(
        llm.completar_json("s", "u", ESQUEMA, 10),
        llm.completar_json("s", "u", ESQUEMA, 10),
        return_exceptions=True,
    )
    assert primera == {}
    assert isinstance(segunda, LLMNoDisponible)  # 0.3 s en la fila y 0.3 s de respuesta
    assert segunda.motivo == "sin_respuesta"


async def test_completar_json_devuelve_el_objeto_del_modelo() -> None:
    peticiones: list[httpx.Request] = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        return respuesta('{"a": 1}')

    assert await cliente(manejador).completar_json("sistema", "usuario", ESQUEMA, 50) == {"a": 1}
    [peticion] = peticiones
    assert peticion.url == "http://llm/v1/chat/completions"
    cuerpo = json.loads(peticion.content)
    assert cuerpo["temperature"] == 0
    assert cuerpo["response_format"]["type"] == "json_schema"
    assert cuerpo["response_format"]["json_schema"]["schema"] == ESQUEMA
    assert cuerpo["model"] == "llama3.2:3b"
    assert cuerpo["max_tokens"] == 50
    assert [m["role"] for m in cuerpo["messages"]] == ["system", "user"]


async def test_url_vacia_no_llama_y_lanza_apagado() -> None:
    peticiones: list[httpx.Request] = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        return respuesta("{}")

    with pytest.raises(LLMNoDisponible) as error:
        await cliente(manejador, url="").completar_json("s", "u", ESQUEMA, 50)
    assert error.value.motivo == "apagado"
    assert peticiones == []


async def test_tiempo_agotado_lanza_sin_respuesta() -> None:
    def manejador(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("tarda", request=peticion)

    with pytest.raises(LLMNoDisponible) as error:
        await cliente(manejador).completar_json("s", "u", ESQUEMA, 50)
    assert error.value.motivo == "sin_respuesta"


@pytest.mark.parametrize("contenido", ["hola", "[1, 2]"])
async def test_contenido_que_no_es_json_lanza_respuesta_invalida(contenido: str) -> None:
    with pytest.raises(LLMNoDisponible) as error:
        await cliente(lambda _: respuesta(contenido)).completar_json("s", "u", ESQUEMA, 50)
    assert error.value.motivo == "respuesta_invalida"


async def test_atiende_una_peticion_a_la_vez() -> None:
    en_curso = maximo = 0

    async def manejador(_: httpx.Request) -> httpx.Response:
        nonlocal en_curso, maximo
        en_curso += 1
        maximo = max(maximo, en_curso)
        await asyncio.sleep(0.05)
        en_curso -= 1
        return respuesta("{}")

    llm = cliente(manejador)
    await asyncio.gather(*(llm.completar_json("s", "u", ESQUEMA, 50) for _ in range(2)))
    assert maximo == 1
