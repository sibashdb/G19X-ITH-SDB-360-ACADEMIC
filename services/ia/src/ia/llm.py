"""Cliente del LLM por la API compatible con OpenAI (ADR-003): salidas JSON con esquema."""

import asyncio
import json
import logging
from typing import Any, Literal

import httpx

log = logging.getLogger(__name__)
Motivo = Literal["apagado", "sin_respuesta", "respuesta_invalida"]


class LLMNoDisponible(Exception):
    def __init__(self, motivo: Motivo) -> None:
        super().__init__(motivo)
        self.motivo: Motivo = motivo


class ClienteLLM:
    def __init__(self, http: httpx.AsyncClient, url: str, modelo: str, espera_s: float) -> None:
        self._http = http
        self._url = url.rstrip("/")
        self.modelo = modelo
        self._espera_s = espera_s
        # ponytail: una petición a la vez; la GPU de 4 GB no atiende dos (ADR-003).
        self._cola = asyncio.Semaphore(1)

    async def completar_json(
        self, sistema: str, usuario: str, esquema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        """El objeto JSON que devuelve el modelo, ya decodificado; nunca un texto suelto."""
        if not self._url:
            raise LLMNoDisponible("apagado")
        cuerpo = {
            "model": self.modelo,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "respuesta", "schema": esquema},
            },
        }
        async with self._cola:
            try:
                respuesta = await self._http.post(
                    f"{self._url}/chat/completions", json=cuerpo, timeout=self._espera_s
                )
                respuesta.raise_for_status()
                contenido = respuesta.json()["choices"][0]["message"]["content"]
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                log.warning("El LLM no respondió: %r", exc)
                raise LLMNoDisponible("sin_respuesta") from exc
        try:
            objeto = json.loads(contenido)
        except (TypeError, ValueError) as exc:
            raise LLMNoDisponible("respuesta_invalida") from exc
        if not isinstance(objeto, dict):
            raise LLMNoDisponible("respuesta_invalida")
        return objeto

    async def disponible(self) -> bool:
        if not self._url:
            return False
        try:
            respuesta = await self._http.get(f"{self._url}/models", timeout=2)
        except httpx.HTTPError:
            return False
        return respuesta.status_code == 200

    async def precargar(self) -> None:
        """Una petición mínima para que Ollama cargue el modelo antes del primer turno."""
        try:
            await self.completar_json("Responde {}.", "{}", {"type": "object"}, 1)
        except LLMNoDisponible:
            log.info("No se pudo precargar el modelo %s", self.modelo)
