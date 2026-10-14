"""Consultas a inteligencia y a proveedores con el token del comprador (spec D5).

Solo se usan al crear o editar un borrador; los turnos nunca llaman a otros servicios, así que una
negociación se reproduce aunque cambie el benchmark.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from negociacion.errores import invalido, no_disponible

log = logging.getLogger(__name__)
TIEMPO_ESPERA_S = 5.0
CAMPOS_REFERENCIA = ("p25", "p50", "p75", "metodo", "version", "confianza", "observaciones")


@dataclass(frozen=True)
class LineaVigente:
    codigo_servicio: str
    nombre: str
    unidad: str
    cantidad: Decimal
    precio_unitario: Decimal


@dataclass(frozen=True)
class ContratoVigente:
    id: uuid.UUID
    folio: str
    moneda: str
    fecha_inicio: date
    fecha_fin: date
    plazo_pago_dias: int
    sla_disponibilidad: Decimal | None
    tope_aumento_pct: Decimal | None
    cuota_implementacion: Decimal
    lineas: tuple[LineaVigente, ...]

    @property
    def plazo_meses(self) -> int:
        """Meses de calendario del contrato (del 2025-11-01 al 2026-10-31 son 12), de 1 a 60."""
        meses = (
            (self.fecha_fin.year - self.fecha_inicio.year) * 12
            + self.fecha_fin.month
            - self.fecha_inicio.month
            + 1
        )
        return min(60, max(1, meses))

    def terminos(self) -> dict[str, Any]:
        """Lo que se guarda en la foto del evento: los términos vigentes, como texto."""
        return {
            "folio": self.folio,
            "fecha_inicio": self.fecha_inicio.isoformat(),
            "fecha_fin": self.fecha_fin.isoformat(),
            "plazo_meses": self.plazo_meses,
            "plazo_pago_dias": self.plazo_pago_dias,
            "sla_disponibilidad": _texto(self.sla_disponibilidad),
            "tope_aumento_pct": _texto(self.tope_aumento_pct),
            "cuota_implementacion": str(self.cuota_implementacion),
        }


def _texto(valor: Decimal | None) -> str | None:
    return None if valor is None else str(valor)


def _decimal(valor: Any) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def _contrato(datos: dict[str, Any]) -> ContratoVigente:
    return ContratoVigente(
        id=uuid.UUID(str(datos["id"])),
        folio=str(datos["folio"]),
        moneda=str(datos["moneda"]),
        fecha_inicio=date.fromisoformat(str(datos["fecha_inicio"])),
        fecha_fin=date.fromisoformat(str(datos["fecha_fin"])),
        plazo_pago_dias=int(datos["plazo_pago_dias"]),
        sla_disponibilidad=_decimal(datos["sla_disponibilidad"]),
        tope_aumento_pct=_decimal(datos["tope_aumento_pct"]),
        cuota_implementacion=Decimal(str(datos["cuota_implementacion"])),
        lineas=tuple(
            LineaVigente(
                codigo_servicio=str(linea["codigo_servicio"]),
                nombre=str(linea["nombre_servicio"]),
                unidad=str(linea["unidad"]),
                cantidad=Decimal(str(linea["cantidad"])),
                precio_unitario=Decimal(str(linea["precio_unitario"])),
            )
            for linea in datos["lineas"]
        ),
    )


class Integraciones:
    def __init__(
        self, http: httpx.AsyncClient, inteligencia_url: str, proveedores_url: str
    ) -> None:
        self._http = http
        self._inteligencia = inteligencia_url.rstrip("/")
        self._proveedores = proveedores_url.rstrip("/")

    async def _get(
        self, url: str, token: str, params: dict[str, str] | None = None
    ) -> httpx.Response:
        try:
            return await self._http.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIEMPO_ESPERA_S,
            )
        except httpx.HTTPError as exc:
            log.warning("No respondió %s: %r", url, exc)
            raise no_disponible() from exc

    async def referencia(
        self, token: str, codigo: str, cantidad: Decimal, plazo: int
    ) -> dict[str, Any] | None:
        """P25/P50/P75 y su origen para esa cantidad y plazo; None si no hay referencia."""
        respuesta = await self._get(
            f"{self._inteligencia}/precios/servicios/{codigo}/referencia",
            token,
            {"cantidad": str(cantidad), "plazo": str(plazo)},
        )
        if respuesta.status_code == 404:  # sin contratos recientes (o aún no llega a su copia)
            return None
        if respuesta.status_code != 200:
            raise no_disponible()
        try:
            datos = respuesta.json()
            return {campo: datos[campo] for campo in CAMPOS_REFERENCIA}
        except (ValueError, KeyError, TypeError) as exc:
            raise no_disponible() from exc

    async def contrato(
        self, token: str, proveedor_id: uuid.UUID, contrato_id: uuid.UUID
    ) -> ContratoVigente:
        respuesta = await self._get(
            f"{self._proveedores}/proveedores/{proveedor_id}/contratos", token
        )
        if respuesta.status_code == 404:
            raise invalido("proveedor_id", "El proveedor no existe.", "proveedor_inexistente")
        if respuesta.status_code != 200:
            raise no_disponible()
        try:
            for datos in respuesta.json():
                if str(datos["id"]) == str(contrato_id):
                    return _contrato(datos)
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            raise no_disponible() from exc
        raise invalido("contrato_id", "El contrato no es de ese proveedor.", "contrato_inexistente")
