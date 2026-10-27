import pytest
from comun.numeros import palabras_a_numeros


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("mil doscientos ochenta la hora", "1280 la hora"),
        ("treinta y dos dólares", "32 dólares"),
        ("dos mil quinientos", "2500"),
        ("un millón doscientos mil", "1200000"),
        (
            "Le dejo la hora en mil trescientos si firmamos a veinticuatro meses",
            "Le dejo la hora en 1300 si firmamos a 24 meses",
        ),
        ("ciento cinco pesos", "105 pesos"),
        ("Cien por ciento de SLA", "100 por ciento de SLA"),
    ],
)
def test_convierte_los_numeros_escritos_con_palabras(texto: str, esperado: str) -> None:
    assert palabras_a_numeros(texto) == esperado


def test_no_toca_el_texto_sin_numeros_en_palabras() -> None:
    texto = "Le dejo $1,300.00 MXN por hora; es una oferta final y un buen precio."
    assert palabras_a_numeros(texto) == texto
