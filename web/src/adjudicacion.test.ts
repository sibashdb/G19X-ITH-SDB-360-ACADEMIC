import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, renderHook, waitFor } from "@testing-library/react"
import { createElement, type ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import {
  CRITERIOS,
  PESOS_POR_OMISION,
  pesosValidos,
  razonesAprobacion,
  sonEnteros,
  superaUmbral,
  TEXTOS_RESULTADO,
  textoPesos,
  totalPesos,
  useEvaluacion,
} from "@/adjudicacion"
import { respuestaJson, simularApi, urlDeLlamada } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("pesos de la adjudicación", () => {
  it("textoPesos respeta el orden del servicio", () => {
    expect(textoPesos({ costo: 40, desempeno: 30, riesgo: 15, sla: 15 })).toBe(
      "40,30,15,15"
    )
  })

  it("pesosValidos exige enteros de 0 a 100 que sumen 100", () => {
    expect(
      pesosValidos({ costo: "40", desempeno: "30", riesgo: "15", sla: "15" })
    ).toEqual(PESOS_POR_OMISION)
    for (const malo of ["", "-1", "10.5", "101", "abc"])
      expect(
        pesosValidos({ costo: malo, desempeno: "30", riesgo: "15", sla: "15" })
      ).toBeNull()
    expect(
      pesosValidos({ costo: "40", desempeno: "30", riesgo: "15", sla: "10" })
    ).toBeNull()
  })

  it("CRITERIOS es el orden de «?pesos=»", () => {
    expect(CRITERIOS).toEqual(["costo", "desempeno", "riesgo", "sla"])
  })

  it("sonEnteros distingue un campo que no es entero de una suma que no da 100", () => {
    expect(
      sonEnteros({ costo: "40", desempeno: "30", riesgo: "15", sla: "15" })
    ).toBe(true)
    // «1000» y «-5» suman 0 en totalPesos: sin esto, el total parecería 100 con campos inválidos.
    for (const malo of ["", "-5", "10.5", "1000", "abc"])
      expect(
        sonEnteros({ costo: malo, desempeno: "30", riesgo: "15", sla: "15" })
      ).toBe(false)
  })

  it("totalPesos suma los enteros y cuenta 0 lo que no lo es", () => {
    expect(
      totalPesos({ costo: "40", desempeno: "30", riesgo: "", sla: "x1" })
    ).toBe(70)
    expect(
      totalPesos({ costo: "40", desempeno: "30", riesgo: "-5", sla: "15" })
    ).toBe(85)
  })
})

describe("regla de aprobación", () => {
  it("superaUmbral es estricto como el servicio", () => {
    expect(superaUmbral("500000.00", "500000.00")).toBe(false)
    expect(superaUmbral("500000.01", "500000.00")).toBe(true)
  })

  it("razonesAprobacion junta el umbral y los límites", () => {
    expect(razonesAprobacion("600000.00", "500000.00", true)).toEqual([
      "umbral",
      "fuera_de_limites",
    ])
    expect(razonesAprobacion("1.00", "500000.00", false)).toEqual([])
  })
})

describe("textos del resultado", () => {
  it("son los del correo", () => {
    expect(TEXTOS_RESULTADO.no_elegida).toBe(
      "La negociación se adjudicó a otra propuesta"
    )
  })
})

describe("useEvaluacion", () => {
  const VACIA = { recomendacion: null, vigente: null, historial: [] }

  function envoltura(cliente: QueryClient) {
    return ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: cliente }, children)
  }

  it("pide la evaluación sin pesos si no se indican", async () => {
    const simulado = simularApi(() => respuestaJson(VACIA))
    const cliente = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const { result } = renderHook(() => useEvaluacion("ev-1", null), {
      wrapper: envoltura(cliente),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const url = urlDeLlamada(simulado)
    expect(url.pathname).toBe("/api/negociacion/eventos/ev-1/evaluacion")
    expect(url.search).toBe("")
  })

  it("manda los pesos en el orden del servicio", async () => {
    const simulado = simularApi(() => respuestaJson(VACIA))
    const cliente = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const { result } = renderHook(
      () => useEvaluacion("ev-1", PESOS_POR_OMISION),
      { wrapper: envoltura(cliente) }
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(urlDeLlamada(simulado).search).toBe("?pesos=40,30,15,15")
  })

  it("pasa las opciones a la consulta", async () => {
    const simulado = simularApi(() => respuestaJson(VACIA))
    const cliente = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const { result } = renderHook(
      () => useEvaluacion("ev-1", null, { enabled: false }),
      { wrapper: envoltura(cliente) }
    )
    await waitFor(() => expect(result.current.fetchStatus).toBe("idle"))
    expect(simulado).not.toHaveBeenCalled()
  })
})
