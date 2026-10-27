from decimal import Decimal as D

from negociacion.dominio.redaccion import numeros_en, texto_verificado


def test_lee_los_formatos_de_mexico() -> None:
    texto = "Le proponemos $1,247.25 por hora a 24 meses y 99.5 % de SLA."
    assert numeros_en(texto) == [D("1247.25"), D("24"), D("99.5")]


def test_un_texto_sin_numeros_esta_verificado() -> None:
    assert texto_verificado("Gracias por su oferta.", [])


def test_un_numero_cambiado_no_pasa() -> None:
    assert texto_verificado("Le proponemos $1,247.20.", [D("1247.25")]) is False


def test_un_numero_de_mas_no_pasa() -> None:
    assert texto_verificado("$1,247.25 en 3 rondas", [D("1247.25")]) is False


def test_el_mismo_valor_con_otro_formato_pasa() -> None:
    assert texto_verificado("1247.250 MXN", [D("1247.25")])


def test_hablar_de_otras_ofertas_solo_pasa_si_las_hay() -> None:
    texto = "Le proponemos 1318.90 MXN. No hay mejores ofertas en la mesa."
    assert texto_verificado(texto, [D("1318.90")]) is False
    assert texto_verificado(texto, [D("1318.90")], hay_mejor_oferta=True)


def test_anunciar_la_ultima_ronda_solo_pasa_si_lo_es() -> None:
    texto = "Le proponemos 1322.08 MXN; la próxima será la última."
    assert texto_verificado(texto, [D("1322.08")]) is False
    assert texto_verificado(texto, [D("1322.08")], ultima_ronda=True)
