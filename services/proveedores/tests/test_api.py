import logging
import uuid
from datetime import UTC, datetime, tzinfo
from typing import Any

import httpx
import pytest
from comun.pruebas import ClavesPrueba
from proveedores.config import Configuracion
from proveedores.main import crear_app
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integracion

SERVICIOS = (
    "codigo,nombre,categoria,unidad,moneda\n"
    "SAAS-OFI-EMP,Suite de productividad en la nube - plan empresarial,"
    "licencia_saas,usuario_mes,USD\n"
    "SOP-MESA-TK,Mesa de ayuda - ticket,soporte,ticket,MXN\n"
)
PROVEEDORES = (
    "rfc,nombre,tamano,categorias,contacto_nombre,contacto_email,activo\n"
    "NAZ210315AB1,Nube Azteca S.A. de C.V.,mediana,licencia_saas|nube,"
    "Laura Méndez,ventas01@proveedor01.example,true\n"
    "SDN190822K7P,Sistemas del Norte S.A. de C.V.,grande,consultoria,"
    "Jorge Ruiz,ventas02@proveedor02.example,true\n"
    "CPC200101QW3,Cien Por Ciento Soporte S.A. de C.V.,pequena,soporte,"
    "Ana Torres,ventas03@proveedor03.example,false\n"
)
CONTRATOS = (
    "folio,rfc_proveedor,tipo,fecha_inicio,fecha_fin,moneda,plazo_pago_dias,"
    "sla_disponibilidad,tope_aumento_pct,cuota_implementacion,codigo_servicio,"
    "cantidad,precio_unitario\n"
    "C-0001,NAZ210315AB1,nuevo,2020-01-01,2020-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,200,20\n"
    "C-0002,NAZ210315AB1,renovacion,2021-01-01,2099-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,250,21.5\n"
)
DESEMPENO = (
    "rfc_proveedor,periodo,sla_cumplimiento_pct,tiempo_resolucion_h,"
    "incidentes_criticos,entregas_a_tiempo_pct,satisfaccion\n"
    "NAZ210315AB1,2025-01-01,99.5,4.25,0,97,4.6\n"
    "NAZ210315AB1,2025-02-01,98.75,6.5,1,93,4.1\n"
)


def _auth(claves: ClavesPrueba, *roles: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token(*roles)}"}


async def _subir(
    cliente: httpx.AsyncClient,
    claves: ClavesPrueba,
    entidad: str,
    contenido: bytes,
    rol: str = "admin",
) -> httpx.Response:
    return await cliente.post(
        f"/importaciones/{entidad}",
        files={"archivo": (f"{entidad}.csv", contenido, "text/csv")},
        headers=_auth(claves, rol),
    )


