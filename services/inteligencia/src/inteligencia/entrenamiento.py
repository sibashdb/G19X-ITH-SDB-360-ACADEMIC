"""Entrenamiento del modelo de precios: a pedido del administrador o automático.

Nunca corre más de uno a la vez. El automático espera a acumular MIN_LINEAS_NUEVAS líneas de
contrato desde el último entrenamiento y a que la última haya llegado hace ESPERA_TRAS_ULTIMA_S o
más, para no entrenar a la mitad de una importación.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from comun.outbox import registrar_evento
from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inteligencia import consultas
from inteligencia.modelo import DatosInsuficientes, entrenar, guardar_modelo
from inteligencia.modelos import Contrato, LineaContrato, ModeloBenchmark, Outbox

log = logging.getLogger(__name__)

ACTOR_AUTOMATICO: dict[str, str | None] = {"id": None, "nombre": "Sistema (automático)"}
MIN_LINEAS_NUEVAS = 50
ESPERA_TRAS_ULTIMA_S = 30
INTERVALO_REVISION_S = 60
ERROR_INTERNO = "El entrenamiento falló por un error interno; revise los registros del servicio."


def _metrica(valor: float, decimales: int = 6) -> Decimal:
    return Decimal(f"{valor:.{decimales}f}")


class Entrenador:
    def __init__(
        self,
        fabrica: async_sessionmaker[AsyncSession],
        directorio: Path,
        ahora: Callable[[], datetime] | None = None,
    ) -> None:
        self._fabrica = fabrica
        self._directorio = directorio
        self._ahora = ahora or (lambda: datetime.now(UTC))
        self._en_curso = False
        self._tarea: asyncio.Task[None] | None = None
        self._ultimo_error: str | None = None

    @property
    def entrenando(self) -> bool:
        return self._en_curso

    @property
    def ultimo_error(self) -> str | None:
        """Por qué falló el último entrenamiento; None si terminó bien o no ha corrido ninguno."""
        return self._ultimo_error

    def iniciar(self, origen: str, actor: dict[str, str | None]) -> bool:
        """Lanza un entrenamiento en segundo plano; False si ya hay uno en curso."""
        if self._en_curso:
            return False
        self._ultimo_error = None
        self._en_curso = True  # antes de crear la tarea: dos pedidos seguidos no lanzan dos
        self._tarea = asyncio.create_task(self._entrenar(origen, actor))
        return True

    async def esperar(self) -> None:
        if self._tarea is not None:
            await self._tarea

    async def _entrenar(self, origen: str, actor: dict[str, str | None]) -> None:
        try:
            async with self._fabrica() as sesion:
                observaciones = await consultas.observaciones(sesion)
                tasa = float((await consultas.configuracion(sesion)).inflacion_anual) / 100
                ultima = await sesion.scalar(select(func.max(ModeloBenchmark.version)))
            version = (ultima or 0) + 1
            resultado = await asyncio.to_thread(entrenar, observaciones, tasa, version)
            artefacto = None
            if resultado.modelo is not None:
                ruta = self._directorio / f"modelo-v{version}.joblib"
                await asyncio.to_thread(guardar_modelo, resultado.modelo, ruta)
                artefacto = str(ruta)
            async with self._fabrica() as sesion, sesion.begin():
                sesion.add(
                    ModeloBenchmark(
                        version=version,
                        entrenado_en=self._ahora(),
                        origen=origen,
                        actor_nombre=str(actor["nombre"]),
                        observaciones=resultado.observaciones,
                        datos_hasta=resultado.datos_hasta,
                        mape=_metrica(resultado.mape),
                        mape_linea_base=_metrica(resultado.mape_linea_base),
                        cobertura=_metrica(resultado.cobertura),
                        pinball=_metrica(resultado.pinball),
                        promovido=resultado.promovido,
                        artefacto=artefacto,
                    )
                )
                registrar_evento(
                    sesion,
                    Outbox,
                    "modelo.entrenado",
                    {
                        "version": version,
                        "mape": round(resultado.mape, 6),
                        "mape_linea_base": round(resultado.mape_linea_base, 6),
                        "cobertura": round(resultado.cobertura, 6),
                        "promovido": resultado.promovido,
                        "origen": origen,
                        "actor": actor,
                    },
                )
            log.info(
                "Modelo de precios v%s: MAPE %.4f (línea base %.4f), promovido: %s",
                version,
                resultado.mape,
                resultado.mape_linea_base,
                resultado.promovido,
            )
        except DatosInsuficientes as exc:
            log.warning("No se entrenó el modelo de precios: %s", exc)
            self._ultimo_error = f"No hay datos suficientes para entrenar. {exc}"
        except Exception:
            log.exception("Falló el entrenamiento del modelo de precios")
            self._ultimo_error = ERROR_INTERNO
        finally:
            self._en_curso = False

    async def revisar_automatico(self) -> bool:
        """Lanza un entrenamiento automático si toca; True si lo lanzó."""
        if self._en_curso:
            return False
        async with self._fabrica() as sesion:
            ultimo = await sesion.scalar(select(func.max(ModeloBenchmark.entrenado_en)))
            nuevas, mas_reciente = (
                await sesion.execute(
                    select(func.count(), func.max(Contrato.recibido_en))
                    .select_from(LineaContrato)
                    .join(Contrato, LineaContrato.contrato_id == Contrato.id)
                    .where(Contrato.recibido_en > ultimo if ultimo is not None else true())
                )
            ).one()
        if nuevas < MIN_LINEAS_NUEVAS or mas_reciente is None:
            return False
        if (self._ahora() - mas_reciente).total_seconds() < ESPERA_TRAS_ULTIMA_S:
            return False
        return self.iniciar("automatico", ACTOR_AUTOMATICO)

    async def ejecutar_periodicamente(self, intervalo: float = INTERVALO_REVISION_S) -> None:
        # ponytail: si el entrenamiento falla siempre (p. ej. pocos datos), se reintenta cada
        # `intervalo`; el motivo queda en `ultimo_error` y Configuración lo muestra.
        while True:
            try:
                await self.revisar_automatico()
            except Exception:
                log.exception("No se pudo revisar si hay que reentrenar el modelo")
            await asyncio.sleep(intervalo)
