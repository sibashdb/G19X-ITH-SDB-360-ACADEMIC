import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from negociacion import modelos  # noqa: F401
from negociacion.db import Base
from negociacion.modelos import Adjudicacion, Evento, SesionNegociacion
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integracion
BITACORA = (
    "INSERT INTO bitacora (id, fecha, actor_tipo, actor_nombre, accion, detalle) "
    "VALUES (gen_random_uuid(), now(), 'sistema', 'Sistema', 'prueba', '{}')"
)


def _diferencias(conexion: Connection) -> list[object]:
    return list(compare_metadata(MigrationContext.configure(conexion), Base.metadata))


async def test_modelos_y_migraciones_coinciden(urls_bd: tuple[str, str]) -> None:
    motor = create_async_engine(urls_bd[0], poolclass=NullPool)
    async with motor.connect() as conexion:
        diferencias = await conexion.run_sync(_diferencias)
    await motor.dispose()
    assert diferencias == []


async def test_la_aplicacion_usa_las_secuencias(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica() as bd:
        assert await bd.scalar(text("SELECT nextval('folio_evento')")) == 1
        assert await bd.scalar(text("SELECT nextval('orden')")) >= 1


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE bitacora SET accion = 'otra'",
        "DELETE FROM bitacora",
        "UPDATE mensaje SET texto = 'otro'",
        "DELETE FROM mensaje",
        "UPDATE oferta SET valida = false",
        "DELETE FROM oferta",
        "DELETE FROM evento",
        "DELETE FROM sesion",
        "DELETE FROM adjudicacion",
    ],
)
async def test_la_aplicacion_no_reescribe_el_historial(
    fabrica: async_sessionmaker[AsyncSession], sentencia: str
) -> None:
    async with fabrica() as bd:
        await bd.execute(text(BITACORA))
        await bd.commit()
    async with fabrica() as bd:
        with pytest.raises(DBAPIError, match="permission denied"):
            await bd.execute(text(sentencia))


async def _guardar_propuesta(fabrica: async_sessionmaker[AsyncSession], **cambios: Any) -> None:
    """Guarda un evento con una sesión y una propuesta de adjudicación (con `cambios`)."""
    ahora = datetime(2026, 10, 16, 15, tzinfo=UTC)
    evento = Evento(
        id=uuid.uuid4(),
        folio="NEG-2026-0001",
        tipo="compra",
        titulo="Licencias",
        moneda="MXN",
        plazo_meses=12,
        fecha_limite=ahora,
        creado_por_id="comprador-1",
        creado_por_nombre="Ana",
    )
    sesion = SesionNegociacion(
        id=uuid.uuid4(),
        evento_id=evento.id,
        proveedor_id=uuid.uuid4(),
        proveedor_nombre="Nube Norte",
        destinatario="ventas@nubenorte.example",
    )
    datos: dict[str, Any] = {
        "evento_id": evento.id,
        "sesion_id": sesion.id,
        "recomendada_sesion_id": sesion.id,
        "propuesta_por_id": "comprador-1",
        "propuesta_por_nombre": "Ana",
        "se_aparta": False,
        "costo_total": Decimal("600000.00"),
        "costo_total_mxn": Decimal("600000.00"),
        "requiere_aprobacion": True,
        "motivo_aprobacion": ["umbral"],
        "recomendacion": {"recomendado": str(sesion.id)},
        "estado": "pendiente",
    }
    async with fabrica() as bd, bd.begin():
        bd.add(evento)
        await bd.flush()
        bd.add(sesion)
        await bd.flush()
        bd.add(Adjudicacion(**(datos | cambios)))


async def test_la_aplicacion_no_reescribe_la_propuesta(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    await _guardar_propuesta(
        fabrica,
        se_aparta=True,
        justificacion="Mejor SLA",
        motivo_aprobacion=["umbral", "fuera_de_limites"],
    )
    async with fabrica() as bd:
        with pytest.raises(DBAPIError, match="permission denied"):
            await bd.execute(text("UPDATE adjudicacion SET justificacion = 'x'"))
    async with fabrica() as bd, bd.begin():
        resultado = await bd.execute(text("UPDATE adjudicacion SET estado = 'aprobada'"))
        assert resultado.rowcount == 1


@pytest.mark.parametrize(
    "cambios",
    [
        {"se_aparta": True, "justificacion": None},
        {"motivo_aprobacion": ["otro"]},
        {"estado": "olvidada"},
    ],
)
async def test_una_propuesta_invalida_no_se_guarda(
    fabrica: async_sessionmaker[AsyncSession], cambios: dict[str, Any]
) -> None:
    with pytest.raises(IntegrityError, match="ck_adjudicacion_"):
        await _guardar_propuesta(fabrica, **cambios)


async def test_los_estados_y_el_actor_nuevos_se_aceptan(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    await _guardar_propuesta(fabrica)
    for estado in ("pendiente_aprobacion", "adjudicado", "desierto"):
        async with fabrica() as bd, bd.begin():
            await bd.execute(text("UPDATE evento SET estado = :estado"), {"estado": estado})
    async with fabrica() as bd, bd.begin():
        await bd.execute(text("UPDATE evento SET motivo_desierta = 'Sin ofertas viables'"))
        await bd.execute(text("UPDATE sesion SET resultado_avisado_en = now()"))
        await bd.execute(
            text(
                "INSERT INTO bitacora (id, fecha, actor_tipo, actor_nombre, accion, detalle) "
                "VALUES (gen_random_uuid(), now(), 'aprobador', 'Rosa', 'prueba', '{}')"
            )
        )
