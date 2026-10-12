import httpx
import pytest
from comun.pruebas import ClavesPrueba
from proveedores.modelos import Outbox
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

SERVICIOS = (
    "codigo,nombre,categoria,unidad,moneda\n"
    "SAAS-OFI-EMP,Suite de productividad,licencia_saas,usuario_mes,USD\n"
    "SOP-MESA-TK,Mesa de ayuda - ticket,soporte,ticket,MXN\n"
)
PROVEEDORES = (
    "rfc,nombre,tamano,categorias,contacto_nombre,contacto_email,activo\n"
    "NAZ210315AB1,Nube Azteca S.A. de C.V.,mediana,licencia_saas,"
    "Laura Méndez,ventas01@proveedor01.example,true\n"
)
CONTRATOS = (
    "folio,rfc_proveedor,tipo,fecha_inicio,fecha_fin,moneda,plazo_pago_dias,"
    "sla_disponibilidad,tope_aumento_pct,cuota_implementacion,codigo_servicio,"
    "cantidad,precio_unitario\n"
    "C-0001,NAZ210315AB1,nuevo,2020-01-01,2099-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,200,20\n"
)


def _auth(claves: ClavesPrueba, rol: str, sub: str = "admin-7") -> dict[str, str]:
    return {"Authorization": f"Bearer {claves.token(rol, sub=sub)}"}


