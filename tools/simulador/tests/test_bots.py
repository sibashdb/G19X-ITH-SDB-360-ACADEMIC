import random
from datetime import date
from decimal import Decimal as D

from generador.modelo import generar
from simulador.bots import Bot, Termino
from simulador.escenarios import bandas, escenarios
from simulador.orquestador import dentro_de_limites

PRECIO = Termino("precio", D("40.00"), D("30.00"), mas_es_mejor=True)


def test_el_bot_concede_de_su_inicio_a_su_reserva() -> None:
    bot = Bot("duro", {"l": PRECIO}, {}, random.Random(1))
    ofertas = [D(bot.oferta(k, 6)["precios"]["l"]) for k in range(1, 7)]
    assert ofertas[0] < D("40.00")
    assert ofertas[-1] == D("30.00")  # en la última ronda ofrece su reserva
    assert ofertas == sorted(ofertas, reverse=True)


def test_el_duro_concede_despues_que_el_flexible() -> None:
    duro = Bot("duro", {"l": PRECIO}, {}, random.Random(1))
    flexible = Bot("flexible", {"l": PRECIO}, {}, random.Random(1))
    assert D(duro.oferta(2, 6)["precios"]["l"]) > D(flexible.oferta(2, 6)["precios"]["l"])


def test_acepta_solo_lo_que_no_cruza_su_reserva() -> None:
    pago = Termino("plazo_pago_dias", D(20), D(45), mas_es_mejor=False)
    bot = Bot("flexible", {"l": PRECIO}, {"plazo_pago_dias": pago}, random.Random(1))
    assert bot.acepta({"precios": {"l": "30.00"}, "palancas": {"plazo_pago_dias": "45"}})
    assert not bot.acepta({"precios": {"l": "29.99"}, "palancas": {"plazo_pago_dias": "45"}})
    assert not bot.acepta({"precios": {"l": "35.00"}, "palancas": {"plazo_pago_dias": "46"}})


def test_la_comprobacion_de_limites_es_independiente_del_motor() -> None:
    evento = {
        "lineas": [{"id": "l", "ideal": "28.00", "limite": "31.50"}],
        "palancas": [
            {"clave": "precio", "activa": True, "ideal": None, "limite": None},
            {"clave": "plazo_pago_dias", "activa": True, "ideal": "60", "limite": "30"},
        ],
    }
    assert dentro_de_limites(
        evento, {"precios": {"l": "31.50"}, "palancas": {"plazo_pago_dias": "30"}}
    )
    assert not dentro_de_limites(
        evento, {"precios": {"l": "31.51"}, "palancas": {"plazo_pago_dias": "30"}}
    )
    assert not dentro_de_limites(
        evento, {"precios": {"l": "30.00"}, "palancas": {"plazo_pago_dias": "29"}}
    )


def test_las_bandas_y_los_escenarios_son_reproducibles() -> None:
    datos = generar(42, n_proveedores=20)
    hoy = date(2026, 9, 15)
    referencias = bandas(datos, hoy)
    assert referencias
    assert all(b.p25 <= b.p50 <= b.p75 for b in referencias.values())
    lista = escenarios(datos, hoy, compras=5, renovaciones=3)
    assert lista == escenarios(datos, hoy, compras=5, renovaciones=3)
    assert {e.tipo for e in lista} == {"compra", "renovacion"}
    for escenario in lista:
        if escenario.tipo == "compra":
            assert 1 <= len(escenario.lineas) <= 3
            assert 2 <= len(escenario.rfcs) <= 5
