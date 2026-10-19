import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from proveedores.eventos import aplicar, atendedor
from proveedores.importacion.aplicar import Entidad, importar
from proveedores.modelos import (
    Contrato,
    EventoProcesado,
    LineaContrato,
    Outbox,
    Proveedor,
    ServicioCatalogo,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]

PROVEEDOR_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


def _sobre(event_id: str = "evento-1", **cambios_contrato: Any) -> dict[str, Any]:
    """Un negociacion.adjudicada tal como lo publica la negociación (Task 8)."""
    contrato = {
        "folio": "C-NEG-2026-0001",
        "tipo": "nuevo",
        "moneda": "USD",
        "fecha_inicio": "2026-10-14",
        "fecha_fin": "2027-10-13",
        "plazo_pago_dias": 30,
        "sla_disponibilidad": None,
        "tope_aumento_pct": None,
        "cuota_implementacion": "0",
        "lineas": [
            {"codigo_servicio": "SAAS-OFI-EMP", "cantidad": "250", "precio_unitario": "21.5"},
            {"codigo_servicio": "SOP-MESA-TK", "cantidad": "40.0000", "precio_unitario": "12.00"},
        ],
    } | cambios_contrato
    return {
        "event_id": event_id,
        "type": "negociacion.adjudicada",
        "version": 1,
        "occurred_at": "2026-10-13T15:00:00+00:00",
        "correlation_id": "c-1",
        "payload": {
            "folio": "NEG-2026-0001",
            "titulo": "Suite de productividad",
            "tipo": "compra",
            "proveedor_id": str(PROVEEDOR_ID),
            "proveedor": "Nube Azteca S.A. de C.V.",
            "costo_total_mxn": "125000.00",
            "contrato": contrato,
            "aprobacion": "directa",
            "actor": {"id": "comprador-1", "nombre": "comprador-1"},
        },
    }


@pytest.fixture
async def catalogo_y_proveedor(fabrica: Fabrica) -> None:
    async with fabrica() as bd, bd.begin():
        bd.add(
            Proveedor(
                id=PROVEEDOR_ID,
                rfc="NAZ210315AB1",
                nombre="Nube Azteca S.A. de C.V.",
                tamano="mediana",
                categorias=["licencia_saas"],
                contacto_nombre="Laura Méndez",
                contacto_email="ventas01@proveedor01.example",
            )
        )
        bd.add_all(
            [
                ServicioCatalogo(
                    codigo="SAAS-OFI-EMP",
                    nombre="Suite de productividad en la nube - plan empresarial",
                    categoria="licencia_saas",
                    unidad="usuario_mes",
                    moneda="USD",
                ),
                ServicioCatalogo(
                    codigo="SOP-MESA-TK",
                    nombre="Mesa de ayuda - ticket",
                    categoria="soporte",
                    unidad="ticket",
                    moneda="USD",
                ),
            ]
        )


async def _aplicar(fabrica: Fabrica, sobre: dict[str, Any]) -> bool:
    async with fabrica() as bd, bd.begin():
        return await aplicar(bd, sobre)


async def _contar(fabrica: Fabrica, *modelos: type[object]) -> list[int]:
    async with fabrica() as bd:
        return [
            int(await bd.scalar(select(func.count()).select_from(modelo)) or 0)
            for modelo in modelos
        ]


async def _contratos_publicados(fabrica: Fabrica) -> list[dict[str, Any]]:
    async with fabrica() as bd:
        filas = await bd.scalars(select(Outbox).where(Outbox.tipo == "contrato.registrado"))
        return [fila.payload for fila in filas]


