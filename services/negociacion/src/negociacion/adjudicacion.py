"""Casos de uso de la adjudicación: los candidatos, su evaluación y las propuestas (spec §4)."""

import re
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion import consultas, turnos
from negociacion.api import esquemas
from negociacion.errores import conflicto, invalido
from negociacion.integraciones import Integraciones
from negociacion.modelos import Adjudicacion, Evento, SesionNegociacion

ESTADOS_EVALUACION = ("en_evaluacion", "pendiente_aprobacion", "adjudicado", "desierto")
CRITERIOS = ("costo", "desempeno", "riesgo", "sla")  # el orden de `?pesos=40,30,15,15`
VIGENTES = ("pendiente", "aprobada", "directa")
ETIQUETAS_ESTADO = {
    "borrador": "borrador",
    "abierto": "abierto",
    "en_evaluacion": "en evaluación",
    "pendiente_aprobacion": "pendiente de aprobación",
    "adjudicado": "adjudicado",
    "desierto": "desierto",
    "cancelado": "cancelado",
}
ENTERO = re.compile(r"[0-9]{1,3}")
PESOS_INVALIDOS = (
    "Indique los pesos como cuatro enteros de 0 a 100 que sumen 100, en el orden costo, "
    "desempeño, riesgo y SLA; por ejemplo, 40,30,15,15."
)


def pesos_de(texto: str | None) -> dict[str, int] | None:
    """Los pesos de la consulta; None si no se indicaron (inteligencia usa los configurados)."""
    if texto is None:
        return None
    partes = texto.split(",")
    if len(partes) == len(CRITERIOS) and all(ENTERO.fullmatch(parte) for parte in partes):
        pesos = dict(zip(CRITERIOS, map(int, partes), strict=True))
        if sum(pesos.values()) == 100:  # sin signo y sumando 100, ninguno pasa de 100
            return pesos
    raise invalido("pesos", PESOS_INVALIDOS, "pesos_invalidos")


def exigir_estado(evento: Evento, *estados: str) -> None:
    """409 `estado_invalido` si el evento no está en uno de esos estados; dice cuál tiene."""
    if evento.estado not in estados:
        permitidos = ", ".join(ETIQUETAS_ESTADO.get(estado, estado) for estado in estados)
        actual = ETIQUETAS_ESTADO.get(evento.estado, evento.estado)
        raise conflicto(
            f"La negociación está en estado «{actual}»; esta acción solo procede en: {permitidos}.",
            "estado_invalido",
        )


async def candidatos(bd: AsyncSession, evento: Evento) -> list[dict[str, Any]]:
    """Un candidato por sesión en acuerdo tentativo, con lo que se acordó (la última oferta del
    proveedor) y, de lo que no se negoció, el plazo del evento y el SLA del contrato vigente."""
    sesiones = (
        await bd.scalars(
            select(SesionNegociacion)
            .where(
                SesionNegociacion.evento_id == evento.id,
                SesionNegociacion.estado == "acuerdo_tentativo",
            )
            .order_by(SesionNegociacion.proveedor_nombre, SesionNegociacion.id)
        )
    ).all()
    lineas = await consultas.lineas_de(bd, evento.id)
    vigente = evento.foto.get("contrato") or {}  # solo una renovación tiene contrato vigente
    resultado: list[dict[str, Any]] = []
    # ponytail: una consulta por sesión (a lo más 10 invitados); un solo JOIN si hubiera más.
    for sesion in sesiones:
        oferta = await turnos.ultima_oferta_proveedor(bd, sesion.id)
        if oferta is None:
            raise RuntimeError("Un acuerdo tentativo siempre tiene una oferta del proveedor")
        precios, palancas = oferta.valores["precios"], oferta.valores["palancas"]
        resultado.append(
            {
                "id": str(sesion.id),
                "proveedor_id": str(sesion.proveedor_id),
                "nombre": sesion.proveedor_nombre,
                "plazo_meses": int(Decimal(str(palancas.get("plazo_meses", evento.plazo_meses)))),
                "cuota_implementacion": str(palancas.get("cuota_implementacion", 0)),
                "sla": palancas.get("sla_disponibilidad", vigente.get("sla_disponibilidad")),
                "lineas": [
                    {
                        "codigo_servicio": linea.codigo_servicio,
                        "unidad": linea.unidad,
                        "cantidad": str(linea.cantidad),
                        "precio": str(precios[str(linea.id)]),
                    }
                    for linea in lineas
                ],
            }
        )
    return resultado


async def peticion_de(
    bd: AsyncSession, evento: Evento, pesos: dict[str, int] | None
) -> dict[str, Any]:
    """El cuerpo de la consulta a inteligencia: los acuerdos de hoy y, si se dieron, los pesos."""
    cuerpo: dict[str, Any] = {"moneda": evento.moneda, "candidatos": await candidatos(bd, evento)}
    if pesos is not None:
        cuerpo["pesos"] = pesos
    return cuerpo


async def evaluar(
    bd: AsyncSession,
    integ: Integraciones,
    token: str,
    evento: Evento,
    pesos: dict[str, int] | None,
) -> dict[str, Any]:
    """La recomendación de inteligencia para los acuerdos de hoy, con los pesos dados o, sin
    ellos, los configurados. Si inteligencia falla, 503.

    Usa la transacción que tenga `bd`: quien la llame con el evento bloqueado lo conserva así
    durante la consulta.
    """
    return await integ.recomendacion(token, await peticion_de(bd, evento, pesos))


async def propuestas(
    bd: AsyncSession, evento_id: uuid.UUID
) -> tuple[Adjudicacion | None, list[Adjudicacion]]:
    """La propuesta vigente (pendiente, aprobada o directa) y las rechazadas, la más reciente
    primero."""
    filas = (
        await bd.scalars(
            select(Adjudicacion)
            .where(Adjudicacion.evento_id == evento_id)
            .order_by(Adjudicacion.propuesta_en.desc())
        )
    ).all()
    vigente = next((fila for fila in filas if fila.estado in VIGENTES), None)
    return vigente, [fila for fila in filas if fila.estado == "rechazada"]


async def evaluacion(
    bd: AsyncSession,
    integ: Integraciones,
    token: str,
    evento_id: uuid.UUID,
    pesos: dict[str, int] | None,
) -> esquemas.Evaluacion:
    """La recomendación de hoy, la propuesta vigente y las rechazadas de un evento.

    Lee la base en su propia transacción (llámela sin una en curso) y la cierra antes de esperar
    a inteligencia, hasta 5 s: así no retiene una conexión del pool mientras tanto.
    """
    peticion = None
    async with bd.begin():
        evento = await consultas.evento_o_404(bd, evento_id)
        exigir_estado(evento, *ESTADOS_EVALUACION)
        hay_acuerdos = exists().where(
            SesionNegociacion.evento_id == evento.id,
            SesionNegociacion.estado == "acuerdo_tentativo",
        )
        if evento.estado != "desierto" and await bd.scalar(select(hay_acuerdos)):
            # Aun pendiente o adjudicado se calcula de nuevo: la foto de la propuesta es `vigente`.
            peticion = await peticion_de(bd, evento, pesos)
        vigente, historial = await propuestas(bd, evento.id)
        propuesta = None if vigente is None else esquemas.AdjudicacionSalida.model_validate(vigente)
        rechazadas = [esquemas.AdjudicacionSalida.model_validate(fila) for fila in historial]
    recomendacion = None if peticion is None else await integ.recomendacion(token, peticion)
    return esquemas.Evaluacion(recomendacion=recomendacion, vigente=propuesta, historial=rechazadas)
