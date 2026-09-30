import argparse
from pathlib import Path

from generador.modelo import generar
from generador.salida import escribir


def _entero_positivo(texto: str) -> int:
    try:
        valor = int(texto)
    except ValueError:
        valor = 0
    if valor < 1:
        raise argparse.ArgumentTypeError(
            f"debe ser un entero mayor o igual a 1 (se recibió {texto!r})"
        )
    return valor


def main(argumentos: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Genera datos sintéticos del ERP simulado")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--proveedores", type=_entero_positivo, default=60)
    parser.add_argument("--anios", type=_entero_positivo, default=5)
    parser.add_argument("--salida", type=Path, default=Path("datos"))
    args = parser.parse_args(argumentos)
    datos = generar(args.semilla, args.proveedores, args.anios)
    escribir(datos, args.salida)
    folios = len({fila["folio"] for fila in datos.contratos})
    print(
        f"{len(datos.proveedores)} proveedores, {folios} contratos "
        f"({len(datos.contratos)} líneas), {len(datos.desempeno)} registros de desempeño "
        f"-> {args.salida}"
    )


if __name__ == "__main__":
    main()
