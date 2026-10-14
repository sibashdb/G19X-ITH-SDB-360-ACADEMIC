from negociacion.dominio.motor import Decision
from negociacion.textos import respuesta_del_agente

NOMBRES = {"a": "CRM profesional", "b": "Soporte", "c": "Nube"}


def test_la_contraoferta_suma_la_presion_y_la_ultima_ronda() -> None:
    simple = Decision("contraofertar", traza={"hay_mejor_oferta": False})
    assert respuesta_del_agente(simple, NOMBRES) == (
        "Gracias por su oferta. Le proponemos los términos que aparecen en la propuesta."
    )
    completa = Decision("contraofertar", ultima_ronda=True, traza={"hay_mejor_oferta": True})
    assert respuesta_del_agente(completa, NOMBRES) == (
        "Gracias por su oferta. Le proponemos los términos que aparecen en la propuesta. "
        "Hemos recibido propuestas más competitivas. "
        "La siguiente ronda es la última: envíe su mejor y última oferta."
    )


def test_la_aclaracion_nombra_las_lineas_en_singular_o_plural() -> None:
    una = Decision("pedir_aclaracion", dudosas=("a",))
    assert respuesta_del_agente(una, NOMBRES) == (
        "El precio de CRM profesional parece fuera de lo usual. Si es correcto, márquelo como "
        "confirmado y envíelo de nuevo."
    )
    tres = Decision("pedir_aclaracion", dudosas=("a", "b", "c"))
    assert respuesta_del_agente(tres, NOMBRES).startswith(
        "Los precios de CRM profesional, Soporte y Nube parecen fuera de lo usual."
    )


def test_ningun_mensaje_lleva_cifras() -> None:
    decisiones = [
        Decision("aceptar"),
        Decision("cerrar_sin_acuerdo"),
        Decision("contraofertar", ultima_ronda=True, traza={"hay_mejor_oferta": True}),
    ]
    for decision in decisiones:
        texto = respuesta_del_agente(decision, NOMBRES)
        assert not any(caracter.isdigit() for caracter in texto)
