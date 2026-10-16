import { describe, expect, it } from "vitest"
import {
  aEntradaFechaHora,
  desdeEntradaFechaHora,
  formatoFechaHora,
  haceCuanto,
  hoyEnMexico,
} from "@/fechas"

const AHORA = new Date("2026-10-08T18:00:00Z")

describe("haceCuanto", () => {
  it.each([
    ["2026-10-08T17:59:30Z", "hace un momento"],
    ["2026-10-08T17:45:00Z", "hace 15 minutos"],
    ["2026-10-08T16:00:00Z", "hace 2 horas"],
    ["2026-10-07T18:00:00Z", "ayer"],
    ["2026-09-08T18:00:00Z", "hace 1 mes"],
  ])("%s → %s", (iso, esperado) => {
    expect(haceCuanto(iso, AHORA)).toBe(esperado)
  })
})

describe("formatoFechaHora", () => {
  it("muestra la hora de la Ciudad de México", () => {
    // 05:30 UTC = 23:30 del día anterior en la Ciudad de México.
    expect(formatoFechaHora("2026-10-08T05:30:00Z")).toMatch(
      /7 oct 2026.*11:30/
    )
  })
})

describe("campos de fecha y hora", () => {
  it("da el valor de un datetime-local en la hora de la Ciudad de México", () => {
    expect(aEntradaFechaHora(new Date("2026-10-22T00:05:00Z"))).toBe(
      "2026-10-21T18:05"
    )
    // La medianoche es 00 (no 24).
    expect(aEntradaFechaHora(new Date("2026-10-22T06:00:00Z"))).toBe(
      "2026-10-22T00:00"
    )
  })

  it("lee el valor del campo como hora de la Ciudad de México y da el instante ISO, o null si no sirve", () => {
    expect(desdeEntradaFechaHora("2026-10-21T18:00")).toBe(
      "2026-10-22T00:00:00.000Z"
    )
    expect(desdeEntradaFechaHora("2026-10-21T18:00:30")).toBe(
      "2026-10-22T00:00:30.000Z"
    )
    expect(desdeEntradaFechaHora("")).toBeNull()
    expect(desdeEntradaFechaHora("mañana")).toBeNull()
    expect(desdeEntradaFechaHora("2026-13-45T25:00")).toBeNull()
  })

  it("da la fecha de hoy en la Ciudad de México", () => {
    // 05:30 UTC del 8 = 23:30 del 7 en la Ciudad de México.
    expect(hoyEnMexico(new Date("2026-10-08T05:30:00Z"))).toBe("2026-10-07")
  })
})
