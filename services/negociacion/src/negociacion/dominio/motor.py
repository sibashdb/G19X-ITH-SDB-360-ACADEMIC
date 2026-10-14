"""Motor de concesiones (spec §6): decide cómo responde el agente a una oferta del proveedor.

Es puro: no lee la base ni la red. La capa de servicio arma los términos y el estado, llama a
`decidir` y guarda la decisión con su traza en la bitácora.
"""

from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any, Literal

from negociacion.dominio.terminos import (
    Rango,
    Terminos,
    Valores,
    combinar,
    es_valida,
    fuera_de_limite,
    ideales,
    redondear,
    transformar,
    utilidad,
    utilidades,
)

VERSION_MOTOR = 1  # sube con cada cambio de comportamiento; queda en cada traza
BETA = {"firme": 0.3, "balanceado": 0.6, "flexible": 1.0}
ITERACIONES = 60  # bisección sobre un camino de largo 2: sobra para centavos
TOLERANCIA = 1e-9  # ruido de punto flotante al comparar utilidades
CORDURA = (Decimal("0.1"), Decimal(10))  # spec §6.3: fuera de 0.1x a 10x se pide aclaración

Accion = Literal["aceptar", "contraofertar", "pedir_aclaracion", "cerrar_sin_acuerdo"]


@dataclass(frozen=True)
class Estado:
    ronda: int  # t: el número de esta oferta del proveedor, desde 1
    rondas: int  # T: las rondas máximas del evento
    beta: float
    anterior: Valores | None = (
        None  # la última contraoferta de la sesión, del agente o del comprador
    )
    hay_mejor_oferta: bool = False


@dataclass(frozen=True)
class Decision:
    accion: Accion
    contraoferta: Valores | None = None
    dudosas: tuple[str, ...] = ()  # líneas con un precio fuera de lo usual
    ultima_ronda: bool = False  # la siguiente oferta del proveedor será la última
    traza: dict[str, Any] = field(default_factory=dict)


def u_objetivo(t: int, rondas: int, beta: float) -> float:
    """U_obj(t) = 1 - (t/T)^(1/β); más allá de T vale lo mismo que en T."""
    return 1.0 - float((min(t, rondas) / rondas) ** (1.0 / beta))


def curva(clave: str, rango: Rango, u_obj: float) -> Decimal:
    """Lo que el agente pide por su cuenta en un término: llega al límite solo con U_obj = 0."""
    valor = rango.ideal + Decimal(repr(1.0 - u_obj)) * (rango.limite - rango.ideal)
    return redondear(clave, valor)


def dudosas(terminos: Terminos, oferta: Valores) -> tuple[str, ...]:
    """Las líneas con un precio fuera de 0.1x a 10x de su referencia (o de su límite, sin ella)."""
    minimo, maximo = CORDURA
    fuera: list[str] = []
    for linea in terminos.lineas:
        base = linea.referencia if linea.referencia is not None else linea.rango.limite
        if not base * minimo <= oferta.precios[linea.id] <= base * maximo:
            fuera.append(linea.id)
    return tuple(fuera)


def _interpolar(terminos: Terminos, a: Valores, b: Valores, fraccion: float) -> Valores:
    f = Decimal(repr(fraccion))
    return combinar(terminos, a, b, lambda _c, _r, x, y: x + f * (y - x))


