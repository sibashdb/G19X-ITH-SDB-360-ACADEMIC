import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
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

/** Respuesta que la prueba resuelve a mano, para fijar el momento exacto en que termina una petición. */
export function respuestaDiferida() {
  let resolver!: (respuesta: Response) => void
  const promesa = new Promise<Response>((resolve) => {
    resolver = resolve
  })
  return { promesa, resolver }
}

/**
 * Sustituye fetch. Con un objeto, responde cada URL exacta (404 si no está); con una función,
 * decide por URL. Cada llamada crea una respuesta nueva (el cuerpo solo se lee una vez).
 */
export function simularApi(
  respuestas: Record<string, () => Respuesta> | ((url: string) => Respuesta)
) {
  const simulado = vi.fn((url: string) => {
    if (typeof respuestas === "function")
      return Promise.resolve(respuestas(url))
    const respuesta = respuestas[url]
    return Promise.resolve(
      respuesta ? respuesta() : new Response("", { status: 404 })
    )
  })
  vi.stubGlobal("fetch", simulado)
  return simulado
}

/** Espera a que ninguna mutación en caché conserve el texto (el gcTime de la mutación debe ser 0). */
export async function esperarSinEnMutaciones(
  cliente: QueryClient,
  texto: string
): Promise<void> {
  await waitFor(() => {
    const estados = cliente
      .getMutationCache()
      .getAll()
      .map((mutacion) => JSON.stringify(mutacion.state))
    expect(estados.join()).not.toContain(texto)
  })
}

/** URL de una llamada a fetch simulada (por defecto, la última), para revisar sus parámetros. */
export function urlDeLlamada(
  simulado: { mock: { calls: unknown[][] } },
  indice = -1
): URL {
  return new URL(
    String(simulado.mock.calls.at(indice)?.[0]),
    "http://localhost"
  )
}

/**
 * La última llamada a fetch simulada con esa URL exacta (y ese método, si se indica): su cuerpo
 * JSON y sus cabeceras. Sin método en `init`, la llamada cuenta como GET.
 */
export function llamadaA(
  simulado: { mock: { calls: unknown[][] } },
  url: string,
  metodo?: string
): { cuerpo: unknown; cabeceras: Headers } {
  const llamada = simulado.mock.calls.findLast(
    ([u, init]) =>
      u === url &&
      (!metodo ||
        ((init as RequestInit | undefined)?.method ?? "GET") === metodo)
  )
  if (!llamada)
    throw new Error(`No hubo ninguna llamada ${metodo ?? ""} a ${url}`)
  const init = (llamada[1] ?? {}) as RequestInit
  return {
    cuerpo: init.body ? JSON.parse(String(init.body)) : undefined,
    cabeceras: new Headers(init.headers),
  }
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
export function renderizarPagina(
  elemento: ReactNode,
  { ruta = "/", patron = "*" } = {}
) {
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
export async function esperarSinViolaciones(
  contenedor: Element
): Promise<void> {
  for (const oscuro of [false, true]) {
    document.documentElement.classList.toggle("dark", oscuro)
    const { violations } = await axe.run(contenedor, {
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
      },
      rules: { "color-contrast": { enabled: false } },
    })
    expect(violations.map((v) => `${v.id}: ${v.help}`)).toEqual([])
  }
  document.documentElement.classList.remove("dark")
}
