import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from administracion.bitacora import Actor, registrar
from administracion.identidad import DatosRechazados, IdentidadNoDisponible, UsuarioIdentidad
from administracion.identidad_falsa import IdentidadFalsa
from comun.pruebas import ClavesPrueba
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

NUEVO = {
    "usuario": "Ana.Lopez",
    "nombre": "Ana",
    "apellidos": "López",
    "correo": "ana@plataforma.example",
    "roles": ["comprador"],
    "metodo": "invitacion",
}


@pytest.fixture
def admin(claves: ClavesPrueba) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token('admin', sub='admin-1')}"}


async def _bitacora(fabrica: async_sessionmaker[AsyncSession]) -> list[dict[str, Any]]:
    async with fabrica() as sesion:
        filas = await sesion.execute(
            text(
                "SELECT tipo, objeto_id, objeto_nombre, detalle, resultado "
                "FROM actividad ORDER BY fecha"
            )
        )
        return [dict(f._mapping) for f in filas]


async def test_todas_las_rutas_exigen_el_rol_admin(
    app: FastAPI, cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    comprador = {"Authorization": f"Bearer {claves.token('comprador')}"}
    # app.routes no aplana los routers incluidos (FastAPI los envuelve): se usa el esquema OpenAPI.
    rutas = [
        (metodo, re.sub(r"\{[^}]+\}", "x", ruta))
        for ruta, metodos in app.openapi()["paths"].items()
        if not ruta.startswith("/salud")
        for metodo in metodos
    ]
    assert len(rutas) >= 10  # que el recorrido no quede vacío si cambia cómo se declaran
    for metodo, ruta in rutas:
        sin_token = await cliente.request(metodo, ruta)
        assert sin_token.status_code == 401, (metodo, ruta)
        de_comprador = await cliente.request(metodo, ruta, headers=comprador)
        assert de_comprador.status_code == 403, (metodo, ruta)


async def test_lista_filtra_busca_sin_acentos_y_pagina(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    identidad.agregar("lopez", ["aprobador"], nombre="Lucía", apellidos="López", activo=False)
    async with fabrica() as sesion:
        await registrar(
            sesion,
            "sesion.iniciada",
            Actor("lopez", "lopez"),
            origen="keycloak",
            clave_origen="k:1",
            fecha=datetime(2026, 10, 7, tzinfo=UTC),
        )
        await sesion.commit()

    todos = (await cliente.get("/usuarios", headers=admin)).json()
    assert todos["total"] == 3
    busqueda = (await cliente.get("/usuarios", params={"busqueda": "LOPEZ"}, headers=admin)).json()
    assert [u["usuario"] for u in busqueda["elementos"]] == ["lopez"]
    assert busqueda["elementos"][0]["ultimo_acceso"] == "2026-10-07T00:00:00Z"
    assert busqueda["elementos"][0]["activo"] is False
    por_rol = (await cliente.get("/usuarios", params={"rol": "admin"}, headers=admin)).json()
    assert [u["usuario"] for u in por_rol["elementos"]] == ["admin-1"]
    inactivos = (
        await cliente.get("/usuarios", params={"estado": "inactivos"}, headers=admin)
    ).json()
    assert inactivos["total"] == 1
    pagina = (
        await cliente.get("/usuarios", params={"tamano": 2, "pagina": 2}, headers=admin)
    ).json()
    assert pagina["total"] == 3
    assert len(pagina["elementos"]) == 1


async def test_alta_por_invitacion(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await cliente.post("/usuarios", json=NUEVO, headers=admin)
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["usuario"]["usuario"] == "ana.lopez"
    assert cuerpo["usuario"]["roles"] == ["comprador"]
    assert cuerpo["correo_enviado"] is True
    assert cuerpo["contrasena_temporal"] is None
    assert identidad.correos == [("id-ana.lopez", 259200)]
    assert [(f["tipo"], f["resultado"]) for f in await _bitacora(fabrica)] == [
        ("usuario.creado", "exito"),
        ("usuario.correo_contrasena", "exito"),
    ]
    correos = (await cliente.get("/correos", headers=admin)).json()
    assert correos["elementos"][0]["tipo"] == "invitacion"
    assert correos["elementos"][0]["estado"] == "enviado"


async def test_alta_con_nombre_y_apellidos_de_100_caracteres_queda_en_la_bitacora(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    # "nombre apellidos" mide 201 y la columna objeto_nombre 200.
    datos = {**NUEVO, "nombre": "N" * 100, "apellidos": "A" * 100}
    respuesta = await cliente.post("/usuarios", json=datos, headers=admin)
    assert respuesta.status_code == 201, respuesta.text
    assert {len(str(f["objeto_nombre"])) for f in await _bitacora(fabrica)} == {200}


async def test_alta_con_contrasena_temporal_no_la_guarda(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await cliente.post("/usuarios", json={**NUEVO, "metodo": "temporal"}, headers=admin)
    assert respuesta.status_code == 201
    temporal = respuesta.json()["contrasena_temporal"]
    assert len(temporal) == 16
    assert identidad.temporales["id-ana.lopez"] == temporal
    assert identidad.correos == []
    assert temporal not in json.dumps(await _bitacora(fabrica), default=str)
    async with fabrica() as sesion:
        assert await sesion.scalar(text("SELECT count(*) FROM correo_enviado")) == 0


async def test_alta_duplicada_marca_el_campo(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    respuesta = await cliente.post(
        "/usuarios", json={**NUEVO, "usuario": "comprador-1"}, headers=admin
    )
    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "usuario_duplicado"
    assert cuerpo["errores"] == [
        {"campo": "usuario", "mensaje": "Ya existe un usuario con ese nombre de usuario."}
    ]
    correo = await cliente.post(
        "/usuarios", json={**NUEVO, "correo": "comprador-1@plataforma.example"}, headers=admin
    )
    assert correo.json()["codigo"] == "correo_duplicado"


async def test_alta_con_correo_caido_crea_la_cuenta_y_lo_avisa(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    identidad.falla_correo = True
    respuesta = await cliente.post("/usuarios", json=NUEVO, headers=admin)
    assert respuesta.status_code == 201
    assert respuesta.json()["correo_enviado"] is False
    assert "id-ana.lopez" in identidad.usuarios
    assert (await _bitacora(fabrica))[-1]["resultado"] == "fallo"
    correos = (await cliente.get("/correos", headers=admin)).json()
    assert correos["elementos"][0]["estado"] == "fallido"


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"usuario": "ana lopez"}, "body.usuario"),
        ({"roles": []}, "body.roles"),
        ({"correo": "no-es-correo"}, "body.correo"),
        ({"roles": ["root"]}, "body.roles.0"),
        ({"usuario": ".ana"}, "body.usuario"),
        ({"usuario": "ana-"}, "body.usuario"),
        ({"usuario": "service-account-x"}, "body.usuario"),
        ({"nombre": "Ana (Compras)"}, "body.nombre"),
        ({"apellidos": "Pérez & Asociados"}, "body.apellidos"),
    ],
)
async def test_validacion(
    cliente: httpx.AsyncClient, admin: dict[str, str], cambio: dict[str, Any], campo: str
) -> None:
    respuesta = await cliente.post("/usuarios", json={**NUEVO, **cambio}, headers=admin)
    assert respuesta.status_code == 422
    assert campo in [e["campo"] for e in respuesta.json()["errores"]]


async def test_nombre_con_caracteres_que_keycloak_rechaza_dice_cuales(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    alta = await cliente.post("/usuarios", json={**NUEVO, "nombre": "Ana (Compras)"}, headers=admin)
    assert alta.status_code == 422
    assert {"campo": "body.nombre", "mensaje": "No use estos caracteres: ( )"} in (
        alta.json()["errores"]
    )
    edicion = await cliente.patch(
        "/usuarios/comprador-1", json={"apellidos": "A/B <C>"}, headers=admin
    )
    assert edicion.status_code == 422
    assert {"campo": "body.apellidos", "mensaje": "No use estos caracteres: / < >"} in (
        edicion.json()["errores"]
    )


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo", "falla"),
    [
        ("post", "/usuarios", NUEVO, "crear_usuario"),
        ("patch", "/usuarios/comprador-1", {"apellidos": "Compras"}, "actualizar_datos"),
    ],
)
async def test_si_keycloak_rechaza_los_datos_es_un_422(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    monkeypatch: pytest.MonkeyPatch,
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any],
    falla: str,
) -> None:
    _que_falle(identidad, monkeypatch, falla, DatosRechazados("simulado"))
    respuesta = await getattr(cliente, metodo)(ruta, json=cuerpo, headers=admin)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "datos_rechazados"
    assert respuesta.json()["detail"] == (
        "El servicio de identidad rechazó los datos; revise nombre, apellidos y correo."
    )


async def test_identidad_caida(
    cliente: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    identidad.caida = True
    respuesta = await cliente.get("/usuarios", headers=admin)
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "identidad_no_disponible"
    assert respuesta.json()["detail"] == (
        "No se pudo conectar con el servicio de identidad. Intente de nuevo en unos minutos."
    )


async def test_editar_datos_y_roles_registra_antes_y_despues(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await cliente.patch(
        "/usuarios/comprador-1",
        json={"apellidos": "Compras", "roles": ["comprador", "aprobador"]},
        headers=admin,
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["roles"] == ["comprador", "aprobador"]
    assert identidad.usuarios["comprador-1"].apellidos == "Compras"
    registros = await _bitacora(fabrica)
    assert [r["tipo"] for r in registros] == ["usuario.actualizado", "usuario.roles_cambiados"]
    assert registros[0]["detalle"] == {"campos": ["apellidos"]}
    assert registros[1]["detalle"] == {
        "antes": ["comprador"],
        "despues": ["comprador", "aprobador"],
    }


async def test_el_correo_se_guarda_en_minusculas_y_guardar_igual_no_registra(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    alta = await cliente.post(
        "/usuarios", json={**NUEVO, "correo": "Ana@Ejemplo.com"}, headers=admin
    )
    assert alta.json()["usuario"]["correo"] == "ana@ejemplo.com"
    for _ in range(2):
        edicion = await cliente.patch(
            "/usuarios/comprador-1", json={"correo": "Carlos@Ejemplo.com"}, headers=admin
        )
        assert edicion.json()["correo"] == "carlos@ejemplo.com"
    assert identidad.usuarios["comprador-1"].correo == "carlos@ejemplo.com"
    tipos = [r["tipo"] for r in await _bitacora(fabrica)]
    assert tipos.count("usuario.actualizado") == 1


async def test_nadie_se_quita_admin(
    cliente: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    respuesta = await cliente.patch(
        "/usuarios/admin-1", json={"roles": ["comprador"]}, headers=admin
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "regla_proteccion"
    assert respuesta.json()["detail"] == "No puede quitarse el rol de administrador."
    assert identidad.usuarios["admin-1"].roles == {"admin"}


async def test_desactivar_y_activar(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    propia = await cliente.post("/usuarios/admin-1/desactivar", headers=admin)
    assert propia.json()["detail"] == "No puede desactivar su propia cuenta."
    desactivado = await cliente.post("/usuarios/comprador-1/desactivar", headers=admin)
    assert desactivado.json()["activo"] is False
    assert identidad.sesiones_cerradas == ["comprador-1"]
    activado = await cliente.post("/usuarios/comprador-1/activar", headers=admin)
    assert activado.json()["activo"] is True
    assert [r["tipo"] for r in await _bitacora(fabrica)] == [
        "usuario.desactivado",
        "usuario.activado",
    ]


async def test_contrasena_por_correo_distingue_invitacion_y_restablecimiento(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    await cliente.post("/usuarios/comprador-1/contrasena", json={"metodo": "correo"}, headers=admin)
    async with fabrica() as sesion:
        await registrar(
            sesion,
            "sesion.iniciada",
            Actor("comprador-1", "comprador-1"),
            origen="keycloak",
            clave_origen="k:1",
        )
        await sesion.commit()
    await cliente.post("/usuarios/comprador-1/contrasena", json={"metodo": "correo"}, headers=admin)
    assert identidad.correos == [("comprador-1", 259200), ("comprador-1", 86400)]
    tipos = [c["tipo"] for c in (await cliente.get("/correos", headers=admin)).json()["elementos"]]
    assert tipos == ["restablecimiento", "invitacion"]


async def test_contrasena_temporal_y_correo_caido(
    cliente: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    temporal = await cliente.post(
        "/usuarios/comprador-1/contrasena", json={"metodo": "temporal"}, headers=admin
    )
    assert len(temporal.json()["contrasena_temporal"]) == 16
    identidad.falla_correo = True
    caido = await cliente.post(
        "/usuarios/comprador-1/contrasena", json={"metodo": "correo"}, headers=admin
    )
    assert caido.status_code == 503
    assert caido.json()["codigo"] == "correo_no_enviado"
    correos = (await cliente.get("/correos", headers=admin)).json()
    assert correos["elementos"][0]["estado"] == "fallido"


async def test_correo_a_una_cuenta_desactivada_se_rechaza_sin_dejar_rastro(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    identidad.agregar("baja", ["comprador"], activo=False)
    respuesta = await cliente.post(
        "/usuarios/baja/contrasena", json={"metodo": "correo"}, headers=admin
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "cuenta_inactiva"
    assert respuesta.json()["detail"] == (
        "La cuenta está desactivada; actívela antes de enviarle el correo."
    )
    assert identidad.correos == []
    assert await _bitacora(fabrica) == []
    async with fabrica() as sesion:
        assert await sesion.scalar(text("SELECT count(*) FROM correo_enviado")) == 0
    # La contraseña temporal sí se puede asignar a una cuenta desactivada.
    temporal = await cliente.post(
        "/usuarios/baja/contrasena", json={"metodo": "temporal"}, headers=admin
    )
    assert temporal.status_code == 200


async def test_cerrar_sesiones(
    cliente: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    respuesta = await cliente.post("/usuarios/comprador-1/cerrar-sesiones", headers=admin)
    assert respuesta.status_code == 204
    assert identidad.sesiones_cerradas == ["comprador-1"]


async def test_usuario_inexistente(cliente: httpx.AsyncClient, admin: dict[str, str]) -> None:
    respuesta = await cliente.get("/usuarios/nadie", headers=admin)
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "usuario_no_encontrado"


@pytest.mark.parametrize("id_", ["%2E%2E", "abc%3Fx=1", "a%20b", "a.b", "a" * 65])
async def test_un_id_con_caracteres_raros_es_un_422(
    cliente: httpx.AsyncClient, admin: dict[str, str], id_: str
) -> None:
    for respuesta in (
        await cliente.get(f"/usuarios/{id_}", headers=admin),
        await cliente.post(f"/usuarios/{id_}/desactivar", headers=admin),
    ):
        assert respuesta.status_code == 422
        assert "path.usuario_id" in [e["campo"] for e in respuesta.json()["errores"]]


async def test_la_cuenta_de_servicio_no_se_puede_tocar(
    cliente: httpx.AsyncClient, admin: dict[str, str], identidad: IdentidadFalsa
) -> None:
    identidad.agregar("service-account-administracion", ["admin"])
    respuesta = await cliente.post(
        "/usuarios/service-account-administracion/desactivar", headers=admin
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "usuario_no_encontrado"
    assert identidad.usuarios["service-account-administracion"].activo is True


async def test_si_la_bitacora_falla_lo_dice(
    cliente: httpx.AsyncClient, admin: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def falla(*_: object, **__: object) -> None:
        raise SQLAlchemyError("sin base")

    monkeypatch.setattr("administracion.api.rutas.registrar", falla)
    respuesta = await cliente.post("/usuarios/comprador-1/cerrar-sesiones", headers=admin)
    assert respuesta.status_code == 500
    assert respuesta.json()["codigo"] == "bitacora_no_registrada"
    assert respuesta.json()["detail"] == "La acción se aplicó, pero no quedó en la bitácora."


async def test_nombre_reservado_dice_por_que(
    cliente: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    respuesta = await cliente.post(
        "/usuarios", json={**NUEVO, "usuario": "Service-Account-x"}, headers=admin
    )
    assert respuesta.status_code == 422
    assert {"campo": "body.usuario", "mensaje": "Ese nombre de usuario está reservado."} in (
        respuesta.json()["errores"]
    )


def _que_falle(
    identidad: IdentidadFalsa,
    monkeypatch: pytest.MonkeyPatch,
    metodo: str,
    error: Exception | None = None,
) -> list[Any]:
    """Hace que un solo método del proveedor falle; devuelve los argumentos con que lo llamaron."""
    llamadas: list[Any] = []

    async def falla(*args: object, **_: object) -> None:
        llamadas.append(args)
        raise error or IdentidadNoDisponible("simulado")

    monkeypatch.setattr(identidad, metodo, falla)
    return llamadas


@pytest.mark.parametrize(
    ("metodo_alta", "falla", "pendiente"),
    [
        ("invitacion", "fijar_roles", "roles"),
        ("temporal", "fijar_contrasena_temporal", "contrasena"),
    ],
)
async def test_alta_a_medias_queda_en_la_bitacora(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    metodo_alta: str,
    falla: str,
    pendiente: str,
) -> None:
    llamadas = _que_falle(identidad, monkeypatch, falla)
    respuesta = await cliente.post(
        "/usuarios", json={**NUEVO, "metodo": metodo_alta}, headers=admin
    )
    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "alta_incompleta"
    assert cuerpo["usuario_id"] == "id-ana.lopez"
    assert cuerpo["detail"] == (
        "Se creó la cuenta, pero no se pudo terminar de configurar. "
        "Abra su ficha en Usuarios para asignar los roles o la contraseña."
    )
    assert "id-ana.lopez" in identidad.usuarios
    registros = await _bitacora(fabrica)
    assert [(r["tipo"], r["resultado"], r["objeto_id"]) for r in registros] == [
        ("usuario.creado", "fallo", "id-ana.lopez")
    ]
    assert registros[0]["detalle"] == {"roles": ["comprador"], "pendiente": pendiente}
    if metodo_alta == "temporal":
        temporal = str(llamadas[0][1])
        assert len(temporal) == 16
        assert temporal not in respuesta.text
        assert temporal not in json.dumps(registros, default=str)


async def test_desactivar_con_sesiones_que_no_se_cierran(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _que_falle(identidad, monkeypatch, "cerrar_sesiones")
    respuesta = await cliente.post("/usuarios/comprador-1/desactivar", headers=admin)
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "sesiones_no_cerradas"
    assert respuesta.json()["detail"] == (
        "La cuenta quedó desactivada, pero no se pudieron cerrar sus sesiones abiertas. "
        "Use «Cerrar sesiones» en unos minutos."
    )
    assert identidad.usuarios["comprador-1"].activo is False
    registros = await _bitacora(fabrica)
    assert [(r["tipo"], r["resultado"], r["objeto_id"]) for r in registros] == [
        ("usuario.desactivado", "exito", "comprador-1")
    ]


async def test_editar_con_roles_que_no_se_cambian(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _que_falle(identidad, monkeypatch, "fijar_roles")
    respuesta = await cliente.patch(
        "/usuarios/comprador-1",
        json={"apellidos": "Compras", "roles": ["comprador", "aprobador"]},
        headers=admin,
    )
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "roles_no_cambiados"
    assert respuesta.json()["detail"] == (
        "Se guardaron los datos, pero no se pudieron cambiar los roles. "
        "Intente de nuevo en unos minutos."
    )
    assert identidad.usuarios["comprador-1"].apellidos == "Compras"
    assert identidad.usuarios["comprador-1"].roles == {"comprador"}
    registros = await _bitacora(fabrica)
    assert [(r["tipo"], r["resultado"], r["objeto_id"]) for r in registros] == [
        ("usuario.actualizado", "exito", "comprador-1")
    ]
    assert registros[0]["detalle"] == {"campos": ["apellidos"]}


async def test_editar_solo_roles_y_la_identidad_cae_no_deja_bitacora(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _que_falle(identidad, monkeypatch, "fijar_roles")
    respuesta = await cliente.patch(
        "/usuarios/comprador-1", json={"roles": ["comprador", "aprobador"]}, headers=admin
    )
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "identidad_no_disponible"
    assert await _bitacora(fabrica) == []


def _releer_falla(identidad: IdentidadFalsa, monkeypatch: pytest.MonkeyPatch) -> None:
    """Deja pasar la primera lectura del usuario y hace fallar la siguiente (la de la respuesta)."""
    original = identidad.obtener_usuario
    lecturas = 0

    async def obtener(usuario_id: str) -> UsuarioIdentidad:
        nonlocal lecturas
        lecturas += 1
        if lecturas > 1:
            raise IdentidadNoDisponible("simulado")
        return await original(usuario_id)

    monkeypatch.setattr(identidad, "obtener_usuario", obtener)


async def test_editar_y_fallar_la_ultima_lectura_deja_la_bitacora(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _releer_falla(identidad, monkeypatch)
    respuesta = await cliente.patch(
        "/usuarios/comprador-1",
        json={"apellidos": "Compras", "roles": ["comprador", "aprobador"]},
        headers=admin,
    )
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "identidad_no_disponible"
    assert identidad.usuarios["comprador-1"].apellidos == "Compras"
    assert identidad.usuarios["comprador-1"].roles == {"comprador", "aprobador"}
    registros = await _bitacora(fabrica)
    assert [(r["tipo"], r["resultado"], r["objeto_nombre"]) for r in registros] == [
        ("usuario.actualizado", "exito", "Carlos Compras"),
        ("usuario.roles_cambiados", "exito", "Carlos Compras"),
    ]


async def test_desactivar_y_fallar_la_ultima_lectura_deja_la_bitacora(
    cliente: httpx.AsyncClient,
    admin: dict[str, str],
    identidad: IdentidadFalsa,
    fabrica: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _releer_falla(identidad, monkeypatch)
    respuesta = await cliente.post("/usuarios/comprador-1/desactivar", headers=admin)
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "identidad_no_disponible"
    assert identidad.usuarios["comprador-1"].activo is False
    assert identidad.sesiones_cerradas == ["comprador-1"]
    registros = await _bitacora(fabrica)
    assert [(r["tipo"], r["resultado"], r["objeto_nombre"]) for r in registros] == [
        ("usuario.desactivado", "exito", "Carlos Comprador")
    ]
