import { act, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import {
  claveGuia,
  marcarVisita,
  mostrarGuia,
  ocultarGuia,
  useGuia,
} from "@/guia"

const ANA = "ana-1"
const LUIS = "luis-2"

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe("guía de uso", () => {
  it("empieza visible y sin visitas", () => {
    const { result } = renderHook(() => useGuia(ANA))
    expect(result.current).toEqual({
      oculta: false,
      visitas: { proveedores: false, precios: false, negociaciones: false },
    })
  })

  it("registra visitas y las conserva en la clave de su usuario", () => {
    const { result } = renderHook(() => useGuia(ANA))
    act(() => marcarVisita(ANA, "proveedores"))
    expect(result.current.visitas.proveedores).toBe(true)
    expect(
      JSON.parse(localStorage.getItem(claveGuia(ANA)) ?? "{}").visitas
        .proveedores
    ).toBe(true)
  })

  it("registra la visita a Negociaciones", () => {
    const { result } = renderHook(() => useGuia(ANA))
    act(() => marcarVisita(ANA, "negociaciones"))
    expect(result.current.visitas.negociaciones).toBe(true)
  })

  it("cada persona tiene su propia guía en el mismo navegador", () => {
    const ana = renderHook(() => useGuia(ANA))
    const luis = renderHook(() => useGuia(LUIS))

    act(() => ocultarGuia(ANA))

    expect(ana.result.current.oculta).toBe(true)
    expect(luis.result.current.oculta).toBe(false)
    expect(localStorage.getItem(claveGuia(LUIS))).toBeNull()
  })

  it("se oculta y se vuelve a mostrar", () => {
    const { result } = renderHook(() => useGuia(ANA))
    act(() => ocultarGuia(ANA))
    expect(result.current.oculta).toBe(true)
    act(() => mostrarGuia(ANA))
    expect(result.current.oculta).toBe(false)
  })

  it("un valor corrupto cuenta como estado inicial", () => {
    localStorage.setItem(claveGuia(ANA), "{")
    const { result } = renderHook(() => useGuia(ANA))
    expect(result.current).toEqual({
      oculta: false,
      visitas: { proveedores: false, precios: false, negociaciones: false },
    })
  })

  it("funciona aunque el navegador bloquee localStorage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    const { result } = renderHook(() => useGuia(ANA))
    expect(result.current.oculta).toBe(false)
    expect(() => act(() => marcarVisita(ANA, "precios"))).not.toThrow()
  })

  it("se oculta aunque el navegador bloquee localStorage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    const { result } = renderHook(() => useGuia(ANA))
    act(() => ocultarGuia(ANA))
    expect(result.current.oculta).toBe(true)
    // Deja el respaldo en memoria como estaba para las demás pruebas.
    act(() => mostrarGuia(ANA))
    expect(result.current.oculta).toBe(false)
  })
})
