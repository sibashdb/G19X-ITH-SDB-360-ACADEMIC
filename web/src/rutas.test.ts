import { describe, expect, it } from "vitest"
import { ErrorDePagina } from "@/componentes/ErrorDePagina"
import { marco, paginas, portal } from "@/rutas"

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

  it("las páginas van en una frontera de error dentro del marco, para que el menú no desaparezca", () => {
    expect(marco.children).toHaveLength(1)
    expect(marco.children?.[0].ErrorBoundary).toBe(ErrorDePagina)
    expect(marco.children?.[0].children).toBe(paginas)
  })

  it("el portal va fuera del marco: no pasa por el Layout ni por el inicio de sesión", async () => {
    expect(portal.path).toBe("/portal")
    expect(paginas.some((r) => r.path?.includes("portal"))).toBe(false)
    const cargada = await (
      portal.lazy as () => Promise<{ Component?: unknown }>
    )()
    expect(cargada.Component).toEqual(expect.any(Function))
  })
})
