from decimal import Decimal

import pytest
from proveedores.importacion.aplicar import (
    Entidad,
    ErrorImportacion,
    ResumenImportacion,
    importar,
)
from proveedores.modelos import Contrato, Outbox, Proveedor, RegistroDesempeno, TipoCambio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]

SERVICIOS = (
    "codigo,nombre,categoria,unidad,moneda\n"
    "SAAS-OFI-EMP,Suite de productividad en la nube - plan empresarial,"
    "licencia_saas,usuario_mes,USD\n"
    "CONS-DEV-SR,Desarrollador(a) senior - hora,consultoria,hora,MXN\n"
)
PROVEEDORES = (
    "rfc,nombre,tamano,categorias,contacto_nombre,contacto_email,activo\n"
    "NAZ210315AB1,Nube Azteca S.A. de C.V.,mediana,licencia_saas|nube,"
    "Laura Méndez,ventas01@proveedor01.example,true\n"
    "SDN190822K7P,Sistemas del Norte S.A. de C.V.,grande,consultoria,"
    "Jorge Ruiz,ventas02@proveedor02.example,true\n"
)
CONTRATO_ENC = (
    "folio,rfc_proveedor,tipo,fecha_inicio,fecha_fin,moneda,plazo_pago_dias,"
    "sla_disponibilidad,tope_aumento_pct,cuota_implementacion,codigo_servicio,"
    "cantidad,precio_unitario\n"
)
CONTRATOS = (
    CONTRATO_ENC
    + "C-0001,NAZ210315AB1,nuevo,2025-01-01,2025-12-31,USD,30,99.9,5,0,SAAS-OFI-EMP,250,21.5\n"
    + "C-0002,SDN190822K7P,nuevo,2025-03-01,2025-08-31,MXN,45,,,0,CONS-DEV-SR,160,1050\n"
)
DESEMPENO_ENC = (
    "rfc_proveedor,periodo,sla_cumplimiento_pct,tiempo_resolucion_h,"
    "incidentes_criticos,entregas_a_tiempo_pct,satisfaccion\n"
)
DESEMPENO = (
    DESEMPENO_ENC
    + "NAZ210315AB1,2025-01-01,99.5,4.25,0,97,4.6\n"
    + "NAZ210315AB1,2025-02-01,98.75,6.5,1,93,4.1\n"
)


async def _importar(fabrica: Fabrica, entidad: Entidad, texto: str) -> ResumenImportacion:
    async with fabrica() as sesion, sesion.begin():
        return await importar(sesion, entidad, texto.encode())


async def _contar(fabrica: Fabrica, modelo: type[object]) -> int:
    async with fabrica() as sesion:
        return int(await sesion.scalar(select(func.count()).select_from(modelo)) or 0)


async def _eventos(fabrica: Fabrica, tipo: str) -> list[Outbox]:
    async with fabrica() as sesion:
        return list((await sesion.scalars(select(Outbox).where(Outbox.tipo == tipo))).all())


async def _catalogo_y_proveedores(fabrica: Fabrica) -> None:
    await _importar(fabrica, Entidad.SERVICIOS, SERVICIOS)
    await _importar(fabrica, Entidad.PROVEEDORES, PROVEEDORES)


async def test_importar_proveedores_crea_registros_y_eventos(fabrica: Fabrica) -> None:
    await _importar(fabrica, Entidad.SERVICIOS, SERVICIOS)
    resumen = await _importar(fabrica, Entidad.PROVEEDORES, PROVEEDORES)
    assert resumen == ResumenImportacion("proveedores", 2, 2, 0, 2)
    eventos = await _eventos(fabrica, "proveedor.actualizado")
    assert sorted(e.payload["rfc"] for e in eventos) == ["NAZ210315AB1", "SDN190822K7P"]
    assert eventos[0].payload["categorias"] in (["licencia_saas", "nube"], ["consultoria"])


async def test_reimportar_proveedores_actualiza_sin_duplicar(fabrica: Fabrica) -> None:
    await _importar(fabrica, Entidad.PROVEEDORES, PROVEEDORES)
    await _importar(fabrica, Entidad.PROVEEDORES, PROVEEDORES.replace("Nube Azteca", "Nube Maya"))
    assert await _contar(fabrica, Proveedor) == 2
    async with fabrica() as sesion:
        nombre = await sesion.scalar(
            select(Proveedor.nombre).where(Proveedor.rfc == "NAZ210315AB1")
        )
    assert nombre == "Nube Maya S.A. de C.V."