@pytest.fixture
async def con_datos(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> httpx.AsyncClient:
    for entidad, texto in (
        ("servicios", SERVICIOS),
        ("proveedores", PROVEEDORES),
        ("contratos", CONTRATOS),
        ("desempeno", DESEMPENO),
    ):
        respuesta = await _subir(cliente, claves, entidad, texto.encode())
        assert respuesta.status_code == 200, respuesta.text
    return cliente


async def _id_de(cliente: httpx.AsyncClient, claves: ClavesPrueba, rfc: str) -> str:
    respuesta = await cliente.get(
        "/proveedores", params={"q": rfc}, headers=_auth(claves, "comprador")
    )
    [proveedor] = respuesta.json()["elementos"]
    return str(proveedor["id"])


async def test_sin_token_responde_401(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/proveedores")
    assert respuesta.status_code == 401
    assert respuesta.headers["content-type"] == "application/problem+json"


async def test_comprador_no_puede_importar(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await _subir(cliente, claves, "servicios", SERVICIOS.encode(), rol="comprador")
    assert respuesta.status_code == 403


async def test_importar_devuelve_resumen(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await _subir(cliente, claves, "servicios", SERVICIOS.encode())
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "entidad": "servicios",
        "filas": 2,
        "registros": 2,
        "omitidos": 0,
        "eventos": 0,
    }


async def test_importar_registra_resumen_y_usuario_sin_contenido_ni_token(
    cliente: httpx.AsyncClient, claves: ClavesPrueba, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="proveedores.api.rutas")
    token = claves.token("admin", sub="admin-42")
    respuesta = await cliente.post(
        "/importaciones/servicios",
        files={"archivo": ("servicios.csv", SERVICIOS.encode(), "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 200
    [registro] = [r for r in caplog.records if r.name == "proveedores.api.rutas"]
    assert registro.getMessage() == (
        "Importación de servicios confirmada: 2 filas, 2 registros, 0 omitidos, 0 eventos "
        "(usuario admin-42)"
    )
    assert "SAAS-OFI-EMP" not in caplog.text
    assert token not in caplog.text


async def test_importar_con_errores_devuelve_422_con_detalle(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    texto = PROVEEDORES.replace("ventas01@proveedor01.example", "correo-invalido")
    respuesta = await _subir(cliente, claves, "proveedores", texto.encode())
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["title"] == "Archivo con errores"
    assert cuerpo["errores"] == [
        {"fila": 2, "campo": "contacto_email", "mensaje": "Formato inválido"}
    ]


async def test_archivo_no_utf8_devuelve_422(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await _subir(cliente, claves, "proveedores", PROVEEDORES.encode("cp1252"))
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"][0]["mensaje"] == "El archivo debe estar codificado en UTF-8"


async def test_archivo_mayor_a_10_mb_devuelve_413(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await _subir(cliente, claves, "servicios", b"a" * (10 * 1024 * 1024 + 1))
    assert respuesta.status_code == 413


async def test_entidad_desconocida_devuelve_422(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await _subir(cliente, claves, "facturas", SERVICIOS.encode())
    assert respuesta.status_code == 422


async def test_importaciones_concurrentes_en_conflicto_devuelven_409(
    cliente: httpx.AsyncClient,
    claves: ClavesPrueba,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def choca(*_args: Any, **_kwargs: Any) -> None:
        raise IntegrityError("x", {}, Exception("dup"))

    monkeypatch.setattr("proveedores.api.rutas.importar", choca)
    respuesta = await _subir(cliente, claves, "servicios", SERVICIOS.encode())
    assert respuesta.status_code == 409
    assert respuesta.json()["title"] == "Conflicto"
    assert "Conflicto de integridad al importar servicios" in caplog.text


async def test_listar_filtrar_y_buscar(con_datos: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    async def buscar(**params: str) -> dict[str, object]:
        respuesta = await con_datos.get(
            "/proveedores", params=params, headers=_auth(claves, "aprobador")
        )
        assert respuesta.status_code == 200
        return dict(respuesta.json())

    todos = await buscar()
    assert todos["total"] == 3
    assert [p["nombre"] for p in todos["elementos"]] == [  # type: ignore[attr-defined]
        "Cien Por Ciento Soporte S.A. de C.V.",
        "Nube Azteca S.A. de C.V.",
        "Sistemas del Norte S.A. de C.V.",
    ]
    assert (await buscar(q="norte"))["total"] == 1
    assert (await buscar(q="%"))["total"] == 0
    assert (await buscar(q="_"))["total"] == 0
    assert (await buscar(categoria="soporte"))["total"] == 1
    assert (await buscar(activo="false"))["total"] == 1


async def test_paginacion(con_datos: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await con_datos.get(
        "/proveedores",
        params={"limite": 2, "desplazamiento": 2},
        headers=_auth(claves, "comprador"),
    )
    assert respuesta.json()["total"] == 3
    assert len(respuesta.json()["elementos"]) == 1


async def test_detalle_contratos_y_desempeno(
    con_datos: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    cabeceras = _auth(claves, "comprador")
    proveedor_id = await _id_de(con_datos, claves, "NAZ210315AB1")

    detalle = (await con_datos.get(f"/proveedores/{proveedor_id}", headers=cabeceras)).json()
    assert detalle["contratos_vigentes"] == 1
    assert detalle["contacto_email"] == "ventas01@proveedor01.example"

    contratos = (
        await con_datos.get(f"/proveedores/{proveedor_id}/contratos", headers=cabeceras)
    ).json()
    assert [c["folio"] for c in contratos] == ["C-0002", "C-0001"]
    assert contratos[0]["lineas"] == [
        {
            "codigo_servicio": "SAAS-OFI-EMP",
            "nombre_servicio": "Suite de productividad en la nube - plan empresarial",
            "unidad": "usuario_mes",
            "cantidad": "250.0000",
            "precio_unitario": "21.5000",
        }
    ]

    desempeno = (
        await con_datos.get(
            f"/proveedores/{proveedor_id}/desempeno", params={"meses": 1}, headers=cabeceras
        )
    ).json()
    assert [d["periodo"] for d in desempeno] == ["2025-02-01"]


async def test_contratos_vigentes_usa_el_dia_de_negocio_en_mexico(
    con_datos: httpx.AsyncClient, claves: ClavesPrueba, monkeypatch: pytest.MonkeyPatch
) -> None:
    class RelojFijo:
        @staticmethod
        def now(tz: tzinfo | None = None) -> datetime:
            # 04:00 UTC del 2100-01-01 son las 22:00 del 2099-12-31 en Ciudad de México.
            return datetime(2100, 1, 1, 4, 0, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr("proveedores.api.rutas.datetime", RelojFijo)
    proveedor_id = await _id_de(con_datos, claves, "NAZ210315AB1")
    detalle = await con_datos.get(
        f"/proveedores/{proveedor_id}", headers=_auth(claves, "comprador")
    )
    # C-0002 vence el 2099-12-31: sigue vigente en México aunque en UTC ya sea 2100.
    assert detalle.json()["contratos_vigentes"] == 1


async def test_orden_deterministico_con_nombres_y_fechas_iguales(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    proveedores = (
        "rfc,nombre,tamano,categorias,contacto_nombre,contacto_email,activo\n"
        "AAA210101AB1,Mismo Nombre S.A.,mediana,nube,Ana,a@proveedor.example,true\n"
        "BBB210101AB1,Mismo Nombre S.A.,mediana,nube,Beto,b@proveedor.example,true\n"
        "CCC210101AB1,Mismo Nombre S.A.,mediana,nube,Caro,c@proveedor.example,true\n"
    )
    # Dos contratos con la misma fecha de inicio; el folio mayor se importa primero, así que
    # sin desempate saldrían en orden de inserción.
    contratos = (
        CONTRATOS.split("\n", 1)[0]
        + "\n"
        + "C-0009,AAA210101AB1,nuevo,2020-01-01,2099-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,10,20\n"
        + "C-0002,AAA210101AB1,nuevo,2020-01-01,2099-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,10,20\n"
    )
    for entidad, texto in (
        ("servicios", SERVICIOS),
        ("proveedores", proveedores),
        ("contratos", contratos),
    ):
        assert (await _subir(cliente, claves, entidad, texto.encode())).status_code == 200
    cabeceras = _auth(claves, "comprador")

    ids = []
    for desplazamiento in range(3):
        pagina = await cliente.get(
            "/proveedores",
            params={"limite": 1, "desplazamiento": desplazamiento},
            headers=cabeceras,
        )
        ids.append(pagina.json()["elementos"][0]["id"])
    assert ids == sorted(ids)

    proveedor_id = await _id_de(cliente, claves, "AAA210101AB1")
    salida = await cliente.get(f"/proveedores/{proveedor_id}/contratos", headers=cabeceras)
    assert [c["folio"] for c in salida.json()] == ["C-0002", "C-0009"]


async def test_proveedor_inexistente_o_id_invalido(
    con_datos: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    cabeceras = _auth(claves, "comprador")
    inexistente = uuid.uuid4()
    assert (
        await con_datos.get(f"/proveedores/{inexistente}", headers=cabeceras)
    ).status_code == 404
    assert (
        await con_datos.get(f"/proveedores/{inexistente}/contratos", headers=cabeceras)
    ).status_code == 404
    assert (await con_datos.get("/proveedores/no-es-uuid", headers=cabeceras)).status_code == 422


async def test_errores_de_validacion_de_parametros_en_espanol(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    cabeceras = _auth(claves, "comprador")

    async def errores(ruta: str, **params: str | int) -> list[dict[str, str]]:
        respuesta = await cliente.get(ruta, params=params, headers=cabeceras)
        assert respuesta.status_code == 422
        return list(respuesta.json()["errores"])

    assert await errores("/proveedores/no-es-uuid") == [
        {"campo": "path.proveedor_id", "mensaje": "Debe ser un UUID válido"}
    ]
    assert await errores("/proveedores", limite=500) == [
        {"campo": "query.limite", "mensaje": "Debe ser menor o igual que 100"}
    ]
    assert await errores("/proveedores", categoria="otra") == [
        {
            "campo": "query.categoria",
            "mensaje": "Valor no permitido; opciones: licencia_saas, nube, consultoria o soporte",
        }
    ]
    assert await errores("/proveedores", activo="quizas") == [
        {"campo": "query.activo", "mensaje": "Debe ser true o false"}
    ]


async def test_desplazamiento_fuera_de_rango_devuelve_422(
    cliente: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await cliente.get(
        "/proveedores", params={"desplazamiento": 1_000_001}, headers=_auth(claves, "comprador")
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        {"campo": "query.desplazamiento", "mensaje": "Debe ser menor o igual que 1000000"}
    ]


async def test_catalogo_de_servicios(con_datos: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await con_datos.get("/servicios", headers=_auth(claves, "comprador"))
    assert [s["codigo"] for s in respuesta.json()] == ["SAAS-OFI-EMP", "SOP-MESA-TK"]


def test_motor_no_expone_parametros_sql_y_verifica_conexiones(claves: ClavesPrueba) -> None:
    app = crear_app(Configuracion(), claves.validador())
    motor = app.state.fabrica.kw["bind"].sync_engine
    assert motor.hide_parameters is True
    assert motor.pool._pre_ping is True


async def test_salud(cliente: httpx.AsyncClient) -> None:
    assert (await cliente.get("/salud/vivo")).status_code == 200
    listo = await cliente.get("/salud/listo")
    # En pruebas no corre el ciclo de vida, así que el relay no está conectado.
    assert listo.status_code == 503
    assert listo.json()["dependencias"] == {"postgres": "ok", "rabbitmq": "error"}
