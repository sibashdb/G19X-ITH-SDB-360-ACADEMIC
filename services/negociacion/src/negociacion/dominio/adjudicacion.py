"""Reglas de la adjudicación: cuándo exige aprobación y qué contrato nace (spec §4.3 y §4.4)."""

import calendar
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from negociacion.dominio.terminos import Valores

# Lo que un proveedor sabe del resultado de su negociación (nunca quién ganó ni cuánto).
Resultado = Literal["adjudicada", "no_elegida", "desierta"]
ZONA_NEGOCIO = ZoneInfo("America/Mexico_City")  # el "hoy" de los contratos es el del negocio
PLAZO_PAGO_POR_DEFECTO = 30  # días, en una compra donde no se negoció
HEREDABLES = ("plazo_pago_dias", "sla_disponibilidad", "tope_aumento_pct")  # de la renovación
UN_DIA = timedelta(days=1)


def requiere_aprobacion(
    costo_total_mxn: Decimal, umbral: Decimal, fuera_de_limites: bool
) -> tuple[bool, list[str]]:
    """Si la propuesta necesita aprobador y por qué: pasa el umbral o la sesión salió de límites."""
    motivos = []
    if costo_total_mxn > umbral:
        motivos.append("umbral")
    if fuera_de_limites:
        motivos.append("fuera_de_limites")
    return bool(motivos), motivos


def sumar_meses(fecha: date, meses: int) -> date:
    """La fecha, `meses` después; si el mes de llegada es más corto, el día se acota a su fin."""
    anio, mes = divmod(fecha.year * 12 + fecha.month - 1 + meses, 12)
    mes += 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


@dataclass(frozen=True)
class LineaTerminos:
    """Una línea del evento, para armar las del contrato."""

    id: str
    codigo_servicio: str
    cantidad: Decimal


@dataclass(frozen=True)
class LineaContrato:
    codigo_servicio: str
    cantidad: Decimal
    precio_unitario: Decimal


@dataclass(frozen=True)
class TerminosContrato:
    folio: str
    tipo: str  # nuevo o renovacion
    moneda: str
    fecha_inicio: date
    fecha_fin: date
    plazo_pago_dias: int
    sla_disponibilidad: Decimal | None
    tope_aumento_pct: Decimal | None
    cuota_implementacion: Decimal
    lineas: tuple[LineaContrato, ...]

    def para_evento(self) -> dict[str, Any]:
        """El contrato como viaja en negociacion.adjudicada: fechas ISO y montos como texto."""
        return {
            "folio": self.folio,
            "tipo": self.tipo,
            "moneda": self.moneda,
            "fecha_inicio": self.fecha_inicio.isoformat(),
            "fecha_fin": self.fecha_fin.isoformat(),
            "plazo_pago_dias": self.plazo_pago_dias,
            "sla_disponibilidad": _texto(self.sla_disponibilidad),
            "tope_aumento_pct": _texto(self.tope_aumento_pct),
            "cuota_implementacion": str(self.cuota_implementacion),
            "lineas": [
                {
                    "codigo_servicio": linea.codigo_servicio,
                    "cantidad": str(linea.cantidad),
                    "precio_unitario": str(linea.precio_unitario),
                }
                for linea in self.lineas
            ],
        }


def _texto(valor: Decimal | None) -> str | None:
    return None if valor is None else str(valor)


def _decimal(valor: Any) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def terminos_contrato(
    *,
    folio_evento: str,
    tipo_evento: str,
    moneda: str,
    plazo_evento: int,
    valores: Valores,
    lineas: Sequence[LineaTerminos],
    contrato_vigente: Mapping[str, Any] | None,
    decidida_en: datetime,
) -> TerminosContrato:
    """Los términos del contrato que nace al adjudicar.

    Lo acordado en `valores` manda; lo que no se negoció sale del contrato vigente (renovación,
    `foto["contrato"]` del evento) o de un valor por defecto. La cuota de implementación no pasa de
    un contrato al siguiente: sin acuerdo, es 0.
    """
    renovacion = tipo_evento == "renovacion"
    if renovacion and contrato_vigente is None:
        raise ValueError("Una renovación necesita el contrato vigente.")
    vigente = contrato_vigente if renovacion else None
    palancas = valores.palancas

    if vigente is None:
        inicio = decidida_en.astimezone(ZONA_NEGOCIO).date() + UN_DIA
        heredados: dict[str, Decimal | None] = {}
    else:
        inicio = date.fromisoformat(str(vigente["fecha_fin"])) + UN_DIA
        heredados = {clave: _decimal(vigente[clave]) for clave in HEREDABLES}
    acordados = {**heredados, **palancas}  # lo negociado manda sobre lo heredado
    plazo = int(palancas.get("plazo_meses", plazo_evento))
    pago = acordados.get("plazo_pago_dias")

    return TerminosContrato(
        folio=f"C-{folio_evento}",
        tipo="renovacion" if renovacion else "nuevo",
        moneda=moneda,
        fecha_inicio=inicio,
        fecha_fin=sumar_meses(inicio, plazo) - UN_DIA,
        plazo_pago_dias=PLAZO_PAGO_POR_DEFECTO if pago is None else int(pago),
        sla_disponibilidad=acordados.get("sla_disponibilidad"),
        tope_aumento_pct=acordados.get("tope_aumento_pct"),
        cuota_implementacion=palancas.get("cuota_implementacion", Decimal(0)),
        lineas=tuple(
            LineaContrato(linea.codigo_servicio, linea.cantidad, valores.precios[linea.id])
            for linea in lineas
        ),
    )