async def test_la_adjudicacion_crea_el_contrato_y_lo_publica(
    fabrica: Fabrica, catalogo_y_proveedor: None
) -> None:
    assert await _aplicar(fabrica, _sobre()) is True

    async with fabrica() as bd:
        contrato = await bd.scalar(select(Contrato).where(Contrato.folio == "C-NEG-2026-0001"))
        assert contrato is not None
        assert contrato.proveedor_id == PROVEEDOR_ID
        assert (contrato.tipo, contrato.moneda) == ("nuevo", "USD")
        assert (contrato.fecha_inicio, contrato.fecha_fin) == (
            date(2026, 10, 14),
            date(2027, 10, 13),
        )
        assert contrato.plazo_pago_dias == 30
        assert (contrato.sla_disponibilidad, contrato.tope_aumento_pct) == (None, None)
        assert contrato.cuota_implementacion == Decimal(0)
        lineas = (
            await bd.execute(
                select(
                    ServicioCatalogo.codigo, LineaContrato.cantidad, LineaContrato.precio_unitario
                )
                .join(LineaContrato.servicio)
                .where(LineaContrato.contrato_id == contrato.id)
                .order_by(ServicioCatalogo.codigo)
            )
        ).all()
    assert [tuple(linea) for linea in lineas] == [
        ("SAAS-OFI-EMP", Decimal("250"), Decimal("21.5")),
        ("SOP-MESA-TK", Decimal("40"), Decimal("12")),
    ]

    [publicado] = await _contratos_publicados(fabrica)
    assert publicado["id"] == str(contrato.id)
    assert publicado["proveedor_id"] == str(PROVEEDOR_ID)
    assert publicado["rfc_proveedor"] == "NAZ210315AB1"
    assert publicado["folio"] == "C-NEG-2026-0001"
    assert publicado["fecha_inicio"] == "2026-10-14"
    assert publicado["sla_disponibilidad"] is None
    assert publicado["lineas"][0] == {
        "codigo_servicio": "SAAS-OFI-EMP",
        "nombre_servicio": "Suite de productividad en la nube - plan empresarial",
        "categoria": "licencia_saas",
        "unidad": "usuario_mes",
        "cantidad": "250",
        "precio_unitario": "21.5",
    }


async def test_publica_lo_mismo_que_la_importacion(
    fabrica: Fabrica, catalogo_y_proveedor: None
) -> None:
    csv = (
        "folio,rfc_proveedor,tipo,fecha_inicio,fecha_fin,moneda,plazo_pago_dias,"
        "sla_disponibilidad,tope_aumento_pct,cuota_implementacion,codigo_servicio,"
        "cantidad,precio_unitario\n"
        "C-IMP-0001,NAZ210315AB1,nuevo,2026-10-14,2027-10-13,USD,30,,,0,SAAS-OFI-EMP,250,21.5\n"
    )
    async with fabrica() as bd, bd.begin():
        await importar(bd, Entidad.CONTRATOS, csv.encode())
    [importado] = await _contratos_publicados(fabrica)

    sobre = _sobre()  # el mismo contrato, ahora por adjudicación
    sobre["payload"]["contrato"]["lineas"].pop()
    await _aplicar(fabrica, sobre)
    adjudicado = next(p for p in await _contratos_publicados(fabrica) if p["id"] != importado["id"])

    assert adjudicado | {"id": importado["id"], "folio": "C-IMP-0001"} == importado


async def test_el_mismo_evento_dos_veces_no_duplica(
    fabrica: Fabrica, catalogo_y_proveedor: None
) -> None:
    assert await _aplicar(fabrica, _sobre()) is True
    assert await _aplicar(fabrica, _sobre()) is False
    assert await _contar(fabrica, Contrato, LineaContrato, Outbox, EventoProcesado) == [1, 2, 1, 1]


async def test_folio_existente_no_duplica(fabrica: Fabrica, catalogo_y_proveedor: None) -> None:
    await _aplicar(fabrica, _sobre("evento-1"))

    assert await _aplicar(fabrica, _sobre("evento-2")) is False

    assert await _contar(fabrica, Contrato, LineaContrato, Outbox) == [1, 2, 1]


async def test_servicio_desconocido_se_reintenta_y_no_guarda_nada(
    fabrica: Fabrica, catalogo_y_proveedor: None
) -> None:
    sobre = _sobre()
    sobre["payload"]["contrato"]["lineas"][1]["codigo_servicio"] = "NO-EXISTE"

    with pytest.raises(KeyError, match="NO-EXISTE"):
        await _aplicar(fabrica, sobre)

    assert await _contar(fabrica, Contrato, LineaContrato, Outbox, EventoProcesado) == [0] * 4


async def test_proveedor_desconocido_se_reintenta_y_no_guarda_nada(
    fabrica: Fabrica, catalogo_y_proveedor: None
) -> None:
    sobre = _sobre()
    sobre["payload"]["proveedor_id"] = str(uuid.uuid4())

    with pytest.raises(KeyError, match="Proveedor"):
        await _aplicar(fabrica, sobre)

    assert await _contar(fabrica, Contrato, LineaContrato, Outbox, EventoProcesado) == [0] * 4


