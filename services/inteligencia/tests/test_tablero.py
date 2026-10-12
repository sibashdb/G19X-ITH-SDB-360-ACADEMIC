from dataclasses import replace
from datetime import date
from decimal import Decimal

from inteligencia.dominio.alertas import Alerta
from inteligencia.dominio.contratos import ContratoInfo, Linea
from inteligencia.dominio.monedas import a_mxn, tipo_cambio_en
from inteligencia.dominio.tablero import calcular

HOY = date(2026, 10, 10)
TIPOS_CAMBIO = {date(2026, 9, 1): Decimal("18.0000")}
USD = ContratoInfo(
    id="c-usd",
    folio="C-0001",
    proveedor_id="p-1",
    proveedor="Nube Azteca",
    tipo="nuevo",
    fecha_inicio=date(2025, 11, 1),
    fecha_fin=date(2026, 10, 31),
    moneda="USD",
    lineas=(
        Linea(
            "SAAS-OFI-EMP", "Suite", "licencia_saas", "usuario_mes", Decimal("100"), Decimal("20")
        ),
    ),
)
MXN = ContratoInfo(
    id="c-mxn",
    folio="C-0002",
    proveedor_id="p-2",
    proveedor="Datos del Norte",
    tipo="nuevo",
    fecha_inicio=date(2025, 1, 1),
    fecha_fin=date(2026, 12, 31),
    moneda="MXN",
    lineas=(
        Linea("SOP-ADM-SRV", "Administración", "soporte", "mes", Decimal("2"), Decimal("5000")),
        # Por consumo: 240 horas en los 24 meses del contrato, 10 al mes.
        Linea(
            "SOP-APP-HR",
            "Soporte a aplicaciones",
            "soporte",
            "hora",
            Decimal("240"),
            Decimal("650"),
        ),
    ),
)


def _alerta(
    tipo: str, proveedor_id: str, ahorro: str | None = None, moneda: str | None = None
) -> Alerta:
    return Alerta(
        id=f"{tipo}:{proveedor_id}",
        tipo=tipo,  # type: ignore[arg-type]
        severidad="media",
        titulo="t",
        explicacion="e",
        entidad_tipo="proveedor",
        entidad_id=proveedor_id,
        entidad_nombre="n",
        proveedor_id=proveedor_id,
        proveedor_nombre="n",
        fecha=HOY,
        ahorro_potencial=Decimal(ahorro) if ahorro else None,
        moneda=moneda,
    )


def test_tipo_de_cambio_y_conversion() -> None:
    assert tipo_cambio_en(TIPOS_CAMBIO, HOY) == Decimal("18.0000")
    assert tipo_cambio_en(TIPOS_CAMBIO, date(2020, 1, 1)) == Decimal("18.0000")  # el más viejo
    assert tipo_cambio_en({}, HOY) is None
    assert a_mxn(Decimal("10"), "USD", Decimal("18")) == Decimal("180")
    assert a_mxn(Decimal("10"), "MXN", None) == Decimal("10")
    assert a_mxn(Decimal("10"), "USD", None) == Decimal("0")


def test_gasto_anual_por_categoria_y_variacion() -> None:
    tablero = calcular([USD, MXN], TIPOS_CAMBIO, {}, {}, 2, [], HOY)
    # USD: 100 x 20 x 18 = 36,000 al mes. MXN: 2 x 5,000 + 10 x 650 = 16,500 al mes.
    assert tablero.gasto_anual == Decimal("630000.00")
    assert tablero.gasto_por_categoria == {
        "licencia_saas": Decimal("432000.00"),
        "soporte": Decimal("198000.00"),
    }
    # Hace un año solo estaba vigente el contrato en MXN (198,000 al año).
    assert tablero.variacion_pct is not None
    assert round(tablero.variacion_pct, 1) == 218.2


def test_serie_de_24_meses() -> None:
    serie = calcular([USD, MXN], TIPOS_CAMBIO, {}, {}, 2, [], HOY).gasto_por_mes
    assert len(serie) == 24
    assert serie[-1] == (date(2026, 10, 1), Decimal("52500.00"))
    assert serie[0] == (date(2024, 11, 1), Decimal("0.00"))
    assert dict(serie)[date(2025, 10, 1)] == Decimal("16500.00")