@pytest.fixture
async def con_catalogo(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> httpx.AsyncClient:
    for entidad, texto in (
        ("servicios", SERVICIOS),
        ("proveedores", PROVEEDORES),
        ("contratos", CONTRATOS),
    ):
        respuesta = await cliente.post(
            f"/importaciones/{entidad}",
            files={"archivo": (f"{entidad}.csv", texto.encode(), "text/csv")},
            headers=_auth(claves, "admin"),
        )
        assert respuesta.status_code == 200, respuesta.text
    return cliente


async def _eventos_servicio(fabrica: async_sessionmaker[AsyncSession]) -> list[dict[str, object]]:
    async with fabrica() as sesion:
        filas = await sesion.scalars(
            select(Outbox).where(Outbox.tipo == "servicio.actualizado").order_by(Outbox.ocurrido_en)
        )
        return [f.payload for f in filas if "cambio" in f.payload]


async def test_lista_solo_activos_y_marca_los_que_tienen_contratos(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    lista = (await con_catalogo.get("/servicios", headers=_auth(claves, "comprador"))).json()
    assert [(s["codigo"], s["activo"], s["tiene_contratos"]) for s in lista] == [
        ("SAAS-OFI-EMP", True, True),
        ("SOP-MESA-TK", True, False),
    ]


async def test_solo_admin_ve_los_inactivos(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await con_catalogo.get(
        "/servicios", params={"incluir_inactivos": "true"}, headers=_auth(claves, "comprador")
    )
    assert respuesta.status_code == 403


async def test_alta_normaliza_el_codigo_y_publica_el_evento(
    cliente: httpx.AsyncClient,
    claves: ClavesPrueba,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await cliente.post(
        "/servicios",
        json={
            "codigo": "nube-vm-2",
            "nombre": "Máquina virtual de 2 vCPU",
            "categoria": "nube",
            "unidad": "vcpu_mes",
            "moneda": "USD",
        },
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["codigo"] == "NUBE-VM-2"
    assert respuesta.json()["activo"] is True
    [evento] = await _eventos_servicio(fabrica)
    assert evento["cambio"] == "creado"
    assert evento["codigo"] == "NUBE-VM-2"
    assert evento["campos"] == []
    assert evento["actor"] == {"id": "admin-7", "nombre": "admin-7"}


async def test_alta_con_codigo_repetido(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    respuesta = await con_catalogo.post(
        "/servicios",
        json={
            "codigo": "SOP-MESA-TK",
            "nombre": "Otro",
            "categoria": "soporte",
            "unidad": "ticket",
            "moneda": "MXN",
        },
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "servicio_duplicado"
    assert respuesta.json()["errores"] == [
        {"campo": "codigo", "mensaje": "Ya existe un servicio con ese código."}
    ]


async def test_alta_con_datos_invalidos(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await cliente.post(
        "/servicios",
        json={"codigo": "x", "nombre": "", "categoria": "nube", "unidad": "litro", "moneda": "EUR"},
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 422
    assert {e["campo"] for e in respuesta.json()["errores"]} == {
        "body.codigo",
        "body.nombre",
        "body.unidad",
        "body.moneda",
    }


async def test_editar_publica_los_campos_cambiados(
    con_catalogo: httpx.AsyncClient,
    claves: ClavesPrueba,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await con_catalogo.patch(
        "/servicios/sop-mesa-tk",
        json={"nombre": "Mesa de ayuda por ticket", "unidad": "ticket"},
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["nombre"] == "Mesa de ayuda por ticket"
    [evento] = await _eventos_servicio(fabrica)
    assert (evento["cambio"], evento["campos"]) == ("actualizado", ["nombre"])


async def test_desactivar_lo_oculta_y_activar_lo_devuelve(
    con_catalogo: httpx.AsyncClient,
    claves: ClavesPrueba,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    admin = _auth(claves, "admin")
    await con_catalogo.patch("/servicios/SOP-MESA-TK", json={"activo": False}, headers=admin)
    activos = (await con_catalogo.get("/servicios", headers=admin)).json()
    assert [s["codigo"] for s in activos] == ["SAAS-OFI-EMP"]
    todos = (
        await con_catalogo.get("/servicios", params={"incluir_inactivos": "true"}, headers=admin)
    ).json()
    assert [(s["codigo"], s["activo"]) for s in todos] == [
        ("SAAS-OFI-EMP", True),
        ("SOP-MESA-TK", False),
    ]
    await con_catalogo.patch("/servicios/SOP-MESA-TK", json={"activo": True}, headers=admin)
    assert [e["cambio"] for e in await _eventos_servicio(fabrica)] == ["desactivado", "activado"]


async def test_categoria_unidad_y_moneda_bloqueadas_con_contratos(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    admin = _auth(claves, "admin")
    bloqueado = await con_catalogo.patch(
        "/servicios/SAAS-OFI-EMP",
        json={"categoria": "nube", "unidad": "vcpu_mes", "moneda": "MXN"},
        headers=admin,
    )
    assert bloqueado.status_code == 409
    assert bloqueado.json()["codigo"] == "servicio_con_contratos"
    assert bloqueado.json()["detail"] == (
        "El servicio ya tiene contratos: su categoría, su unidad y su moneda no se pueden cambiar."
    )
    assert [e["campo"] for e in bloqueado.json()["errores"]] == ["categoria", "unidad", "moneda"]
    libre = await con_catalogo.patch(
        "/servicios/SOP-MESA-TK", json={"categoria": "consultoria", "unidad": "hora"}, headers=admin
    )
    assert libre.status_code == 200
    assert (libre.json()["categoria"], libre.json()["unidad"]) == ("consultoria", "hora")


async def test_editar_sin_cambios_no_publica_nada(
    con_catalogo: httpx.AsyncClient,
    claves: ClavesPrueba,
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    respuesta = await con_catalogo.patch(
        "/servicios/SOP-MESA-TK",
        json={"nombre": "Mesa de ayuda - ticket", "activo": True},
        headers=_auth(claves, "admin"),
    )
    assert respuesta.status_code == 200
    assert await _eventos_servicio(fabrica) == []


async def test_servicio_inexistente(cliente: httpx.AsyncClient, claves: ClavesPrueba) -> None:
    respuesta = await cliente.patch(
        "/servicios/NO-EXISTE", json={"nombre": "x"}, headers=_auth(claves, "admin")
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "servicio_no_encontrado"


async def test_comprador_no_edita_el_catalogo(
    con_catalogo: httpx.AsyncClient, claves: ClavesPrueba
) -> None:
    comprador = _auth(claves, "comprador")
    alta = await con_catalogo.post(
        "/servicios",
        json={
            "codigo": "X-1",
            "nombre": "X",
            "categoria": "nube",
            "unidad": "mes",
            "moneda": "MXN",
        },
        headers=comprador,
    )
    assert alta.status_code == 403
    edicion = await con_catalogo.patch(
        "/servicios/SOP-MESA-TK", json={"nombre": "x"}, headers=comprador
    )
    assert edicion.status_code == 403
