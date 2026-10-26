"""Números escritos con palabras en español, a dígitos, antes de llamar al LLM.

Los modelos de 3B leían «mil doscientos ochenta» como 280 (prueba del 26/10); convertirlo antes,
de forma determinista, quita ese error. Cubre de 0 a 999,999,999.
"""

import re
import unicodedata

UNIDADES = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21, "veintiuno": 21,
    "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
    "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29,
}  # fmt: skip
DECENAS = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
    "ochenta": 80, "noventa": 90,
}  # fmt: skip
CENTENAS = {
    "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200, "trescientos": 300,
    "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400, "quinientos": 500,
    "quinientas": 500, "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
    "setecientas": 700, "ochocientos": 800, "ochocientas": 800, "novecientos": 900,
    "novecientas": 900,
}  # fmt: skip
MILLON = {"millon", "millones"}
VALORES = UNIDADES | DECENAS | CENTENAS
# Solas son artículos o parte de «por ciento»: «una oferta», «cien por ciento».
SOLAS_NO = {"un", "una", "uno", "ciento"}
PALABRA = re.compile(r"[^\W\d_]+")


def _clave(palabra: str) -> str:
    sin_acentos = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")


def _es_numero(clave: str) -> bool:
    return clave in VALORES or clave == "mil" or clave in MILLON


def _valor(claves: list[str]) -> int:
    total = actual = 0
    for clave in claves:
        if clave in MILLON:
            total += (actual or 1) * 1_000_000
            actual = 0
        elif clave == "mil":
            total += (actual or 1) * 1000
            actual = 0
        elif clave != "y":
            actual += VALORES[clave]
    return total + actual


def palabras_a_numeros(texto: str) -> str:
    palabras = list(PALABRA.finditer(texto))
    partes: list[str] = []
    cursor = i = 0
    while i < len(palabras):
        if not _es_numero(_clave(palabras[i].group())):
            i += 1
            continue
        fin = i
        claves = [_clave(palabras[i].group())]
        while fin + 1 < len(palabras):
            siguiente = _clave(palabras[fin + 1].group())
            entre = texto[palabras[fin].end() : palabras[fin + 1].start()]
            if entre.strip():  # una coma, un punto o un número en dígitos cortan la serie
                break
            if _es_numero(siguiente):
                claves.append(siguiente)
                fin += 1
            elif (
                siguiente == "y"
                and claves[-1] in DECENAS
                and fin + 2 < len(palabras)
                and _clave(palabras[fin + 2].group()) in UNIDADES
                and not texto[palabras[fin + 1].end() : palabras[fin + 2].start()].strip()
            ):
                claves += ["y", _clave(palabras[fin + 2].group())]
                fin += 2
            else:
                break
        if len(claves) == 1 and claves[0] in SOLAS_NO:
            i += 1
            continue
        partes += [texto[cursor : palabras[i].start()], str(_valor(claves))]
        cursor = palabras[fin].end()
        i = fin + 1
    return "".join(partes) + texto[cursor:]
