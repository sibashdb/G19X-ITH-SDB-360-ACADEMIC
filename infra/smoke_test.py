"""Prueba de humo contra el stack de Docker Compose: uv run python infra/smoke_test.py"""

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://localhost:8080"
BUZON = "http://localhost:8025"
CORREO_HUMO = "humo.prueba@plataforma.example"
ASUNTO_CORREO = "Defina su contraseña de PluriOne"
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


def correos_de_humo() -> dict[str, str]:
    """ID -> asunto de los correos que Mailpit tiene para el usuario de humo."""
    respuesta = httpx.get(
        f"{BUZON}/api/v1/search", params={"query": f"to:{CORREO_HUMO}"}, timeout=10
    )
    verificar(respuesta.status_code == 200, f"Mailpit no respondió: {respuesta.text}")
    return {m["ID"]: m["Subject"] for m in respuesta.json().get("messages", [])}


def sesiones_de_admin1(cliente: httpx.Client, admin: dict[str, str]) -> set[str]:
    """IDs de los inicios de sesión de admin1 en las 100 entradas más recientes de la bitácora."""
    respuesta = cliente.get(
        "/api/administracion/actividad",
        params={"tipo": "sesiones", "tamano": 100},
        headers=admin,
    )
    verificar(respuesta.status_code == 200, f"consultar la actividad falló: {respuesta.text}")
    return {e["id"] for e in respuesta.json()["elementos"] if e["actor_nombre"] == "admin1"}


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
        "correo": CORREO_HUMO,
        "roles": ["comprador"],
        "metodo": "invitacion",
    }
    # Los correos de corridas anteriores siguen en Mailpit: solo cuenta uno nuevo.
    correos_antes = set(correos_de_humo())
    alta = cliente.post(f"{api}/usuarios", json=datos, headers=admin)
    if alta.status_code == 201:
        usuario_id = alta.json()["usuario"]["id"]
        verificar(alta.json()["correo_enviado"] is True, "la invitación no se envió")
    else:
        verificar(alta.status_code == 409, f"alta falló: {alta.text}")
        # Con usuario y correo repetidos, Keycloak reporta primero el correo.
        verificar(
            alta.json().get("codigo") in ("usuario_duplicado", "correo_duplicado"),
            f"alta falló: {alta.text}",
        )
        [existente] = cliente.get(
            f"{api}/usuarios", params={"busqueda": "humo.prueba"}, headers=admin
        ).json()["elementos"]
        usuario_id = existente["id"]
        activar = cliente.post(f"{api}/usuarios/{usuario_id}/activar", headers=admin)
        verificar(activar.status_code == 200, f"activar falló: {activar.text}")
        correo = cliente.post(
            f"{api}/usuarios/{usuario_id}/contrasena", json={"metodo": "correo"}, headers=admin
        )
        verificar(correo.status_code == 200, f"el correo no se envió: {correo.text}")

    nuevos = [a for id_, a in correos_de_humo().items() if id_ not in correos_antes]
    verificar(
        ASUNTO_CORREO in nuevos,
        f"no llegó a Mailpit un correo nuevo con el asunto esperado: {nuevos}",
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

    # Un inicio de sesión nuevo llega a la bitácora en menos de un minuto (lectura cada 30 s).
    # Los de corridas anteriores no cuentan: se compara contra los que ya estaban.
    sesiones_antes = sesiones_de_admin1(cliente, admin)
    admin = token_de(cliente, "admin1")
    limite = time.monotonic() + 75
    while time.monotonic() < limite:
        if sesiones_de_admin1(cliente, admin) - sesiones_antes:
            return
        time.sleep(5)
    raise SystemExit("FALLA: los inicios de sesión no llegaron a la bitácora en 75 s")


SERVICIO_HUMO = "HUMO-SERV"


def eventos_del_servicio_de_humo(cliente: httpx.Client, admin: dict[str, str]) -> set[str]:
    """IDs de los registros del catálogo sobre el servicio de humo (los 100 más recientes)."""
    respuesta = cliente.get(
        "/api/administracion/actividad",
        params={"tipo": "catalogo", "tamano": 100},
        headers=admin,
    )
    verificar(respuesta.status_code == 200, f"consultar la actividad falló: {respuesta.text}")
    return {e["id"] for e in respuesta.json()["elementos"] if e["objeto_id"] == SERVICIO_HUMO}


def verificar_operacion(cliente: httpx.Client) -> None:
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")

    estado = cliente.get("/api/administracion/estado", headers=admin)
    verificar(estado.status_code == 200, f"el estado del sistema falló: {estado.text}")
    caidos = [s["nombre"] for s in estado.json()["servicios"] if s["estado"] == "caido"]
    verificar(not caidos, f"servicios caídos según el estado del sistema: {caidos}")
    resumen = cliente.get("/api/administracion/resumen", headers=admin)
    verificar(
        resumen.status_code == 200 and resumen.json()["usuarios_activos"] is not None,
        f"el resumen del panel falló: {resumen.text}",
    )
    inactivos = cliente.get(
        "/api/proveedores/servicios", params={"incluir_inactivos": "true"}, headers=comprador
    )
    verificar(inactivos.status_code == 403, "un comprador no debe ver los servicios inactivos")

    # Servicio de humo reutilizable: se crea la primera vez; cada corrida lo desactiva y lo
    # reactiva. Solo cuentan los registros nuevos de esta corrida.
    antes = eventos_del_servicio_de_humo(cliente, admin)
    alta = cliente.post(
        "/api/proveedores/servicios",
        json={
            "codigo": SERVICIO_HUMO,
            "nombre": "Servicio de la prueba de humo",
            "categoria": "soporte",
            "unidad": "ticket",
            "moneda": "MXN",
        },
        headers=admin,
    )
    verificar(alta.status_code in (201, 409), f"el alta del servicio falló: {alta.text}")
    for activo in (False, True):
        cambio = cliente.patch(
            f"/api/proveedores/servicios/{SERVICIO_HUMO}", json={"activo": activo}, headers=admin
        )
        verificar(
            cambio.status_code == 200 and cambio.json()["activo"] is activo,
            f"cambiar el estado del servicio falló: {cambio.text}",
        )
    # Los cambios viajan por el outbox y RabbitMQ hasta la bitácora de administración.
    limite = time.monotonic() + 30
    while time.monotonic() < limite:
        if len(eventos_del_servicio_de_humo(cliente, admin) - antes) >= 2:
            return
        time.sleep(1)
    raise SystemExit("FALLA: los cambios del catálogo no llegaron a la bitácora en 30 s")


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
        verificar_operacion(cliente)

    print(
        f"OK: SPA, Keycloak, proveedores, administración y operación responden "
        f"({lista.json()['total']} proveedores)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
