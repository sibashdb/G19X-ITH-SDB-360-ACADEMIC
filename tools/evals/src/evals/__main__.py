"""uv run python -m evals --modelo qwen2.5:3b [--modelo …] [--url …] [--salida …]

Con --generar, reescribe los datos versionados de tools/evals/datos/ y termina.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

from evals import reporte
from evals.datos import SEMILLA, a_json, generar, generar_varias
from evals.medir import correr

DATOS = Path(__file__).resolve().parents[2] / "datos"


def main(argv: list[str] | None = None, transporte: httpx.AsyncBaseTransport | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals", description=__doc__)
    parser.add_argument("--modelo", action="append", default=[])
    parser.add_argument("--url", default="http://localhost:11434/v1")
    parser.add_argument("--salida", default="docs/qa/evals-llm.md")
    parser.add_argument("--espera", type=float, default=60.0)
    parser.add_argument("--generar", action="store_true")
    args = parser.parse_args(argv)
    casos, ataques = generar(SEMILLA)
    varias = generar_varias(SEMILLA)
    if args.generar:
        archivos = {
            "mensajes.json": a_json(casos),
            "ataques.json": a_json(ataques),
            "mensajes_varias.json": a_json(varias),
        }
        for nombre, datos in archivos.items():
            texto = json.dumps(datos, ensure_ascii=False, indent=2) + "\n"
            (DATOS / nombre).write_text(texto, encoding="utf-8", newline="\n")
        return 0
    if not args.modelo:
        parser.error("indique al menos un --modelo")
    resultados = [
        asyncio.run(correr(modelo, args.url, casos, ataques, transporte, args.espera, varias))
        for modelo in args.modelo
    ]
    reporte.escribir(Path(args.salida), resultados)
    for r in resultados:
        print(f"{r.modelo}: campos {r.pct_campos:.1f} %, p95 {r.percentil(95):.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