async def test_importar_contratos_crea_lineas_y_evento_con_detalle(fabrica: Fabrica) -> None:
    await _catalogo_y_proveedores(fabrica)
    resumen = await _importar(fabrica, Entidad.CONTRATOS, CONTRATOS)
    assert resumen == ResumenImportacion("contratos", 2, 2, 0, 2)
    [evento] = [
        e for e in await _eventos(fabrica, "contrato.registrado") if e.payload["folio"] == "C-0001"
    ]
    assert evento.payload["rfc_proveedor"] == "NAZ210315AB1"
    assert evento.payload["lineas"] == [
        {
            "codigo_servicio": "SAAS-OFI-EMP",
            "nombre_servicio": "Suite de productividad en la nube - plan empresarial",
            "categoria": "licencia_saas",
            "unidad": "usuario_mes",
            "cantidad": "250",
            "precio_unitario": "21.5",
        }
    ]
    async with fabrica() as sesion:
        precio = await sesion.scalar(
            select(Contrato.cuota_implementacion).where(Contrato.folio == "C-0002")
        )
    assert precio == Decimal("0.0000")


async def test_reimportar_contratos_es_idempotente(fabrica: Fabrica) -> None:
    await _catalogo_y_proveedores(fabrica)
    await _importar(fabrica, Entidad.CONTRATOS, CONTRATOS)
    segunda = await _importar(fabrica, Entidad.CONTRATOS, CONTRATOS)
    assert segunda == ResumenImportacion("contratos", 2, 0, 2, 0)
    assert await _contar(fabrica, Contrato) == 2
    assert len(await _eventos(fabrica, "contrato.registrado")) == 2


async def test_referencias_inexistentes_no_escriben_nada(fabrica: Fabrica) -> None:
    await _catalogo_y_proveedores(fabrica)
    texto = (
        CONTRATO_ENC
        + "C-0003,XAX010101AB1,nuevo,2025-01-01,2025-12-31,USD,30,,,0,SAAS-OFI-EMP,10,20\n"
        + "C-0004,NAZ210315AB1,nuevo,2025-01-01,2025-12-31,USD,30,,,0,NO-EXISTE,10,20\n"
        + "C-0005,NAZ210315AB1,nuevo,2025-01-01,2025-12-31,MXN,30,,,0,SAAS-OFI-EMP,10,20\n"
    )
    with pytest.raises(ErrorImportacion) as error:
        await _importar(fabrica, Entidad.CONTRATOS, texto)
    assert [(e.fila, e.campo) for e in error.value.errores] == [
        (2, "rfc_proveedor"),
        (3, "codigo_servicio"),
        (4, "moneda"),
    ]
    assert error.value.estado == 422
    assert await _contar(fabrica, Contrato) == 0
    assert await _eventos(fabrica, "contrato.registrado") == []


async def test_un_error_de_formato_cancela_todo_el_archivo(fabrica: Fabrica) -> None:
    texto = PROVEEDORES + "MAL210315AB1,Otro,mediana,nube,Ana,correo-invalido,true\n"
    with pytest.raises(ErrorImportacion) as error:
        await _importar(fabrica, Entidad.PROVEEDORES, texto)
    assert error.value.extra["total_errores"] == 1
    assert error.value.extra["errores"][0]["campo"] == "contacto_email"
    assert await _contar(fabrica, Proveedor) == 0


async def test_desempeno_se_actualiza_por_periodo(fabrica: Fabrica) -> None:
    await _catalogo_y_proveedores(fabrica)
    await _importar(fabrica, Entidad.DESEMPENO, DESEMPENO)
    resumen = await _importar(fabrica, Entidad.DESEMPENO, DESEMPENO.replace("4.6", "4.9"))
    assert resumen == ResumenImportacion("desempeno", 2, 2, 0, 2)
    assert await _contar(fabrica, RegistroDesempeno) == 2
    async with fabrica() as sesion:
        satisfacciones = (await sesion.scalars(select(RegistroDesempeno.satisfaccion))).all()
    assert Decimal("4.90") in satisfacciones
    assert len(await _eventos(fabrica, "desempeno.registrado")) == 4


async def test_tipo_cambio_se_actualiza_sin_eventos(fabrica: Fabrica) -> None:
    await _importar(fabrica, Entidad.TIPO_CAMBIO, "periodo,usd_mxn\n2025-01-01,20.4512\n")
    await _importar(fabrica, Entidad.TIPO_CAMBIO, "periodo,usd_mxn\n2025-01-01,20.1000\n")
    async with fabrica() as sesion:
        [valor] = (await sesion.scalars(select(TipoCambio.usd_mxn))).all()
    assert valor == Decimal("20.1000")
    assert await _contar(fabrica, Outbox) == 0


async def test_archivo_solo_con_encabezado_no_hace_nada(fabrica: Fabrica) -> None:
    resumen = await _importar(fabrica, Entidad.SERVICIOS, "codigo,nombre,categoria,unidad,moneda\n")
    assert resumen == ResumenImportacion("servicios", 0, 0, 0, 0)
