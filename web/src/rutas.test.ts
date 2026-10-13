import { describe, expect, it } from "vitest"
import { paginas } from "@/rutas"

describe("rutas", () => {
  it("cada página se descarga aparte y entrega su componente", async () => {
    expect(paginas.length).toBeGreaterThan(0)
    for (const ruta of paginas) {
      // Ninguna página va dentro del bundle inicial: todas se cargan con `lazy`.
      expect(ruta.Component).toBeUndefined()
      expect(typeof ruta.lazy).toBe("function")
      const cargada = await (
        ruta.lazy as () => Promise<{ Component?: unknown }>
      )()
      expect(cargada.Component).toEqual(expect.any(Function))
    }
  })
})
