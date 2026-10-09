import { describe, expect, it } from "vitest"
import { formatoFechaHora, haceCuanto } from "@/fechas"

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
