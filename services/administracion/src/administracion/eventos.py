"""Copia a la bitácora los eventos que publican los otros servicios."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from comun.consumidor import Atender, EventoInvalido
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from administracion.bitacora import MAX_NOMBRE, Actor, Objeto, registrar
from administracion.modelos import CorreoEnviado

NOMBRES_ENTIDAD = {
    "servicios": "servicios del catálogo",
    "proveedores": "proveedores",
    "tipo_cambio": "tipos de cambio",
    "contratos": "contratos",
    "desempeno": "registros de desempeño",
}
CAMBIOS_SERVICIO = frozenset({"creado", "actualizado", "desactivado", "activado"})
TIPOS_INTELIGENCIA = ("configuracion.", "modelo.")  # los publica inteligencia
PREFIJO_NEGOCIACION = "negociacion."  # los publica negociacion


@dataclass(frozen=True)
class CorreoNegociacion:
    """La invitación a negociar que mandó el servicio de negociación, para la página Correos."""

    destinatario: str
    solicitado_por: str
    estado: str  # enviado o fallido
    error: str | None


@dataclass(frozen=True)
class Registro:
    tipo: str
    actor: Actor
    objeto: Objeto
    detalle: dict[str, Any]
    resultado: str
    clave_origen: str
    fecha: datetime
    origen: str = "proveedores"
    correo: CorreoNegociacion | None = None


def _actor(payload: dict[str, Any]) -> Actor:
    actor = payload.get("actor") or {}
    return Actor(actor.get("id"), str(actor.get("nombre") or "Sistema"))


def _origen(tipo: str) -> str:
    if tipo.startswith(TIPOS_INTELIGENCIA):
        return "inteligencia"
    if tipo.startswith(PREFIJO_NEGOCIACION):
        return "negociacion"
    return "proveedores"


def _negociacion(
    tipo: str, payload: dict[str, Any], clave: str, fecha: datetime
) -> Registro | None:
    folio = str(payload["folio"])
    objeto = Objeto("negociacion", folio, f"{folio} «{payload['titulo']}»")
    actor = _actor(payload)
    if tipo == "negociacion.publicada":
        detalle: dict[str, Any] = {"proveedores": int(payload["proveedores"])}
        return Registro(tipo, actor, objeto, detalle, "exito", clave, fecha, "negociacion")
    if tipo == "negociacion.cancelada":
        detalle = {"motivo": str(payload["motivo"])}
        return Registro(tipo, actor, objeto, detalle, "exito", clave, fecha, "negociacion")
    if tipo == "negociacion.invitacion_enviada":
        estado = str(payload["estado"])
        if estado not in ("enviado", "fallido"):
            raise ValueError(f"Estado de correo desconocido: {estado}")
        error = payload.get("error")
        detalle = {
            "proveedor": str(payload["proveedor"]),
            "destinatario": str(payload["destinatario"]),
            "estado": estado,
            "reenvio": bool(payload["reenvio"]),
        }
        correo = CorreoNegociacion(
            str(payload["destinatario"]),
            actor.nombre[:MAX_NOMBRE],  # la columna mide lo mismo que actor_nombre
            estado,
            None if error is None else str(error),
        )
        resultado = "exito" if estado == "enviado" else "fallo"
        return Registro(
            tipo, actor, objeto, detalle, resultado, clave, fecha, "negociacion", correo
        )
    return None


def traducir(sobre: dict[str, Any]) -> Registro | None:
    """El registro de bitácora de un sobre de evento; None si el evento no es una acción."""
    try:
        tipo = sobre["type"]
        payload = sobre["payload"]
        origen = _origen(tipo)
        clave = f"{origen}:{sobre['event_id']}"
        fecha = datetime.fromisoformat(sobre["occurred_at"])
        if tipo.startswith(PREFIJO_NEGOCIACION):
            return _negociacion(tipo, payload, clave, fecha)
        if tipo in ("importacion.completada", "importacion.rechazada"):
            entidad = str(payload["entidad"])
            objeto = Objeto("importacion", entidad, NOMBRES_ENTIDAD.get(entidad, entidad))
            if tipo == "importacion.completada":
                detalle: dict[str, Any] = {
                    c: int(payload[c]) for c in ("filas", "registros", "omitidos")
                }
                return Registro(tipo, _actor(payload), objeto, detalle, "exito", clave, fecha)
            detalle = {"errores": int(payload["errores"])}
            return Registro(tipo, _actor(payload), objeto, detalle, "fallo", clave, fecha)
        if tipo == "servicio.actualizado":
            cambio = payload.get("cambio")
            if cambio not in CAMBIOS_SERVICIO or "actor" not in payload:
                return None
            codigo = str(payload["codigo"])
            detalle = (
                {"campos": list(payload.get("campos") or [])} if cambio == "actualizado" else {}
            )
            return Registro(
                f"servicio.{cambio}",
                _actor(payload),
                Objeto("servicio", codigo, codigo),
                detalle,
                "exito",
                clave,
                fecha,
            )
        if tipo == "configuracion.actualizada":
            cambios = [
                {"campo": str(c["campo"]), "anterior": c["anterior"], "nuevo": c["nuevo"]}
                for c in payload["cambios"]
            ]
            return Registro(
                tipo,
                _actor(payload),
                Objeto("configuracion", "puntuacion", "configuración de la puntuación"),
                {"cambios": cambios},
                "exito",
                clave,
                fecha,
                origen,
            )
        if tipo == "modelo.entrenado":
            version = int(payload["version"])
            detalle = {
                "version": version,
                "mape": float(payload["mape"]),
                "mape_linea_base": float(payload["mape_linea_base"]),
                "promovido": bool(payload["promovido"]),
                "origen": str(payload["origen"]),
            }
            return Registro(
                tipo,
                _actor(payload),
                Objeto("modelo", str(version), f"modelo de precios v{version}"),
                detalle,
                "exito",
                clave,
                fecha,
                origen,
            )
        return None
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise EventoInvalido(str(exc)) from exc


async def guardar(fabrica: async_sessionmaker[AsyncSession], registro: Registro) -> None:
    """Inserta el registro (y su correo, si trae); un evento ya recibido no hace nada."""
    async with fabrica() as sesion:
        nuevo = await registrar(
            sesion,
            registro.tipo,
            registro.actor,
            objeto=registro.objeto,
            detalle=registro.detalle,
            resultado=registro.resultado,
            origen=registro.origen,
            clave_origen=registro.clave_origen,
            fecha=registro.fecha,
        )
        if nuevo and registro.correo is not None:
            sesion.add(
                CorreoEnviado(
                    fecha=registro.fecha,
                    tipo="negociacion",
                    destinatario=registro.correo.destinatario,
                    usuario_id=None,
                    solicitado_por=registro.correo.solicitado_por,
                    estado=registro.correo.estado,
                    error=registro.correo.error,
                )
            )
        await sesion.commit()


def atendedor(fabrica: async_sessionmaker[AsyncSession]) -> Atender:
    """La función que el consumidor común llama con cada sobre de evento."""

    async def atender(sobre: dict[str, Any]) -> None:
        registro = traducir(sobre)
        if registro is not None:
            await guardar(fabrica, registro)

    return atender
