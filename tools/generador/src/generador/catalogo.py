"""Catálogo base de servicios de TI con precios de referencia. Nombres genéricos, sin marcas."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ServicioBase:
    codigo: str
    nombre: str
    categoria: str
    unidad: str
    moneda: str
    precio_base: Decimal


def _s(
    codigo: str, nombre: str, categoria: str, unidad: str, moneda: str, precio: str
) -> ServicioBase:
    return ServicioBase(codigo, nombre, categoria, unidad, moneda, Decimal(precio))


SAAS, NUBE, CONS, SOP = "licencia_saas", "nube", "consultoria", "soporte"

SERVICIOS: tuple[ServicioBase, ...] = (
    _s(
        "SAAS-OFI-BAS",
        "Suite de productividad en la nube - plan básico",
        SAAS,
        "usuario_mes",
        "USD",
        "7",
    ),
    _s(
        "SAAS-OFI-EMP",
        "Suite de productividad en la nube - plan empresarial",
        SAAS,
        "usuario_mes",
        "USD",
        "22",
    ),
    _s(
        "SAAS-OFI-PRE",
        "Suite de productividad en la nube - plan premium",
        SAAS,
        "usuario_mes",
        "USD",
        "38",
    ),
    _s("SAAS-CRM-PRO", "CRM en la nube - plan profesional", SAAS, "usuario_mes", "USD", "65"),
    _s("SAAS-CRM-ENT", "CRM en la nube - plan corporativo", SAAS, "usuario_mes", "USD", "150"),
    _s("SAAS-ERP-USR", "ERP en la nube - usuario completo", SAAS, "usuario_mes", "USD", "120"),
    _s("SAAS-PRY-EST", "Gestión de proyectos - plan estándar", SAAS, "usuario_mes", "USD", "12"),
    _s("SAAS-VID-EMP", "Videoconferencia empresarial", SAAS, "usuario_mes", "USD", "15"),
    _s(
        "SAAS-EDR-USR", "Protección de estaciones de trabajo (EDR)", SAAS, "usuario_mes", "USD", "9"
    ),
    _s(
        "SAAS-BI-USR",
        "Inteligencia de negocios - usuario analista",
        SAAS,
        "usuario_mes",
        "USD",
        "14",
    ),
    _s("NUBE-CPU-GEN", "Cómputo de propósito general", NUBE, "vcpu_mes", "USD", "28"),
    _s("NUBE-CPU-MEM", "Cómputo optimizado para memoria", NUBE, "vcpu_mes", "USD", "38"),
    _s("NUBE-BD-ADM", "Base de datos administrada", NUBE, "vcpu_mes", "USD", "70"),
    _s("NUBE-OBJ-GB", "Almacenamiento de objetos", NUBE, "gb_mes", "USD", "0.023"),
    _s("NUBE-BLQ-SSD", "Almacenamiento en bloque SSD", NUBE, "gb_mes", "USD", "0.10"),
    _s("NUBE-RSP-GB", "Respaldo en la nube", NUBE, "gb_mes", "USD", "0.05"),
    _s(
        "NUBE-CDN-GB",
        "Red de distribución de contenido - transferencia",
        NUBE,
        "gb_mes",
        "USD",
        "0.08",
    ),
    _s("NUBE-K8S-CLU", "Clúster de contenedores administrado", NUBE, "mes", "USD", "73"),
    _s("NUBE-LB-STD", "Balanceador de carga", NUBE, "mes", "USD", "18"),
    _s("NUBE-VPN-S2S", "VPN sitio a sitio", NUBE, "mes", "USD", "36"),
    _s("CONS-DEV-JR", "Desarrollador(a) junior", CONS, "hora", "MXN", "450"),
    _s("CONS-DEV-SS", "Desarrollador(a) semi-senior", CONS, "hora", "MXN", "700"),
    _s("CONS-DEV-SR", "Desarrollador(a) senior", CONS, "hora", "MXN", "1000"),
    _s("CONS-ARQ-SW", "Arquitecto(a) de software", CONS, "hora", "MXN", "1500"),
    _s("CONS-DAT-SR", "Consultor(a) senior de datos", CONS, "hora", "MXN", "1250"),
    _s("CONS-CIE-DAT", "Científico(a) de datos", CONS, "hora", "MXN", "1300"),
    _s("CONS-SEG-ESP", "Especialista en ciberseguridad", CONS, "hora", "MXN", "1400"),
    _s("CONS-GER-PRY", "Gerente de proyecto", CONS, "hora", "MXN", "1200"),
    _s("CONS-QA-ANL", "Analista de calidad (QA)", CONS, "hora", "MXN", "550"),
    _s("CONS-ERP-FUN", "Consultor(a) funcional de ERP", CONS, "hora", "MXN", "1100"),
    _s("SOP-MESA-TK", "Mesa de ayuda - ticket", SOP, "ticket", "MXN", "180"),
    _s("SOP-N2-TK", "Soporte de segundo nivel - ticket", SOP, "ticket", "MXN", "420"),
    _s("SOP-SITIO-HR", "Soporte en sitio - hora", SOP, "hora", "MXN", "520"),
    _s("SOP-MON-SRV", "Monitoreo 24x7 por servidor", SOP, "mes", "MXN", "1500"),
    _s("SOP-ADM-SRV", "Administración de servidores", SOP, "mes", "MXN", "3200"),
    _s("SOP-DBA-MES", "Soporte de base de datos", SOP, "mes", "MXN", "6500"),
    _s("SOP-EQP-MES", "Mantenimiento de equipos de cómputo", SOP, "mes", "MXN", "250"),
    _s("SOP-RED-SIT", "Gestión de red por sitio", SOP, "mes", "MXN", "4800"),
    _s("SOP-APP-HR", "Soporte a aplicaciones - hora", SOP, "hora", "MXN", "650"),
    _s("SOP-POL-SAAS", "Póliza de soporte de plataformas SaaS", SOP, "mes", "MXN", "9000"),
)
