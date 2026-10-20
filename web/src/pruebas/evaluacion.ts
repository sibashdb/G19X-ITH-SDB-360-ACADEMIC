import type {
  Adjudicacion,
  Candidato,
  Evaluacion,
  Recomendacion,
} from "@/adjudicacion"

// Datos de prueba de la evaluación de una negociación con dos acuerdos tentativos (más una sesión
// sin acuerdo), compartidos por las pruebas de la evaluación, de adjudicar y de aprobar.

export const ID = "5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42"
export const RUTA = `/api/negociacion/eventos/${ID}`
export const EVALUACION = `${RUTA}/evaluacion`

export const sesion = (
  id: string,
  proveedor: string,
  estado: string,
  fueraDeLimites = false
) => ({
  id,
  proveedor_id: `p-${id}`,
  proveedor_nombre: proveedor,
  estado,
  modo: "agente",
  ronda: 3,
  utilidad: 0.62,
  correo_estado: "enviado",
  correo_error: null,
  fuera_de_limites: fueraDeLimites,
  actualizado_en: "2026-10-14T18:30:00Z",
})

/** La negociación en evaluación; las pruebas cambian `estado` y `sesiones` según el caso. */
export const EVENTO = {
  id: ID,
  folio: "NEG-2026-0001",
  tipo: "compra",
  titulo: "Licencias de correo 2027",
  moneda: "MXN",
  plazo_meses: 12,
  estado: "en_evaluacion",
  fecha_limite: "2026-10-21T23:00:00Z",
  rondas_max: 6,
  estilo: "balanceado",
  contrato_origen_id: null,
  proveedor_vigente_id: null,
  invitados: [
    { id: "p-s1", nombre: "Nube Norte" },
    { id: "p-s2", nombre: "Datos del Sur" },
    { id: "p-s3", nombre: "Cielo Azul" },
  ],
  lineas: [],
  palancas: [],
  referencia_fecha: null,
  creado_por_nombre: "Ana López",
  creado_en: "2026-10-14T18:00:00Z",
  publicado_en: "2026-10-14T18:00:00Z",
  cerrado_en: "2026-10-21T23:00:00Z",
  motivo_cancelacion: null,
  motivo_desierta: null,
  version: 5,
  errores: [],
  avisos: [],
  sesiones: [
    sesion("s1", "Nube Norte", "acuerdo_tentativo"),
    sesion("s2", "Datos del Sur", "acuerdo_tentativo", true),
    sesion("s3", "Cielo Azul", "sin_acuerdo"),
  ],
}

const NORMALIZADOS = { costo: 1, desempeno: 1, riesgo: 1, sla: 1 }

export const NUBE_NORTE: Candidato = {
  id: "s1",
  proveedor_id: "p-s1",
  nombre: "Nube Norte",
  costo_total: "480000.00",
  costo_total_mxn: "480000.00",
  desempeno: 82.4,
  riesgo: {
    valor: 0.2,
    nivel: "bajo",
    concentracion: 0.35,
    tendencia: 0.1,
    sin_historial: false,
  },
  sla: "99.90",
  normalizados: NORMALIZADOS,
  aportes: { costo: 40, desempeno: 24, riesgo: 12, sla: 12 },
  puntaje: 78.3,
  lugar: 1,
}
export const DATOS_DEL_SUR: Candidato = {
  id: "s2",
  proveedor_id: "p-s2",
  nombre: "Datos del Sur",
  costo_total: "510000.00",
  costo_total_mxn: "510000.00",
  desempeno: 75,
  riesgo: {
    valor: 0.5,
    nivel: "medio",
    concentracion: 0.6,
    tendencia: 0.25,
    sin_historial: true,
  },
  sla: null,
  normalizados: NORMALIZADOS,
  aportes: { costo: 20, desempeno: 20, riesgo: 6, sla: 0 },
  puntaje: 66.1,
  lugar: 2,
}

export const RECOMENDACION: Recomendacion = {
  pesos: { costo: 40, desempeno: 30, riesgo: 15, sla: 15 },
  umbral_aprobacion: "500000.00",
  tipo_cambio: null,
  candidatos: [NUBE_NORTE, DATOS_DEL_SUR],
  recomendado: "s1",
  margen: 12.2,
  explicacion: [
    "Nube Norte obtiene el mejor puntaje: 78.3 contra 66.1 de Datos del Sur.",
    "Costo: $480,000.00 aporta 40.0 puntos con un peso de 40.",
    "Si el peso del costo bajara a 10, Datos del Sur quedaría primero.",
  ],
  sensibilidad: [],
}

/** Lo que devuelve el servicio en evaluación: la recomendación y ninguna propuesta. */
export const CON_RECOMENDACION: Evaluacion = {
  recomendacion: RECOMENDACION,
  vigente: null,
  historial: [],
}
export const SIN_ACUERDOS: Evaluacion = {
  recomendacion: null,
  vigente: null,
  historial: [],
}

/**
 * Lo que devuelve el servicio con una propuesta vigente (la de Ana López, `ana-1`): la evaluación
 * con la foto guardada. `cambios` ajusta la propuesta (p. ej. otro autor o una justificación).
 */
export const propuesta = (
  sesionId: string,
  estado: Adjudicacion["estado"],
  cambios: Partial<Adjudicacion> = {}
): Evaluacion => ({
  recomendacion: RECOMENDACION,
  historial: [],
  vigente: {
    id: "a1",
    sesion_id: sesionId,
    propuesta_por_id: "ana-1",
    propuesta_por_nombre: "Ana López",
    propuesta_en: "2026-10-22T16:00:00Z",
    recomendada_sesion_id: "s1",
    se_aparta: sesionId !== "s1",
    justificacion: null,
    costo_total: "480000.00",
    costo_total_mxn: "480000.00",
    requiere_aprobacion: estado === "pendiente",
    motivo_aprobacion: [],
    recomendacion: RECOMENDACION,
    estado,
    decidida_por_nombre: null,
    decidida_en: null,
    motivo_rechazo: null,
    contrato_folio: null,
    ...cambios,
  },
})
