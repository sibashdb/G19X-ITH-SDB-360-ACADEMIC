"""Arranque limpio en un comando: uv run python infra/arrancar.py [--imagenes mvp-1.2]

Deja la plataforma lista desde cero y se puede repetir sin dañar nada:
1. copia infra/.env desde infra/.env.example si falta;
2. genera los datos sintéticos si faltan;
3. levanta el stack y espera a que esté sano: compila las imágenes propias o, con --imagenes,
   descarga de GHCR las de esa etiqueta;
4. importa los datos (repetir la importación no duplica nada);
5. corre la prueba de humo.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-f", "infra/docker-compose.yml"]
IMAGENES = "ghcr.io/sibashdb/g19x-ith-sdb-360-academic"
# Los servicios que se construyen aquí; las imágenes de terceros se bajan de sus registros.
SERVICIOS_PROPIOS = (
    "proveedores",
    "administracion",
    "inteligencia",
    "ia",
    "negociacion",
    "gateway",
)
ETIQUETA = re.compile(r"mvp-\d+\.\d+(-rc\d+)?|latest")
GENERAR = ["uv", "run", "--all-packages", "python", "-m", "generador", "--salida", "datos"]
# Sin shell de por medio: Git Bash no convierte /datos en una ruta de Windows.
IMPORTAR = [*COMPOSE, "exec", "-T", "proveedores", "python", "-m", "proveedores.importacion.cli"]
HUMO = ["uv", "run", "python", "infra/smoke_test.py"]


def pasos(version: str | None, con_datos: bool) -> list[list[str]]:
    """Los comandos del arranque: con una versión, las imágenes se descargan y no se compilan."""
    if version is None:
        levantar = [[*COMPOSE, "up", "-d", "--build", "--wait"]]
    else:
        levantar = [
            [*COMPOSE, "pull", *SERVICIOS_PROPIOS],
            [*COMPOSE, "up", "-d", "--no-build", "--wait"],
        ]
    return [*([] if con_datos else [GENERAR]), *levantar, [*IMPORTAR, "/datos"], HUMO]


def entorno(version: str | None) -> dict[str, str]:
    """Con una versión, el compose usa esas imágenes y el Estado del sistema la muestra."""
    return {} if version is None else {"PLURIONE_VERSION": version, "VERSION_APP": version}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arrancar", description=__doc__)
    parser.add_argument("--imagenes", metavar="ETIQUETA", help="por ejemplo, mvp-1.2")
    version = parser.parse_args(argv).imagenes
    if version is not None and not ETIQUETA.fullmatch(version):
        print("La etiqueta debe ser como mvp-1.2, mvp-1.2-rc1 o latest.")
        return 2
    # En Git Bash la salida es una tubería y Python escribiría en cp1252: los acentos saldrían
    # rotos aquí y en los pasos que lanza (la prueba de humo).
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ.update(entorno(version))
    env = RAIZ / "infra" / ".env"
    if not env.exists():
        shutil.copyfile(RAIZ / "infra" / ".env.example", env)
        print("Se creó infra/.env con los valores de ejemplo (solo para desarrollo).")
    con_datos = (RAIZ / "datos" / "verdad_oculta.json").exists()
    for comando in pasos(version, con_datos):
        print("->", " ".join(comando), flush=True)
        try:
            # Comandos fijos de este archivo; la etiqueta ya pasó por ETIQUETA.
            subprocess.run(comando, cwd=RAIZ, check=True)  # noqa: S603
        except FileNotFoundError:
            print(f"FALLA: no se encontró «{comando[0]}». Revise los Requisitos del README.")
            return 1
        except subprocess.CalledProcessError as error:
            print(f"FALLA: el paso terminó con código {error.returncode}.")
            return error.returncode
    print(
        "Listo: abra http://localhost:8080. Los usuarios de desarrollo están en "
        "infra/keycloak/realm-plataforma.json."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
