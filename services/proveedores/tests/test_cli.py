from pathlib import Path

import pytest
from generador.modelo import generar
from generador.salida import escribir
from proveedores.importacion.cli import ErrorCarga, _principal, cargar_carpeta
from proveedores.modelos import Contrato, Outbox, Proveedor
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

FILA_INVALIDA = "C-999999,NO-ES-RFC,nuevo,2024-01-01,2023-01-01,MXN,30,,,0,SOP-N2-TK,1,1\n"


def _carpeta_con_contratos_invalidos(carpeta: Path) -> None:
    escribir(generar(21, n_proveedores=3), carpeta)
    with (carpeta / "contratos.csv").open("a", encoding="utf-8", newline="") as archivo:
        archivo.write(FILA_INVALIDA)


async def test_carpeta_incompleta_falla_antes_de_tocar_la_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "servicios.csv").write_text("codigo\n", encoding="utf-8")
    assert await _principal(tmp_path) == 1
    salida = capsys.readouterr()
    assert salida.out == ""
    assert salida.err == (
        f"Faltan archivos en {tmp_path}: "
        "proveedores.csv, tipo_cambio.csv, contratos.csv, desempeno.csv\n"
    )


@pytest.mark.integracion
async def test_error_en_un_archivo_indica_cual_fue_y_que_ya_se_importo(
    fabrica: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    _carpeta_con_contratos_invalidos(tmp_path)
    with pytest.raises(ErrorCarga) as error:
        await cargar_carpeta(fabrica, tmp_path)
    assert error.value.entidad == "contratos"
    assert error.value.importadas == ["servicios", "proveedores", "tipo_cambio"]
    async with fabrica() as sesion:
        assert await sesion.scalar(select(func.count()).select_from(Proveedor)) == 3
        assert await sesion.scalar(select(func.count()).select_from(Contrato)) == 0


@pytest.mark.integracion
async def test_la_carga_registra_cada_archivo_con_el_actor_de_linea_de_comandos(
    fabrica: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    _carpeta_con_contratos_invalidos(tmp_path)
    with pytest.raises(ErrorCarga):
        await cargar_carpeta(fabrica, tmp_path)
    async with fabrica() as sesion:
        filas = list(
            (
                await sesion.scalars(
                    select(Outbox)
                    .where(Outbox.tipo.startswith("importacion."))
                    .order_by(Outbox.ocurrido_en)
                )
            ).all()
        )
    assert [(f.tipo, f.payload["entidad"]) for f in filas] == [
        ("importacion.completada", "servicios"),
        ("importacion.completada", "proveedores"),
        ("importacion.completada", "tipo_cambio"),
        ("importacion.rechazada", "contratos"),
    ]
    assert {f.payload["actor"]["nombre"] for f in filas} == {"Sistema (línea de comandos)"}
    assert filas[-1].payload["errores"] == 1


# `fabrica` fija DATABASE_URL (contenedor de la sesión) y limpia las tablas al terminar.
@pytest.mark.integracion
@pytest.mark.usefixtures("fabrica")
async def test_la_cli_nombra_el_archivo_que_fallo_y_los_ya_importados(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _carpeta_con_contratos_invalidos(tmp_path)
    assert await _principal(tmp_path) == 1
    lineas = capsys.readouterr().err.splitlines()
    assert lineas[0] == (
        "Error en contratos.csv: Se encontraron 1 error(es); no se importó ninguna fila. "
        "Ya se importaron: servicios, proveedores, tipo_cambio."
    )
    assert all(linea.startswith("  contratos.csv, fila ") for linea in lineas[1:])
    assert len(lineas) == 2


@pytest.mark.integracion
@pytest.mark.usefixtures("fabrica")
async def test_la_cli_imprime_un_resumen_por_entidad(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    datos = generar(21, n_proveedores=3)
    escribir(datos, tmp_path)
    assert await _principal(tmp_path) == 0
    salida = capsys.readouterr()
    assert salida.err == ""
    folios = len({fila["folio"] for fila in datos.contratos})
    assert salida.out.splitlines() == [
        "servicios: 40 registros, 0 omitidos, 40 eventos",
        "proveedores: 3 registros, 0 omitidos, 3 eventos",
        f"tipo_cambio: {len(datos.tipo_cambio)} registros, 0 omitidos, "
        f"{len(datos.tipo_cambio)} eventos",
        f"contratos: {folios} registros, 0 omitidos, {folios} eventos",
        f"desempeno: {len(datos.desempeno)} registros, 0 omitidos, {len(datos.desempeno)} eventos",
    ]


@pytest.mark.integracion
@pytest.mark.usefixtures("fabrica")
async def test_la_cli_avisa_cuando_el_primer_archivo_falla(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    escribir(generar(21, n_proveedores=3), tmp_path)
    (tmp_path / "servicios.csv").write_text("codigo,nombre\nX,Y\n", encoding="utf-8")
    assert await _principal(tmp_path) == 1
    primera = capsys.readouterr().err.splitlines()[0]
    assert primera.startswith("Error en servicios.csv: ")
    assert primera.endswith("No se había importado ningún archivo antes del error.")
