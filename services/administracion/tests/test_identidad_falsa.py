import pytest
from administracion.identidad import (
    DatoDuplicado,
    DatosUsuarioNuevo,
    IdentidadNoDisponible,
    UsuarioNoEncontrado,
)
from administracion.identidad_falsa import IdentidadFalsa


async def test_crear_y_duplicados() -> None:
    falsa = IdentidadFalsa()
    falsa.agregar("ana", ["comprador"], correo="ana@x.mx")
    nuevo = await falsa.crear_usuario(DatosUsuarioNuevo("beto", "Beto", "Ruiz", "beto@x.mx"))
    assert (await falsa.obtener_usuario(nuevo)).usuario == "beto"
    with pytest.raises(DatoDuplicado) as usuario:
        await falsa.crear_usuario(DatosUsuarioNuevo("ana", "A", "B", "otro@x.mx"))
    assert usuario.value.campo == "usuario"
    with pytest.raises(DatoDuplicado) as correo:
        await falsa.crear_usuario(DatosUsuarioNuevo("carla", "C", "D", "ana@x.mx"))
    assert correo.value.campo == "correo"


async def test_no_entrega_cuentas_de_servicio_por_id() -> None:
    falsa = IdentidadFalsa()
    falsa.agregar("service-account-administracion", ["admin"])
    with pytest.raises(UsuarioNoEncontrado):
        await falsa.obtener_usuario("service-account-administracion")


async def test_caida() -> None:
    falsa = IdentidadFalsa()
    falsa.caida = True
    with pytest.raises(IdentidadNoDisponible):
        await falsa.listar_usuarios()
