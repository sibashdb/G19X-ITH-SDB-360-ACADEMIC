const ZONA = "America/Mexico_City"

/** Fecha y hora en la Ciudad de México (p. ej. "7 oct 2026, 11:30 p.m."). */
export function formatoFechaHora(iso: string): string {
  return new Date(iso).toLocaleString("es-MX", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: ZONA,
  })
}

const UNIDADES: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
]

/** Tiempo relativo en español ("hace 2 horas", "ayer"). */
export function haceCuanto(iso: string, ahora: Date = new Date()): string {
  const segundos = Math.round(
    (new Date(iso).getTime() - ahora.getTime()) / 1000
  )
  for (const [unidad, tamano] of UNIDADES) {
    if (Math.abs(segundos) >= tamano) {
      // "auto" solo para los días ("ayer"); en las demás unidades da "el mes pasado" en lugar de "hace 1 mes".
      const numeric = unidad === "day" ? "auto" : "always"
      return new Intl.RelativeTimeFormat("es-MX", { numeric }).format(
        Math.trunc(segundos / tamano),
        unidad
      )
    }
  }
  return "hace un momento"
}

// ponytail: la Ciudad de México no cambia de horario desde 2022; si lo retomara, calcular el desfase con Intl.
const DESFASE = "-06:00"

const FORMA_ENTRADA = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(:\d{2})?$/

const PARTES = new Intl.DateTimeFormat("en-CA", {
  timeZone: ZONA,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
})

/** "2026-10-21T18:00" en la hora de la Ciudad de México, para un <input type="datetime-local">. */
export function aEntradaFechaHora(fecha: Date): string {
  const p = Object.fromEntries(
    PARTES.formatToParts(fecha).map(({ type, value }) => [type, value])
  )
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`
}

/**
 * El valor de un <input type="datetime-local"> (hora de la Ciudad de México) como instante ISO;
 * null si está vacío o no sirve.
 */
export function desdeEntradaFechaHora(valor: string): string | null {
  const forma = FORMA_ENTRADA.exec(valor)
  if (!forma) return null
  const fecha = new Date(
    `${forma[1]}T${forma[2]}${forma[3] ?? ":00"}${DESFASE}`
  )
  return Number.isNaN(fecha.getTime()) ? null : fecha.toISOString()
}

/** Hoy en la Ciudad de México, "AAAA-MM-DD", para compararlo con las fechas de los contratos. */
export function hoyEnMexico(ahora: Date = new Date()): string {
  return ahora.toLocaleDateString("en-CA", { timeZone: ZONA })
}
