import {
  Activity,
  Bell,
  Building2,
  FileUp,
  Gauge,
  History,
  LayoutDashboard,
  LifeBuoy,
  Mail,
  Package,
  Settings,
  Tags,
  Trophy,
  UsersRound,
  type LucideIcon,
} from "lucide-react"
import type { Rol } from "@/auth"

export type ElementoNavegacion = {
  titulo: string
  ruta: string
  descripcion: string
  icono: LucideIcon
  soloAdmin?: boolean
  /** Solo cuenta como activa en su ruta exacta, no en sus subrutas (el Panel en /sistema). */
  exacta?: boolean
}
export type SeccionNavegacion = {
  titulo: string
  elementos: ElementoNavegacion[]
}
export type Miga = { titulo: string; ruta?: string }

export const NAVEGACION: SeccionNavegacion[] = [
  {
    titulo: "Resumen",
    elementos: [
      {
        titulo: "Tablero",
        ruta: "/",
        descripcion: "Resumen del gasto y lo urgente",
        icono: LayoutDashboard,
      },
    ],
  },
  {
    titulo: "Proveedores",
    elementos: [
      {
        titulo: "Proveedores",
        ruta: "/proveedores",
        descripcion: "Quién le vende y cómo rinde",
        icono: Building2,
      },
      {
        titulo: "Ranking",
        ruta: "/ranking",
        descripcion: "Los mejores proveedores por categoría",
        icono: Trophy,
      },
    ],
  },
  {
    titulo: "Inteligencia",
    elementos: [
      {
        titulo: "Precios",
        ruta: "/precios",
        descripcion: "Cuánto debería pagar",
        icono: Tags,
      },
      {
        titulo: "Alertas",
        ruta: "/alertas",
        descripcion: "Qué atender hoy",
        icono: Bell,
      },
    ],
  },
  {
    titulo: "Sistema",
    elementos: [
      {
        titulo: "Panel",
        ruta: "/sistema",
        descripcion: "Lo importante de un vistazo",
        icono: Gauge,
        soloAdmin: true,
        exacta: true,
      },
      {
        titulo: "Usuarios",
        ruta: "/sistema/usuarios",
        descripcion: "Quién entra y con qué rol",
        icono: UsersRound,
        soloAdmin: true,
      },
      {
        titulo: "Actividad",
        ruta: "/sistema/actividad",
        descripcion: "Quién hizo qué y cuándo",
        icono: History,
        soloAdmin: true,
      },
      {
        titulo: "Catálogo",
        ruta: "/sistema/catalogo",
        descripcion: "Servicios de TI que se compran",
        icono: Package,
        soloAdmin: true,
      },
      {
        titulo: "Estado del sistema",
        ruta: "/sistema/estado",
        descripcion: "Si cada servicio responde",
        icono: Activity,
        soloAdmin: true,
      },
      {
        titulo: "Correos",
        ruta: "/sistema/correos",
        descripcion:
          "Invitaciones, restablecimientos e invitaciones a negociar",
        icono: Mail,
        soloAdmin: true,
      },
      {
        titulo: "Importación",
        ruta: "/importacion",
        descripcion: "Cargar datos del ERP",
        icono: FileUp,
        soloAdmin: true,
      },
      {
        titulo: "Configuración",
        ruta: "/configuracion",
        descripcion: "Ajustes de puntuación y precios",
        icono: Settings,
        soloAdmin: true,
      },
    ],
  },
  {
    titulo: "Soporte",
    elementos: [
      {
        titulo: "Centro de ayuda",
        ruta: "/ayuda",
        descripcion: "Guías y preguntas frecuentes",
        icono: LifeBuoy,
      },
    ],
  },
]

/** Menú visible para los roles dados; la API vuelve a validar cada permiso. */
export function navegacionPara(roles: Rol[]): SeccionNavegacion[] {
  const esAdmin = roles.includes("admin")
  return NAVEGACION.map((seccion) => ({
    ...seccion,
    elementos: seccion.elementos.filter((e) => esAdmin || !e.soloAdmin),
  })).filter((seccion) => seccion.elementos.length > 0)
}

export function estaActiva(
  ruta: string,
  pathname: string,
  exacta = false
): boolean {
  if (ruta === "/" || exacta) return pathname === ruta
  return pathname === ruta || pathname.startsWith(`${ruta}/`)
}

/** Migas de pan: sección › página › detalle (la sección se omite si se llama igual que la página). */
export function migasDe(pathname: string): Miga[] {
  const ruta = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname
  let mejor: {
    seccion: SeccionNavegacion
    elemento: ElementoNavegacion
  } | null = null
  for (const seccion of NAVEGACION) {
    for (const elemento of seccion.elementos) {
      const coincide = estaActiva(elemento.ruta, ruta, elemento.exacta)
      if (
        coincide &&
        (!mejor || elemento.ruta.length > mejor.elemento.ruta.length)
      )
        mejor = { seccion, elemento }
    }
  }
  if (!mejor) return [{ titulo: "Página no encontrada" }]
  const { seccion, elemento } = mejor
  const migas: Miga[] =
    seccion.titulo === elemento.titulo ? [] : [{ titulo: seccion.titulo }]
  if (ruta !== elemento.ruta) {
    return [
      ...migas,
      { titulo: elemento.titulo, ruta: elemento.ruta },
      { titulo: "Detalle" },
    ]
  }
  return [...migas, { titulo: elemento.titulo }]
}