def test_proximos_vencimientos() -> None:
    tablero = calcular([USD, MXN], TIPOS_CAMBIO, {}, {}, 2, [], HOY)
    assert tablero.por_vencer == 2
    [primero, segundo] = tablero.proximos_vencimientos
    assert (primero.contrato.folio, primero.dias, primero.monto_mensual) == (
        "C-0001",
        21,
        Decimal("36000.00"),
    )
    assert (segundo.contrato.folio, segundo.dias) == ("C-0002", 82)


def test_ahorro_en_riesgo_y_destacados() -> None:
    alertas = [
        _alerta("sobreprecio", "p-1", "100.00", "USD"),
        _alerta("sobreprecio", "p-2", "500.00", "MXN"),
        _alerta("riesgo", "p-3"),
    ]
    puntuaciones = {"p-1": 90.0, "p-2": 50.0, "p-3": 10.0}
    nombres = {"p-1": "Nube Azteca", "p-2": "Datos del Norte", "p-3": "Red Maya"}
    tablero = calcular([USD, MXN], TIPOS_CAMBIO, puntuaciones, nombres, 3, alertas, HOY)
    assert tablero.ahorro_potencial == Decimal("2300.00")
    assert (tablero.en_riesgo, tablero.total_proveedores) == (1, 3)
    assert [d.nombre for d in tablero.mejores] == ["Nube Azteca", "Datos del Norte", "Red Maya"]
    assert [d.nombre for d in tablero.peores] == ["Red Maya", "Datos del Norte", "Nube Azteca"]
    assert tablero.distribucion == [
        ("0-19", 1),
        ("20-39", 0),
        ("40-59", 1),
        ("60-79", 0),
        ("80-100", 1),
    ]
    assert len(tablero.alertas_principales) == 3


def test_sin_tipo_de_cambio_los_montos_en_usd_no_cuentan() -> None:
    assert calcular([USD, MXN], {}, {}, {}, 2, [], HOY).gasto_anual == Decimal("198000.00")


def _por_mes(contratos: list[ContratoInfo], tipos: dict[date, Decimal]) -> dict[date, Decimal]:
    return dict(calcular(contratos, tipos, {}, {}, 1, [], HOY).gasto_por_mes)


def _mensual(inicio: date, fin: date) -> ContratoInfo:
    """Contrato en MXN de 1,000 al mes."""
    return ContratoInfo(
        id="c-mes",
        folio="C-0003",
        proveedor_id="p-3",
        proveedor="Red Maya",
        tipo="nuevo",
        fecha_inicio=inicio,
        fecha_fin=fin,
        moneda="MXN",
        lineas=(
            Linea("SOP-MES", "Soporte mensual", "soporte", "mes", Decimal("1"), Decimal("1000")),
        ),
    )


def test_serie_convierte_cada_mes_con_su_tipo_de_cambio() -> None:
    tipos = {date(2025, 9, 1): Decimal("17"), date(2026, 9, 1): Decimal("18")}
    usd = replace(USD, fecha_inicio=date(2024, 1, 1), fecha_fin=date(2027, 12, 31))
    serie = _por_mes([usd], tipos)
    # 100 x 20 = 2,000 USD al mes. Antes del primer periodo se usa el más viejo (17).
    assert serie[date(2024, 11, 1)] == Decimal("34000.00")
    # Entre los dos periodos: 2,000 x 17.
    assert serie[date(2025, 10, 1)] == Decimal("34000.00")
    # Después del segundo periodo: 2,000 x 18.
    assert serie[date(2026, 10, 1)] == Decimal("36000.00")


def test_serie_cuenta_cada_contrato_solo_en_sus_meses() -> None:
    desde_noviembre = _por_mes([_mensual(date(2025, 11, 1), date(2027, 12, 31))], {})
    desde_mitad = _por_mes([_mensual(date(2025, 11, 15), date(2027, 12, 31))], {})
    hasta_marzo = _por_mes([_mensual(date(2025, 1, 1), date(2026, 3, 31))], {})
    # Empieza el 1 de noviembre: cuenta en noviembre y no en octubre.
    assert desde_noviembre[date(2025, 10, 1)] == Decimal("0.00")
    assert desde_noviembre[date(2025, 11, 1)] == Decimal("1000.00")
    # Empieza el 15 de noviembre: también cuenta en todo noviembre.
    assert desde_mitad[date(2025, 10, 1)] == Decimal("0.00")
    assert desde_mitad[date(2025, 11, 1)] == Decimal("1000.00")
    # Termina el 31 de marzo: cuenta en marzo y no en abril.
    assert hasta_marzo[date(2026, 3, 1)] == Decimal("1000.00")
    assert hasta_marzo[date(2026, 4, 1)] == Decimal("0.00")
