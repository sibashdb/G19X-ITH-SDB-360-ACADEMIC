import {
  Bell,
  Building2,
  FileUp,
  LayoutDashboard,
  Settings,
  Tags,
  Trophy,
  type LucideIcon,
} from "lucide-react"
import type { Rol } from "@/auth"

export type ElementoNavegacion = {
  titulo: string
  ruta: string
  icono: LucideIcon
  soloAdmin?: boolean
}
export type SeccionNavegacion = {
  titulo: string
  elementos: ElementoNavegacion[]
}
export type Miga = { titulo: string; ruta?: string }

export const NAVEGACION: SeccionNavegacion[] = [
  {
    titulo: "Resumen",
    elementos: [{ titulo: "Tablero", ruta: "/", icono: LayoutDashboard }],
  },
  {
    titulo: "Proveedores",
    elementos: [
      { titulo: "Proveedores", ruta: "/proveedores", icono: Building2 },
      { titulo: "Ranking", ruta: "/ranking", icono: Trophy },
    ],
  },
  {
    titulo: "Inteligencia",
    elementos: [
      { titulo: "Precios", ruta: "/precios", icono: Tags },
      { titulo: "Alertas", ruta: "/alertas", icono: Bell },
    ],
  },
  {
    titulo: "Datos",
    elementos: [
      {
        titulo: "Importación",
        ruta: "/importacion",
        icono: FileUp,
        soloAdmin: true,
      },
      {
        titulo: "Configuración",
        ruta: "/configuracion",
        icono: Settings,
        soloAdmin: true,
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

export function estaActiva(ruta: string, pathname: string): boolean {
  if (ruta === "/") return pathname === "/"
  return pathname === ruta || pathname.startsWith(`${ruta}/`)
}

/** Migas de pan: sección › página › detalle (la sección se omite si se llama igual que la página). */
export function migasDe(pathname: string): Miga[] {
  const [, primero = "", ...resto] = pathname.split("/")
  const base = `/${primero}`
  for (const seccion of NAVEGACION) {
    const elemento = seccion.elementos.find((e) => e.ruta === base)
    if (!elemento) continue
    const migas: Miga[] =
      seccion.titulo === elemento.titulo ? [] : [{ titulo: seccion.titulo }]
    if (resto.some(Boolean)) {
      return [
        ...migas,
        { titulo: elemento.titulo, ruta: elemento.ruta },
        { titulo: "Detalle" },
      ]
    }
    return [...migas, { titulo: elemento.titulo }]
  }
  return [{ titulo: "Página no encontrada" }]
}
