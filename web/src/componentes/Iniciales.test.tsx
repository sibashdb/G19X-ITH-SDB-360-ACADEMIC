import { describe, expect, it } from "vitest"
import { iniciales } from "@/componentes/Iniciales"

describe("iniciales", () => {
  it.each([
    ["Código Azteca S.A. de C.V.", "CA"],
    ["Nube Andina", "NA"],
    ["Consultores", "C"],
    ["Ñandú Digital S. de R.L.", "ÑD"],
    ["", "?"],
  ])("%s → %s", (nombre, esperado) => {
    expect(iniciales(nombre)).toBe(esperado)
  })
})
