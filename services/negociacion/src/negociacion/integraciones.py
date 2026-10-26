"""Consultas a inteligencia y a proveedores con el token del comprador (spec D5).

Se usan al crear o editar un borrador y al evaluar los acuerdos para adjudicar; los turnos nunca
llaman a otros servicios, así que una negociación se reproduce aunque cambie el benchmark.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from comun.errores import ErrorDominio

from negociacion.errores import SIN_REFERENCIA, invalido, no_disponible

log = logging.getLogger(__name__)
TIEMPO_ESPERA_S = 5.0
SIN_RECOMENDACION = (
    "No se pudo obtener la recomendación de adjudicación. Intente de nuevo en unos minutos."
)
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


def _sin_observaciones(respuesta: httpx.Response) -> bool:
    """Solo el 404 con ese código significa «no hay referencia»; cualquier otro 404 es una falla."""
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return False
    return isinstance(cuerpo, dict) and cuerpo.get("codigo") == "sin_observaciones"


def _falla(respuesta: httpx.Response, detalle: str = SIN_REFERENCIA) -> ErrorDominio:
    """Registra la respuesta inesperada (sin cabeceras ni token) y devuelve el 503."""
    log.warning("%s respondió %s", respuesta.url.path, respuesta.status_code)
    return no_disponible(detalle)


def _revisar_recomendacion(datos: Any, pedidos: list[str]) -> None:
    """Lanza ValueError (o KeyError/TypeError) si la respuesta no es la recomendación de esos
    candidatos: los mismos ids, un recomendado entre ellos y montos finitos y positivos."""
    candidatos = datos["candidatos"]
    if sorted(c["id"] for c in candidatos) != sorted(pedidos):
        raise ValueError("los candidatos no son los pedidos")
    if datos["recomendado"] not in pedidos:
        raise ValueError("el recomendado no es un candidato")
    for candidato in candidatos:
        for campo in ("costo_total", "costo_total_mxn"):
            monto = Decimal(str(candidato[campo]))
            if not monto.is_finite() or monto <= 0:
                raise ValueError(f"{campo} no es un monto positivo")
    umbral = Decimal(str(datos["umbral_aprobacion"]))
    if not umbral.is_finite() or umbral < 0 or not isinstance(datos["pesos"], dict):
        raise ValueError("faltan los pesos o el umbral")


class Integraciones:
    def __init__(
        self, http: httpx.AsyncClient, inteligencia_url: str, proveedores_url: str
    ) -> None:
        self._http = http
        self._inteligencia = inteligencia_url.rstrip("/")
        self._proveedores = proveedores_url.rstrip("/")

    async def _pedir(
        self, metodo: str, url: str, token: str, *, detalle: str = SIN_REFERENCIA, **opciones: Any
    ) -> httpx.Response:
        try:
            return await self._http.request(
                metodo,
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIEMPO_ESPERA_S,
                **opciones,
            )
        except httpx.HTTPError as exc:
            log.warning("No respondió %s: %r", url, exc)
            raise no_disponible(detalle) from exc

    async def referencia(
        self, token: str, codigo: str, cantidad: Decimal, plazo: int
    ) -> dict[str, Any] | None:
        """P25/P50/P75 y su origen para esa cantidad y plazo; None si no hay referencia."""
        respuesta = await self._pedir(
            "GET",
            f"{self._inteligencia}/precios/servicios/{codigo}/referencia",
            token,
            params={"cantidad": str(cantidad), "plazo": str(plazo)},
        )
        if respuesta.status_code == 404 and _sin_observaciones(respuesta):
            return None  # sin contratos recientes: el servicio existe pero no hay referencia
        if respuesta.status_code != 200:
            raise _falla(respuesta)
        try:
            datos = respuesta.json()
            referencia = {campo: datos[campo] for campo in CAMPOS_REFERENCIA}
            for campo in ("p25", "p50", "p75"):  # nunca se guarda un percentil que no es número
                if not Decimal(str(referencia[campo])).is_finite():
                    raise ValueError(f"{campo} no es finito")
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            log.warning("Respuesta mal formada de %s: %r", respuesta.url.path, exc)
            raise no_disponible() from exc
        return referencia

    async def contrato(
        self, token: str, proveedor_id: uuid.UUID, contrato_id: uuid.UUID
    ) -> ContratoVigente:
        respuesta = await self._pedir(
            "GET", f"{self._proveedores}/proveedores/{proveedor_id}/contratos", token
        )
        if respuesta.status_code == 404:
            raise invalido("proveedor_id", "El proveedor no existe.", "proveedor_inexistente")
        if respuesta.status_code != 200:
            raise _falla(respuesta)
        try:
            for datos in respuesta.json():
                if str(datos["id"]) == str(contrato_id):
                    return _contrato(datos)
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            log.warning("Respuesta mal formada de %s: %r", respuesta.url.path, exc)
            raise no_disponible() from exc
        raise invalido("contrato_id", "El contrato no es de ese proveedor.", "contrato_inexistente")

    async def recomendacion(self, token: str, cuerpo: dict[str, Any]) -> dict[str, Any]:
        """La recomendación de adjudicación de inteligencia para los candidatos del cuerpo.

        Cualquier falla (un código que no es 200, incluidos su 409 y su 422, el tiempo agotado o
        una respuesta que no corresponde a lo pedido) es un 503: nunca se inventa una
        recomendación ni un costo de 0.
        """
        respuesta = await self._pedir(
            "POST",
            f"{self._inteligencia}/adjudicacion/recomendacion",
            token,
            detalle=SIN_RECOMENDACION,
            json=cuerpo,
        )
        if respuesta.status_code != 200:
            raise _falla(respuesta, SIN_RECOMENDACION)
        try:
            datos = respuesta.json()
            _revisar_recomendacion(datos, [c["id"] for c in cuerpo["candidatos"]])
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            log.warning("Respuesta mal formada de %s: %r", respuesta.url.path, exc)
            raise no_disponible(SIN_RECOMENDACION) from exc
        return dict(datos)


class ClienteIA:
    """Cliente del servicio ia (N2). Cualquier falla devuelve None: el agente usa su plantilla.

    Los turnos sí llaman a ia, pero solo para el texto: el motor decide igual sin él, así que la
    negociación se sigue reproduciendo desde la bitácora.
    """

    def __init__(self, http: httpx.AsyncClient, url: str) -> None:
        self._http = http
        self.url = url.rstrip("/")

    async def _pedir(
        self, ruta: str, cuerpo: dict[str, Any], espera_s: float
    ) -> dict[str, Any] | None:
        if not self.url or espera_s <= 0:
            return None
        try:
            respuesta = await self._http.post(f"{self.url}/{ruta}", json=cuerpo, timeout=espera_s)
        except httpx.HTTPError as exc:
            log.warning("ia no respondió en %s: %r", ruta, exc)
            return None
        if respuesta.status_code != 200:
            return None
        try:
            datos = respuesta.json()
        except ValueError:
            return None
        return datos if isinstance(datos, dict) else None

    async def redactar(self, cuerpo: dict[str, Any], espera_s: float) -> dict[str, Any] | None:
        return await self._pedir("redactar", cuerpo, espera_s)

    async def interpretar(self, cuerpo: dict[str, Any], espera_s: float) -> dict[str, Any] | None:
        return await self._pedir("interpretar", cuerpo, espera_s)
