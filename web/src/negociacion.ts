import {
  useQuery,
  type QueryKey,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { aEntradaFechaHora, desdeEntradaFechaHora } from "@/fechas"
import { formatoDecimal } from "@/inteligencia"
import { formatoMoneda } from "@/tipos"

// Tipos de services/negociacion/src/negociacion/api/esquemas.py: un campo nuevo va en los dos.
// Montos, precios y valores llegan como texto decimal; las utilidades, como número de 0 a 1.

export type TipoEvento = "compra" | "renovacion"
export type EstadoEvento =
  "borrador" | "abierto" | "en_evaluacion" | "cancelado"
export type EstadoSesion =
  | "invitada"
  | "activa"
  | "acuerdo_tentativo"
  | "sin_acuerdo"
  | "expirada"
  | "escalada"
export type Modo = "agente" | "comprador"
export type Estilo = "firme" | "balanceado" | "flexible"
export type ClavePalanca =
  | "precio"
  | "plazo_meses"
  | "plazo_pago_dias"
  | "sla_disponibilidad"
  | "tope_aumento_pct"
  | "cuota_implementacion"
export type Autor = "proveedor" | "agente" | "comprador" | "sistema"
export type EstadoCorreo = "pendiente" | "enviado" | "fallido"

export type Banda = {
  p25: string
  p50: string
  p75: string
  metodo: string
  confianza: string
  observaciones: number
}
export type LineaEvento = {
  id: string
  orden: number
  codigo_servicio: string
  nombre: string
  unidad: string
  cantidad: string
  precio_vigente: string | null
  ideal: string | null
  limite: string | null
  referencia: Banda | null
}
export type PalancaEvento = {
  clave: ClavePalanca
  nombre: string
  unidad: string
  activa: boolean
  peso: number
  ideal: string | null
  limite: string | null
  vigente: string | null
}
export type Problema = { campo: string; mensaje: string }
export type SesionResumen = {
  id: string
  proveedor_id: string
  proveedor_nombre: string
  estado: EstadoSesion
  modo: Modo
  ronda: number
  utilidad: number | null
  correo_estado: EstadoCorreo
  correo_error: string | null
  fuera_de_limites: boolean
  actualizado_en: string
}
export type Evento = {
  id: string
  folio: string
  tipo: TipoEvento
  titulo: string
  moneda: string
  plazo_meses: number
  estado: EstadoEvento
  fecha_limite: string
  rondas_max: number
  estilo: Estilo
  contrato_origen_id: string | null
  proveedor_vigente_id: string | null
  invitados: { id: string; nombre: string }[]
  lineas: LineaEvento[]
  palancas: PalancaEvento[]
  referencia_fecha: string | null
  creado_por_nombre: string
  creado_en: string
  publicado_en: string | null
  cerrado_en: string | null
  motivo_cancelacion: string | null
  version: number
  errores: Problema[]
  avisos: Problema[]
  sesiones: SesionResumen[]
}
export type EventoResumen = {
  id: string
  folio: string
  tipo: TipoEvento
  titulo: string
  estado: EstadoEvento
  fecha_limite: string
  invitados: number
  sesiones: number
  acuerdos: number
  escaladas: number
  creado_por_nombre: string
  creado_en: string
}
export type PaginaEventos = { total: number; elementos: EventoResumen[] }
export type EnlaceInvitacion = {
  sesion_id: string
  proveedor_nombre: string
  destinatario: string
  enlace: string
  correo_estado: EstadoCorreo
}
export type Publicacion = { evento: Evento; enlaces: EnlaceInvitacion[] }
export type Valores = {
  precios: Record<string, string>
  palancas: Record<string, string>
}
export type AccionAgente =
  "aceptar" | "contraofertar" | "cerrar_sin_acuerdo" | "pedir_aclaracion"
/** La traza del motor (spec §6.6); aquí solo los campos que la interfaz explica. */
export type Decision = {
  accion: AccionAgente
  t: number
  T: number
  utilidad_oferta: number
  valida: boolean
  hay_mejor_oferta: boolean
  objetivo?: number
  utilidad_contraoferta?: number
}
export type MensajeSesion = {
  id: string
  autor: Autor
  texto: string
  ronda: number
  fecha: string
  oferta_id: string | null
  decision: Decision | null
}
export type OfertaSesion = {
  id: string
  autor: Exclude<Autor, "sistema">
  ronda: number
  valores: Valores
  utilidad: number
  valida: boolean
  fuera_de_limites_confirmada: boolean
  fecha: string
}
export type LineaSesion = {
  id: string
  nombre: string
  unidad: string
  cantidad: string
  ideal: string | null
  limite: string | null
}
export type PalancaSesion = {
  clave: ClavePalanca
  nombre: string
  unidad: string
  peso: number
  ideal: string | null
  limite: string | null
}
export type SesionDetalle = {
  id: string
  evento_id: string
  folio: string
  titulo: string
  moneda: string
  proveedor_id: string
  proveedor_nombre: string
  destinatario: string
  estado: EstadoSesion
  modo: Modo
  ronda: number
  rondas_max: number
  fuera_de_limites: boolean
  correo_estado: EstadoCorreo
  correo_error: string | null
  lineas: LineaSesion[]
  palancas: PalancaSesion[]
  mensajes: MensajeSesion[]
  ofertas: OfertaSesion[]
}
export type LineaPortal = {
  id: string
  codigo_servicio: string
  nombre: string
  unidad: string
  cantidad: string
}
export type PalancaPortal = {
  clave: ClavePalanca
  nombre: string
  unidad: string
}
export type MensajePortal = {
  autor: Autor
  texto: string
  ronda: number
  fecha: string
  oferta: Valores | null
}
export type VistaPortal = {
  folio: string
  titulo: string
  moneda: string
  fecha_limite: string
  rondas_max: number
  rondas_restantes: number
  estado: EstadoSesion
  atendido_por: "agente" | "persona"
  pide_confirmacion: boolean
  lineas: LineaPortal[]
  palancas: PalancaPortal[]
  mensajes: MensajePortal[]
  ultima_propuesta: Valores | null
}

export const NOMBRES_TIPO: Record<TipoEvento, string> = {
  compra: "Compra",
  renovacion: "Renovación",
}

export const NOMBRES_ESTADO_EVENTO: Record<EstadoEvento, string> = {
  borrador: "Borrador",
  abierto: "Abierta",
  en_evaluacion: "En evaluación",
  cancelado: "Cancelada",
}

export const NOMBRES_ESTADO_SESION: Record<EstadoSesion, string> = {
  invitada: "Invitada",
  activa: "Activa",
  acuerdo_tentativo: "Acuerdo tentativo",
  sin_acuerdo: "Sin acuerdo",
  expirada: "Expirada",
  escalada: "Escalada",
}

export const NOMBRES_AUTOR: Record<Autor, string> = {
  proveedor: "Proveedor",
  agente: "Agente",
  comprador: "Compras",
  sistema: "Sistema",
}

export const ESTILOS: { clave: Estilo; nombre: string; descripcion: string }[] =
  [
    {
      clave: "firme",
      nombre: "Firme",
      descripcion:
        "Cede muy poco hasta las últimas rondas: busca el mejor valor aunque tome más rondas.",
    },
    {
      clave: "balanceado",
      nombre: "Balanceado",
      descripcion:
        "Un punto medio: cede poco al principio y más hacia el final.",
    },
    {
      clave: "flexible",
      nombre: "Flexible",
      descripcion:
        "Cede de forma pareja desde la primera ronda: prioriza llegar a un acuerdo.",
    },
  ]

/** Paso de cada término en los campos numéricos: la precisión de la spec §6.4. */
export const PASOS: Record<ClavePalanca, string> = {
  precio: "0.01",
  plazo_meses: "1",
  plazo_pago_dias: "1",
  sla_disponibilidad: "0.01",
  tope_aumento_pct: "0.1",
  cuota_implementacion: "0.01",
}

const FINALES: readonly EstadoSesion[] = [
  "acuerdo_tentativo",
  "sin_acuerdo",
  "expirada",
]

/** Acuerdo, sin acuerdo o expirada: ya no recibe ofertas. «Escalada» no es final. */
export function esFinal(estado: EstadoSesion): boolean {
  return FINALES.includes(estado)
}

type OpcionesConsulta<T> = Omit<
  UseQueryOptions<T, Error, T>,
  "queryKey" | "queryFn" | "enabled"
> & { enabled?: boolean }

/** GET a /api/negociacion{ruta}. La clave común ["negociacion", …] permite invalidarlas juntas. */
export function useNegociacion<T>(
  ruta: string,
  opciones: OpcionesConsulta<T> = {}
): UseQueryResult<T, Error> {
  const token = useToken()
  const queryKey: QueryKey = ["negociacion", ruta]
  return useQuery({
    ...opciones,
    queryKey,
    queryFn: () => pedir<T>(`/negociacion${ruta}`, token),
    enabled: Boolean(token) && (opciones.enabled ?? true),
  })
}

/** Qué tan buena es una oferta para el comprador: "41 %"; sin oferta, "—". */
export function formatoUtilidad(utilidad: number | null): string {
  return utilidad === null ? "—" : `${Math.round(utilidad * 100)} %`
}

/** Un valor de palanca con su unidad; los montos (unidad = moneda), con el formato de moneda. */
export function formatoTermino(
  valor: string,
  unidad: string,
  moneda: string
): string {
  if (unidad === moneda) return formatoMoneda(valor, moneda)
  // Solo presentación: el valor exacto no se opera en el navegador.
  return `${formatoDecimal(Number(valor), 2)} ${unidad}`
}

/** La traza del motor en palabras, para «¿Por qué respondió esto?». */
export function explicarDecision(d: Decision): string {
  const vale = `La oferta del proveedor vale ${formatoUtilidad(d.utilidad_oferta)} para usted`
  switch (d.accion) {
    case "pedir_aclaracion":
      return "Algún precio de la oferta quedó muy lejos de lo usual (menos de la décima parte o más de 10 veces la referencia de precio o, si no hay referencia, el límite), así que el agente pidió al proveedor confirmarlo. Esta respuesta no cuenta como ronda."
    case "aceptar":
      return `${vale}, respeta sus límites y alcanza lo que el agente pediría en esta ronda (${formatoUtilidad(d.utilidad_contraoferta ?? 0)}), así que la aceptó como acuerdo tentativo.`
    case "cerrar_sin_acuerdo":
      return `Era la última ronda (${d.t} de ${d.T}) y la oferta cruzaba al menos uno de sus límites, así que el agente cerró sin acuerdo.`
    case "contraofertar": {
      const partes = [
        `${vale}; en esta ronda (${d.t} de ${d.T}) el agente busca al menos ${formatoUtilidad(d.objetivo ?? 0)}, así que propuso valores que valen ${formatoUtilidad(d.utilidad_contraoferta ?? 0)} para usted.`,
      ]
      if (!d.valida)
        partes.push("La oferta cruzaba al menos uno de sus límites.")
      if (d.hay_mejor_oferta)
        partes.push(
          "Mencionó que hay propuestas más competitivas, sin decir de quién ni cuánto."
        )
      if (d.t + 1 === d.T) partes.push("Pidió la mejor y última oferta.")
      return partes.join(" ")
    }
  }
}

/** Página para renovar un contrato vigente (spec §10.1, botón «Renovar»). */
export function rutaRenovacion(
  proveedorId: string,
  contratoId: string
): string {
  return `/negociaciones/nueva?${new URLSearchParams({
    proveedor: proveedorId,
    contrato: contratoId,
  })}`
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Solo un UUID llega a la API como id (la URL se puede editar a mano). */
export function esUuid(valor: string | null): valor is string {
  return valor !== null && UUID.test(valor)
}

/** Fecha límite sugerida: dentro de una semana, a las 18:00 de la Ciudad de México. */
export function sugerirFechaLimite(ahora: Date = new Date()): Date {
  const dia = aEntradaFechaHora(new Date(ahora.getTime() + 7 * 86_400_000))
  return new Date(desdeEntradaFechaHora(`${dia.slice(0, 10)}T18:00`)!)
}

/**
 * Claves de `Idempotency-Key`: la misma al reintentar el mismo cuerpo (un corte de red no duplica
 * la oferta) y otra si el cuerpo cambió o el envío anterior ya se completó.
 */
export function crearClaves() {
  let ultimo: { cuerpo: string; clave: string } | null = null
  return {
    para(cuerpo: string): string {
      if (!ultimo || ultimo.cuerpo !== cuerpo)
        ultimo = { cuerpo, clave: crypto.randomUUID() }
      return ultimo.clave
    },
    olvidar(): void {
      ultimo = null
    },
  }
}
