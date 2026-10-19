import { useNegociacion, type VistaPortal } from "@/negociacion"

// Tipos de services/negociacion/src/negociacion/api/esquemas.py (Evaluacion, AdjudicacionSalida) y de
// services/inteligencia/src/inteligencia/api/esquemas.py (RecomendacionSalida, CandidatoSalida,
// RiesgoSalida, SensibilidadSalida, TipoCambioSalida): un campo nuevo va en los dos.
// Montos y precios llegan como texto decimal; fechas e identificadores, como texto; puntajes, como número.

export type Criterio = "costo" | "desempeno" | "riesgo" | "sla"
export type Pesos = Record<Criterio, number>

export type Riesgo = {
  valor: number
  nivel: "bajo" | "medio" | "alto"
  concentracion: number
  tendencia: number
  sin_historial: boolean
}
export type Candidato = {
  id: string
  proveedor_id: string
  nombre: string
  costo_total: string
  costo_total_mxn: string
  desempeno: number
  riesgo: Riesgo
  sla: string | null
  normalizados: Record<Criterio, number>
  aportes: Record<Criterio, number>
  puntaje: number
  lugar: number
}
export type Sensibilidad = {
  criterio: Criterio
  peso_actual: number
  peso_necesario: number | null
  ganaria: string | null
}
export type Recomendacion = {
  pesos: Pesos
  umbral_aprobacion: string
  tipo_cambio: { periodo: string; usd_mxn: string } | null
  candidatos: Candidato[]
  recomendado: string
  margen: number
  explicacion: string[]
  sensibilidad: Sensibilidad[]
}
export type MotivoAprobacion = "umbral" | "fuera_de_limites"
export type Adjudicacion = {
  id: string
  sesion_id: string
  propuesta_por_id: string
  propuesta_por_nombre: string
  propuesta_en: string
  recomendada_sesion_id: string
  se_aparta: boolean
  justificacion: string | null
  costo_total: string
  costo_total_mxn: string
  requiere_aprobacion: boolean
  motivo_aprobacion: MotivoAprobacion[]
  recomendacion: Recomendacion
  estado: "pendiente" | "aprobada" | "rechazada" | "directa"
  decidida_por_nombre: string | null
  decidida_en: string | null
  motivo_rechazo: string | null
  contrato_folio: string | null
}
export type Evaluacion = {
  recomendacion: Recomendacion | null
  vigente: Adjudicacion | null
  historial: Adjudicacion[]
}

export const PESOS_POR_OMISION: Pesos = {
  costo: 40,
  desempeno: 30,
  riesgo: 15,
  sla: 15,
}
// El orden de «?pesos=» en el servicio.
const CRITERIOS: Criterio[] = ["costo", "desempeno", "riesgo", "sla"]

export const NOMBRES_CRITERIO: Record<Criterio, string> = {
  costo: "Costo total",
  desempeno: "Desempeño",
  riesgo: "Riesgo",
  sla: "SLA",
}
export const NOMBRES_NIVEL_RIESGO: Record<Riesgo["nivel"], string> = {
  bajo: "Bajo",
  medio: "Medio",
  alto: "Alto",
}
export const NOMBRES_MOTIVO: Record<MotivoAprobacion, string> = {
  umbral: "Supera el umbral de aprobación",
  fuera_de_limites: "Fuera de límites",
}
// Copia de services/negociacion/src/negociacion/correo.py (spec §4.6): si cambia allá, cambia aquí.
export const TEXTOS_RESULTADO: Record<
  NonNullable<VistaPortal["resultado"]>,
  string
> = {
  adjudicada:
    "Su oferta fue adjudicada; el equipo de compras se pondrá en contacto",
  no_elegida: "La negociación se adjudicó a otra propuesta",
  desierta: "La negociación se declaró desierta",
}

/** Un entero de 1 a 3 dígitos, sin signo ni punto: el mismo criterio que el servicio. */
const ENTERO = /^\d{1,3}$/

function entero(valor: string): number | null {
  return ENTERO.test(valor) ? Number(valor) : null
}

/** Los pesos en el orden de «?pesos=»: costo, desempeño, riesgo y SLA. */
export function textoPesos(p: Pesos): string {
  return CRITERIOS.map((criterio) => p[criterio]).join(",")
}

/** La suma de los campos; lo que no es entero cuenta 0 (el total se muestra mientras se escribe). */
export function totalPesos(campos: Record<Criterio, string>): number {
  return CRITERIOS.reduce(
    (total, criterio) => total + (entero(campos[criterio]) ?? 0),
    0
  )
}

/** Los pesos si cada campo es un entero y suman 100; si no, null. */
export function pesosValidos(campos: Record<Criterio, string>): Pesos | null {
  const pesos = {} as Pesos
  for (const criterio of CRITERIOS) {
    const valor = entero(campos[criterio])
    if (valor === null) return null
    pesos[criterio] = valor
  }
  // Enteros sin signo que suman 100: ninguno pasa de 100 (igual que el servicio).
  return totalPesos(campos) === 100 ? pesos : null
}

/**
 * Si el costo supera el umbral, con `>` estricto como el servicio. Solo sirve para anticipar el
 * texto de la confirmación; quien decide es el servicio.
 */
// ponytail: Number es exacto para montos con 2 decimales hasta unos 9e13; más allá, comparar con enteros.
export function superaUmbral(costoMxn: string, umbral: string): boolean {
  return Number(costoMxn) > Number(umbral)
}

/** Por qué la propuesta pide aprobación (spec §4.3): el umbral, y luego los límites de la sesión. */
export function razonesAprobacion(
  costoMxn: string,
  umbral: string,
  fueraDeLimites: boolean
): MotivoAprobacion[] {
  const motivos: MotivoAprobacion[] = []
  if (superaUmbral(costoMxn, umbral)) motivos.push("umbral")
  if (fueraDeLimites) motivos.push("fuera_de_limites")
  return motivos
}

/** La evaluación del evento; con `pesos`, la recomendación con esos pesos en vez de los configurados. */
export function useEvaluacion(eventoId: string, pesos: Pesos | null) {
  const consulta = pesos ? `?pesos=${textoPesos(pesos)}` : ""
  return useNegociacion<Evaluacion>(
    `/eventos/${encodeURIComponent(eventoId)}/evaluacion${consulta}`
  )
}
