import { describe, expect, it } from "vitest"
import { enteroPositivo, unoDe } from "@/parametros"

describe("enteroPositivo", () => {
  it.each([
    ["3", 3],
    [null, 1],
    ["", 1],
    ["abc", 1],
    ["0", 1],
    ["-2", 1],
    ["2.5", 1],
  ])("%s → %d", (valor, esperado) => {
    expect(enteroPositivo(valor, 1)).toBe(esperado)
  })

  it("limita al máximo", () => {
    expect(enteroPositivo("999999999", 1, 40_000)).toBe(40_000)
  })
})

describe("unoDe", () => {
  it("acepta solo valores permitidos", () => {
    expect(unoDe("nube", ["nube", "soporte"])).toBe("nube")
    expect(unoDe("hackeo", ["nube", "soporte"])).toBeNull()
    expect(unoDe(null, ["nube"])).toBeNull()
  })
})
