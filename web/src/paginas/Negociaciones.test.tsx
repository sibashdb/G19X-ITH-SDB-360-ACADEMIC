import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Negociaciones } from "@/paginas/Negociaciones"
import { sesionDePrueba } from "@/pruebas/sesion"
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

const ID = "5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42"
const PAGINA = {
  total: 1,
  elementos: [
    {
      id: ID,
      folio: "NEG-2026-0001",
      tipo: "compra",
      titulo: "Licencias de correo 2027",
      estado: "abierto",
      fecha_limite: "2026-10-21T23:00:00Z",
      invitados: 3,
      sesiones: 3,
      acuerdos: 2,
      escaladas: 1,
      creado_por_nombre: "Ana López",
      creado_en: "2026-10-14T18:00:00Z",
    },
  ],
}

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Negociaciones", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("lista las negociaciones con su estado, sus acuerdos y las escaladas", async () => {
    simularApi(() => respuestaJson(PAGINA))
    const { container } = renderizarPagina(<Negociaciones />, {
      ruta: "/negociaciones",
    })
    expect(
      await screen.findByRole("link", { name: "NEG-2026-0001" })
    ).toHaveAttribute("href", `/negociaciones/${ID}`)
    const tabla = screen.getByRole("table")
    expect(
      within(tabla).getByText("Licencias de correo 2027")
    ).toBeInTheDocument()
    expect(within(tabla).getByText("Compra")).toBeInTheDocument()
    expect(within(tabla).getByText("Abierta")).toBeInTheDocument()
    expect(within(tabla).getByText("2 de 3")).toBeInTheDocument()
    expect(within(tabla).getByText("1 escalada")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("solo el comprador ve «Nueva negociación»", async () => {
    simularApi(() => respuestaJson(PAGINA))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    expect(
      await screen.findByRole("link", { name: "Nueva negociación" })
    ).toHaveAttribute("href", "/negociaciones/nueva")
    cleanup()
    sesionDePrueba.roles = ["aprobador"]
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    expect(
      screen.queryByRole("link", { name: "Nueva negociación" })
    ).not.toBeInTheDocument()
  })

  it("los filtros van a la URL y a la consulta, y vuelven a la primera página", async () => {
    const api = simularApi(() => respuestaJson(PAGINA))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones?pagina=2" })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    const estados = screen.getByRole("group", { name: "Estado" })
    await userEvent.click(
      within(estados).getByRole("button", { name: "Abierta" })
    )
    expect(ubicacionActual()).toBe("/negociaciones?estado=abierto")
    await waitFor(() =>
      expect(urlDeLlamada(api).searchParams.get("estado")).toBe("abierto")
    )
    expect(urlDeLlamada(api).searchParams.get("pagina")).toBe("1")
    expect(
      within(estados).getByRole("button", { name: "Abierta" })
    ).toHaveAttribute("aria-pressed", "true")
  })

  it("ignora filtros inválidos de la URL", async () => {
    const api = simularApi(() => respuestaJson(PAGINA))
    renderizarPagina(<Negociaciones />, {
      ruta: "/negociaciones?estado=hackeo&tipo=x&pagina=abc",
    })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    const url = urlDeLlamada(api)
    expect(url.pathname).toBe("/api/negociacion/eventos")
    expect(url.searchParams.get("estado")).toBeNull()
    expect(url.searchParams.get("tipo")).toBeNull()
    expect(url.searchParams.get("pagina")).toBe("1")
    expect(url.searchParams.get("tamano")).toBe("25")
  })

  it("sin negociaciones lo explica, y con filtros ofrece quitarlos", async () => {
    simularApi(() => respuestaJson({ total: 0, elementos: [] }))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    expect(
      await screen.findByText("Aún no hay negociaciones")
    ).toBeInTheDocument()
    cleanup()
    renderizarPagina(<Negociaciones />, {
      ruta: "/negociaciones?tipo=renovacion",
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Quitar filtros" })
    )
    expect(ubicacionActual()).toBe("/negociaciones")
    expect(
      within(screen.getByRole("group", { name: "Estado" })).getByRole(
        "button",
        {
          name: "Todas",
        }
      )
    ).toHaveFocus()
  })

  it("una página fuera de rango ofrece volver a la primera", async () => {
    simularApi(() => respuestaJson({ total: 3, elementos: [] }))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones?pagina=9" })
    await userEvent.click(
      await screen.findByRole("button", { name: "Ir a la primera página" })
    )
    expect(ubicacionActual()).toBe("/negociaciones")
    expect(
      within(screen.getByRole("group", { name: "Estado" })).getByRole(
        "button",
        {
          name: "Todas",
        }
      )
    ).toHaveFocus()
  })

  it("si el servicio no responde, lo dice y permite reintentar", async () => {
    simularApi(() =>
      respuestaJson(
        {
          title: "Servicio no disponible",
          detail: "El servicio no está disponible; intente más tarde.",
        },
        503
      )
    )
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    expect(
      await screen.findByRole("button", { name: "Reintentar" })
    ).toBeInTheDocument()
  })
})
