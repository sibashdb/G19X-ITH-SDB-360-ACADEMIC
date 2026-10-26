"""El agente responde con el texto del LLM, verificado; si no, con su plantilla (spec §3)."""

import json
from decimal import Decimal as D
from typing import Any

import httpx
from fastapi import FastAPI
from negociacion import textos


async def _ofertar_y_ver(
    cliente: httpx.AsyncClient, comprador: dict[str, str], publicar: Any, ofertar: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Publica, el primer proveedor ofrece sobre el límite y devuelve (evento, sesión)."""
    evento, enlaces = await publicar()
    linea = str(evento["lineas"][0]["id"])
    respuesta = await ofertar(enlaces[0], {linea: "40.00"})
    assert respuesta.status_code == 200, respuesta.text
    sesion = await cliente.get(f"/sesiones/{enlaces[0]['sesion_id']}", headers=comprador)
    return evento, sesion.json()


def _ultima_del_agente(sesion: dict[str, Any]) -> dict[str, Any]:
    return [m for m in sesion["mensajes"] if m["autor"] == "agente"][-1]


def _precio_propuesto(cuerpo: dict[str, Any]) -> str:
    return str(cuerpo["cifras"][0]["valor"])


async def test_la_contraoferta_usa_el_texto_del_llm_si_sus_numeros_coinciden(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    externos: Any,
) -> None:
    externos.redactar = lambda cuerpo: f"Le proponemos {_precio_propuesto(cuerpo)} por usuario."
    _, sesion = await _ofertar_y_ver(cliente, comprador, publicar, ofertar)

    mensaje = _ultima_del_agente(sesion)
    [cuerpo] = externos.cuerpos_ia("/redactar")
    assert mensaje["texto"] == f"Le proponemos {_precio_propuesto(cuerpo)} por usuario."
    assert mensaje["decision"]["redaccion"]["origen"] == "llm"
    assert cuerpo["tipo"] == "contraoferta"


async def test_un_numero_que_el_motor_no_decidio_usa_la_plantilla(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    externos: Any,
) -> None:
    externos.redactar = lambda _: "Le proponemos $1.00 por usuario."
    _, sesion = await _ofertar_y_ver(cliente, comprador, publicar, ofertar)

    mensaje = _ultima_del_agente(sesion)
    assert len(externos.cuerpos_ia("/redactar")) == 2
    assert mensaje["texto"] == textos.CONTRAOFERTA
    assert mensaje["decision"]["redaccion"] == {
        "origen": "plantilla",
        "modelo": "falso",
        "version_prompt": "1",
        "motivo": "verificacion",
    }


async def test_sin_tiempo_no_reintenta(
    app: FastAPI,
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    externos: Any,
) -> None:
    app.state.config.ia_presupuesto_s = 5
    externos.retraso_ia = 3
    externos.redactar = lambda _: "Le proponemos $1.00 por usuario."
    _, sesion = await _ofertar_y_ver(cliente, comprador, publicar, ofertar)

    assert len(externos.cuerpos_ia("/redactar")) == 1
    assert _ultima_del_agente(sesion)["decision"]["redaccion"]["motivo"] == "sin_tiempo"


async def test_sin_ia_el_agente_responde_con_la_plantilla(
    app: FastAPI,
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    externos: Any,
) -> None:
    # El falso responde 503 (LLM apagado) porque no tiene función de redactar.
    _, sesion = await _ofertar_y_ver(cliente, comprador, publicar, ofertar)
    mensaje = _ultima_del_agente(sesion)
    assert mensaje["texto"] == textos.CONTRAOFERTA
    assert mensaje["decision"]["redaccion"]["motivo"] == "sin_ia"
    assert sesion["ronda"] == 1  # la negociación sigue

    # Sin URL de ia, ni siquiera se le llama.
    app.state.ia = type(app.state.ia)(app.state.ia._http, "")
    externos.peticiones.clear()
    _, otra = await _ofertar_y_ver(cliente, comprador, publicar, ofertar)
    assert externos.cuerpos_ia("/redactar") == []
    assert _ultima_del_agente(otra)["decision"]["redaccion"]["motivo"] == "sin_ia"


async def test_el_redactor_nunca_recibe_limites_ni_pesos(
    cliente: httpx.AsyncClient,
    comprador: dict[str, str],
    publicar: Any,
    ofertar: Any,
    externos: Any,
) -> None:
    externos.redactar = lambda cuerpo: f"Le proponemos {_precio_propuesto(cuerpo)}."
    evento, _ = await _ofertar_y_ver(cliente, comprador, publicar, ofertar)
    detalle = (await cliente.get(f"/eventos/{evento['id']}", headers=comprador)).json()
    limite = D(str(detalle["lineas"][0]["limite"]))

    cuerpos = externos.cuerpos_ia("/redactar")
    assert cuerpos

    def claves(valor: Any) -> set[str]:
        if isinstance(valor, dict):
            return set(valor) | {c for v in valor.values() for c in claves(v)}
        if isinstance(valor, list):
            return {c for v in valor for c in claves(v)}
        return set()

    for cuerpo in cuerpos:
        assert not claves(cuerpo) & {"limite", "ideal", "peso", "utilidad"}
        numeros = {D(str(c["valor"])).normalize() for c in cuerpo["cifras"]}
        assert limite.normalize() not in numeros
        assert str(limite) not in json.dumps(cuerpo)
