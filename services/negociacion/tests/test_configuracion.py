from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest
from negociacion.dominio.configuracion import (
    Banda,
    LineaRevision,
    PalancaRevision,
    Problema,
    Revision,
    avisos,
    errores,
    sugerir_precio,
)

AHORA = datetime(2026, 10, 13, 15, tzinfo=UTC)
BANDA = Banda(D("28.1234"), D("31.5049"), D("36.0000"))


@pytest.mark.parametrize(
    ("tipo", "banda", "vigente", "tope", "esperado"),
    [
        ("compra", BANDA, None, None, (D("28.12"), D("31.50"))),
        ("compra", None, None, None, (None, None)),
        # Renovación: ideal = min(P25, vigente x 0.95); límite = min(P50, vigente x (1 + tope)).
        ("renovacion", BANDA, D("32.0000"), D("5.00"), (D("28.12"), D("31.50"))),
        ("renovacion", BANDA, D("25.0000"), None, (D("23.75"), D("25.00"))),
        ("renovacion", None, D("40.0000"), D("10.00"), (D("38.00"), D("44.00"))),
        # El techo se redondea hacia abajo para que la sugerencia nunca lo supere.
        ("renovacion", None, D("33.3333"), D("5.00"), (D("31.67"), D("34.99"))),
    ],
)
def test_sugiere_ideal_y_limite(
    tipo: str,
    banda: Banda | None,
    vigente: D | None,
    tope: D | None,
    esperado: tuple[D | None, D | None],
) -> None:
    assert sugerir_precio(tipo, banda, vigente, tope) == esperado


def _revision(**cambios: object) -> Revision:
    datos: dict[str, object] = {
        "tipo": "compra",
        "fecha_limite": AHORA + timedelta(days=7),
        "lineas": (LineaRevision("Licencias", D("28.00"), D("31.50"), p75=D("36.00")),),
        "palancas": (PalancaRevision("precio", 100),),
        "invitados": 2,
    }
    return Revision(**(datos | cambios))  # type: ignore[arg-type]


def test_una_configuracion_completa_no_tiene_errores() -> None:
    assert errores(_revision(), AHORA) == []
    assert avisos(_revision()) == []


@pytest.mark.parametrize(
    "fecha", [AHORA + timedelta(minutes=30), AHORA + timedelta(days=61), AHORA - timedelta(days=1)]
)
def test_la_fecha_limite_va_de_1_hora_a_60_dias(fecha: datetime) -> None:
    assert errores(_revision(fecha_limite=fecha), AHORA) == [
        Problema(
            "fecha_limite", "La fecha límite debe estar entre 1 hora y 60 días a partir de ahora."
        )
    ]


def test_cada_linea_necesita_ideal_y_limite_distintos_y_en_centavos() -> None:
    lineas = (
        LineaRevision("Sin valores", None, None),
        LineaRevision("Iguales", D("30.00"), D("30.00")),
        LineaRevision("Milésimos", D("28.00"), D("31.505")),
    )
    assert errores(_revision(lineas=lineas, invitados=0), AHORA) == [
        Problema("proveedores", "Invite al menos a un proveedor."),
        Problema("lineas.0.ideal", "Indique el precio ideal."),
        Problema("lineas.0.limite", "Indique el precio límite."),
        Problema("lineas.1.limite", "El ideal y el límite deben ser distintos."),
        Problema("lineas.2.limite", "Use como máximo 2 decimales."),
    ]


def test_en_renovacion_el_limite_no_supera_el_vigente_mas_el_tope() -> None:
    lineas = (LineaRevision("Licencias", D("30.00"), D("33.61"), precio_vigente=D("32.0000")),)
    assert errores(_revision(tipo="renovacion", lineas=lineas, tope_pct=D("5.00")), AHORA) == [
        Problema(
            "lineas.0.limite",
            "En una renovación, el límite no puede superar $33.60 "
            "(el precio vigente más el tope de aumento).",
        )
    ]


def test_las_palancas_necesitan_valores_y_los_pesos_suman_100() -> None:
    palancas = (
        PalancaRevision("precio", 70),
        PalancaRevision("plazo_pago_dias", 30, None, D(30)),
        PalancaRevision("sla_disponibilidad", 0, D("99.9"), D("101")),
    )
    assert errores(_revision(palancas=palancas), AHORA) == [
        Problema("palancas.plazo_pago_dias.ideal", "Indique el valor ideal."),
        Problema(
            "palancas.sla_disponibilidad.peso",
            "Cada palanca activa necesita un peso de al menos 1.",
        ),
        Problema("palancas.sla_disponibilidad.limite", "Debe estar entre 0 y 100."),
    ]
    sin_cien = (PalancaRevision("precio", 80), PalancaRevision("plazo_meses", 10, D(12), D(36)))
    assert errores(_revision(palancas=sin_cien), AHORA) == [
        Problema("palancas", "Los pesos deben sumar 100; ahora suman 90.")
    ]


def test_avisa_si_el_limite_queda_sobre_p75() -> None:
    lineas = (LineaRevision("Licencias", D("28.00"), D("37.00"), p75=D("36.00")),)
    assert avisos(_revision(lineas=lineas)) == [
        Problema(
            "lineas.0.limite",
            "El límite queda por encima del P75 del mercado ($36.00): pagaría más que en tres de "
            "cada cuatro contratos.",
        )
    ]
