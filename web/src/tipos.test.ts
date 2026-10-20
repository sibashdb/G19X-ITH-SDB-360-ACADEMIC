import { describe, expect, it } from "vitest"
import { conPuntoFinal } from "@/tipos"

describe("conPuntoFinal", () => {
  it("cierra la frase con un punto", () => {
    expect(conPuntoFinal("Se copió el enlace de Nube Norte")).toBe(
      "Se copió el enlace de Nube Norte."
    )
  })

  it("no duplica el punto de una frase que ya termina en uno", () => {
    expect(conPuntoFinal("Nube Norte obtiene el mejor puntaje.")).toBe(
      "Nube Norte obtiene el mejor puntaje."
    )
  })

  it("un nombre que termina en punto sirve de punto final, tenga la frase el suyo o no", () => {
    const nombre = "Datos Integrales S.A. de C.V."
    // Sin punto propio: el del nombre cierra la frase.
    expect(conPuntoFinal(`Se adjudicó la negociación a ${nombre}`)).toBe(
      `Se adjudicó la negociación a ${nombre}`
    )
    // Con el punto de la plantilla del servicio detrás del nombre: quedan dos y se reducen a uno.
    expect(conPuntoFinal(`Si el costo bajara, ganaría ${nombre}.`)).toBe(
      `Si el costo bajara, ganaría ${nombre}`
    )
  })

  it("ignora los espacios finales y nunca deja «..»", () => {
    expect(conPuntoFinal("Datos del Sur, S.A. ")).toBe("Datos del Sur, S.A.")
    for (const frase of ["Hola", "Hola.", "Hola..", "S.A. de C.V..", "x. ..."])
      expect(conPuntoFinal(frase)).not.toMatch(/\.\./)
  })
})
