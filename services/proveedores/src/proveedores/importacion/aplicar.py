"""Aplica en la BD los CSV validados y registra los eventos en el outbox. Todo o nada."""

import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from comun.errores import ErrorDominio
from comun.outbox import registrar_evento
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from proveedores.importacion.esquemas import (
    FilaContrato,
    FilaDesempeno,
    FilaProveedor,
    FilaServicio,
    FilaTipoCambio,
)
from proveedores.importacion.parseo import ErrorFila, agrupar_contratos, duplicados, leer_csv
from proveedores.modelos import (
    Contrato,
    LineaContrato,
    Outbox,
    Proveedor,
    RegistroDesempeno,
    ServicioCatalogo,
    TipoCambio,
)

MAX_ERRORES_REPORTADOS = 200


class Entidad(StrEnum):
    SERVICIOS = "servicios"
    PROVEEDORES = "proveedores"
    TIPO_CAMBIO = "tipo_cambio"
    CONTRATOS = "contratos"
    DESEMPENO = "desempeno"


# Contratos y desempeño referencian proveedores y servicios: se cargan después.
ORDEN_CARGA = (
    Entidad.SERVICIOS,
    Entidad.PROVEEDORES,
    Entidad.TIPO_CAMBIO,
    Entidad.CONTRATOS,
    Entidad.DESEMPENO,
)


@dataclass(frozen=True)
class ResumenImportacion:
    """`filas`: registros del CSV · `registros`: entidades creadas o actualizadas ·
    `omitidos`: contratos que ya existían (los contratos no se modifican) · `eventos`."""

    entidad: str
    filas: int
    registros: int
    omitidos: int
    eventos: int


ACTOR_LINEA_DE_COMANDOS: dict[str, str | None] = {
    "id": None,
    "nombre": "Sistema (línea de comandos)",
}


def registrar_importacion(
    sesion: AsyncSession, resumen: ResumenImportacion, actor: dict[str, str | None]
) -> None:
    """Deja en el outbox, en la transacción de los datos, que la importación se completó."""
    registrar_evento(
        sesion,
        Outbox,
        "importacion.completada",
        {
            "entidad": resumen.entidad,
            "filas": resumen.filas,
            "registros": resumen.registros,
            "omitidos": resumen.omitidos,
            "actor": actor,
        },
    )


def registrar_rechazo(
    sesion: AsyncSession, entidad: str, total_errores: int, actor: dict[str, str | None]
) -> None:
    """La transacción de los datos se revirtió: el intento se registra en una propia."""
    registrar_evento(
        sesion,
        Outbox,
        "importacion.rechazada",
        {"entidad": entidad, "errores": total_errores, "actor": actor},
    )


class ErrorImportacion(ErrorDominio):
    def __init__(self, errores: list[ErrorFila]) -> None:
        super().__init__(
            422,
            "Archivo con errores",
            f"Se encontraron {len(errores)} error(es); no se importó ninguna fila.",
            {
                "errores": [asdict(e) for e in errores[:MAX_ERRORES_REPORTADOS]],
                "total_errores": len(errores),
            },
        )
        self.errores = errores


def _exigir_sin_errores(errores: list[ErrorFila]) -> None:
    if errores:
        raise ErrorImportacion(sorted(errores, key=lambda e: (e.fila, e.campo)))


async def _ids_proveedores(sesion: AsyncSession) -> dict[str, uuid.UUID]:
    filas = await sesion.execute(select(Proveedor.rfc, Proveedor.id))
    return dict(filas.all())


async def importar(sesion: AsyncSession, entidad: Entidad, contenido: bytes) -> ResumenImportacion:
    match entidad:
        case Entidad.SERVICIOS:
            return await _servicios(sesion, contenido)
        case Entidad.PROVEEDORES:
            return await _proveedores(sesion, contenido)
        case Entidad.TIPO_CAMBIO:
            return await _tipo_cambio(sesion, contenido)
        case Entidad.CONTRATOS:
            return await _contratos(sesion, contenido)
        case Entidad.DESEMPENO:
            return await _desempeno(sesion, contenido)


async def _servicios(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaServicio)
    _exigir_sin_errores(resultado.errores + duplicados(resultado, lambda f: f.codigo, "codigo"))
    datos = [fila.model_dump() for _, fila in resultado.filas]
    if datos:
        consulta = insert(ServicioCatalogo)
        consulta = consulta.on_conflict_do_update(
            index_elements=[ServicioCatalogo.codigo],
            set_={c: consulta.excluded[c] for c in ("nombre", "categoria", "unidad", "moneda")},
        )
        await sesion.execute(consulta, datos)
    return ResumenImportacion(Entidad.SERVICIOS, len(datos), len(datos), 0, 0)


async def _proveedores(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaProveedor)
    _exigir_sin_errores(resultado.errores + duplicados(resultado, lambda f: f.rfc, "rfc"))
    datos = [fila.model_dump() for _, fila in resultado.filas]
    if not datos:
        return ResumenImportacion(Entidad.PROVEEDORES, 0, 0, 0, 0)
    columnas = ("nombre", "tamano", "categorias", "contacto_nombre", "contacto_email", "activo")
    insercion = insert(Proveedor)
    consulta = insercion.on_conflict_do_update(
        index_elements=[Proveedor.rfc],
        set_={
            **{c: insercion.excluded[c] for c in columnas},
            "actualizado_en": func.now(),
        },
    ).returning(Proveedor)
    proveedores = (
        await sesion.scalars(consulta, datos, execution_options={"populate_existing": True})
    ).all()
    for proveedor in proveedores:
        registrar_evento(
            sesion,
            Outbox,
            "proveedor.actualizado",
            {"id": proveedor.id, "rfc": proveedor.rfc}
            | {c: getattr(proveedor, c) for c in columnas},
        )
    return ResumenImportacion(
        Entidad.PROVEEDORES, len(datos), len(proveedores), 0, len(proveedores)
    )


