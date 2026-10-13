import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Ranking } from "@/paginas/Ranking"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const FILAS = [
  {
    posicion: 1,
    proveedor_id: "p1",
    nombre: "Nube Andina",
    categoria: "nube",
    puntuacion: 72.4,
    componentes: {
      sla: 80,
      resolucion: 65,
      incidentes: 60,
      entregas: 70,
      satisfaccion: 75,
    },
    meses: 12,
    historial_corto: false,
    tendencia: 3.2,
  },
  {
    posicion: 2,
    proveedor_id: "p2",
    nombre: "Datos del Norte",
    categoria: "nube",
    puntuacion: 31,
    componentes: {
      sla: 20,
      resolucion: 35,
      incidentes: 40,
      entregas: 25,
      satisfaccion: 30,
    },
    meses: 4,
    historial_corto: true,
    tendencia: null,
  },
]

function api(respuesta: () => Response = () => respuestaJson(FILAS)) {
  return simularApi((url) =>
    url.startsWith("/api/inteligencia/ranking")
      ? respuesta()
      : new Response("", { status: 404 })
  )
}

/** La última consulta del ranking (la configuración también llama a fetch). */
function consultaDeRanking(simulado: ReturnType<typeof simularApi>): URL {
  const indice = simulado.mock.calls.findLastIndex(([url]) =>
    String(url).startsWith("/api/inteligencia/ranking")
  )
  return urlDeLlamada(simulado, indice)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Ranking", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("abre la categoría indicada en la URL y muestra su ranking", async () => {
    const simulado = api()
    renderizarPagina(<Ranking />, { ruta: "/ranking?categoria=nube" })

    expect(screen.getByRole("tab", { name: "Nube" })).toHaveAttribute(
      "aria-selected",
      "true"
    )
    expect(
      screen.getByRole("heading", { name: "Ranking · Nube" })
    ).toBeInTheDocument()
    const tabla = await screen.findByRole("table")
    expect(consultaDeRanking(simulado).searchParams.get("categoria")).toBe(
      "nube"
    )
    const primera = within(tabla).getByRole("link", { name: "Nube Andina" })
    expect(primera).toHaveAttribute("href", "/proveedores/p1")
    const fila = primera.closest("tr")!
    expect(fila).toHaveTextContent("72.4")
    expect(fila).toHaveTextContent("80.0")
    expect(fila).toHaveTextContent("+3.2")
    expect(within(tabla).getByText("Historial corto")).toBeInTheDocument()
    expect(
      screen.getByRole("columnheader", { name: "Posición" })
    ).toBeInTheDocument()
  })

  it("cambiar de pestaña actualiza la URL", async () => {
    api()
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    await userEvent.click(screen.getByRole("tab", { name: "Soporte" }))
    expect(ubicacionActual()).toBe("/ranking?categoria=soporte")
    await userEvent.click(screen.getByRole("tab", { name: "Todas" }))
    expect(ubicacionActual()).toBe("/ranking")
  })

  it("una categoría inválida muestra todas", async () => {
    const simulado = api()
    renderizarPagina(<Ranking />, { ruta: "/ranking?categoria=inventada" })
    expect(screen.getByRole("tab", { name: "Todas" })).toHaveAttribute(
      "aria-selected",
      "true"
    )
    await screen.findByRole("table")
    expect(consultaDeRanking(simulado).searchParams.has("categoria")).toBe(
      false
    )
  })

  it("sin puntuaciones lo explica", async () => {
    api(() => respuestaJson([]))
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    expect(
      await screen.findByText("Sin puntuaciones todavía")
    ).toBeInTheDocument()
  })

  it("si el servicio no responde, lo dice y permite reintentar", async () => {
    let fallar = true
    api(() =>
      fallar ? new Response("", { status: 502 }) : respuestaJson(FILAS)
    )
    renderizarPagina(<Ranking />, { ruta: "/ranking" })

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByRole("table")).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizarPagina(<Ranking />, { ruta: "/ranking" })
    await screen.findByRole("table")
    await esperarSinViolaciones(container)
  })

  it("sugiere ver proveedores y revisar precios", () => {
    api()
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    expect(
      screen.getByRole("link", { name: /Ver proveedores/ })
    ).toHaveAttribute("href", "/proveedores")
    expect(
      screen.getByRole("link", { name: /Revisar precios/ })
    ).toHaveAttribute("href", "/precios")
  })
})