@pytest.mark.parametrize(
    "cambio",
    [
        {"fecha_inicio": "no es fecha"},
        {"plazo_pago_dias": None},
        {"cuota_implementacion": "mucho"},
        {"lineas": []},
        {"lineas": [{"codigo_servicio": "SAAS-OFI-EMP", "cantidad": "250"}]},
        {"tipo": "compra"},
        {"moneda": "EUR"},
        {"fecha_fin": "2026-10-14"},  # la vigencia no empieza antes de terminar
        {
            "lineas": [
                {"codigo_servicio": "SAAS-OFI-EMP", "cantidad": "1", "precio_unitario": "2"},
                {"codigo_servicio": "SAAS-OFI-EMP", "cantidad": "3", "precio_unitario": "4"},
            ]
        },
    ],
    ids=[
        "fecha",
        "plazo",
        "cuota",
        "sin_lineas",
        "linea_sin_precio",
        "tipo",
        "moneda",
        "vigencia",
        "servicio_repetido",
    ],
)
async def test_un_payload_mal_formado_es_evento_invalido(
    fabrica: Fabrica, catalogo_y_proveedor: None, cambio: dict[str, Any]
) -> None:
    with pytest.raises(ValueError):
        await _aplicar(fabrica, _sobre(**cambio))

    assert await _contar(fabrica, Contrato, Outbox, EventoProcesado) == [0] * 3


async def test_una_moneda_distinta_a_la_del_servicio_es_evento_invalido(
    fabrica: Fabrica, catalogo_y_proveedor: None
) -> None:
    with pytest.raises(ValueError, match="SAAS-OFI-EMP, SOP-MESA-TK"):
        await _aplicar(fabrica, _sobre(moneda="MXN"))  # el catálogo está en USD

    assert await _contar(fabrica, Contrato, LineaContrato, Outbox, EventoProcesado) == [0] * 4


async def test_una_renovacion_conserva_el_sla_y_el_tope_acordados(
    fabrica: Fabrica, catalogo_y_proveedor: None
) -> None:
    await _aplicar(
        fabrica,
        _sobre(
            tipo="renovacion",
            plazo_pago_dias=45,
            sla_disponibilidad="99.90",
            tope_aumento_pct="5.00",
            cuota_implementacion="1500.50",
        ),
    )

    async with fabrica() as bd:
        contrato = await bd.scalar(select(Contrato))
    assert contrato is not None
    assert (contrato.tipo, contrato.plazo_pago_dias) == ("renovacion", 45)
    assert contrato.sla_disponibilidad == Decimal("99.90")
    assert contrato.tope_aumento_pct == Decimal("5.00")
    assert contrato.cuota_implementacion == Decimal("1500.50")
    [publicado] = await _contratos_publicados(fabrica)
    assert (publicado["tipo"], publicado["plazo_pago_dias"]) == ("renovacion", 45)
    assert publicado["sla_disponibilidad"] == "99.90"
    assert publicado["tope_aumento_pct"] == "5.00"
    assert publicado["cuota_implementacion"] == "1500.50"


async def test_un_folio_existente_deja_un_aviso_sin_los_terminos(
    fabrica: Fabrica, catalogo_y_proveedor: None, caplog: pytest.LogCaptureFixture
) -> None:
    await _aplicar(fabrica, _sobre("evento-1"))

    with caplog.at_level(logging.WARNING, logger="proveedores.eventos"):
        await _aplicar(fabrica, _sobre("evento-2"))

    [aviso] = [r.getMessage() for r in caplog.records if r.name == "proveedores.eventos"]
    assert "C-NEG-2026-0001" in aviso
    assert "evento-2" in aviso
    assert "Nube Azteca" not in aviso
    assert "125000" not in aviso


async def test_un_payload_sin_contrato_es_evento_invalido(
    fabrica: Fabrica, catalogo_y_proveedor: None
) -> None:
    sobre = _sobre()
    del sobre["payload"]["contrato"]

    with pytest.raises(ValueError):
        await _aplicar(fabrica, sobre)


async def test_el_atendedor_aplica_en_su_propia_transaccion(
    fabrica: Fabrica, catalogo_y_proveedor: None
) -> None:
    await atendedor(fabrica)(_sobre())

    assert await _contar(fabrica, Contrato, Outbox, EventoProcesado) == [1, 1, 1]
