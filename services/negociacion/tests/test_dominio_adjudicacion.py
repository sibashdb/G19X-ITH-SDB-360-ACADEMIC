import json
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal as D
from typing import Any

import pytest
from negociacion.dominio.adjudicacion import (
    LineaTerminos,
    TerminosContrato,
    requiere_aprobacion,
    sumar_meses,
    terminos_contrato,
)
from negociacion.dominio.terminos import Valores

# 05:30 UTC del 2 de noviembre es todavía el 1 de noviembre (23:30) en la Ciudad de México.
ADJUDICADA = datetime(2026, 11, 2, 5, 30, tzinfo=UTC)
LINEAS = (
    LineaTerminos("l1", "SAAS-CRM-PRO", D("120.0000")),
    LineaTerminos("l2", "NUBE-VM-STD", D("8.0000")),
)
SIN_NEGOCIAR = Valores(precios={"l1": D("30.50"), "l2": D("100.00")}, palancas={})
VIGENTE = {  # como lo guarda ContratoVigente.terminos() en la foto del evento
    "folio": "C-000901",
    "fecha_inicio": "2025-11-01",
    "fecha_fin": "2026-10-31",
    "plazo_meses": 12,
    "plazo_pago_dias": 45,
    "sla_disponibilidad": "99.50",
    "tope_aumento_pct": "5.00",
    "cuota_implementacion": "1500.00",
}


def terminos(
    *,
    tipo: str = "compra",
    valores: Valores = SIN_NEGOCIAR,
    vigente: Mapping[str, Any] | None = None,
    plazo: int = 12,
    decidida_en: datetime = ADJUDICADA,
) -> TerminosContrato:
    return terminos_contrato(
        folio_evento="NEG-2026-0004",
        tipo_evento=tipo,
        moneda="USD",
        plazo_evento=plazo,
        valores=valores,
        lineas=LINEAS,
        contrato_vigente=vigente,
        decidida_en=decidida_en,
    )


def test_regla_de_aprobacion() -> None:
    assert requiere_aprobacion(D("400000"), D("500000"), False) == (False, [])
    assert requiere_aprobacion(D("500000.01"), D("500000"), False) == (True, ["umbral"])
    assert requiere_aprobacion(D("1"), D("500000"), True) == (True, ["fuera_de_limites"])
    assert requiere_aprobacion(D("600000"), D("500000"), True) == (
        True,
        ["umbral", "fuera_de_limites"],
    )


def test_el_umbral_exacto_no_pide_aprobacion() -> None:
    assert requiere_aprobacion(D("500000"), D("500000"), False) == (False, [])


@pytest.mark.parametrize(
    ("inicio", "meses", "esperado"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),  # año bisiesto
        (date(2026, 11, 2), 12, date(2027, 11, 2)),
        (date(2026, 12, 15), 2, date(2027, 2, 15)),  # cruza el año
        (date(2026, 3, 31), 60, date(2031, 3, 31)),
    ],
)
def test_sumar_meses_acota_el_fin_de_mes(inicio: date, meses: int, esperado: date) -> None:
    assert sumar_meses(inicio, meses) == esperado


def test_compra_empieza_el_dia_siguiente_en_hora_de_mexico() -> None:
    contrato = terminos()
    assert contrato.tipo == "nuevo"
    assert contrato.fecha_inicio == date(2026, 11, 2)
    assert contrato.fecha_fin == date(2027, 11, 1)


def test_pasada_la_medianoche_de_mexico_la_compra_empieza_un_dia_despues() -> None:
    contrato = terminos(decidida_en=datetime(2026, 11, 2, 6, 0, tzinfo=UTC))  # 00:00 del 2/11
    assert contrato.fecha_inicio == date(2026, 11, 3)


def test_renovacion_empieza_al_dia_siguiente_del_contrato_vigente() -> None:
    contrato = terminos(tipo="renovacion", vigente=VIGENTE)
    assert contrato.tipo == "renovacion"
    assert contrato.fecha_inicio == date(2026, 11, 1)
    assert contrato.fecha_fin == date(2027, 10, 31)


