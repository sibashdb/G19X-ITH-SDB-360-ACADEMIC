"""Arranque limpio en un comando: uv run python infra/arrancar.py

Deja la plataforma lista desde cero y se puede repetir sin dañar nada:
1. copia infra/.env desde infra/.env.example si falta;
2. genera los datos sintéticos si faltan;
3. levanta el stack y espera a que esté sano;
4. importa los datos (repetir la importación no duplica nada);
5. corre la prueba de humo.
"""

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-f", "infra/docker-compose.yml"]
PASOS = [
    ["uv", "run", "--all-packages", "python", "-m", "generador", "--salida", "datos"],
    [*COMPOSE, "up", "-d", "--build", "--wait"],
    # Sin shell de por medio: Git Bash no convierte /datos en una ruta de Windows.
    [
        *COMPOSE,
        "exec",
        "-T",
        "proveedores",
        "python",
        "-m",
        "proveedores.importacion.cli",
        "/datos",
    ],
    ["uv", "run", "python", "infra/smoke_test.py"],
]


def main() -> int:
    env = RAIZ / "infra" / ".env"
    if not env.exists():
        shutil.copyfile(RAIZ / "infra" / ".env.example", env)
        print("Se creó infra/.env con los valores de ejemplo (solo para desarrollo).")
    pasos = PASOS[1:] if (RAIZ / "datos" / "verdad_oculta.json").exists() else PASOS
    for comando in pasos:
        print("->", " ".join(comando), flush=True)
        try:
            # Comandos fijos de este archivo; no reciben nada del usuario.
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
