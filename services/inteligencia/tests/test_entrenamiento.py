from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from generador.modelo import DatosSinteticos, generar
from inteligencia import entrenamiento
from inteligencia.entrenamiento import Entrenador
from inteligencia.modelo import cargar_modelo
from inteligencia.modelos import ModeloBenchmark, Outbox
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integracion

Fabrica = async_sessionmaker[AsyncSession]
Cargar = Callable[[DatosSinteticos], Awaitable[None]]
ADMIN: dict[str, str | None] = {"id": "admin-1", "nombre": "admin1"}


async def _registros(fabrica: Fabrica) -> list[ModeloBenchmark]:
    async with fabrica() as sesion:
        return list((await sesion.scalars(select(ModeloBenchmark))).all())


async def test_entrenar_registra_el_modelo_y_publica_el_evento(
    fabrica: Fabrica, cargar: Cargar, tmp_path: Path
) -> None:
    await cargar(generar(42, n_proveedores=15))
    entrenador = Entrenador(fabrica, tmp_path)
    assert entrenador.iniciar("manual", ADMIN)
    assert entrenador.entrenando
    assert not entrenador.iniciar("manual", ADMIN)  # un segundo pedido mientras corre
    await entrenador.esperar()
    assert not entrenador.entrenando
    assert entrenador.ultimo_error is None

    [registro] = await _registros(fabrica)
    assert (registro.version, registro.origen, registro.actor_nombre) == (1, "manual", "admin1")
    if registro.promovido:
        assert registro.artefacto is not None
        assert cargar_modelo(Path(registro.artefacto)).version == 1
    else:
        assert registro.artefacto is None
    async with fabrica() as sesion:
        [evento] = (
            await sesion.scalars(select(Outbox).where(Outbox.tipo == "modelo.entrenado"))
        ).all()
    assert set(evento.payload) == {
        "version",
        "mape",
        "mape_linea_base",
        "cobertura",
        "promovido",
        "origen",
        "actor",
    }
    assert (evento.payload["version"], evento.payload["actor"]) == (1, ADMIN)


async def test_un_entrenamiento_fallido_libera_el_candado(
    fabrica: Fabrica, cargar: Cargar, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await cargar(generar(42, n_proveedores=15))

    def fallar(*_argumentos: object) -> None:
        raise RuntimeError("se acabó la memoria")

    monkeypatch.setattr(entrenamiento, "entrenar", fallar)
    entrenador = Entrenador(fabrica, tmp_path)
    assert entrenador.iniciar("manual", ADMIN)
    await entrenador.esperar()
    assert not entrenador.entrenando
    assert entrenador.ultimo_error == entrenamiento.ERROR_INTERNO
    assert await _registros(fabrica) == []
    assert entrenador.iniciar("manual", ADMIN)  # se puede volver a intentar
    assert entrenador.ultimo_error is None  # un intento nuevo borra el error anterior
    await entrenador.esperar()


async def test_sin_datos_no_registra_nada(
    fabrica: Fabrica, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    entrenador = Entrenador(fabrica, tmp_path)
    assert entrenador.iniciar("manual", ADMIN)
    await entrenador.esperar()
    assert await _registros(fabrica) == []
    assert "No se entrenó el modelo de precios" in caplog.text
    assert entrenador.ultimo_error == (
        "No hay datos suficientes para entrenar. Solo hay 0 líneas de contrato."
    )


async def test_el_automatico_espera_a_que_termine_la_importacion(
    fabrica: Fabrica, cargar: Cargar, tmp_path: Path
) -> None:
    await cargar(generar(42, n_proveedores=15))
    reloj = [datetime.now(UTC)]
    entrenador = Entrenador(fabrica, tmp_path, ahora=lambda: reloj[0])
    assert not await entrenador.revisar_automatico()  # la última línea llegó hace menos de 30 s
    reloj[0] += timedelta(seconds=31)
    assert await entrenador.revisar_automatico()
    await entrenador.esperar()
    [registro] = await _registros(fabrica)
    assert (registro.origen, registro.actor_nombre) == ("automatico", "Sistema (automático)")
    reloj[0] = datetime.now(UTC) + timedelta(minutes=5)
    assert not await entrenador.revisar_automatico()  # no hay líneas nuevas desde entonces
