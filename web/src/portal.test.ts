import { afterEach, describe, expect, it, vi } from "vitest"
import { pedirPortal, tomarToken } from "@/portal"
import { llamadaA, respuestaJson, simularApi } from "@/pruebas/utilidades"

afterEach(() => {
  sessionStorage.clear()
  window.history.replaceState(null, "", "/")
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("tomarToken", () => {
  it("toma el token del fragmento, lo guarda y lo quita de la barra", () => {
    window.history.replaceState(null, "", "/portal?x=1#t=tok-123")
    expect(tomarToken()).toBe("tok-123")
    expect(window.location.hash).toBe("")
    expect(window.location.pathname + window.location.search).toBe(
      "/portal?x=1"
    )
    expect(sessionStorage.getItem("portal-negociacion")).toBe("tok-123")
    // Al recargar la pestaña, ya sin fragmento, sigue sirviendo.
    expect(tomarToken()).toBe("tok-123")
  })

  it("un enlace nuevo en la misma pestaña reemplaza al anterior", () => {
    window.history.replaceState(null, "", "/portal#t=viejo")
    tomarToken()
    window.history.replaceState(null, "", "/portal#t=nuevo")
    expect(tomarToken()).toBe("nuevo")
    expect(tomarToken()).toBe("nuevo")
  })

  it("sin fragmento ni nada guardado no hay token", () => {
    window.history.replaceState(null, "", "/portal")
    expect(tomarToken()).toBeNull()
  })

  it("con el almacenamiento bloqueado, lo conserva en memoria", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    window.history.replaceState(null, "", "/portal#t=tok-memoria")
    expect(tomarToken()).toBe("tok-memoria")
    expect(tomarToken()).toBe("tok-memoria")
  })
})

describe("pedirPortal", () => {
  it("manda Authorization: Invitacion a la API del portal, nunca un Bearer", async () => {
    const api = simularApi(() => respuestaJson({ ok: true }))
    await pedirPortal("/sesion", "tok-123")
    expect(
      llamadaA(api, "/api/negociacion/portal/sesion").cabeceras.get(
        "Authorization"
      )
    ).toBe("Invitacion tok-123")
  })
})
