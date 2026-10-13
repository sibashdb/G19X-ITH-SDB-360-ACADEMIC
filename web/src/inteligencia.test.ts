import { describe, expect, it } from "vitest"
import {
  formatoPorcentaje,
  formatoPuntuacion,
  fraccionComoPorcentaje,
  montoCorto,
  porUnidad,
  rangoPuntuacion,
  rutaDeAlerta,
  type Alerta,
} from "@/inteligencia"

const ALERTA: Alerta = {
  id: "vencimiento:c1",
  tipo: "vencimiento",
  severidad: "alta",
  titulo: "Vence en 12 días: CT-0001",
  explicacion:
    "El contrato con Nube Andina (Nube pública) termina el 24/10/2026.",
  entidad_tipo: "contrato",
  entidad_id: "c1",
  entidad_nombre: "CT-0001",
  proveedor_id: "p 1",
  proveedor_nombre: "Nube Andina",
  fecha: "2026-10-24",
  ahorro_potencial: null,
  moneda: null,
}

describe("formatos de la inteligencia", () => {
  it("abrevia las cifras grandes del Tablero", () => {
    expect(montoCorto("48200000.00")).toBe("$48.2 M MXN")
    expect(montoCorto("1174700000.00")).toBe("$1,174.7 M MXN")
    expect(montoCorto("12500.00")).toBe("$12.5 mil MXN")
    expect(montoCorto("950.5")).toBe("$950.50 MXN")
  })

  it("da un decimal a las puntuaciones y a los porcentajes", () => {
    expect(formatoPuntuacion(72.44)).toBe("72.4")
    expect(formatoPuntuacion(6)).toBe("6.0")
    expect(formatoPorcentaje(8.3)).toBe("8.3 %")
    expect(formatoPorcentaje(-3.1)).toBe("-3.1 %")
    expect(fraccionComoPorcentaje("0.083000")).toBe("8.3 %")
  })

  it("dice la unidad del precio en palabras", () => {
    expect(porUnidad("usuario_mes")).toBe("por usuario al mes")
    expect(porUnidad("vcpu_mes")).toBe("por vCPU al mes")
    expect(porUnidad("otra")).toBe("por otra")
  })

  it("ubica la puntuación en su rango según el umbral de riesgo", () => {
    expect(rangoPuntuacion(39.9, 40)).toBe("bajo")
    expect(rangoPuntuacion(40, 40)).toBe("medio")
    expect(rangoPuntuacion(69.9, 40)).toBe("medio")
    expect(rangoPuntuacion(70, 40)).toBe("alto")
    // Con un umbral por encima de 70 no hay rango medio: o está en riesgo o está bien.
    expect(rangoPuntuacion(72, 75)).toBe("bajo")
    expect(rangoPuntuacion(75, 75)).toBe("alto")
  })

  it("lleva cada alerta a su proveedor, en la pestaña de contratos si es de un contrato", () => {
    expect(rutaDeAlerta(ALERTA)).toBe("/proveedores/p%201?pestana=contratos")
    expect(
      rutaDeAlerta({ ...ALERTA, entidad_tipo: "proveedor", entidad_id: "p 1" })
    ).toBe("/proveedores/p%201")
  })
})
