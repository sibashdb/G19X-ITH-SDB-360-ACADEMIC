import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Proveedores } from "@/paginas/Proveedores"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

const PAGINA = {
  total: 2,
  elementos: [
    { id: "p1", rfc: "AAA010101AAA", nombre: "Nube Andina", tamano: "mediana", categorias: ["nube"], activo: true },
    {
      id: "p2",
      rfc: "BBB020202BBB",
      nombre: "Consultores Bajío",
      tamano: "pequena",
      categorias: ["consultoria", "soporte"],
      activo: false,
    },
  ],
}
const VACIA = { total: 0, elementos: [] }

function apiDeProveedores(pagina: object = PAGINA) {
  return simularApi((url) =>
    url.startsWith("/api/proveedores/proveedores?")
      ? respuestaJson(pagina)
      : new Response("", { status: 404 })
  )
}

const renderizar = (ruta = "/proveedores") => renderizarPagina(<Proveedores />, { ruta })

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Proveedores", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})))
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("lista los proveedores con RFC, categorías y estado", async () => {
    apiDeProveedores()
    renderizar()

    const tabla = await screen.findByRole("table")
    expect(within(tabla).getByRole("link", { name: "Nube Andina" })).toHaveAttribute("href", "/proveedores/p1")
    expect(within(tabla).getByText("AAA010101AAA")).toBeInTheDocument()
    expect(within(tabla).getByText("Consultoría")).toBeInTheDocument()
    expect(within(tabla).getByText("Activo")).toBeInTheDocument()
    expect(within(tabla).getByText("Inactivo")).toBeInTheDocument()
    expect(screen.getByText("Mostrando 1–2 de 2 proveedores")).toBeInTheDocument()
  })

  it("filtra por categoría y estado, y cada filtro vuelve a la primera página", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=3")
    await screen.findByRole("table")
    expect(urlDeLlamada(simulado).searchParams.get("desplazamiento")).toBe("50")

    await userEvent.click(screen.getByRole("button", { name: "Nube" }))
    await waitFor(() => expect(urlDeLlamada(simulado).searchParams.get("categoria")).toBe("nube"))
    expect(urlDeLlamada(simulado).searchParams.get("desplazamiento")).toBe("0")
    expect(ubicacionActual()).toBe("/proveedores?categoria=nube")
    expect(screen.getByRole("button", { name: "Nube" })).toHaveAttribute("aria-pressed", "true")

    await userEvent.click(screen.getByRole("button", { name: "Inactivos" }))
    await waitFor(() => expect(urlDeLlamada(simulado).searchParams.get("activo")).toBe("false"))
    expect(ubicacionActual()).toBe("/proveedores?categoria=nube&estado=inactivos")
  })

  it("busca por nombre o RFC", async () => {
    const simulado = apiDeProveedores()
    renderizar()
    await screen.findByRole("table")

    await userEvent.type(screen.getByLabelText("Buscar por nombre o RFC"), "  andina ")
    await userEvent.click(screen.getByRole("button", { name: "Buscar" }))

    await waitFor(() => expect(urlDeLlamada(simulado).searchParams.get("q")).toBe("andina"))
    expect(ubicacionActual()).toBe("/proveedores?q=andina")
  })

  it("el buscador conserva el foco tras pulsar Enter y se vacía con Limpiar filtros", async () => {
    apiDeProveedores()
    renderizar()
    await screen.findByRole("table")
    const campo = screen.getByLabelText("Buscar por nombre o RFC")

    await userEvent.type(campo, "andina{Enter}")

    await waitFor(() => expect(ubicacionActual()).toBe("/proveedores?q=andina"))
    expect(campo).toHaveFocus()
    expect(campo).toHaveValue("andina")

    await userEvent.click(screen.getAllByRole("button", { name: "Limpiar filtros" })[0])

    await waitFor(() => expect(ubicacionActual()).toBe("/proveedores"))
    expect(campo).toHaveValue("")
  })

  it("pagina con Siguiente", async () => {
    const simulado = apiDeProveedores({ ...PAGINA, total: 60 })
    renderizar()
    expect(await screen.findByText("Mostrando 1–25 de 60 proveedores")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled()

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))

    await waitFor(() => expect(urlDeLlamada(simulado).searchParams.get("desplazamiento")).toBe("25"))
    expect(ubicacionActual()).toBe("/proveedores?pagina=2")
    expect(await screen.findByText("Mostrando 26–50 de 60 proveedores")).toBeInTheDocument()
  })

  it("ignora parámetros inválidos de la URL", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=abc&categoria=hackeo&estado=quiza")
    await screen.findByRole("table")

    const url = urlDeLlamada(simulado)
    expect(url.searchParams.get("desplazamiento")).toBe("0")
    expect(url.searchParams.has("categoria")).toBe(false)
    expect(url.searchParams.has("activo")).toBe(false)
  })

  it("limita la página al máximo que acepta la API", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=999999999")
    await waitFor(() =>
      expect(urlDeLlamada(simulado).searchParams.get("desplazamiento")).toBe("999975")
    )
  })

  it("sin proveedores invita al administrador a importar", async () => {
    sesionDePrueba.roles = ["admin"]
    apiDeProveedores(VACIA)
    renderizar()

    expect(await screen.findByText("Aún no hay proveedores")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Ir a Importación" })).toHaveAttribute("href", "/importacion")
  })

  it("sin proveedores, un comprador recibe la indicación sin enlace de importación", async () => {
    apiDeProveedores(VACIA)
    renderizar()

    expect(await screen.findByText("Pida a un administrador que importe el catálogo del ERP.")).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "Ir a Importación" })).not.toBeInTheDocument()
  })

  it("sin resultados con filtros ofrece limpiarlos", async () => {
    apiDeProveedores(VACIA)
    renderizar("/proveedores?q=zzz&categoria=nube")

    expect(await screen.findByText("Sin resultados")).toBeInTheDocument()
    const botones = screen.getAllByRole("button", { name: "Limpiar filtros" })
    await userEvent.click(botones[botones.length - 1])
    expect(ubicacionActual()).toBe("/proveedores")
  })

  it.each([
    ["con filtros", "/proveedores?categoria=nube&pagina=5", "Hay 30 proveedores que coinciden", "/proveedores?categoria=nube"],
    ["sin filtros", "/proveedores?pagina=5", "Hay 30 proveedores en total", "/proveedores"],
  ])(
    "una página fuera de rango %s ofrece volver a la primera, no dice que no hay resultados",
    async (_caso, ruta, descripcion, destino) => {
      apiDeProveedores({ total: 30, elementos: [] })
      renderizar(ruta)

      expect(await screen.findByText("Esta página no tiene resultados")).toBeInTheDocument()
      expect(screen.getByText(new RegExp(descripcion))).toBeInTheDocument()
      expect(screen.queryByText("Sin resultados")).not.toBeInTheDocument()

      await userEvent.click(screen.getByRole("button", { name: "Ir a la primera página" }))
      expect(ubicacionActual()).toBe(destino)
    }
  )

  it("muestra el error en español y permite reintentar", async () => {
    let fallar = true
    simularApi(() => (fallar ? new Response("Bad Gateway", { status: 502 }) : respuestaJson(PAGINA)))
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible; intente más tarde."
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByRole("link", { name: "Nube Andina" })).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    apiDeProveedores()
    const { container } = renderizar()
    await screen.findByRole("table")
    await esperarSinViolaciones(container)
  })
})
