import { act, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { CLAVE_GUIA, marcarVisita, mostrarGuia, ocultarGuia, useGuia } from "@/guia"

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe("guía de uso", () => {
  it("empieza visible y sin visitas", () => {
    const { result } = renderHook(() => useGuia())
    expect(result.current).toEqual({
      oculta: false,
      visitas: { proveedores: false, precios: false },
    })
  })

  it("registra visitas y las conserva en localStorage", () => {
    const { result } = renderHook(() => useGuia())
    act(() => marcarVisita("proveedores"))
    expect(result.current.visitas.proveedores).toBe(true)
    expect(JSON.parse(localStorage.getItem(CLAVE_GUIA) ?? "{}").visitas.proveedores).toBe(true)
  })

  it("se oculta y se vuelve a mostrar", () => {
    const { result } = renderHook(() => useGuia())
    act(() => ocultarGuia())
    expect(result.current.oculta).toBe(true)
    act(() => mostrarGuia())
    expect(result.current.oculta).toBe(false)
  })

  it("un valor corrupto cuenta como estado inicial", () => {
    localStorage.setItem(CLAVE_GUIA, "{")
    const { result } = renderHook(() => useGuia())
    expect(result.current).toEqual({
      oculta: false,
      visitas: { proveedores: false, precios: false },
    })
  })

  it("funciona aunque el navegador bloquee localStorage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    const { result } = renderHook(() => useGuia())
    expect(result.current.oculta).toBe(false)
    expect(() => act(() => marcarVisita("precios"))).not.toThrow()
  })
})
