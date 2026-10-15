import { afterEach, describe, expect, it, vi } from "vitest"
import {
  crearClaves,
  esFinal,
  esUuid,
  explicarDecision,
  formatoTermino,
  formatoUtilidad,
  rutaRenovacion,
  sugerirFechaLimite,
  type Decision,
} from "@/negociacion"
import { formatoMoneda } from "@/tipos"

afterEach(() => {
  vi.restoreAllMocks()
})

const BASE: Decision = {
  accion: "contraofertar",
  t: 2,
  T: 6,
  utilidad_oferta: 0.413,
  valida: false,
  hay_mejor_oferta: false,
  objetivo: 0.49,
  utilidad_contraoferta: 0.492,
}

describe("explicarDecision", () => {
  it("explica una contraoferta con lo que vale la oferta y lo que busca el agente", () => {
    expect(explicarDecision(BASE)).toBe(
      "La oferta del proveedor vale 41 % para usted; en esta ronda (2 de 6) el agente busca al menos 49 %, así que propuso valores que valen 49 % para usted. La oferta cruzaba al menos uno de sus límites."
    )
  })

  it("menciona la presión competitiva y la última oferta sin dar cifras de otros", () => {
    const texto = explicarDecision({
      ...BASE,
      t: 5,
      valida: true,
      hay_mejor_oferta: true,
    })
    expect(texto).toContain(
      "Mencionó que hay propuestas más competitivas, sin decir de quién ni cuánto."
    )
    expect(texto).toContain("Pidió la mejor y última oferta.")
    expect(texto).not.toContain("cruzaba")
  })

  it("explica la aceptación, el cierre sin acuerdo y la aclaración", () => {
    expect(
      explicarDecision({
        ...BASE,
        accion: "aceptar",
        valida: true,
        utilidad_oferta: 0.52,
      })
    ).toBe(
      "La oferta del proveedor vale 52 % para usted, respeta sus límites y alcanza lo que el agente pediría en esta ronda (49 %), así que la aceptó como acuerdo tentativo."
    )
    expect(
      explicarDecision({ ...BASE, accion: "cerrar_sin_acuerdo", t: 6 })
    ).toBe(
      "Era la última ronda (6 de 6) y la oferta cruzaba al menos uno de sus límites, así que el agente cerró sin acuerdo."
    )
    expect(explicarDecision({ ...BASE, accion: "pedir_aclaracion" })).toBe(
      "Algún precio de la oferta quedó muy lejos de lo usual (menos de la décima parte o más de 10 veces la referencia de precio o, si no hay referencia, el límite), así que el agente pidió al proveedor confirmarlo. Esta respuesta no cuenta como ronda."
    )
  })
})

describe("formatos", () => {
  it("la utilidad va como porcentaje entero, y sin oferta como raya", () => {
    expect(formatoUtilidad(0.413)).toBe("41 %")
    expect(formatoUtilidad(1)).toBe("100 %")
    expect(formatoUtilidad(null)).toBe("—")
  })

  it("el valor de una palanca lleva su unidad, o el formato de moneda", () => {
    expect(formatoTermino("45", "días", "MXN")).toBe("45 días")
    expect(formatoTermino("99.5", "%", "MXN")).toBe("99.5 %")
    expect(formatoTermino("15000.00", "MXN", "MXN")).toBe(
      formatoMoneda("15000.00", "MXN")
    )
  })
})

describe("utilidades", () => {
  it("sabe qué estados de sesión son finales", () => {
    expect(esFinal("acuerdo_tentativo")).toBe(true)
    expect(esFinal("sin_acuerdo")).toBe(true)
    expect(esFinal("expirada")).toBe(true)
    expect(esFinal("escalada")).toBe(false)
    expect(esFinal("activa")).toBe(false)
  })

  it("arma la ruta de renovación con los parámetros codificados", () => {
    expect(rutaRenovacion("p 1", "c/2")).toBe(
      "/negociaciones/nueva?proveedor=p+1&contrato=c%2F2"
    )
  })

  it("reconoce un UUID y rechaza lo demás", () => {
    expect(esUuid("5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42")).toBe(true)
    expect(esUuid("abc")).toBe(false)
    expect(esUuid(null)).toBe(false)
  })

  it("sugiere la fecha límite a una semana, a las 18:00", () => {
    expect(sugerirFechaLimite(new Date(2026, 9, 14, 10, 30))).toEqual(
      new Date(2026, 9, 21, 18, 0)
    )
  })
})

describe("crearClaves", () => {
  it("reutiliza la clave al reintentar el mismo cuerpo y usa otra si cambia o ya se completó", () => {
    vi.spyOn(crypto, "randomUUID")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000001")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000002")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000003")
    const claves = crearClaves()
    expect(claves.para('{"a":1}')).toBe("00000000-0000-4000-8000-000000000001")
    expect(claves.para('{"a":1}')).toBe("00000000-0000-4000-8000-000000000001")
    expect(claves.para('{"a":2}')).toBe("00000000-0000-4000-8000-000000000002")
    claves.olvidar()
    expect(claves.para('{"a":2}')).toBe("00000000-0000-4000-8000-000000000003")
  })
})
