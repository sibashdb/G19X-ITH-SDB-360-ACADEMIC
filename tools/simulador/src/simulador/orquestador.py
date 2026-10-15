"""Corre los escenarios por la API (comprador y portal) y mide cada sesión (spec §13).

Solo usa HTTP: en las pruebas el cliente va a la app dentro del proceso; en N2, al stack real con
el token de servicio.
"""

import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
from generador.modelo import DatosSinteticos, ProveedorSintetico

from simulador.bots import ESTILOS, Bot, Termino, cuantizar
from simulador.escenarios import Banda, Escenario

FINALES = {"acuerdo_tentativo", "sin_acuerdo", "expirada"}
Encabezados = Callable[[], dict[str, str]]


@dataclass(frozen=True)
class Contexto:
    datos: DatosSinteticos
    bandas: dict[str, Banda]
    ids: Callable[[str], str]  # id estable por RFC, código o folio
    fecha_limite: datetime
    semilla: int = 11


@dataclass(frozen=True)
class Resultado:
    tipo: str
    estilo: str
    estado: str
    posible: bool  # la reserva del bot cabe en los límites del comprador
    primera: Decimal  # gasto de la primera oferta del proveedor: Σ cantidad * precio
    acordado: Decimal | None  # gasto del acuerdo tentativo
    fuera_de_limites: bool  # el acuerdo cruza algún límite del comprador

    @property
    def ahorro(self) -> float | None:
        return None if self.acordado is None else float(1 - self.acordado / self.primera)


def _ok(respuesta: httpx.Response, estado: int = 200) -> dict[str, Any]:
    if respuesta.status_code != estado:
        raise RuntimeError(
            f"{respuesta.request.method} {respuesta.request.url.path}: "
            f"{respuesta.status_code} {respuesta.text}"
        )
    return dict(respuesta.json())


def _cruza(ideal: Any, limite: Any, valor: Any) -> bool:
    meta, tope, medido = Decimal(str(ideal)), Decimal(str(limite)), Decimal(str(valor))
    return medido > tope if meta < tope else medido < tope


def dentro_de_limites(evento: dict[str, Any], valores: dict[str, Any]) -> bool:
    """Comprobación independiente del motor: ningún valor cruza el límite del comprador."""
    for linea in evento["lineas"]:
        if _cruza(linea["ideal"], linea["limite"], valores["precios"][str(linea["id"])]):
            return False
    for palanca in evento["palancas"]:
        if palanca["activa"] and palanca["clave"] != "precio":
            if _cruza(palanca["ideal"], palanca["limite"], valores["palancas"][palanca["clave"]]):
                return False
    return True


async def _crear(
    cliente: httpx.AsyncClient, comprador: Encabezados, contexto: Contexto, escenario: Escenario
) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "tipo": escenario.tipo,
        "titulo": escenario.titulo,
        "fecha_limite": contexto.fecha_limite.isoformat(),
    }
    if escenario.tipo == "compra":
        cuerpo["lineas"] = [
            {"codigo_servicio": linea.codigo, "cantidad": str(linea.cantidad)}
            for linea in escenario.lineas
        ]
        cuerpo["proveedores"] = [contexto.ids(rfc) for rfc in escenario.rfcs]
    else:
        cuerpo["proveedor_id"] = contexto.ids(escenario.rfcs[0])
        cuerpo["contrato_id"] = contexto.ids(str(escenario.folio))
    evento = _ok(await cliente.post("/eventos", json=cuerpo, headers=comprador()), 201)
    if escenario.con_plazo_de_pago:
        vigente = next(p["vigente"] for p in evento["palancas"] if p["clave"] == "plazo_pago_dias")
        base = Decimal(30) if vigente is None else Decimal(str(vigente))
        palancas = [
            {"clave": "precio", "peso": 80},
            {
                "clave": "plazo_pago_dias",
                "peso": 20,
                "ideal": str(min(base + 30, Decimal(180))),
                "limite": str(base),
            },
        ]
        evento = _ok(
            await cliente.patch(
                f"/eventos/{evento['id']}",
                json={"version": evento["version"], "palancas": palancas},
                headers=comprador(),
            )
        )
    if evento["errores"]:
        raise RuntimeError(f"La negociación simulada no se puede publicar: {evento['errores']}")
    return evento


def _bot(
    proveedor: ProveedorSintetico, evento: dict[str, Any], contexto: Contexto, rng: random.Random
) -> Bot:
    _, margen = ESTILOS[proveedor.estilo]
    precios: dict[str, Termino] = {}
    for linea in evento["lineas"]:
        banda = contexto.bandas.get(linea["codigo_servicio"])
        base = (
            banda.p50
            if banda is not None
            else Decimal(str(linea["precio_vigente"] or linea["limite"]))
        )
        lista = base * Decimal(repr(proveedor.nivel_precio))
        precios[str(linea["id"])] = Termino(
            "precio",
            cuantizar("precio", lista * (1 + margen), True),
            cuantizar("precio", lista * (1 - Decimal(repr(proveedor.flexibilidad))), True),
            True,
        )
    palancas: dict[str, Termino] = {}
    for palanca in evento["palancas"]:
        if not palanca["activa"] or palanca["clave"] == "precio":
            continue
        clave = palanca["clave"]
        ideal, limite = Decimal(str(palanca["ideal"])), Decimal(str(palanca["limite"]))
        mas = ideal < limite  # al proveedor le conviene lo contrario que al comprador
        reserva = ideal + Decimal(repr(rng.uniform(0.2, 1.0))) * (limite - ideal)
        inicio = limite + (limite - ideal) / 4  # pide algo más allá del límite del comprador
        palancas[clave] = Termino(
            clave, cuantizar(clave, inicio, mas), cuantizar(clave, reserva, mas), mas
        )
    return Bot(proveedor.estilo, precios, palancas, rng)


