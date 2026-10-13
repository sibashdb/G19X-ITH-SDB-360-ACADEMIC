import {
  useQuery,
  type QueryKey,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import type { Categoria, Severidad, TipoAlerta } from "@/tipos"

// Tipos de services/inteligencia/src/inteligencia/api/esquemas.py: un campo nuevo va en los dos.
// Los montos y precios llegan como texto decimal; puntuaciones y percentiles, como número.

export type Confianza = "normal" | "baja"
export type Metodo = "linea_base" | "modelo"
export type ClaveComponente =
  "sla" | "resolucion" | "incidentes" | "entregas" | "satisfaccion"

export type Alerta = {
  id: string
  tipo: TipoAlerta
  severidad: Severidad
  titulo: string
  explicacion: string
  entidad_tipo: "contrato" | "proveedor"
  entidad_id: string
  entidad_nombre: string
  proveedor_id: string
  proveedor_nombre: string
  fecha: string
  ahorro_potencial: string | null
  moneda: string | null
}
export type PaginaAlertas = { total: number; elementos: Alerta[] }

export type Destacado = {
  proveedor_id: string
  nombre: string
  puntuacion: number
}
export type Vencimiento = {
  contrato_id: string
  folio: string
  proveedor_id: string
  proveedor: string
  servicios: string[]
  fecha_fin: string
  dias: number
  monto_mensual: string
}
export type TableroDatos = {
  fecha: string
  moneda: "MXN"
  gasto_anual: string
  variacion_pct: number | null
  por_vencer: number
  en_riesgo: number
  total_proveedores: number
  ahorro_potencial: string
  gasto_por_categoria: { categoria: Categoria; monto: string }[]
  gasto_por_mes: { mes: string; monto: string }[]
  proximos_vencimientos: Vencimiento[]
  alertas_principales: Alerta[]
  mejores: Destacado[]
  peores: Destacado[]
  distribucion: { rango: string; proveedores: number }[]
}

export type ServicioPrecios = {
  codigo: string
  nombre: string
  categoria: Categoria
  unidad: string
  moneda: string
  observaciones: number
}
export type Referencia = {
  codigo: string
  moneda: string
  unidad: string
  cantidad: string
  plazo: number
  fecha: string
  p25: string
  p50: string
  p75: string
  metodo: Metodo
  version: number | null
  confianza: Confianza
  observaciones: number
}
export type HistorialPrecios = {
  codigo: string
  moneda: string
  cantidad: string
  puntos: {
    fecha: string
    precio: string
    cantidad: string
    folio: string
    proveedor: string
  }[]
  bandas: { mes: string; p25: string; p50: string; p75: string }[]
}
export type Sobreprecio = {
  contrato_id: string
  folio: string
  proveedor_id: string
  proveedor: string
  codigo_servicio: string
  servicio: string
  moneda: string
  precio: string
  p25: string
  p50: string
  p75: string
  fecha_fin: string
  ahorro_potencial: string
  ahorro_potencial_mxn: string
}

export type ProveedorConPuntuacion = {
  id: string
  rfc: string
  nombre: string
  tamano: string
  categorias: Categoria[]
  activo: boolean
  puntuacion: number | null
  confianza: Confianza | null
  tendencia: number | null
  gasto_anual: string
  contratos_vigentes: number
  alertas: number
  en_riesgo: boolean
}
export type PaginaProveedoresConPuntuacion = {
  total: number
  elementos: ProveedorConPuntuacion[]
}
export type ComponentePuntuacion = {
  kpi: ClaveComponente
  valor: number
  mediana_categoria: number
  percentil: number
}
export type Puntuacion = {
  proveedor_id: string
  categoria: Categoria | null
  puntuacion: number | null
  sin_ajuste: number | null
  meses: number
  historial_corto: boolean
  tendencia: number | null
  componentes: ComponentePuntuacion[]
  historial: { mes: string; puntuacion: number }[]
}
export type MercadoLinea = {
  contrato_id: string
  folio: string
  codigo_servicio: string
  servicio: string
  moneda: string
  precio: string
  posicion: "bajo_p25" | "justo" | "sobre_p75" | null
  p25: string | null
  p50: string | null
  p75: string | null
  metodo: Metodo | null
  confianza: Confianza | null
  ahorro_potencial: string
}
export type FilaRanking = {
  posicion: number
  proveedor_id: string
  nombre: string
  categoria: Categoria
  puntuacion: number
  componentes: Record<ClaveComponente, number>
  meses: number
  historial_corto: boolean
  tendencia: number | null
}

export type ConfiguracionInteligencia = {
  peso_sla: number
  peso_resolucion: number
  peso_incidentes: number
  peso_entregas: number
  peso_satisfaccion: number
  umbral_riesgo: number
  inflacion_anual: string
  actualizado_en: string | null
  actualizado_por: string | null
}
export type ModeloPrecios = {
  version: number
  entrenado_en: string
  origen: "manual" | "automatico"
  actor_nombre: string
  observaciones: number
  datos_hasta: string
  mape: string
  mape_linea_base: string
  cobertura: string
  pinball: string
  promovido: boolean
}
export type RegistroModelos = {
  entrenando: boolean
  activo: number | null
  en_uso: number | null
  ultimo_error: string | null
  elementos: ModeloPrecios[]
}
export type DatosInteligencia = {
  registros: Record<string, number>
  ultimo_evento: string | null
  modelo: ModeloPrecios | null
  en_uso: number | null
  entrenando: boolean
}

type OpcionesConsulta<T> = Omit<
  UseQueryOptions<T, Error, T>,
  "queryKey" | "queryFn" | "enabled"
> & { enabled?: boolean }

/** GET a /api/inteligencia{ruta}. La clave común ["inteligencia", …] permite invalidarlas juntas. */
export function useInteligencia<T>(
  ruta: string,
  opciones: OpcionesConsulta<T> = {}
): UseQueryResult<T, Error> {
  const token = useToken()
  const queryKey: QueryKey = ["inteligencia", ruta]
  return useQuery({
    ...opciones,
    queryKey,
    queryFn: () => pedir<T>(`/inteligencia${ruta}`, token),
    enabled: Boolean(token) && (opciones.enabled ?? true),
  })
}

export const UMBRAL_POR_OMISION = 40
export const PUNTUACION_ALTA = 70

/** Umbral de "en riesgo" configurado; mientras carga, o si la consulta falla, el valor por omisión. */
export function useUmbralRiesgo(): number {
  const configuracion =
    useInteligencia<ConfiguracionInteligencia>("/configuracion")
  return configuracion.data?.umbral_riesgo ?? UMBRAL_POR_OMISION
}

export type RangoPuntuacion = "bajo" | "medio" | "alto"

/** Bajo: en riesgo (menos que el umbral). Alto: desde 70, o desde el umbral si es mayor. */
export function rangoPuntuacion(
  valor: number,
  umbral: number
): RangoPuntuacion {
  if (valor < umbral) return "bajo"
  return valor >= Math.max(PUNTUACION_ALTA, umbral) ? "alto" : "medio"
}

const UN_DECIMAL = new Intl.NumberFormat("es-MX", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const DOS_DECIMALES = new Intl.NumberFormat("es-MX", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatoPuntuacion(valor: number): string {
  return UN_DECIMAL.format(valor)
}

export function formatoPorcentaje(valor: number): string {
  return `${UN_DECIMAL.format(valor)} %`
}

/** MAPE y cobertura llegan como fracción ("0.083000"): se muestran como "8.3 %". */
export function fraccionComoPorcentaje(valor: string): string {
  return formatoPorcentaje(Number(valor) * 100)
}

export function formatoDecimal(valor: number, decimales = 2): string {
  return valor.toLocaleString("es-MX", { maximumFractionDigits: decimales })
}

/** Cifras grandes en MXN para las tarjetas: "48200000.00" → "$48.2 M MXN". */
export function montoCorto(valor: string): string {
  const numero = Number(valor)
  // La unidad se elige con el valor ya redondeado a un decimal: 999,999.99 es "$1.0 M", no
  // "$1,000.0 mil". Es solo presentación; el monto exacto no se opera en el navegador.
  const milesRedondeados = Math.round(Math.abs(numero) / 100) / 10
  if (Math.abs(numero) >= 1e6 || milesRedondeados >= 1000)
    return `$${UN_DECIMAL.format(numero / 1e6)} M MXN`
  if (Math.abs(numero) >= 1e3)
    return `$${UN_DECIMAL.format(numero / 1e3)} mil MXN`
  return `$${DOS_DECIMALES.format(numero)} MXN`
}

const UNIDADES_EN_TEXTO: Record<string, string> = {
  usuario_mes: "usuario al mes",
  vcpu_mes: "vCPU al mes",
  gb_mes: "GB al mes",
  mes: "mes",
  hora: "hora",
  ticket: "ticket",
}

/** "usuario_mes" → "por usuario al mes", para acompañar un precio unitario. */
export function porUnidad(unidad: string): string {
  return `por ${UNIDADES_EN_TEXTO[unidad] ?? unidad}`
}

/** Los cinco indicadores de la puntuación, en el orden de la API. */
export const COMPONENTES: {
  clave: ClaveComponente
  nombre: string
  corto: string
  unidad: string
}[] = [
  { clave: "sla", nombre: "Cumplimiento de SLA", corto: "SLA", unidad: "%" },
  {
    clave: "resolucion",
    nombre: "Tiempo de resolución",
    corto: "Resolución",
    unidad: "h",
  },
  {
    clave: "incidentes",
    nombre: "Incidentes críticos",
    corto: "Incidentes",
    unidad: "al mes",
  },
  {
    clave: "entregas",
    nombre: "Entregas a tiempo",
    corto: "Entregas",
    unidad: "%",
  },
  {
    clave: "satisfaccion",
    nombre: "Satisfacción",
    corto: "Satisfacción",
    unidad: "de 5",
  },
]

/** Página donde se atiende una alerta: la del proveedor, en Contratos si es de un contrato. */
export function rutaDeAlerta(alerta: Alerta): string {
  const proveedor = `/proveedores/${encodeURIComponent(alerta.proveedor_id)}`
  return alerta.entidad_tipo === "contrato"
    ? `${proveedor}?pestana=contratos`
    : proveedor
}
