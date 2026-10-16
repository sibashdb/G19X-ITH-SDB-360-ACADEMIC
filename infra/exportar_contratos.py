"""Exporta los contratos OpenAPI de los servicios: uv run python infra/exportar_contratos.py

Los toma del stack en marcha, a través del gateway, y los escribe en docs/arquitectura/openapi/.
Repítalo después de cambiar una API para que el documento de arquitectura no quede desfasado.
"""

import json
import sys
from pathlib import Path

import httpx

BASE = "http://localhost:8080/api"
SERVICIOS = ("proveedores", "administracion", "inteligencia", "negociacion")
DESTINO = Path(__file__).resolve().parent.parent / "docs" / "arquitectura" / "openapi"


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=10) as cliente:
        for servicio in SERVICIOS:
            try:
                respuesta = cliente.get(f"{BASE}/{servicio}/openapi.json")
                respuesta.raise_for_status()
            except httpx.HTTPError as error:
                print(f"FALLA: {servicio}: {error}. ¿Está levantado el stack?")
                return 1
            contrato = respuesta.json()
            texto = json.dumps(contrato, ensure_ascii=False, indent=2) + "\n"
            (DESTINO / f"{servicio}.json").write_text(texto, encoding="utf-8", newline="\n")
            print(f"{servicio}: {len(contrato['paths'])} rutas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
