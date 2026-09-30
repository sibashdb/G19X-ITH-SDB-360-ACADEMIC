"""Escribe los CSV con el formato de exportación del ERP y el archivo de verdad oculta."""

import csv
import json
from collections.abc import Iterable
from pathlib import Path

from generador.modelo import DatosSinteticos

COLUMNAS_CONTRATO = (
    "folio",
    "rfc_proveedor",
    "tipo",
    "fecha_inicio",
    "fecha_fin",
    "moneda",
    "plazo_pago_dias",
    "sla_disponibilidad",
    "tope_aumento_pct",
    "cuota_implementacion",
    "codigo_servicio",
    "cantidad",
    "precio_unitario",
)
COLUMNAS_DESEMPENO = (
    "rfc_proveedor",
    "periodo",
    "sla_cumplimiento_pct",
    "tiempo_resolucion_h",
    "incidentes_criticos",
    "entregas_a_tiempo_pct",
    "satisfaccion",
)


def _escribir(ruta: Path, columnas: tuple[str, ...], filas: Iterable[dict[str, str]]) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def escribir(datos: DatosSinteticos, carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    _escribir(
        carpeta / "servicios.csv",
        ("codigo", "nombre", "categoria", "unidad", "moneda"),
        (
            {
                "codigo": s.codigo,
                "nombre": s.nombre,
                "categoria": s.categoria,
                "unidad": s.unidad,
                "moneda": s.moneda,
            }
            for s in datos.servicios
        ),
    )
    _escribir(
        carpeta / "proveedores.csv",
        ("rfc", "nombre", "tamano", "categorias", "contacto_nombre", "contacto_email", "activo"),
        (
            {
                "rfc": p.rfc,
                "nombre": p.nombre,
                "tamano": p.tamano,
                "categorias": "|".join(p.categorias),
                "contacto_nombre": p.contacto_nombre,
                "contacto_email": p.contacto_email,
                "activo": "true" if p.activo else "false",
            }
            for p in datos.proveedores
        ),
    )
    _escribir(carpeta / "tipo_cambio.csv", ("periodo", "usd_mxn"), datos.tipo_cambio)
    _escribir(carpeta / "contratos.csv", COLUMNAS_CONTRATO, datos.contratos)
    _escribir(carpeta / "desempeno.csv", COLUMNAS_DESEMPENO, datos.desempeno)
    verdad = {
        "semilla": datos.semilla,
        "advertencia": "Solo para validación. Nunca cargar este archivo a la plataforma.",
        "proveedores": [
            {
                "rfc": p.rfc,
                "calidad": p.calidad,
                "nivel_precio": p.nivel_precio,
                "flexibilidad": p.flexibilidad,
                "estilo": p.estilo,
            }
            for p in datos.proveedores
        ],
    }
    # newline="\n": mismos bytes en Windows y Linux (sin esto el JSON saldría con CRLF).
    (carpeta / "verdad_oculta.json").write_text(
        json.dumps(verdad, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
