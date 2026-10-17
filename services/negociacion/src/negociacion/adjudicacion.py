"""Casos de uso de la adjudicación: los candidatos, su evaluación, las propuestas y su decisión
(spec §4).

Cada transición toma el evento `FOR UPDATE` y solo procede desde su estado de origen: quien llega
tarde recibe un 409 que dice el estado actual.
"""

import re
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from comun.auth import Usuario
from comun.outbox import registrar_evento
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from negociacion import consultas, turnos
from negociacion.api import esquemas
from negociacion.bitacora import MAX_NOMBRE, Actor, de_usuario, registrar
from negociacion.dominio.adjudicacion import (
    LineaTerminos,
    TerminosContrato,
    requiere_aprobacion,
    terminos_contrato,
)
from negociacion.dominio.terminos import Valores
from negociacion.errores import conflicto, invalido, prohibido
from negociacion.integraciones import Integraciones
from negociacion.modelos import Adjudicacion, Evento, Outbox, SesionNegociacion

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
CENTAVOS = Decimal("0.01")
JUSTIFICACION_MIN, JUSTIFICACION_MAX = 10, 1000
JUSTIFICACION_OBLIGATORIA = (
    "Para elegir un proveedor distinto del recomendado, escriba la justificación "
    "(de 10 a 1,000 caracteres)."
)
JUSTIFICACION_LONGITUD = "La justificación debe tener de 10 a 1,000 caracteres."
SESION_NO_CANDIDATA = "La sesión elegida no es un acuerdo tentativo de esta negociación."
MISMA_PERSONA = "Usted propuso esta adjudicación; la decide otra persona."
SIN_CONTRATO_VIGENTE = (
    "Esta renovación no conserva el contrato vigente, así que no se puede armar el nuevo contrato."
)
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


async def _salidas(
    bd: AsyncSession, evento_id: uuid.UUID
) -> tuple[esquemas.AdjudicacionSalida | None, list[esquemas.AdjudicacionSalida]]:
    vigente, historial = await propuestas(bd, evento_id)
    return (
        None if vigente is None else esquemas.AdjudicacionSalida.model_validate(vigente),
        [esquemas.AdjudicacionSalida.model_validate(fila) for fila in historial],
    )


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
        vigente, rechazadas = await _salidas(bd, evento.id)
    recomendacion = None if peticion is None else await integ.recomendacion(token, peticion)
    return esquemas.Evaluacion(recomendacion=recomendacion, vigente=vigente, historial=rechazadas)


async def _respuesta(
    bd: AsyncSession, evento_id: uuid.UUID, recomendacion: dict[str, Any] | None
) -> esquemas.Evaluacion:
    """La evaluación tras una acción, con lo que ya se tiene: una decisión que se guardó no puede
    contestar 503 por una nueva consulta a inteligencia."""
    vigente, rechazadas = await _salidas(bd, evento_id)
    return esquemas.Evaluacion(recomendacion=recomendacion, vigente=vigente, historial=rechazadas)


def justificacion_de(texto: str | None, obligatoria: bool) -> str | None:
    """La justificación sin espacios sobrantes (10 a 1,000 caracteres); None si no se dio y no
    hacía falta. Vacía o de solo espacios cuenta como no dada."""
    limpia = (texto or "").strip()
    if not limpia and not obligatoria:
        return None
    if not JUSTIFICACION_MIN <= len(limpia) <= JUSTIFICACION_MAX:
        detalle = JUSTIFICACION_LONGITUD if limpia else JUSTIFICACION_OBLIGATORIA
        raise invalido("justificacion", detalle, "justificacion_requerida")
    return limpia


def _centavos(valor: Any) -> Decimal:
    """El monto a centavos, como lo guarda la base: lo que se compara es lo que queda escrito."""
    return Decimal(str(valor)).quantize(CENTAVOS, ROUND_HALF_UP)


async def _terminos(
    bd: AsyncSession, evento: Evento, sesion: SesionNegociacion, momento: datetime
) -> TerminosContrato:
    """Los términos del contrato con lo último que acordó el proveedor de esa sesión."""
    if evento.tipo == "renovacion" and not evento.foto.get("contrato"):
        raise conflicto(SIN_CONTRATO_VIGENTE, "contrato_vigente_faltante")
    oferta = await turnos.ultima_oferta_proveedor(bd, sesion.id)
    if oferta is None:
        raise RuntimeError("Un acuerdo tentativo siempre tiene una oferta del proveedor")
    lineas = [
        LineaTerminos(str(linea.id), linea.codigo_servicio, linea.cantidad)
        for linea in await consultas.lineas_de(bd, evento.id)
    ]
    return terminos_contrato(
        folio_evento=evento.folio,
        tipo_evento=evento.tipo,
        moneda=evento.moneda,
        plazo_evento=evento.plazo_meses,
        valores=Valores.de_json(oferta.valores),
        lineas=lineas,
        contrato_vigente=evento.foto.get("contrato"),
        decidida_en=momento,
    )


