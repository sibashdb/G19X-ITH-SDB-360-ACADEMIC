"""Genera proveedores con variables latentes ocultas, contratos, desempeño y tipo de cambio.

Las variables latentes (calidad, nivel de precio, flexibilidad, estilo) explican los
datos observados con ruido, de modo que después se puede medir si la plataforma
"acierta" sin que las vea nunca.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from generador.catalogo import SERVICIOS, ServicioBase

CATEGORIAS = ("licencia_saas", "nube", "consultoria", "soporte")
ESTILOS = ("duro", "flexible", "erratico", "manipulador")
TAMANOS = ("micro", "pequena", "mediana", "grande")
PREFIJOS = (
    "Nube",
    "Datos",
    "Soluciones",
    "Sistemas",
    "Tecno",
    "Red",
    "Código",
    "Servicios",
    "Infra",
    "Nodo",
)
SUFIJOS = (
    "Azteca",
    "del Norte",
    "Integrales",
    "del Pacífico",
    "Digitales",
    "Globales",
    "del Bajío",
    "Maya",
)
NOMBRES = (
    "Laura",
    "Jorge",
    "Ana",
    "Carlos",
    "María",
    "Luis",
    "Sofía",
    "Diego",
    "Fernanda",
    "Ricardo",
)
APELLIDOS = (
    "Méndez",
    "Ruiz",
    "Torres",
    "García",
    "Hernández",
    "López",
    "Martínez",
    "Ramírez",
    "Flores",
    "Castillo",
)
LETRAS_RFC = "ABCDEFGHJKLMNPRSTUVWXYZ"
INFLACION_ANUAL = 0.045
SESGO_OBSERVACION = 0.10  # desv. estándar del sesgo persistente con que los KPI ven la calidad
DESPLAZAMIENTO_KPI = 0.08  # desv. estándar del desplazamiento persistente de cada KPI
PROPORCION_RECIENTES = 0.15  # proveedores con solo 1 a 12 meses de historial
PLAZOS = {
    "licencia_saas": (12, 24, 36),
    "nube": (12, 24, 36),
    "soporte": (12, 24, 36),
    "consultoria": (3, 6, 9, 12),
}
DESCUENTO_PLAZO = {3: 1.0, 6: 1.0, 9: 1.0, 12: 1.0, 24: 0.95, 36: 0.92}
RANGO_CANTIDAD = {
    "usuario_mes": (10, 800),
    "vcpu_mes": (4, 256),
    "gb_mes": (500, 50_000),
    "mes": (1, 20),
    "hora": (40, 1_500),
    "ticket": (100, 5_000),
}


@dataclass(frozen=True)
class ProveedorSintetico:
    rfc: str
    nombre: str
    tamano: str
    categorias: tuple[str, ...]
    contacto_nombre: str
    contacto_email: str
    activo: bool
    calidad: float  # oculta: 0 (mala) a 1 (excelente)
    nivel_precio: float  # oculta: 0.85 (barato) a 1.25 (caro)
    flexibilidad: float  # oculta: fracción que puede bajar desde su precio de lista
    estilo: str  # oculto: estilo del bot en el simulador de negociación


@dataclass
class DatosSinteticos:
    semilla: int
    servicios: tuple[ServicioBase, ...] = SERVICIOS
    proveedores: list[ProveedorSintetico] = field(default_factory=list)
    contratos: list[dict[str, str]] = field(default_factory=list)  # una fila por línea
    desempeno: list[dict[str, str]] = field(default_factory=list)
    tipo_cambio: list[dict[str, str]] = field(default_factory=list)


def _sumar_meses(fecha: date, meses: int) -> date:
    indice = fecha.year * 12 + fecha.month - 1 + meses
    return date(indice // 12, indice % 12 + 1, 1)


def _meses_entre(inicio: date, fin: date) -> int:
    return (fin.year - inicio.year) * 12 + fin.month - inicio.month


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def _dec(valor: float, decimales: int) -> str:
    return str(Decimal(str(valor)).quantize(Decimal(1).scaleb(-decimales), ROUND_HALF_UP))


def generar(
    semilla: int = 42, n_proveedores: int = 60, anios: int = 5, hasta: date = date(2026, 9, 1)
) -> DatosSinteticos:
    rng = random.Random(semilla)  # noqa: S311 - datos sintéticos reproducibles, no criptografía
    datos = DatosSinteticos(semilla)
    inicio = _sumar_meses(hasta, -12 * anios)
    datos.tipo_cambio = _tipo_cambio(rng, inicio, hasta)
    usados: set[str] = set()
    folio = 0
    for indice in range(1, n_proveedores + 1):
        proveedor = _proveedor(rng, indice, usados)
        datos.proveedores.append(proveedor)
        contratos = _contratos(rng, proveedor, inicio, hasta)
        for lineas in contratos:
            folio += 1
            datos.contratos.extend({"folio": f"C-{folio:06d}"} | linea for linea in lineas)
        primer_mes = date.fromisoformat(contratos[0][0]["fecha_inicio"])
        datos.desempeno.extend(_desempeno(rng, proveedor, primer_mes, hasta))
    return datos


def _rfc(rng: random.Random, usados: set[str]) -> str:
    while True:
        rfc = (
            "".join(rng.choice(LETRAS_RFC) for _ in range(3))
            + f"{rng.randint(0, 99):02d}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}"
            + "".join(rng.choice(LETRAS_RFC + "0123456789") for _ in range(3))
        )
        if rfc not in usados:
            usados.add(rfc)
            return rfc


def _proveedor(rng: random.Random, indice: int, usados: set[str]) -> ProveedorSintetico:
    calidad = rng.betavariate(2, 2)
    prefijo = PREFIJOS[(indice - 1) % len(PREFIJOS)]
    sufijo = SUFIJOS[(indice - 1) // len(PREFIJOS) % len(SUFIJOS)]
    repeticion = (indice - 1) // (len(PREFIJOS) * len(SUFIJOS))
    nombre = f"{prefijo} {sufijo}{f' {repeticion + 1}' if repeticion else ''} S.A. de C.V."
    return ProveedorSintetico(
        rfc=_rfc(rng, usados),
        nombre=nombre,
        tamano=rng.choice(TAMANOS),
        categorias=tuple(sorted(rng.sample(CATEGORIAS, 2 if rng.random() < 0.3 else 1))),
        contacto_nombre=f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}",
        contacto_email=f"ventas{indice:03d}@proveedor{indice:03d}.example",
        activo=rng.random() > 0.05,
        calidad=round(calidad, 4),
        nivel_precio=round(0.85 + 0.2 * calidad + rng.uniform(0, 0.2), 4),
        flexibilidad=round(rng.uniform(0.03, 0.20), 4),
        estilo=rng.choice(ESTILOS),
    )


def _cantidad(rng: random.Random, unidad: str) -> int:
    minimo, maximo = RANGO_CANTIDAD[unidad]
    return round(math.exp(rng.uniform(math.log(minimo), math.log(maximo))))


def _precio(
    rng: random.Random,
    servicio: ServicioBase,
    proveedor: ProveedorSintetico,
    cantidad: int,
    plazo: int,
    meses_desde_inicio: int,
) -> str:
    minimo = RANGO_CANTIDAD[servicio.unidad][0]
    descuento_volumen = max(0.85, 1 - 0.04 * math.log10(max(cantidad, minimo) / minimo))
    inflacion = (1 + INFLACION_ANUAL) ** (meses_desde_inicio / 12)
    valor = (
        float(servicio.precio_base)
        * proveedor.nivel_precio
        * descuento_volumen
        * DESCUENTO_PLAZO[plazo]
        * inflacion
        * rng.lognormvariate(0, 0.08)
    )
    return _dec(max(valor, 0.0001), 4)


def _contratos(
    rng: random.Random, proveedor: ProveedorSintetico, inicio: date, hasta: date
) -> list[list[dict[str, str]]]:
    ofrecidos = [s for s in SERVICIOS if s.categoria in proveedor.categorias]
    catalogo = rng.sample(ofrecidos, k=min(len(ofrecidos), rng.randint(3, 5)))
    total_meses = _meses_entre(inicio, hasta)
    if rng.random() < PROPORCION_RECIENTES:
        # Proveedor reciente: pocos contratos, todos en los últimos 12 meses de la ventana
        # (historial de desempeño de 1 a 12 meses, para probar la contracción bayesiana).
        arranques = sorted(
            rng.randint(total_meses - 11, total_meses) for _ in range(rng.randint(2, 6))
        )
    else:
        arranques = sorted(rng.randrange(total_meses) for _ in range(rng.randint(20, 46)))
    contratos: list[list[dict[str, str]]] = []
    for numero, mes in enumerate(arranques):
        base = rng.choice(catalogo)
        misma_categoria = [s for s in catalogo if s.categoria == base.categoria]
        servicios = rng.sample(misma_categoria, k=rng.randint(1, min(4, len(misma_categoria))))
        plazo = rng.choice(PLAZOS[base.categoria])
        fecha_inicio = _sumar_meses(inicio, mes)
        continuo = base.categoria != "consultoria"
        cabecera = {
            "rfc_proveedor": proveedor.rfc,
            "tipo": "renovacion" if numero and rng.random() < 0.4 else "nuevo",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": (_sumar_meses(fecha_inicio, plazo) - timedelta(days=1)).isoformat(),
            "moneda": base.moneda,
            "plazo_pago_dias": str(rng.choice((15, 30, 45, 60))),
            "sla_disponibilidad": rng.choice(("99.00", "99.50", "99.90", "99.95"))
            if continuo
            else "",
            "tope_aumento_pct": rng.choice(("", "3.00", "5.00", "7.00", "10.00"))
            if continuo
            else "",
            "cuota_implementacion": (
                _dec(rng.uniform(500, 8_000), 4)
                if base.categoria == "licencia_saas" and rng.random() < 0.3
                else "0"
            ),
        }
        lineas = []
        for servicio in servicios:
            cantidad = _cantidad(rng, servicio.unidad)
            precio = _precio(rng, servicio, proveedor, cantidad, plazo, mes)
            lineas.append(
                cabecera
                | {
                    "codigo_servicio": servicio.codigo,
                    "cantidad": str(cantidad),
                    "precio_unitario": precio,
                }
            )
        contratos.append(lineas)
    return contratos


def _desempeno(
    rng: random.Random, proveedor: ProveedorSintetico, desde: date, hasta: date
) -> list[dict[str, str]]:
    # Señales imperfectas de la calidad oculta: los KPI "ven" una calidad con un sesgo
    # persistente del proveedor y, además, cada KPI tiene su propio desplazamiento persistente
    # (en unidades de calidad), de modo que no son colineales ni reflejan la calidad exacta.
    q = _limitar(proveedor.calidad + rng.gauss(0, SESGO_OBSERVACION), 0, 1)
    q_sla, q_res, q_inc, q_ent, q_sat = (q + rng.gauss(0, DESPLAZAMIENTO_KPI) for _ in range(5))
    filas = []
    mes = desde
    while mes <= hasta:
        filas.append(
            {
                "rfc_proveedor": proveedor.rfc,
                "periodo": mes.isoformat(),
                "sla_cumplimiento_pct": _dec(
                    _limitar(95 + 5 * q_sla + rng.gauss(0, 0.8), 80, 100), 2
                ),
                "tiempo_resolucion_h": _dec(max(0.5, 24 - 18 * q_res + rng.gauss(0, 2.5)), 2),
                "incidentes_criticos": str(max(0, round(rng.gauss(3 * (1 - q_inc), 1)))),
                "entregas_a_tiempo_pct": _dec(
                    _limitar(80 + 20 * q_ent + rng.gauss(0, 4), 0, 100), 2
                ),
                "satisfaccion": _dec(_limitar(1.5 + 3.5 * q_sat + rng.gauss(0, 0.4), 1, 5), 2),
            }
        )
        mes = _sumar_meses(mes, 1)
    return filas


def _tipo_cambio(rng: random.Random, inicio: date, hasta: date) -> list[dict[str, str]]:
    valor = 20.0
    filas = []
    mes = inicio
    while mes <= hasta:
        filas.append({"periodo": mes.isoformat(), "usd_mxn": _dec(valor, 4)})
        valor = _limitar(valor + rng.gauss(0, 0.35), 16.5, 22.5)
        mes = _sumar_meses(mes, 1)
    return filas
