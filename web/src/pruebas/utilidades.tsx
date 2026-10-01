import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import axe from "axe-core"
import type { ReactNode } from "react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router"
import { expect, vi } from "vitest"
import { ProveedorTema } from "@/tema"

export function respuestaJson(cuerpo: unknown, estado = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { "Content-Type": "application/json" },
  })
}

type Respuesta = Response | Promise<Response>

/**
 * Sustituye fetch. Con un objeto, responde cada URL exacta (404 si no está); con una función,
 * decide por URL. Cada llamada crea una respuesta nueva (el cuerpo solo se lee una vez).
 */
export function simularApi(respuestas: Record<string, () => Respuesta> | ((url: string) => Respuesta)) {
  const simulado = vi.fn((url: string) => {
    if (typeof respuestas === "function") return Promise.resolve(respuestas(url))
    const respuesta = respuestas[url]
    return Promise.resolve(respuesta ? respuesta() : new Response("", { status: 404 }))
  })
  vi.stubGlobal("fetch", simulado)
  return simulado
}

/** URL de una llamada a fetch simulada (por defecto, la última), para revisar sus parámetros. */
export function urlDeLlamada(simulado: { mock: { calls: unknown[][] } }, indice = -1): URL {
  return new URL(String(simulado.mock.calls.at(indice)?.[0]), "http://localhost")
}

function Ubicacion() {
  const { pathname, search } = useLocation()
  return (
    <span hidden data-testid="ubicacion">
      {pathname + search}
    </span>
  )
}

/** Ruta y parámetros actuales de la página renderizada con renderizarPagina. */
export function ubicacionActual(): string {
  return screen.getByTestId("ubicacion").textContent ?? ""
}

/** Renderiza una página con tema, consultas (sin reintentos) y enrutador en memoria. */
export function renderizarPagina(elemento: ReactNode, { ruta = "/", patron = "*" } = {}) {
  const cliente = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const resultado = render(
    <ProveedorTema>
      <QueryClientProvider client={cliente}>
        <MemoryRouter initialEntries={[ruta]}>
          <Routes>
            <Route
              path={patron}
              element={
                <>
                  {elemento}
                  <Ubicacion />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </ProveedorTema>
  )
  return { cliente, ...resultado }
}

/**
 * axe (reglas WCAG 2.x A y AA) con la clase .dark quitada y puesta. jsdom no calcula estilos,
 * así que la regla de contraste se desactiva: el contraste lo cubre tokens.node.test.ts y la
 * revisión en navegador de la Tarea 11.
 */
export async function esperarSinViolaciones(contenedor: Element): Promise<void> {
  for (const oscuro of [false, true]) {
    document.documentElement.classList.toggle("dark", oscuro)
    const { violations } = await axe.run(contenedor, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      rules: { "color-contrast": { enabled: false } },
    })
    expect(violations.map((v) => `${v.id}: ${v.help}`)).toEqual([])
  }
  document.documentElement.classList.remove("dark")
}