def _decidida(fila: Adjudicacion, actor: Actor, momento: datetime) -> None:
    fila.decidida_por_id = actor.id
    fila.decidida_por_nombre = actor.nombre[:MAX_NOMBRE]
    fila.decidida_en = momento


def _adjudicar(
    bd: AsyncSession,
    evento: Evento,
    fila: Adjudicacion,
    sesion: SesionNegociacion,
    terminos: TerminosContrato,
    actor: Actor,
    aprobacion: str,
) -> None:
    """Adjudica el evento y avisa a proveedores (el contrato) y a administración."""
    fila.contrato_folio = terminos.folio
    evento.estado = "adjudicado"
    registrar_evento(
        bd,
        Outbox,
        "negociacion.adjudicada",
        {
            "folio": evento.folio,
            "titulo": evento.titulo,
            "tipo": evento.tipo,
            "proveedor_id": str(sesion.proveedor_id),
            "proveedor": sesion.proveedor_nombre,
            "costo_total_mxn": str(fila.costo_total_mxn),
            "contrato": terminos.para_evento(),
            "aprobacion": aprobacion,  # directa o aprobada
            "actor": actor.para_evento(),
        },
    )


def _detalle(fila: Adjudicacion, sesion: SesionNegociacion) -> dict[str, Any]:
    """Lo que la bitácora guarda de cada acción sobre una propuesta."""
    return {
        "adjudicacion_id": str(fila.id),
        "sesion_id": str(sesion.id),
        "proveedor": sesion.proveedor_nombre,
        "costo_total_mxn": str(fila.costo_total_mxn),
    }


async def proponer(
    bd: AsyncSession,
    integ: Integraciones,
    token: str,
    usuario: Usuario,
    evento_id: uuid.UUID,
    datos: esquemas.Propuesta,
    momento: datetime,
) -> esquemas.Evaluacion:
    """El comprador propone adjudicar a una sesión (spec §4.2 y §4.3).

    Vuelve a pedir la recomendación con el evento bloqueado: nunca confía en la del cliente. Si
    inteligencia falla, 503 y no se guarda nada. Sin necesitar aprobación queda `directa` y el
    evento `adjudicado`; si la necesita, `pendiente` y el evento `pendiente_aprobacion`.
    """
    pesos, actor = pesos_de(datos.pesos), de_usuario(usuario)
    async with bd.begin():
        evento = await consultas.evento_o_404(bd, evento_id, bloquear=True)
        exigir_estado(evento, "en_evaluacion")
        sesion = await bd.get(SesionNegociacion, datos.sesion_id)
        if sesion is None or sesion.evento_id != evento.id or sesion.estado != "acuerdo_tentativo":
            raise invalido("sesion_id", SESION_NO_CANDIDATA, "sesion_no_candidata")
        recomendacion = await evaluar(bd, integ, token, evento, pesos)
        elegida = str(sesion.id)
        candidato = {c["id"]: c for c in recomendacion["candidatos"]}[elegida]
        se_aparta = elegida != recomendacion["recomendado"]
        justificacion = justificacion_de(datos.justificacion, se_aparta)
        costo_mxn = _centavos(candidato["costo_total_mxn"])
        requiere, motivos = requiere_aprobacion(
            costo_mxn, Decimal(str(recomendacion["umbral_aprobacion"])), sesion.fuera_de_limites
        )
        # También si queda pendiente: una propuesta que no podría adjudicarse no debe esperar.
        terminos = await _terminos(bd, evento, sesion, momento)
        fila = Adjudicacion(
            evento_id=evento.id,
            sesion_id=sesion.id,
            propuesta_por_id=usuario.id,
            propuesta_por_nombre=actor.nombre[:MAX_NOMBRE],
            propuesta_en=momento,
            recomendada_sesion_id=uuid.UUID(recomendacion["recomendado"]),
            se_aparta=se_aparta,
            justificacion=justificacion,
            costo_total=_centavos(candidato["costo_total"]),
            costo_total_mxn=costo_mxn,
            requiere_aprobacion=requiere,
            motivo_aprobacion=motivos,
            recomendacion=recomendacion,
            estado="pendiente" if requiere else "directa",
        )
        bd.add(fila)
        await bd.flush()
        detalle = _detalle(fila, sesion) | {
            "se_aparta": se_aparta,
            "requiere_aprobacion": requiere,
            "motivos": motivos,
        }
        if requiere:
            evento.estado = "pendiente_aprobacion"
            registrar(
                bd,
                "adjudicacion.propuesta",
                actor,
                evento_id=evento.id,
                sesion_id=sesion.id,
                detalle=detalle,
                fecha=momento,
            )
        else:
            _decidida(fila, actor, momento)
            _adjudicar(bd, evento, fila, sesion, terminos, actor, "directa")
            registrar(
                bd,
                "adjudicacion.directa",
                actor,
                evento_id=evento.id,
                sesion_id=sesion.id,
                detalle=detalle | {"contrato_folio": terminos.folio},
                fecha=momento,
            )
        return await _respuesta(bd, evento.id, recomendacion)