def _cabe(bot: Bot, evento: dict[str, Any]) -> bool:
    """Si la reserva del bot cabe en los límites del comprador: si hay acuerdo posible."""
    reservas = {
        "precios": {linea: t.reserva for linea, t in bot.precios.items()},
        "palancas": {clave: t.reserva for clave, t in bot.palancas.items()},
    }
    return dentro_de_limites(evento, reservas)


async def _medir(
    cliente: httpx.AsyncClient,
    comprador: Encabezados,
    evento: dict[str, Any],
    sesion_id: str,
    bot: Bot,
) -> Resultado:
    detalle = _ok(await cliente.get(f"/sesiones/{sesion_id}", headers=comprador()))
    propias = [o for o in detalle["ofertas"] if o["autor"] == "proveedor"]
    cantidades = {str(linea["id"]): Decimal(str(linea["cantidad"])) for linea in evento["lineas"]}

    def gasto(valores: dict[str, Any]) -> Decimal:
        return sum(
            (cantidades[linea] * Decimal(str(p)) for linea, p in valores["precios"].items()),
            Decimal(0),
        )

    acuerdo = detalle["estado"] == "acuerdo_tentativo"
    return Resultado(
        tipo=evento["tipo"],
        estilo=bot.estilo,
        estado=detalle["estado"],
        posible=_cabe(bot, evento),
        primera=gasto(propias[0]["valores"]),
        acordado=gasto(propias[-1]["valores"]) if acuerdo else None,
        fuera_de_limites=acuerdo and not dentro_de_limites(evento, propias[-1]["valores"]),
    )


async def _negociar(
    cliente: httpx.AsyncClient,
    comprador: Encabezados,
    contexto: Contexto,
    escenario: Escenario,
    numero: int,
) -> list[Resultado]:
    borrador = await _crear(cliente, comprador, contexto, escenario)
    publicado = _ok(await cliente.post(f"/eventos/{borrador['id']}/publicar", headers=comprador()))
    evento = publicado["evento"]
    verdad = {p.rfc: p for p in contexto.datos.proveedores}
    rfc_de = {contexto.ids(rfc): rfc for rfc in escenario.rfcs}
    proveedor_de = {str(s["id"]): str(s["proveedor_id"]) for s in evento["sesiones"]}
    bots: dict[str, Bot] = {}
    portales: dict[str, dict[str, str]] = {}
    for enlace in publicado["enlaces"]:
        sesion_id = str(enlace["sesion_id"])
        rfc = rfc_de[proveedor_de[sesion_id]]
        # Un generador por bot: el orden de los ids de sesión no cambia lo que hace cada uno.
        rng = random.Random(f"{contexto.semilla}-{numero}-{rfc}")  # noqa: S311 - reproducible
        bots[sesion_id] = _bot(verdad[rfc], evento, contexto, rng)
        portales[sesion_id] = {"Authorization": f"Invitacion {enlace['enlace'].split('#t=')[1]}"}
    pendientes = set(portales)
    for _ in range(2 * int(evento["rondas_max"]) + 2):  # tope por si una sesión no termina
        for sesion_id in sorted(pendientes):
            vista = _ok(await cliente.get("/portal/sesion", headers=portales[sesion_id]))
            if vista["estado"] in FINALES:
                pendientes.discard(sesion_id)
                continue
            bot = bots[sesion_id]
            propuesta = vista["ultima_propuesta"]
            if propuesta is not None and bot.acepta(propuesta):
                valores = propuesta  # acepta reenviando la propuesta del agente
            else:
                k = vista["rondas_max"] - vista["rondas_restantes"] + 1
                valores = bot.oferta(k, vista["rondas_max"])
            cuerpo = {"valores": valores, "confirmar_valores": vista["pide_confirmacion"]}
            _ok(
                await cliente.post(
                    "/portal/ofertas",
                    json=cuerpo,
                    headers=portales[sesion_id] | {"Idempotency-Key": uuid.uuid4().hex},
                )
            )
        if not pendientes:
            break
    return [
        await _medir(cliente, comprador, evento, sesion_id, bots[sesion_id])
        for sesion_id in sorted(portales)
    ]


async def correr(
    cliente: httpx.AsyncClient,
    comprador: Encabezados,
    contexto: Contexto,
    escenarios: list[Escenario],
) -> list[Resultado]:
    resultados: list[Resultado] = []
    for numero, escenario in enumerate(escenarios):
        resultados += await _negociar(cliente, comprador, contexto, escenario, numero)
    return resultados
