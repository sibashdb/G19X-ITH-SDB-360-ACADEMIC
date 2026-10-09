import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest
from administracion.identidad import (
    CorreoNoEnviado,
    DatoDuplicado,
    DatosUsuarioNuevo,
    IdentidadNoDisponible,
    UsuarioNoEncontrado,
)
from administracion.keycloak import CONSULTAS_DE_ROLES_A_LA_VEZ, IdentidadKeycloak

BASE = "http://kc/auth"
ADMIN = "/auth/admin/realms/plataforma"
TOKEN = "/auth/realms/plataforma/protocol/openid-connect/token"

Manejador = Callable[[httpx.Request], httpx.Response]


def _keycloak(
    rutas: dict[tuple[str, str], Manejador],
) -> tuple[IdentidadKeycloak, list[httpx.Request]]:
    """Keycloak simulado: responde por (método, ruta) y registra cada petición."""
    peticiones: list[httpx.Request] = []

    def manejar(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        if peticion.url.path == TOKEN:
            return httpx.Response(200, json={"access_token": "t", "expires_in": 300})
        manejador = rutas.get((peticion.method, peticion.url.path))
        return manejador(peticion) if manejador else httpx.Response(404)

    identidad = IdentidadKeycloak(
        BASE,
        "plataforma",
        "administracion",
        "secreto",
        "http://app/",
        transporte=httpx.MockTransport(manejar),
    )
    return identidad, peticiones


def _usuario(id_: str, usuario: str, *, activo: bool = True) -> dict[str, object]:
    return {
        "id": id_,
        "username": usuario,
        "firstName": "Ana",
        "lastName": "López",
        "email": f"{usuario}@x.mx",
        "enabled": activo,
        "createdTimestamp": 1_790_000_000_000,
    }


async def test_el_token_se_reutiliza() -> None:
    identidad, peticiones = _keycloak(
        {
            ("GET", f"{ADMIN}/users/u1"): lambda _: httpx.Response(200, json=_usuario("u1", "ana")),
            ("GET", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(
                200, json=[]
            ),
        }
    )
    await identidad.obtener_usuario("u1")
    await identidad.obtener_usuario("u1")
    assert sum(p.url.path == TOKEN for p in peticiones) == 1
    assert peticiones[1].headers["Authorization"] == "Bearer t"


async def test_listar_lee_los_roles_de_cada_usuario_y_omite_cuentas_de_servicio() -> None:
    # Los endpoints /roles piden view-realm, que la cuenta de servicio no tiene: sin rutas para
    # ellos ni para la cuenta de servicio, la prueba falla si el adaptador los consulta.
    usuarios = [
        _usuario("u1", "ana"),
        _usuario("u2", "beto", activo=False),
        _usuario("s1", "service-account-administracion"),
    ]
    identidad, _ = _keycloak(
        {
            ("GET", f"{ADMIN}/users"): lambda _: httpx.Response(200, json=usuarios),
            ("GET", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(
                200,
                json=[
                    {"id": "r1", "name": "admin"},
                    {"id": "r2", "name": "comprador"},
                    {"id": "r3", "name": "default-roles-plataforma"},
                ],
            ),
            ("GET", f"{ADMIN}/users/u2/role-mappings/realm"): lambda _: httpx.Response(
                200, json=[{"id": "r2", "name": "comprador"}]
            ),
        }
    )
    lista = {u.usuario: u for u in await identidad.listar_usuarios()}
    assert set(lista) == {"ana", "beto"}
    assert lista["ana"].roles == {"admin", "comprador"}
    assert lista["beto"].roles == {"comprador"}
    assert lista["beto"].activo is False
    assert lista["ana"].creado_en == datetime.fromtimestamp(1_790_000_000, UTC)


async def test_listar_limita_las_consultas_de_roles_simultaneas() -> None:
    usuarios = [_usuario(f"u{i}", f"usuario{i}") for i in range(50)]
    en_vuelo = 0
    maximo = 0

    async def manejar(peticion: httpx.Request) -> httpx.Response:
        nonlocal en_vuelo, maximo
        if peticion.url.path == TOKEN:
            return httpx.Response(200, json={"access_token": "t", "expires_in": 300})
        if peticion.url.path == f"{ADMIN}/users":
            return httpx.Response(200, json=usuarios)
        en_vuelo += 1
        maximo = max(maximo, en_vuelo)
        await asyncio.sleep(0)  # cede el turno: las demás consultas intentan entrar
        en_vuelo -= 1
        return httpx.Response(200, json=[])

    identidad = IdentidadKeycloak(
        BASE,
        "plataforma",
        "administracion",
        "secreto",
        "http://app/",
        transporte=httpx.MockTransport(manejar),
    )
    assert len(await identidad.listar_usuarios()) == 50
    assert maximo == CONSULTAS_DE_ROLES_A_LA_VEZ


async def test_obtener_inexistente() -> None:
    identidad, _ = _keycloak({})
    with pytest.raises(UsuarioNoEncontrado):
        await identidad.obtener_usuario("nadie")


async def test_crear_usuario_devuelve_el_id_de_location() -> None:
    def crear(peticion: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(peticion.content)
        assert cuerpo == {
            "username": "ana",
            "email": "ana@x.mx",
            "firstName": "Ana",
            "lastName": "López",
            "enabled": True,
            "emailVerified": True,
        }
        return httpx.Response(
            201, headers={"Location": f"{BASE}/admin/realms/plataforma/users/nuevo-id"}
        )

    identidad, _ = _keycloak({("POST", f"{ADMIN}/users"): crear})
    assert (
        await identidad.crear_usuario(DatosUsuarioNuevo("ana", "Ana", "López", "ana@x.mx"))
        == "nuevo-id"
    )


@pytest.mark.parametrize(
    ("mensaje", "campo"),
    [("User exists with same username", "usuario"), ("User exists with same email", "correo")],
)
async def test_crear_usuario_duplicado_distingue_usuario_y_correo(mensaje: str, campo: str) -> None:
    identidad, _ = _keycloak(
        {("POST", f"{ADMIN}/users"): lambda _: httpx.Response(409, json={"errorMessage": mensaje})}
    )
    with pytest.raises(DatoDuplicado) as error:
        await identidad.crear_usuario(DatosUsuarioNuevo("ana", "Ana", "López", "ana@x.mx"))
    assert error.value.campo == campo


async def test_fijar_roles_solo_agrega_y_quita_lo_necesario() -> None:
    actuales = [
        {"id": "r-comprador", "name": "comprador"},
        {"id": "r-def", "name": "default-roles-plataforma"},
    ]
    identidad, peticiones = _keycloak(
        {
            ("GET", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(
                200, json=actuales
            ),
            # /roles/{nombre} pide view-realm; "available" solo pide view-users.
            ("GET", f"{ADMIN}/users/u1/role-mappings/realm/available"): lambda _: httpx.Response(
                200,
                json=[
                    {"id": "r-admin", "name": "admin"},
                    {"id": "r-aprobador", "name": "aprobador"},
                    {"id": "r-uma", "name": "uma_authorization"},
                ],
            ),
            ("POST", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(204),
            ("DELETE", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(204),
        }
    )
    await identidad.fijar_roles("u1", frozenset({"admin"}))
    agregados = next(p for p in peticiones if p.method == "POST" and "role-mappings" in p.url.path)
    quitados = next(p for p in peticiones if p.method == "DELETE")
    assert [r["name"] for r in json.loads(agregados.content)] == ["admin"]
    assert [r["name"] for r in json.loads(quitados.content)] == ["comprador"]


async def test_fijar_roles_con_un_rol_que_keycloak_no_tiene() -> None:
    identidad, _ = _keycloak(
        {
            ("GET", f"{ADMIN}/users/u1/role-mappings/realm"): lambda _: httpx.Response(
                200, json=[]
            ),
            ("GET", f"{ADMIN}/users/u1/role-mappings/realm/available"): lambda _: httpx.Response(
                200, json=[{"id": "r-admin", "name": "admin"}]
            ),
        }
    )
    with pytest.raises(IdentidadNoDisponible):
        await identidad.fijar_roles("u1", frozenset({"admin", "aprobador"}))


async def test_enviar_correo_pide_definir_la_contrasena_con_vigencia_y_regreso() -> None:
    identidad, peticiones = _keycloak(
        {("PUT", f"{ADMIN}/users/u1/execute-actions-email"): lambda _: httpx.Response(204)}
    )
    await identidad.enviar_correo_contrasena("u1", 259200)
    peticion = peticiones[-1]
    assert json.loads(peticion.content) == ["UPDATE_PASSWORD"]
    assert peticion.url.params["lifespan"] == "259200"
    assert peticion.url.params["client_id"] == "web"
    assert peticion.url.params["redirect_uri"] == "http://app/"


async def test_correo_que_no_sale() -> None:
    identidad, _ = _keycloak(
        {
            ("PUT", f"{ADMIN}/users/u1/execute-actions-email"): lambda _: httpx.Response(
                500, json={"errorMessage": "Failed to send execute actions email"}
            )
        }
    )
    with pytest.raises(CorreoNoEnviado):
        await identidad.enviar_correo_contrasena("u1", 86400)


async def test_contrasena_temporal() -> None:
    identidad, peticiones = _keycloak(
        {("PUT", f"{ADMIN}/users/u1/reset-password"): lambda _: httpx.Response(204)}
    )
    await identidad.fijar_contrasena_temporal("u1", "Xy7#abcdefghijkl")
    assert json.loads(peticiones[-1].content) == {
        "type": "password",
        "value": "Xy7#abcdefghijkl",
        "temporary": True,
    }


async def test_red_caida() -> None:
    def falla(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    identidad = IdentidadKeycloak(
        BASE,
        "plataforma",
        "administracion",
        "s",
        "http://app/",
        transporte=httpx.MockTransport(falla),
    )
    with pytest.raises(IdentidadNoDisponible):
        await identidad.listar_usuarios()


async def test_eventos_pagina_traduce_y_filtra_por_fecha() -> None:
    desde = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    ms = int(desde.timestamp() * 1000)
    pagina1 = [
        {
            "id": f"e{i}",
            "time": ms + i * 1000,
            "type": "LOGIN",
            "userId": "u1",
            "ipAddress": "10.0.0.1",
            "details": {"username": "ana"},
        }
        for i in range(200)
    ]
    pagina2 = [
        {
            "time": ms + 500_000,
            "type": "LOGIN_ERROR",
            "userId": None,
            "sessionId": None,
            "error": "user_not_found",
            "details": {"username": "fantasma"},
        },
        {"id": "viejo", "time": ms - 60_000, "type": "LOGOUT", "userId": "u1", "details": {}},
    ]

    def eventos(peticion: httpx.Request) -> httpx.Response:
        assert peticion.url.params.get_list("type") == ["LOGIN", "LOGIN_ERROR", "LOGOUT"]
        assert peticion.url.params["dateFrom"] == "2026-10-08"
        return httpx.Response(200, json=pagina1 if peticion.url.params["first"] == "0" else pagina2)

    identidad, _ = _keycloak({("GET", f"{ADMIN}/events"): eventos})
    lista = await identidad.eventos_de_sesion(desde)
    assert len(lista) == 201  # el evento anterior a "desde" se descarta
    assert lista == sorted(lista, key=lambda e: e.fecha)
    fallido = lista[-1]
    assert fallido.tipo == "LOGIN_ERROR"
    assert fallido.usuario_id is None
    assert fallido.usuario == "fantasma"
    assert fallido.error == "user_not_found"
    assert fallido.id.startswith(str(ms + 500_000))
