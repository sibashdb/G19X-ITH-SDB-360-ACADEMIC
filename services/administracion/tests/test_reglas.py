import string
from datetime import UTC, datetime

import pytest
from administracion.identidad import UsuarioIdentidad
from administracion.reglas import (
    SIMBOLOS,
    ReglaProteccion,
    generar_contrasena_temporal,
    verificar_cambio_de_roles,
    verificar_desactivacion,
)


def _u(id_: str, *roles: str, activo: bool = True) -> UsuarioIdentidad:
    return UsuarioIdentidad(
        id_,
        id_,
        "N",
        "A",
        f"{id_}@x.mx",
        activo,
        frozenset(roles),
        datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_contrasena_temporal_cumple_la_politica() -> None:
    contrasenas = {generar_contrasena_temporal() for _ in range(50)}
    assert len(contrasenas) == 50
    for c in contrasenas:
        assert len(c) == 16
        assert any(x in string.ascii_uppercase for x in c)
        assert any(x in string.ascii_lowercase for x in c)
        assert any(x in string.digits for x in c)
        assert any(x in SIMBOLOS for x in c)


def test_nadie_se_desactiva_a_si_mismo() -> None:
    yo = _u("yo", "admin")
    with pytest.raises(ReglaProteccion, match=r"No puede desactivar su propia cuenta\."):
        verificar_desactivacion("yo", yo, [yo, _u("otro", "admin")])


def test_se_puede_desactivar_a_otro_admin_si_quedan_mas() -> None:
    otro = _u("otro", "admin")
    verificar_desactivacion("yo", otro, [_u("yo", "admin"), otro])


def test_un_admin_inactivo_no_cuenta_como_respaldo() -> None:
    # Token aún vigente de un admin que ya no lo es: el único admin activo es "ultimo".
    ultimo = _u("ultimo", "admin")
    usuarios = [ultimo, _u("dormido", "admin", activo=False), _u("yo", "comprador")]
    with pytest.raises(ReglaProteccion, match=r"Debe quedar al menos un administrador activo\."):
        verificar_desactivacion("yo", ultimo, usuarios)
    with pytest.raises(ReglaProteccion, match=r"Debe quedar al menos un administrador activo\."):
        verificar_cambio_de_roles("yo", ultimo, frozenset({"comprador"}), usuarios)


def test_nadie_se_quita_el_rol_de_admin() -> None:
    yo = _u("yo", "admin", "comprador")
    with pytest.raises(ReglaProteccion, match=r"No puede quitarse el rol de administrador\."):
        verificar_cambio_de_roles("yo", yo, frozenset({"comprador"}), [yo, _u("otro", "admin")])


def test_cambios_de_roles_permitidos() -> None:
    yo = _u("yo", "admin")
    otro = _u("otro", "admin")
    verificar_cambio_de_roles("yo", yo, frozenset({"admin", "aprobador"}), [yo, otro])
    verificar_cambio_de_roles("yo", otro, frozenset({"comprador"}), [yo, otro])
    verificar_cambio_de_roles("yo", _u("c", "comprador"), frozenset({"aprobador"}), [yo])
