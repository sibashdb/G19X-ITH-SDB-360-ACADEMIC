"""Prueba de humo contra el stack de Docker Compose: uv run python infra/smoke_test.py"""

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://localhost:8080"
BUZON = "http://localhost:8025"
REALM = Path(__file__).parent / "keycloak" / "realm-plataforma.json"


def verificar(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise SystemExit(f"FALLA: {mensaje}")


def contrasena_de_desarrollo(usuario: str) -> str:
    realm = json.loads(REALM.read_text(encoding="utf-8"))
    [datos] = [u for u in realm["users"] if u["username"] == usuario]
    return str(datos["credentials"][0]["value"])


def token_de(cliente: httpx.Client, usuario: str) -> dict[str, str]:
    respuesta = cliente.post(
        "/auth/realms/plataforma/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "pruebas-humo",
            "username": usuario,
            "password": contrasena_de_desarrollo(usuario),
        },
    )
    verificar(respuesta.status_code == 200, f"{usuario} no obtuvo token: {respuesta.text}")
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


def verificar_administracion(cliente: httpx.Client) -> None:
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")
    api = "/api/administracion"
    verificar(
        cliente.get(f"{api}/usuarios", headers=comprador).status_code == 403,
        "un comprador no debe gestionar usuarios",
    )
    lista = cliente.get(f"{api}/usuarios", headers=admin)
    verificar(lista.status_code == 200, f"listar usuarios falló: {lista.text}")

    # Usuario de humo reutilizable: se crea la primera vez y después se reactiva.
    datos = {
        "usuario": "humo.prueba",
        "nombre": "Humo",
        "apellidos": "Prueba",
        "correo": "humo.prueba@plataforma.example",
        "roles": ["comprador"],
        "metodo": "invitacion",
    }
    alta = cliente.post(f"{api}/usuarios", json=datos, headers=admin)
    if alta.status_code == 201:
        usuario_id = alta.json()["usuario"]["id"]
        verificar(alta.json()["correo_enviado"] is True, "la invitación no se envió")
    else:
        # Con usuario y correo repetidos, Keycloak reporta primero el correo.
        verificar(
            alta.json().get("codigo") in ("usuario_duplicado", "correo_duplicado"),
            f"alta falló: {alta.text}",
        )
        [existente] = cliente.get(
            f"{api}/usuarios", params={"busqueda": "humo.prueba"}, headers=admin
        ).json()["elementos"]
        usuario_id = existente["id"]
        cliente.post(f"{api}/usuarios/{usuario_id}/activar", headers=admin)
        correo = cliente.post(
            f"{api}/usuarios/{usuario_id}/contrasena", json={"metodo": "correo"}, headers=admin
        )
        verificar(correo.status_code == 200, f"el correo no se envió: {correo.text}")

    mensajes = httpx.get(
        f"{BUZON}/api/v1/search", params={"query": "to:humo.prueba@plataforma.example"}, timeout=10
    )
    asuntos = [m["Subject"] for m in mensajes.json().get("messages", [])]
    verificar(
        "Defina su contraseña de PluriOne" in asuntos,
        f"el correo no llegó a Mailpit con el asunto esperado: {asuntos}",
    )

    baja = cliente.post(f"{api}/usuarios/{usuario_id}/desactivar", headers=admin)
    verificar(
        baja.status_code == 200 and baja.json()["activo"] is False, f"desactivar falló: {baja.text}"
    )
    tipos = [
        e["tipo"]
        for e in cliente.get(
            f"{api}/actividad", params={"persona": usuario_id}, headers=admin
        ).json()["elementos"]
    ]
    verificar(
        "usuario.desactivado" in tipos and "usuario.correo_contrasena" in tipos,
        f"la bitácora no registró las acciones: {tipos}",
    )

    # Los inicios de sesión llegan a la bitácora en menos de un minuto (lectura cada 30 s).
    limite = time.monotonic() + 75
    while time.monotonic() < limite:
        sesiones = cliente.get(
            f"{api}/actividad", params={"tipo": "sesiones"}, headers=admin
        ).json()["elementos"]
        if any(e["actor_nombre"] == "admin1" for e in sesiones):
            return
        time.sleep(5)
    raise SystemExit("FALLA: los inicios de sesión no llegaron a la bitácora en 75 s")


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=10) as cliente:
        spa = cliente.get("/")
        verificar(spa.status_code == 200 and 'id="root"' in spa.text, "el gateway no sirve la SPA")
        verificar(
            "frame-ancestors 'none'" in spa.headers.get("content-security-policy", ""),
            "falta la cabecera CSP",
        )
        acceso = cliente.get(
            "/auth/realms/plataforma/protocol/openid-connect/auth",
            params={
                "client_id": "web",
                "response_type": "code",
                "scope": "openid",
                "redirect_uri": f"{BASE}/",
                "code_challenge": "A" * 43,
                "code_challenge_method": "S256",
            },
        )
        verificar(
            acceso.status_code == 200 and "login/plataforma/css/plataforma.css" in acceso.text,
            "Keycloak no aplica el tema de inicio de sesión 'plataforma'",
        )
        verificar(
            "Pague el precio justo y elija a los mejores proveedores" in acceso.text,
            "el inicio de sesión no muestra el panel con el propósito del producto",
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

        # Sin OTP: admin y aprobador obtienen token solo con usuario y contraseña.
        for usuario in ("admin1", "aprobador1"):
            respuesta = cliente.post(
                "/auth/realms/plataforma/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "pruebas-humo",
                    "username": usuario,
                    "password": contrasena_de_desarrollo(usuario),
                },
            )
            verificar(
                respuesta.status_code == 200,
                f"{usuario} no obtuvo token solo con contraseña (¿OTP pendiente?): "
                f"{respuesta.text}",
            )

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

        verificar_administracion(cliente)

    print(
        f"OK: SPA, Keycloak, proveedores y administración responden "
        f"({lista.json()['total']} proveedores)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
