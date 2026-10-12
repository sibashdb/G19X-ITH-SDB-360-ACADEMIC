import time
from collections.abc import Awaitable, Callable

import httpx
import pytest
from generador.modelo import DatosSinteticos, generar

pytestmark = pytest.mark.integracion

Cargar = Callable[[DatosSinteticos], Awaitable[None]]
REPETICIONES = 20


async def test_el_tablero_responde_en_300_ms_con_el_dataset_por_defecto(
    cliente: httpx.AsyncClient, comprador: dict[str, str], cargar: Cargar
) -> None:
    await cargar(generar(42))  # el dataset por defecto: 60 proveedores, ~1,600 contratos
    inicio = time.perf_counter()
    primera = await cliente.get("/tablero", headers=comprador)
    en_frio = time.perf_counter() - inicio
    assert primera.status_code == 200
    tiempos = []
    for _ in range(REPETICIONES):
        inicio = time.perf_counter()
        respuesta = await cliente.get("/tablero", headers=comprador)
        tiempos.append(time.perf_counter() - inicio)
        assert respuesta.status_code == 200
    p95 = sorted(tiempos)[int(0.95 * REPETICIONES) - 1]
    assert p95 <= 0.3, f"p95 de {p95:.3f} s"
    # El cálculo completo se hace una vez por versión de los datos; este límite solo detecta un
    # cálculo cuadrático accidental.
    assert en_frio <= 10, f"la primera consulta tardó {en_frio:.1f} s"