def contraoferta(
    terminos: Terminos, oferta: Valores, estado: Estado
) -> tuple[Valores, dict[str, Any]]:
    """La contraoferta de la ronda (spec §6.4) y su parte de la traza.

    El camino va de la oferta acotada a los límites (s'), a la oferta con la curva propia del
    agente en lo que cruzaba un límite (s̃), y de ahí al ideal (I). La utilidad no baja a lo
    largo del camino, así que la bisección encuentra el punto con U = objetivo.
    """
    u_obj = u_objetivo(estado.ronda, estado.rondas, estado.beta)
    u_anterior = None if estado.anterior is None else utilidad(terminos, estado.anterior)
    objetivo = u_obj if u_anterior is None else min(u_obj, u_anterior)
    acotada = transformar(terminos, oferta, lambda _c, r, v: r.acotar(v))
    propia = transformar(terminos, oferta, lambda c, r, v: v if r.valido(v) else curva(c, r, u_obj))
    ideal = ideales(terminos)

    def punto(paso: float) -> Valores:
        if paso <= 1:
            return _interpolar(terminos, acotada, propia, paso)
        return _interpolar(terminos, propia, ideal, paso - 1)

    if utilidad(terminos, acotada) >= objetivo:
        paso, resultado = 0.0, acotada
    else:
        bajo, alto = 0.0, 2.0
        for _ in range(ITERACIONES):
            medio = (bajo + alto) / 2
            if utilidad(terminos, punto(medio)) >= objetivo:
                alto = medio
            else:
                bajo = medio
        paso, resultado = alto, punto(alto)

    redondeo = "ninguno"  # s' ya está en la precisión de cada término
    if paso > 0:
        sin_redondear = resultado
        redondeo = "cercano"
        resultado = transformar(terminos, sin_redondear, lambda c, _r, v: redondear(c, v))
        if u_anterior is not None and utilidad(terminos, resultado) > u_anterior + TOLERANCIA:
            # Redondear hacia la oferta del proveedor concede menos de un centavo y nunca
            # retrocede; los extremos del camino ya están en la precisión, así que no cruza límites.
            redondeo = "hacia_proveedor"
            resultado = transformar(
                terminos,
                sin_redondear,
                lambda c, r, v: redondear(c, v, ROUND_CEILING if r.menos_es_mejor else ROUND_FLOOR),
            )
    if paso == 0:
        tramo = "acotada"
    elif paso <= 1:
        tramo = "acotada_a_propia"
    else:
        tramo = "propia_a_ideal"
    traza: dict[str, Any] = {
        "u_objetivo": u_obj,
        "objetivo": objetivo,
        "tramo": tramo,
        "paso": paso,
        "de_curva": fuera_de_limite(terminos, oferta),
        "redondeo": redondeo,
        "utilidad_contraoferta": utilidad(terminos, resultado),
    }
    return resultado, traza


def decidir(
    terminos: Terminos, estado: Estado, oferta: Valores, confirmar_valores: bool = False
) -> Decision:
    """La respuesta del agente a la oferta `estado.ronda` del proveedor (spec §6.3)."""
    u_oferta = utilidad(terminos, oferta)
    valida = es_valida(terminos, oferta)
    base: dict[str, Any] = {
        "version_motor": VERSION_MOTOR,
        "t": estado.ronda,
        "T": estado.rondas,
        "beta": estado.beta,
        "u": utilidades(terminos, oferta),
        "utilidad_oferta": u_oferta,
        "valida": valida,
        "hay_mejor_oferta": estado.hay_mejor_oferta,
    }
    raras = () if confirmar_valores else dudosas(terminos, oferta)
    if raras:
        return Decision(
            "pedir_aclaracion",
            dudosas=raras,
            traza=base | {"accion": "pedir_aclaracion", "dudosas": list(raras)},
        )
    propuesta, parte = contraoferta(terminos, oferta, estado)
    traza = base | parte
    if valida and u_oferta >= utilidad(terminos, propuesta):
        return Decision("aceptar", traza=traza | {"accion": "aceptar"})
    if estado.ronda >= estado.rondas:
        return Decision("cerrar_sin_acuerdo", traza=traza | {"accion": "cerrar_sin_acuerdo"})
    return Decision(
        "contraofertar",
        contraoferta=propuesta,
        ultima_ronda=estado.ronda + 1 == estado.rondas,
        traza=traza | {"accion": "contraofertar", "contraoferta": propuesta.a_json()},
    )
