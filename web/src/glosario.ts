/** Definiciones en lenguaje llano de los términos técnicos de la plataforma. */
export const GLOSARIO = {
  percentiles: {
    termino: "P25 · P50 · P75",
    definicion:
      "Precio bajo, típico y alto del mercado: el 25 %, 50 % y 75 % de los contratos comparables cuestan eso o menos.",
  },
  precioReferencia: {
    termino: "Precio de referencia",
    definicion:
      "Lo que se paga normalmente en el mercado por el servicio, la cantidad y el plazo indicados.",
  },
  sobreprecio: {
    termino: "Sobreprecio",
    definicion: "Paga más que el 75 % de los contratos comparables.",
  },
  ahorroPotencial: {
    termino: "Ahorro potencial",
    definicion:
      "Lo que ahorraría en lo que resta del contrato si pagara el precio típico del mercado (P50).",
  },
  puntuacion: {
    termino: "Puntuación",
    definicion:
      "Calificación de 0 a 100 del desempeño del proveedor en los últimos 12 meses, comparada con los proveedores de su categoría principal (o con todos, si su categoría tiene pocos).",
  },
  sla: {
    termino: "SLA",
    definicion:
      "Nivel de servicio comprometido en el contrato, como el porcentaje de disponibilidad.",
  },
  desempeno: {
    termino: "Desempeño",
    definicion:
      "Cumplimiento del SLA, tiempo de resolución, incidentes críticos, entregas a tiempo y satisfacción.",
  },
  historialCorto: {
    termino: "Historial corto",
    definicion:
      "Menos de 6 meses de datos: la puntuación se acerca al promedio de su categoría hasta tener más historia.",
  },
  bajaConfianza: {
    termino: "Baja confianza",
    definicion:
      "Hay pocos contratos comparables (menos de 8): el precio de referencia es una estimación.",
  },
  mape: {
    termino: "MAPE",
    definicion:
      "Error promedio del modelo al estimar el precio típico, como porcentaje del precio real: 10 % significa que se equivoca, en promedio, por una décima parte.",
  },
  percentil: {
    termino: "Percentil",
    definicion:
      "Posición de 0 a 100 frente a los proveedores con los que se compara: 80 significa que rinde mejor que el 80 % de ellos.",
  },
  lineaBase: {
    termino: "Línea base",
    definicion:
      "Precio de referencia calculado directamente con los contratos de los últimos 24 meses, sin el modelo de precios.",
  },
  palanca: {
    termino: "Palanca",
    definicion:
      "Un término del contrato que se negocia además del precio: plazo, plazo de pago, SLA, tope de aumento o cuota de implementación. Usted elige cuáles se negocian y cuánto pesa cada uno.",
  },
  ideal: {
    termino: "Ideal",
    definicion:
      "El valor que a usted le gustaría conseguir. El agente empieza pidiendo casi ese valor y cede poco a poco hacia el límite.",
  },
  limite: {
    termino: "Límite",
    definicion:
      "El peor valor que usted acepta. El agente nunca acuerda algo que lo cruce y nunca se lo muestra al proveedor.",
  },
  ronda: {
    termino: "Ronda",
    definicion:
      "Cada oferta del proveedor con la respuesta del agente. En la última ronda, el agente acepta si la oferta respeta sus límites o cierra sin acuerdo.",
  },
  acuerdoTentativo: {
    termino: "Acuerdo tentativo",
    definicion:
      "El proveedor aceptó o propuso una oferta que se registró como acuerdo. No es vinculante hasta que se adjudique y se apruebe; si sale de sus límites, se marca para el aprobador.",
  },
} as const satisfies Record<string, { termino: string; definicion: string }>

export type ClaveGlosario = keyof typeof GLOSARIO