async def _pendiente(
    bd: AsyncSession, usuario: Usuario, evento_id: uuid.UUID
) -> tuple[Evento, Adjudicacion, SesionNegociacion]:
    """El evento (bloqueado) y su propuesta pendiente; decide otra persona que quien la hizo."""
    evento = await consultas.evento_o_404(bd, evento_id, bloquear=True)
    exigir_estado(evento, "pendiente_aprobacion")
    fila = await bd.scalar(
        select(Adjudicacion).where(
            Adjudicacion.evento_id == evento.id, Adjudicacion.estado == "pendiente"
        )
    )
    sesion = None if fila is None else await bd.get(SesionNegociacion, fila.sesion_id)
    if fila is None or sesion is None:
        raise RuntimeError("Un evento pendiente de aprobación siempre tiene su propuesta pendiente")
    if fila.propuesta_por_id == usuario.id:  # aunque tenga los dos roles
        raise prohibido(MISMA_PERSONA, "misma_persona")
    return evento, fila, sesion


async def aprobar(
    bd: AsyncSession, usuario: Usuario, evento_id: uuid.UUID, momento: datetime
) -> esquemas.Evaluacion:
    """El aprobador aprueba la propuesta guardada (sin consultar de nuevo a inteligencia)."""
    actor = de_usuario(usuario, "aprobador")
    async with bd.begin():
        evento, fila, sesion = await _pendiente(bd, usuario, evento_id)
        terminos = await _terminos(bd, evento, sesion, momento)
        fila.estado = "aprobada"
        _decidida(fila, actor, momento)
        _adjudicar(bd, evento, fila, sesion, terminos, actor, "aprobada")
        registrar(
            bd,
            "adjudicacion.aprobada",
            actor,
            evento_id=evento.id,
            sesion_id=sesion.id,
            detalle=_detalle(fila, sesion) | {"contrato_folio": terminos.folio},
            fecha=momento,
        )
        return await _respuesta(bd, evento.id, fila.recomendacion)


async def rechazar(
    bd: AsyncSession, usuario: Usuario, evento_id: uuid.UUID, motivo: str, momento: datetime
) -> esquemas.Evaluacion:
    """El aprobador rechaza la propuesta; el evento vuelve a evaluación y se puede proponer de
    nuevo. Responde sin recomendación: el comprador la consulta otra vez al volver a proponer."""
    actor = de_usuario(usuario, "aprobador")
    async with bd.begin():
        evento, fila, sesion = await _pendiente(bd, usuario, evento_id)
        fila.estado, fila.motivo_rechazo = "rechazada", motivo
        _decidida(fila, actor, momento)
        evento.estado = "en_evaluacion"
        registrar(
            bd,
            "adjudicacion.rechazada",
            actor,
            evento_id=evento.id,
            sesion_id=sesion.id,
            detalle=_detalle(fila, sesion) | {"motivo": motivo},
            fecha=momento,
        )
        return await _respuesta(bd, evento.id, None)


async def declarar_desierta(
    bd: AsyncSession, usuario: Usuario, evento_id: uuid.UUID, motivo: str, momento: datetime
) -> esquemas.Evaluacion:
    """El comprador da por desierta la negociación; las sesiones conservan su estado."""
    actor = de_usuario(usuario)
    async with bd.begin():
        evento = await consultas.evento_o_404(bd, evento_id, bloquear=True)
        exigir_estado(evento, "en_evaluacion")
        evento.estado, evento.motivo_desierta = "desierto", motivo
        registrar_evento(
            bd,
            Outbox,
            "negociacion.desierta",
            {
                "folio": evento.folio,
                "titulo": evento.titulo,
                "motivo": motivo,
                "actor": actor.para_evento(),
            },
        )
        registrar(
            bd,
            "evento.desierto",
            actor,
            evento_id=evento.id,
            detalle={"motivo": motivo},
            fecha=momento,
        )
        return await _respuesta(bd, evento.id, None)
