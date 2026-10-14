"""Topología de RabbitMQ que comparten los servicios: qué colas reciben qué eventos.

`infra/rabbitmq/definitions.json` la declara antes de que alguien publique (el contenedor
`rabbitmq-topologia` la aplica con la API de administración). Una prueba verifica que el archivo y
este módulo coinciden, y que todo evento que se publica llega a alguna cola.
"""

import re
from dataclasses import dataclass
from typing import Any

from comun.outbox import EXCHANGE_EVENTOS

EXCHANGE_FALLIDOS = "eventos.dlx"
VHOST = "/"
# Quorum: sobrevive a los reinicios. Tras 5 entregas fallidas, RabbitMQ manda el mensaje a la cola
# de fallidos de esa cola (la política se aplica en definitions.json, no con argumentos: cambiar
# los argumentos de una cola que ya existe falla con PRECONDITION_FAILED).
ARGUMENTOS_COLA: dict[str, Any] = {"x-queue-type": "quorum", "x-delivery-limit": 5}


@dataclass(frozen=True)
class Cola:
    nombre: str
    claves: tuple[str, ...]

    @property
    def fallidos(self) -> str:
        return f"{self.nombre}.dlq"


COLA_INTELIGENCIA = Cola(
    "inteligencia.eventos",
    ("proveedor.*", "servicio.*", "contrato.*", "desempeno.*", "tipo_cambio.*"),
)
COLA_ADMINISTRACION = Cola(
    "administracion.actividad",
    ("importacion.*", "servicio.*", "configuracion.*", "modelo.*", "negociacion.*"),
)
# Copias locales de negociacion: el contacto del proveedor y el catálogo de servicios.
COLA_NEGOCIACION = Cola("negociacion.eventos", ("proveedor.*", "servicio.*"))
COLAS = (COLA_INTELIGENCIA, COLA_ADMINISTRACION, COLA_NEGOCIACION)

TIPOS_EVENTO = frozenset(
    {
        "proveedor.actualizado",
        "servicio.actualizado",
        "contrato.registrado",
        "desempeno.registrado",
        "tipo_cambio.registrado",
        "importacion.completada",
        "importacion.rechazada",
        "configuracion.actualizada",
        "modelo.entrenado",
        "negociacion.publicada",
        "negociacion.cancelada",
        "negociacion.invitacion_enviada",
    }
)


def coincide(clave: str, tipo: str) -> bool:
    """Si la clave de enlace de un exchange topic ("servicio.*") recibe ese tipo de evento."""
    partes_clave, partes_tipo = clave.split("."), tipo.split(".")
    return len(partes_clave) == len(partes_tipo) and all(
        parte in ("*", palabra) for parte, palabra in zip(partes_clave, partes_tipo, strict=True)
    )


def colas_de(tipo: str) -> list[str]:
    return [cola.nombre for cola in COLAS if any(coincide(c, tipo) for c in cola.claves)]


def _exchange(nombre: str, tipo: str) -> dict[str, Any]:
    return {
        "name": nombre,
        "vhost": VHOST,
        "type": tipo,
        "durable": True,
        "auto_delete": False,
        "internal": False,
        "arguments": {},
    }


def _cola(nombre: str, argumentos: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": nombre,
        "vhost": VHOST,
        "durable": True,
        "auto_delete": False,
        "arguments": argumentos,
    }


def _enlace(origen: str, destino: str, clave: str) -> dict[str, Any]:
    return {
        "source": origen,
        "vhost": VHOST,
        "destination": destino,
        "destination_type": "queue",
        "routing_key": clave,
        "arguments": {},
    }


def definiciones() -> dict[str, list[dict[str, Any]]]:
    """El contenido que debe tener infra/rabbitmq/definitions.json."""
    colas: list[dict[str, Any]] = []
    enlaces: list[dict[str, Any]] = []
    politicas: list[dict[str, Any]] = []
    for cola in COLAS:
        colas.append(_cola(cola.nombre, ARGUMENTOS_COLA))
        colas.append(_cola(cola.fallidos, {"x-queue-type": "quorum"}))
        enlaces.extend(_enlace(EXCHANGE_EVENTOS, cola.nombre, clave) for clave in cola.claves)
        enlaces.append(_enlace(EXCHANGE_FALLIDOS, cola.fallidos, cola.nombre))
        politicas.append(
            {
                "vhost": VHOST,
                "name": f"fallidos-{cola.nombre}",
                "pattern": f"^{re.escape(cola.nombre)}$",
                "apply-to": "queues",
                "priority": 0,
                "definition": {
                    "dead-letter-exchange": EXCHANGE_FALLIDOS,
                    "dead-letter-routing-key": cola.nombre,
                },
            }
        )
    return {
        "exchanges": [_exchange(EXCHANGE_EVENTOS, "topic"), _exchange(EXCHANGE_FALLIDOS, "direct")],
        "queues": colas,
        "bindings": enlaces,
        "policies": politicas,
    }
