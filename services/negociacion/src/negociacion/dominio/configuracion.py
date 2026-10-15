"""Valores sugeridos y reglas para publicar un evento (spec §5.2 y §5.3)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, Decimal

from negociacion.dominio.terminos import CENTAVO, problema_de_valor, redondear

DESCUENTO_RENOVACION = Decimal("0.95")  # en renovación, el ideal pide al menos 5 % menos que hoy
VENTANA_FECHA_LIMITE = (timedelta(hours=1), timedelta(days=60))


@dataclass(frozen=True)
class Banda:
    p25: Decimal
    p50: Decimal
    p75: Decimal


@dataclass(frozen=True)
class Problema:
    campo: str
    mensaje: str


@dataclass(frozen=True)
class LineaRevision:
    nombre: str
    ideal: Decimal | None
    limite: Decimal | None
    precio_vigente: Decimal | None = None
    p75: Decimal | None = None


@dataclass(frozen=True)
class PalancaRevision:
    clave: str
    peso: int
    ideal: Decimal | None = None
    limite: Decimal | None = None


@dataclass(frozen=True)
class Revision:
    tipo: str
    fecha_limite: datetime
    lineas: tuple[LineaRevision, ...]
    palancas: tuple[PalancaRevision, ...]  # las activas, incluido el precio (sin ideal ni límite)
    invitados: int
    tope_pct: Decimal | None = None  # del contrato, en renovación


def techo_renovacion(vigente: Decimal, tope_pct: Decimal | None) -> Decimal:
    """El precio vigente más el tope de aumento; un contrato sin tope no admite aumento."""
    return vigente * (1 + (tope_pct or Decimal(0)) / 100)


def techo_redondeado(vigente: Decimal, tope_pct: Decimal | None) -> Decimal:
    """El techo de la renovación a centavos, hacia abajo: nunca lo supera."""
    return redondear("precio", techo_renovacion(vigente, tope_pct), ROUND_FLOOR)


def sugerir_precio(
    tipo: str, banda: Banda | None, vigente: Decimal | None, tope_pct: Decimal | None
) -> tuple[Decimal | None, Decimal | None]:
    """(ideal, límite) sugeridos para el precio de una línea; (None, None) sin datos."""
    if tipo == "renovacion" and vigente is not None:
        ideal = vigente * DESCUENTO_RENOVACION
        limite = techo_renovacion(vigente, tope_pct)
        if banda is not None:
            ideal, limite = min(banda.p25, ideal), min(banda.p50, limite)
        # El límite no pasa del techo a centavos (hacia abajo) y el ideal no pasa del límite:
        # así la sugerencia nunca invierte la dirección del precio.
        limite = min(redondear("precio", limite), techo_redondeado(vigente, tope_pct))
        ideal = min(redondear("precio", ideal), limite)
    elif banda is None:
        return None, None
    else:
        ideal, limite = redondear("precio", banda.p25), redondear("precio", banda.p50)
    # Con precios de pocos centavos el redondeo los iguala y el borrador no se podría publicar.
    if ideal == limite and limite >= 2 * CENTAVO:
        ideal = limite - CENTAVO
    return ideal, limite


def _rango(
    campo: str, clave: str, ideal: Decimal | None, limite: Decimal | None, que: str
) -> list[Problema]:
    problemas: list[Problema] = []
    if ideal is None:
        problemas.append(Problema(f"{campo}.ideal", f"Indique {que} ideal."))
    if limite is None:
        problemas.append(Problema(f"{campo}.limite", f"Indique {que} límite."))
    for nombre, valor in (("ideal", ideal), ("limite", limite)):
        mensaje = None if valor is None else problema_de_valor(clave, valor)
        if mensaje is not None:
            problemas.append(Problema(f"{campo}.{nombre}", mensaje))
    if ideal is not None and limite is not None and ideal == limite:
        problemas.append(Problema(f"{campo}.limite", "El ideal y el límite deben ser distintos."))
    return problemas


def errores(revision: Revision, ahora: datetime) -> list[Problema]:
    """Lo que impide publicar; vacío si se puede."""
    problemas: list[Problema] = []
    minimo, maximo = VENTANA_FECHA_LIMITE
    if not ahora + minimo <= revision.fecha_limite <= ahora + maximo:
        problemas.append(
            Problema(
                "fecha_limite",
                "La fecha límite debe estar entre 1 hora y 60 días a partir de ahora.",
            )
        )
    if revision.invitados == 0:
        problemas.append(Problema("proveedores", "Invite al menos a un proveedor."))
    for i, linea in enumerate(revision.lineas):
        problemas += _rango(f"lineas.{i}", "precio", linea.ideal, linea.limite, "el precio")
        if (
            revision.tipo == "renovacion"
            and linea.precio_vigente is not None
            and linea.limite is not None
        ):
            techo = techo_redondeado(linea.precio_vigente, revision.tope_pct)
            if linea.limite > techo:
                problemas.append(
                    Problema(
                        f"lineas.{i}.limite",
                        "En una renovación, el límite no puede superar "
                        f"${techo:,.2f} "
                        "(el precio vigente más el tope de aumento).",
                    )
                )
    pesos = 0
    for palanca in revision.palancas:
        pesos += palanca.peso
        campo = f"palancas.{palanca.clave}"
        if palanca.peso < 1:
            problemas.append(
                Problema(f"{campo}.peso", "Cada palanca activa necesita un peso de al menos 1.")
            )
        if palanca.clave != "precio":
            problemas += _rango(campo, palanca.clave, palanca.ideal, palanca.limite, "el valor")
    if pesos != 100:
        problemas.append(Problema("palancas", f"Los pesos deben sumar 100; ahora suman {pesos}."))
    return problemas


def avisos(revision: Revision) -> list[Problema]:
    """Lo que conviene revisar pero no impide publicar."""
    return [
        Problema(
            f"lineas.{i}.limite",
            f"El límite queda por encima del P75 del mercado (${linea.p75:,.2f}): pagaría más que "
            "en tres de cada cuatro contratos.",
        )
        for i, linea in enumerate(revision.lineas)
        if linea.p75 is not None and linea.limite is not None and linea.limite > linea.p75
    ]
