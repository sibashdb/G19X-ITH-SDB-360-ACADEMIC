"""Lo que consultan las rutas, calculado una vez por versión de los datos.

La puntuación de un proveedor depende de todos los demás (percentiles) y las alertas recorren todos
los contratos vigentes: el cálculo se hace completo y se guarda hasta que se aplique un evento, se
guarde la configuración, se promueva un modelo o cambie el día.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import sklearn
from sqlalchemy.ext.asyncio import AsyncSession

from inteligencia import consultas
from inteligencia.dominio.alertas import Alerta, ordenar, riesgo, sobreprecio, vencimiento
from inteligencia.dominio.contratos import ContratoInfo, Linea
from inteligencia.dominio.monedas import tipo_cambio_en
from inteligencia.dominio.precios import (
    Observacion,
    Posicion,
    Referencia,
    posicion,
    sumar_meses,
)
from inteligencia.dominio.puntuacion import (
    MESES_TENDENCIA,
    Mes,
    Pesos,
    Puntuacion,
    historial,
    puntuar,
)
from inteligencia.dominio.tablero import Tablero, calcular
from inteligencia.modelo import Consulta, ModeloPrecios, cargar_modelo
from inteligencia.modelos import (
    Configuracion,
    Contrato,
    Desempeno,
    ModeloBenchmark,
    Proveedor,
    Servicio,
)
from inteligencia.precio_justo import referencias

log = logging.getLogger(__name__)

SIN_NOMBRE = "Proveedor sin datos"  # el contrato llegó antes que su proveedor
CERO = Decimal("0.00")


@dataclass(frozen=True)
class LineaMercado:
    """Una línea de un contrato vigente frente al precio justo de su servicio."""

    contrato: ContratoInfo
    linea: Linea
    referencia: Referencia | None  # None: su servicio no tiene contratos recientes
    posicion: Posicion | None
    ahorro: Decimal  # en la moneda del contrato; 0.00 si no está sobre P75


@dataclass(frozen=True)
class Datos:
    """La copia local tal como se leyó de la base."""

    configuracion: Configuracion
    proveedores: list[Proveedor]
    servicios: list[Servicio]
    contratos: list[Contrato]
    tipos_cambio: dict[date, Decimal]
    desempeno: list[Desempeno]
    observaciones: list[Observacion]


def puntuacion_en(serie: Sequence[tuple[date, float]], fecha: date) -> float | None:
    return next((valor for mes, valor in serie if mes == fecha), None)


@dataclass(frozen=True)
class Contexto:
    hoy: date
    pesos: Pesos
    umbral: int
    tasa_inflacion: float
    modelo: ModeloPrecios | None
    proveedores: dict[str, Proveedor]  # por id, como texto
    servicios: dict[str, Servicio]  # por código
    contratos: list[ContratoInfo]
    tipos_cambio: dict[date, Decimal]
    por_categoria: dict[str, list[Observacion]]
    puntuaciones: dict[str, Puntuacion]
    desempeno: dict[str, list[Mes]]  # mensual de los proveedores puntuados, sin orden garantizado
    historial: dict[str, list[tuple[date, float]]]
    mercado: list[LineaMercado]
    alertas: list[Alerta]  # ordenadas por severidad y fecha
    tablero: Tablero

    def anterior(self, proveedor_id: str) -> float | None:
        """La puntuación de hace MESES_TENDENCIA meses; None si aún no tenía historia."""
        return puntuacion_en(
            self.historial.get(proveedor_id, []), sumar_meses(self.hoy, -MESES_TENDENCIA)
        )

    def tendencia(self, proveedor_id: str) -> float | None:
        actual = self.puntuaciones.get(proveedor_id)
        anterior = self.anterior(proveedor_id)
        return None if actual is None or anterior is None else actual.puntuacion - anterior


def _contrato(
    contrato: Contrato, proveedores: dict[str, Proveedor], servicios: dict[str, Servicio]
) -> ContratoInfo:
    proveedor = proveedores.get(str(contrato.proveedor_id))
    return ContratoInfo(
        id=str(contrato.id),
        folio=contrato.folio,
        proveedor_id=str(contrato.proveedor_id),
        proveedor=proveedor.nombre if proveedor is not None else SIN_NOMBRE,
        tipo=contrato.tipo,
        fecha_inicio=contrato.fecha_inicio,
        fecha_fin=contrato.fecha_fin,
        moneda=contrato.moneda,
        lineas=tuple(
            Linea(
                codigo=linea.codigo_servicio,
                servicio=(
                    servicios[linea.codigo_servicio].nombre
                    if linea.codigo_servicio in servicios
                    else linea.codigo_servicio
                ),
                categoria=linea.categoria,
                unidad=linea.unidad,
                cantidad=linea.cantidad,
                precio=linea.precio_unitario,
            )
            for linea in sorted(contrato.lineas, key=lambda linea: linea.codigo_servicio)
        ),
    )


def _meses(registros: Sequence[Desempeno]) -> dict[str, list[Mes]]:
    meses: dict[str, list[Mes]] = defaultdict(list)
    for r in registros:
        meses[str(r.proveedor_id)].append(
            Mes(
                r.periodo,
                sla=float(r.sla_cumplimiento_pct),
                resolucion=float(r.tiempo_resolucion_h),
                incidentes=float(r.incidentes_criticos),
                entregas=float(r.entregas_a_tiempo_pct),
                satisfaccion=float(r.satisfaccion),
            )
        )
    return meses


def construir(datos: Datos, modelo: ModeloPrecios | None, hoy: date) -> Contexto:
    config = datos.configuracion
    pesos = Pesos(
        config.peso_sla,
        config.peso_resolucion,
        config.peso_incidentes,
        config.peso_entregas,
        config.peso_satisfaccion,
    )
    tasa = float(config.inflacion_anual) / 100
    proveedores = {str(p.id): p for p in datos.proveedores}
    servicios = {s.codigo: s for s in datos.servicios}
    contratos = [_contrato(c, proveedores, servicios) for c in datos.contratos]
    por_categoria: dict[str, list[Observacion]] = defaultdict(list)
    for observacion in datos.observaciones:
        por_categoria[observacion.categoria].append(observacion)

    # Solo se puntúa a los proveedores de la copia: su categoría principal decide contra quién se
    # comparan, y su desempeño pudo llegar antes que ellos.
    desempeno = {
        pid: meses
        for pid, meses in _meses(datos.desempeno).items()
        if pid in proveedores and proveedores[pid].categorias
    }
    categorias = {pid: proveedores[pid].categorias[0] for pid in desempeno}
    puntuaciones = puntuar(desempeno, categorias, pesos, hoy)
    series = historial(desempeno, categorias, pesos, hoy)
    hace_tres = sumar_meses(hoy, -MESES_TENDENCIA)

    vigentes = [c for c in contratos if c.vigente(hoy)]
    pares = [(c, linea) for c in vigentes for linea in c.lineas]
    consultas_mercado = []
    for c, linea in pares:
        proveedor = proveedores.get(c.proveedor_id)
        consultas_mercado.append(
            Consulta(
                linea.codigo,
                linea.categoria,
                c.moneda,
                float(linea.cantidad),
                c.plazo_meses,
                c.fecha_inicio,
                proveedor.tamano if proveedor is not None else None,
                c.tipo,
            )
        )
    avisos = [a for c in vigentes if (a := vencimiento(c, hoy)) is not None]
    mercado = []
    for (c, linea), referencia in zip(
        pares, referencias(consultas_mercado, por_categoria, modelo, tasa), strict=True
    ):
        alerta = sobreprecio(c, linea, referencia.banda, hoy) if referencia is not None else None
        if alerta is not None:
            avisos.append(alerta)
        mercado.append(
            LineaMercado(
                c,
                linea,
                referencia,
                posicion(float(linea.precio), referencia.banda) if referencia is not None else None,
                alerta.ahorro_potencial
                if alerta is not None and alerta.ahorro_potencial is not None
                else CERO,
            )
        )
    for pid, puntuacion in puntuaciones.items():
        proveedor = proveedores[pid]
        if not proveedor.activo:
            continue
        alerta = riesgo(
            pid,
            proveedor.nombre,
            puntuacion.puntuacion,
            puntuacion_en(series.get(pid, []), hace_tres),
            config.umbral_riesgo,
            hoy,
        )
        if alerta is not None:
            avisos.append(alerta)
    alertas = ordenar(avisos, tipo_cambio_en(datos.tipos_cambio, hoy))
    activos = {pid for pid, p in proveedores.items() if p.activo}
    tablero = calcular(
        contratos,
        datos.tipos_cambio,
        {pid: p.puntuacion for pid, p in puntuaciones.items() if pid in activos},
        {pid: p.nombre for pid, p in proveedores.items()},
        len(activos),
        alertas,
        hoy,
    )
    return Contexto(
        hoy=hoy,
        pesos=pesos,
        umbral=config.umbral_riesgo,
        tasa_inflacion=tasa,
        modelo=modelo,
        proveedores=proveedores,
        servicios=servicios,
        contratos=contratos,
        tipos_cambio=datos.tipos_cambio,
        por_categoria=dict(por_categoria),
        puntuaciones=puntuaciones,
        desempeno=desempeno,
        historial=series,
        mercado=mercado,
        alertas=alertas,
        tablero=tablero,
    )


def _cargar_modelo(registro: ModeloBenchmark | None) -> ModeloPrecios | None:
    if registro is None or registro.artefacto is None:
        return None
    try:
        modelo = cargar_modelo(Path(registro.artefacto))
    except Exception:
        # El volumen de modelos se perdió o el archivo está dañado: la línea base sigue sirviendo.
        log.exception(
            "No se pudo cargar el modelo de precios v%s; se usa la línea base", registro.version
        )
        return None
    guardada = getattr(modelo, "version_sklearn", None)
    if guardada != sklearn.__version__:
        # Tras actualizar scikit-learn, el modelo guardado puede fallar o predecir distinto.
        log.warning(
            "El modelo de precios v%s se entrenó con la versión %s de scikit-learn y está "
            "instalada la %s; se usa la línea base hasta reentrenarlo",
            registro.version,
            guardada or "desconocida",
            sklearn.__version__,
        )
        return None
    return modelo


async def armar(sesion: AsyncSession, hoy: date) -> Contexto:
    registro = await consultas.modelo_activo(sesion)
    datos = Datos(
        configuracion=await consultas.configuracion(sesion),
        proveedores=await consultas.proveedores(sesion),
        servicios=await consultas.servicios(sesion),
        contratos=await consultas.contratos(sesion),
        tipos_cambio=await consultas.tipos_cambio(sesion),
        desempeno=await consultas.desempeno(sesion),
        observaciones=await consultas.observaciones(sesion),
    )
    modelo = await asyncio.to_thread(_cargar_modelo, registro)
    # Fuera del bucle de eventos: con el dataset por defecto el cálculo tarda alrededor de un
    # segundo, y mientras tanto el servicio debe seguir atendiendo la salud y la cola.
    return await asyncio.to_thread(construir, datos, modelo, hoy)


class CacheContexto:
    """El último Contexto; se rehace cuando cambian el día o `consultas.clave_datos`."""

    def __init__(self) -> None:
        self._candado = asyncio.Lock()
        self._clave: tuple[object, ...] | None = None
        self._contexto: Contexto | None = None

    async def obtener(self, sesion: AsyncSession, hoy: date) -> Contexto:
        version = await consultas.clave_datos(sesion)
        clave = (hoy, *version)
        # Varias consultas a la vez esperan un solo cálculo en lugar de repetirlo.
        async with self._candado:
            if self._contexto is None or clave != self._clave:
                self._contexto = await armar(sesion, hoy)
                self._clave = clave
            return self._contexto