async def _tipo_cambio(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaTipoCambio)
    _exigir_sin_errores(resultado.errores + duplicados(resultado, lambda f: f.periodo, "periodo"))
    datos = [fila.model_dump() for _, fila in resultado.filas]
    if datos:
        consulta = insert(TipoCambio)
        consulta = consulta.on_conflict_do_update(
            index_elements=[TipoCambio.periodo], set_={"usd_mxn": consulta.excluded.usd_mxn}
        )
        await sesion.execute(consulta, datos)
    return ResumenImportacion(Entidad.TIPO_CAMBIO, len(datos), len(datos), 0, 0)


async def _desempeno(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaDesempeno)
    ids = await _ids_proveedores(sesion)
    errores = resultado.errores + duplicados(
        resultado, lambda f: (f.rfc_proveedor, f.periodo), "periodo"
    )
    errores += [
        ErrorFila(numero, "rfc_proveedor", f"Proveedor no registrado: {fila.rfc_proveedor}")
        for numero, fila in resultado.filas
        if fila.rfc_proveedor not in ids
    ]
    _exigir_sin_errores(errores)
    datos = [
        {"proveedor_id": ids[fila.rfc_proveedor]} | fila.model_dump(exclude={"rfc_proveedor"})
        for _, fila in resultado.filas
    ]
    if datos:
        metricas = (
            "sla_cumplimiento_pct",
            "tiempo_resolucion_h",
            "incidentes_criticos",
            "entregas_a_tiempo_pct",
            "satisfaccion",
        )
        consulta = insert(RegistroDesempeno)
        consulta = consulta.on_conflict_do_update(
            index_elements=[RegistroDesempeno.proveedor_id, RegistroDesempeno.periodo],
            set_={c: consulta.excluded[c] for c in metricas},
        )
        await sesion.execute(consulta, datos)
    for fila_datos in datos:
        registrar_evento(sesion, Outbox, "desempeno.registrado", fila_datos)
    return ResumenImportacion(Entidad.DESEMPENO, len(datos), len(datos), 0, len(datos))


async def _contratos(sesion: AsyncSession, contenido: bytes) -> ResumenImportacion:
    resultado = leer_csv(contenido, FilaContrato)
    grupos, errores = agrupar_contratos(resultado.filas)
    errores = resultado.errores + errores
    ids = await _ids_proveedores(sesion)
    servicios = {s.codigo: s for s in (await sesion.scalars(select(ServicioCatalogo))).all()}
    for numero, fila in resultado.filas:
        if fila.rfc_proveedor not in ids:
            errores.append(
                ErrorFila(numero, "rfc_proveedor", f"Proveedor no registrado: {fila.rfc_proveedor}")
            )
        servicio = servicios.get(fila.codigo_servicio)
        if servicio is None:
            errores.append(
                ErrorFila(
                    numero, "codigo_servicio", f"Servicio no registrado: {fila.codigo_servicio}"
                )
            )
        elif servicio.moneda != fila.moneda:
            errores.append(
                ErrorFila(
                    numero,
                    "moneda",
                    f"Debe coincidir con la moneda del servicio ({servicio.moneda})",
                )
            )
    _exigir_sin_errores(errores)

    # ponytail: carga todos los folios existentes; filtrar por lote si llegan a cientos de miles.
    existentes = set((await sesion.scalars(select(Contrato.folio))).all())
    nuevos = 0
    for folio, lineas in grupos.items():
        if folio in existentes:
            continue
        cabecera = lineas[0][1]
        contrato = Contrato(
            id=uuid.uuid4(),
            folio=folio,
            proveedor_id=ids[cabecera.rfc_proveedor],
            tipo=cabecera.tipo,
            fecha_inicio=cabecera.fecha_inicio,
            fecha_fin=cabecera.fecha_fin,
            moneda=cabecera.moneda,
            plazo_pago_dias=cabecera.plazo_pago_dias,
            sla_disponibilidad=cabecera.sla_disponibilidad,
            tope_aumento_pct=cabecera.tope_aumento_pct,
            cuota_implementacion=cabecera.cuota_implementacion,
            lineas=[
                LineaContrato(
                    servicio_id=servicios[fila.codigo_servicio].id,
                    cantidad=fila.cantidad,
                    precio_unitario=fila.precio_unitario,
                )
                for _, fila in lineas
            ],
        )
        sesion.add(contrato)
        registrar_evento(
            sesion,
            Outbox,
            "contrato.registrado",
            _payload_contrato(contrato, cabecera, lineas, servicios),
        )
        nuevos += 1
    return ResumenImportacion(
        Entidad.CONTRATOS, len(resultado.filas), nuevos, len(grupos) - nuevos, nuevos
    )


def _payload_contrato(
    contrato: Contrato,
    cabecera: FilaContrato,
    lineas: list[tuple[int, FilaContrato]],
    servicios: dict[str, ServicioCatalogo],
) -> dict[str, Any]:
    return {
        "id": contrato.id,
        "proveedor_id": contrato.proveedor_id,
        **cabecera.model_dump(exclude={"codigo_servicio", "cantidad", "precio_unitario"}),
        "lineas": [
            {
                "codigo_servicio": fila.codigo_servicio,
                "nombre_servicio": servicios[fila.codigo_servicio].nombre,
                "categoria": servicios[fila.codigo_servicio].categoria,
                "unidad": servicios[fila.codigo_servicio].unidad,
                "cantidad": fila.cantidad,
                "precio_unitario": fila.precio_unitario,
            }
            for _, fila in lineas
        ],
    }
