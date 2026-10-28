"""arrancar.py con y sin las imágenes publicadas en GHCR (entregable 5)."""

import importlib.util
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _cargar() -> ModuleType:
    """infra/ no es un paquete: se carga el archivo directamente."""
    spec = importlib.util.spec_from_file_location("arrancar", RAIZ / "infra" / "arrancar.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


arrancar = _cargar()
COMPOSE = arrancar.COMPOSE


def test_sin_imagenes_compila_como_hoy() -> None:
    pasos = arrancar.pasos(None, con_datos=True)
    assert [*COMPOSE, "up", "-d", "--build", "--wait"] in pasos
    assert not any("pull" in paso for paso in pasos)


def test_con_imagenes_descarga_y_no_compila() -> None:
    pasos = arrancar.pasos("mvp-1.2", con_datos=True)
    descarga = [*COMPOSE, "pull", *arrancar.SERVICIOS_PROPIOS]
    arranque = [*COMPOSE, "up", "-d", "--no-build", "--wait"]
    assert pasos.index(descarga) < pasos.index(arranque)
    assert not any("--build" in paso for paso in pasos)


def test_sin_datos_genera_primero() -> None:
    assert arrancar.pasos("mvp-1.2", con_datos=False)[0][-3:] == ["generador", "--salida", "datos"]


def test_la_version_llega_al_compose_y_al_estado_del_sistema() -> None:
    assert arrancar.entorno("mvp-1.2") == {"PLURIONE_VERSION": "mvp-1.2", "VERSION_APP": "mvp-1.2"}
    assert arrancar.entorno(None) == {}


@pytest.mark.parametrize("etiqueta", ["1.2", "mvp1.2", "mvp-1.2; rm -rf /"])
def test_una_etiqueta_mal_escrita_se_rechaza_sin_llamar_a_docker(
    etiqueta: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas: list[Any] = []
    monkeypatch.setattr(arrancar.subprocess, "run", lambda *a, **k: llamadas.append(a))
    assert arrancar.main(["--imagenes", etiqueta]) == 2
    assert llamadas == []


def _flujo() -> str:
    return (RAIZ / ".github" / "workflows" / "imagenes.yml").read_text(encoding="utf-8")


def test_el_flujo_publica_los_mismos_servicios() -> None:
    flujo = _flujo()
    assert arrancar.IMAGENES in flujo
    for servicio in arrancar.SERVICIOS_PROPIOS:
        dockerfile = f"services/{servicio}/Dockerfile"
        if servicio == "gateway":
            dockerfile = "web/Dockerfile"
        assert re.search(rf"servicio: {servicio}\s+dockerfile: {re.escape(dockerfile)}", flujo)
    # El job latest recorre los mismos servicios, en el mismo orden.
    assert f"for servicio in {' '.join(arrancar.SERVICIOS_PROPIOS)}; do" in flujo


def test_el_flujo_corre_con_las_etiquetas_mvp() -> None:
    flujo = _flujo()
    assert 'tags: ["mvp-*"]' in flujo
    assert "workflow_dispatch:" in flujo


def test_una_candidata_no_mueve_latest() -> None:
    latest = _flujo().split("\n  latest:\n", 1)[1]
    assert "!contains(github.ref_name, '-rc')" in latest
    assert "!contains(inputs.etiqueta, '-rc')" in latest


def test_el_compose_nombra_cada_servicio_propio_con_su_imagen() -> None:
    compose = (RAIZ / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    for servicio in arrancar.SERVICIOS_PROPIOS:
        imagen = f"image: {arrancar.IMAGENES}/{servicio}:${{PLURIONE_VERSION:-local}}"
        assert imagen in compose, servicio
