"""Prueba de humo contra el stack de Docker Compose: uv run python infra/smoke_test.py"""

import json
import sys
from pathlib import Path

import httpx

BASE = "http://localhost:8080"
REALM = Path(__file__).parent / "keycloak" / "realm-plataforma.json"


def verificar(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise SystemExit(f"FALLA: {mensaje}")


def contrasena_de_desarrollo(usuario: str) -> str:
    realm = json.loads(REALM.read_text(encoding="utf-8"))
    [datos] = [u for u in realm["users"] if u["username"] == usuario]
    return str(datos["credentials"][0]["value"])


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=10) as cliente:
        spa = cliente.get("/")
        verificar(spa.status_code == 200 and 'id="root"' in spa.text, "el gateway no sirve la SPA")
        verificar(
            "frame-ancestors 'none'" in spa.headers.get("content-security-policy", ""),
            "falta la cabecera CSP",
        )
        sin_token = cliente.get("/api/proveedores/proveedores")
        verificar(sin_token.status_code == 401, f"sin token se esperaba 401: {sin_token.text}")

        token = cliente.post(
            "/auth/realms/plataforma/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "pruebas-humo",
                "username": "comprador1",
                "password": contrasena_de_desarrollo("comprador1"),
            },
        )
        verificar(token.status_code == 200, f"Keycloak no emitió token: {token.text}")
        cabeceras = {"Authorization": f"Bearer {token.json()['access_token']}"}

        lista = cliente.get("/api/proveedores/proveedores", headers=cabeceras)
        verificar(lista.status_code == 200, f"listar proveedores falló: {lista.text}")
        verificar(bool(lista.headers.get("x-request-id")), "falta X-Request-ID en la respuesta")

        importar = cliente.post(
            "/api/proveedores/importaciones/servicios",
            headers=cabeceras,
            files={"archivo": ("s.csv", b"codigo,nombre,categoria,unidad,moneda\n", "text/csv")},
        )
        verificar(importar.status_code == 403, f"un comprador no debe importar: {importar.text}")

        openapi = cliente.get("/api/proveedores/openapi.json")
        verificar(openapi.status_code == 200, "no se publica el contrato OpenAPI")

    print(f"OK: SPA, Keycloak y proveedores responden ({lista.json()['total']} proveedores).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
