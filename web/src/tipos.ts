export type Categoria = "licencia_saas" | "nube" | "consultoria" | "soporte"

export const NOMBRES_CATEGORIA: Record<Categoria, string> = {
  licencia_saas: "Licencias SaaS",
  nube: "Nube",
  consultoria: "Consultoría",
  soporte: "Soporte",
}

export type ProveedorResumen = {
  id: string
  rfc: string
  nombre: string
  tamano: string
  categorias: Categoria[]
  activo: boolean
}

export type PaginaProveedores = { total: number; elementos: ProveedorResumen[] }

export type ProveedorDetalle = ProveedorResumen & {
  contacto_nombre: string
  contacto_email: string
  contratos_vigentes: number
}

export type LineaContrato = {
  codigo_servicio: string
  nombre_servicio: string
  unidad: string
  cantidad: string
  precio_unitario: string
}

export type Contrato = {
  id: string
  folio: string
  tipo: "nuevo" | "renovacion"
  fecha_inicio: string
  fecha_fin: string
  moneda: "MXN" | "USD"
  plazo_pago_dias: number
  sla_disponibilidad: string | null
  tope_aumento_pct: string | null
  cuota_implementacion: string
  lineas: LineaContrato[]
}

export type Desempeno = {
  periodo: string
  sla_cumplimiento_pct: string
  tiempo_resolucion_h: string
  incidentes_criticos: number
  entregas_a_tiempo_pct: string
  satisfaccion: string
}

export type ResumenImportacion = {
  entidad: string
  filas: number
  registros: number
  omitidos: number
  eventos: number
}

/** Solo para mostrar: los montos llegan como texto decimal y no se operan en el navegador. */
export function formatoMoneda(valor: string, moneda: string): string {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: moneda,
    maximumFractionDigits: 4,
  }).format(Number(valor))
}

export function formatoFecha(iso: string): string {
  const [anio, mes, dia] = iso.split("-").map(Number)
  return new Date(anio, mes - 1, dia).toLocaleDateString("es-MX", { dateStyle: "medium" })
}