def test_una_renovacion_sin_contrato_vigente_es_un_error() -> None:
    with pytest.raises(ValueError, match="contrato vigente"):
        terminos(tipo="renovacion")


def test_lo_no_negociado_sale_del_contrato_vigente_o_del_valor_por_defecto() -> None:
    compra = terminos()
    assert compra.plazo_pago_dias == 30
    assert compra.sla_disponibilidad is None
    assert compra.tope_aumento_pct is None
    assert compra.cuota_implementacion == 0

    renovacion = terminos(tipo="renovacion", vigente=VIGENTE)
    assert renovacion.plazo_pago_dias == 45
    assert renovacion.sla_disponibilidad == D("99.50")
    assert renovacion.tope_aumento_pct == D("5.00")
    # La cuota se paga una vez: no pasa de un contrato al siguiente (spec §4.4).
    assert renovacion.cuota_implementacion == 0


def test_renovacion_sin_sla_ni_tope_vigentes_los_deja_nulos() -> None:
    vigente = VIGENTE | {"sla_disponibilidad": None, "tope_aumento_pct": None}
    contrato = terminos(tipo="renovacion", vigente=vigente)
    assert contrato.sla_disponibilidad is None
    assert contrato.tope_aumento_pct is None


def test_lo_acordado_manda_sobre_el_contrato_vigente() -> None:
    acordado = Valores(
        precios=SIN_NEGOCIAR.precios,
        palancas={
            "plazo_pago_dias": D("60"),
            "sla_disponibilidad": D("99.90"),
            "tope_aumento_pct": D("3.0"),
            "cuota_implementacion": D("2500.00"),
        },
    )
    contrato = terminos(tipo="renovacion", vigente=VIGENTE, valores=acordado)
    assert contrato.plazo_pago_dias == 60
    assert contrato.sla_disponibilidad == D("99.90")
    assert contrato.tope_aumento_pct == D("3.0")
    assert contrato.cuota_implementacion == D("2500.00")


def test_el_plazo_acordado_manda() -> None:
    acordado = Valores(precios=SIN_NEGOCIAR.precios, palancas={"plazo_meses": D("24")})
    contrato = terminos(valores=acordado, plazo=12)
    assert contrato.fecha_fin == date(2028, 11, 1)  # 24 meses desde el 2/11/2026, menos un día


def test_folio_del_contrato() -> None:
    folio = terminos().folio
    assert folio == "C-NEG-2026-0004"
    assert re.fullmatch(r"[A-Z0-9-]{3,30}", folio)


def test_las_lineas_llevan_el_precio_acordado() -> None:
    contrato = terminos()
    assert [(c.codigo_servicio, c.cantidad, c.precio_unitario) for c in contrato.lineas] == [
        ("SAAS-CRM-PRO", D("120.0000"), D("30.50")),
        ("NUBE-VM-STD", D("8.0000"), D("100.00")),
    ]


def test_para_evento_serializa_fechas_y_montos_como_texto() -> None:
    carga = terminos(tipo="renovacion", vigente=VIGENTE).para_evento()
    assert carga == {
        "folio": "C-NEG-2026-0004",
        "tipo": "renovacion",
        "moneda": "USD",
        "fecha_inicio": "2026-11-01",
        "fecha_fin": "2027-10-31",
        "plazo_pago_dias": 45,
        "sla_disponibilidad": "99.50",
        "tope_aumento_pct": "5.00",
        "cuota_implementacion": "0",
        "lineas": [
            {"codigo_servicio": "SAAS-CRM-PRO", "cantidad": "120.0000", "precio_unitario": "30.50"},
            {"codigo_servicio": "NUBE-VM-STD", "cantidad": "8.0000", "precio_unitario": "100.00"},
        ],
    }
    json.dumps(carga)  # lo que va al Outbox tiene que ser JSON


def test_para_evento_deja_nulos_los_terminos_que_no_se_negociaron() -> None:
    carga = terminos().para_evento()
    assert carga["sla_disponibilidad"] is None
    assert carga["tope_aumento_pct"] is None
