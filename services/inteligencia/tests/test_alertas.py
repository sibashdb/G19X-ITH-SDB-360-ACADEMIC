from datetime import date, timedelta
from decimal import Decimal

import pytest
from inteligencia.dominio.alertas import ordenar, riesgo, sobreprecio, vencimiento
from inteligencia.dominio.contratos import ContratoInfo, Linea
from inteligencia.dominio.precios import Banda

HOY = date(2026, 10, 10)
LINEA = Linea(
    codigo="SAAS-OFI-EMP",
    servicio="Suite de productividad",
    categoria="licencia_saas",
    unidad="usuario_mes",
    cantidad=Decimal("100"),
    precio=Decimal("25"),
)


def _contrato(fin: date, lineas: tuple[Linea, ...] = (LINEA,)) -> ContratoInfo:
    return ContratoInfo(
        id="c-1",
        folio="C-0001",
        proveedor_id="p-1",
        proveedor="Nube Azteca S.A. de C.V.",
        tipo="nuevo",
        fecha_inicio=date(2026, 1, 1),
        fecha_fin=fin,
        moneda="USD",
        lineas=lineas,
    )


@pytest.mark.parametrize(
    ("dias", "severidad", "titulo"),
    [
        (0, "alta", "Vence hoy: C-0001"),
        (1, "alta", "Vence mañana: C-0001"),
        (21, "alta", "Vence en 21 días: C-0001"),
        (45, "media", "Vence en 45 días: C-0001"),
        (80, "informativa", "Vence en 80 días: C-0001"),
    ],
)
def test_vencimiento_por_dias(dias: int, severidad: str, titulo: str) -> None:
    alerta = vencimiento(_contrato(HOY + timedelta(days=dias)), HOY)
    assert alerta is not None
    assert (alerta.tipo, alerta.severidad, alerta.titulo) == ("vencimiento", severidad, titulo)
    assert alerta.entidad_tipo == "contrato"
    fin = HOY + timedelta(days=dias)
    assert alerta.explicacion == (
        "El contrato con Nube Azteca S.A. de C.V. (Suite de productividad) termina el "
        f"{fin:%d/%m/%Y}."
    )


def test_sin_alerta_de_vencimiento_lejos_o_ya_terminado() -> None:
    assert vencimiento(_contrato(HOY + timedelta(days=91)), HOY) is None
    assert vencimiento(_contrato(HOY - timedelta(days=1)), HOY) is None


def test_sobreprecio_con_su_ahorro() -> None:
    contrato = _contrato(date(2026, 12, 31))
    alerta = sobreprecio(contrato, LINEA, Banda(18.0, 20.0, 22.0), HOY)
    assert alerta is not None
    # (25 - 20) x 100 al mes x 3 meses (octubre, noviembre y diciembre).
    assert (alerta.ahorro_potencial, alerta.moneda) == (Decimal("1500.00"), "USD")
    assert alerta.titulo == "Sobreprecio en C-0001: Suite de productividad"
    assert alerta.explicacion == (
        "Paga 25.00 USD por usuario al mes; el mercado paga hasta 22.00 (P75). Pagando el precio "
        "típico (20.00) ahorraría 1,500.00 USD en lo que resta del contrato."
    )
    assert sobreprecio(contrato, LINEA, Banda(18.0, 20.0, 25.0), HOY) is None


def test_riesgo_por_puntuacion_baja_o_en_caida() -> None:
    baja = riesgo("p-1", "Nube Azteca", 35.0, 38.0, 40, HOY)
    assert baja is not None
    assert (baja.severidad, baja.titulo) == ("alta", "Puntuación baja: Nube Azteca")
    assert baja.explicacion == "Su puntuación es 35.0 de 100, por debajo del umbral de 40."
    caida = riesgo("p-1", "Nube Azteca", 60.0, 75.0, 40, HOY)
    assert caida is not None
    assert (caida.severidad, caida.titulo) == ("media", "Puntuación en caída: Nube Azteca")
    assert caida.explicacion == "Bajó 15.0 puntos en 3 meses (de 75.0 a 60.0)."
    assert riesgo("p-1", "Nube Azteca", 60.0, 65.0, 40, HOY) is None
    assert riesgo("p-1", "Nube Azteca", 60.0, None, 40, HOY) is None


def test_los_textos_de_riesgo_llevan_un_decimal_para_no_contradecir_al_umbral() -> None:
    # Con cero decimales, 39.6 se leería "40 ... por debajo del umbral de 40".
    baja = riesgo("p-1", "Nube Azteca", 39.6, None, 40, HOY)
    assert baja is not None
    assert baja.explicacion == "Su puntuación es 39.6 de 100, por debajo del umbral de 40."
    # Y una caída de 10.3 se leería "Bajó 10 puntos", sin mostrar que pasa de los 10.
    caida = riesgo("p-1", "Nube Azteca", 60.0, 70.3, 40, HOY)
    assert caida is not None
    assert caida.explicacion == "Bajó 10.3 puntos en 3 meses (de 70.3 a 60.0)."


def test_ordenar_por_severidad_y_fecha() -> None:
    informativa = vencimiento(_contrato(HOY + timedelta(days=80)), HOY)
    alta = riesgo("p-2", "Datos del Norte", 20.0, None, 40, HOY)
    media = vencimiento(_contrato(HOY + timedelta(days=45)), HOY)
    assert informativa is not None and alta is not None and media is not None
    assert [a.severidad for a in ordenar([informativa, media, alta])] == [
        "alta",
        "media",
        "informativa",
    ]
