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

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const PAGINA = {
  total: 2,
  elementos: [
    {
      id: "p1",
      rfc: "AAA010101AAA",
      nombre: "Nube Andina",
      tamano: "mediana",
      categorias: ["nube"],
      activo: true,
      puntuacion: 72.4,
      confianza: "normal",
      tendencia: 3.2,
      gasto_anual: "1500000.00",
      contratos_vigentes: 4,
      alertas: 3,
      en_riesgo: false,
    },
    {
      id: "p2",
      rfc: "BBB020202BBB",
      nombre: "Consultores Bajío",
      tamano: "pequena",
      categorias: ["consultoria", "soporte"],
      activo: false,
      puntuacion: 31,
      confianza: "baja",
      tendencia: null,
      gasto_anual: "0.00",
      contratos_vigentes: 0,
      alertas: 1,
      en_riesgo: true,
    },
  ],
}
const VACIA = { total: 0, elementos: [] }

function apiDeProveedores(pagina: object = PAGINA) {
  return simularApi((url) =>
    url.startsWith("/api/inteligencia/proveedores?")
      ? respuestaJson(pagina)
      : new Response("", { status: 404 })
  )
}

/** La última consulta de la lista (la configuración también llama a fetch). */
function consultaDeLista(simulado: ReturnType<typeof simularApi>): URL {
  const indice = simulado.mock.calls.findLastIndex(([url]) =>
    String(url).startsWith("/api/inteligencia/proveedores?")
  )
  return urlDeLlamada(simulado, indice)
}

const renderizar = (ruta = "/proveedores") =>
  renderizarPagina(<Proveedores />, { ruta })

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Proveedores", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("lista los proveedores con su puntuación, gasto, contratos y alertas", async () => {
    apiDeProveedores()
    renderizar()

    const tabla = await screen.findByRole("table")
    expect(
      within(tabla).getByRole("link", { name: "Nube Andina" })
    ).toHaveAttribute("href", "/proveedores/p1")
    expect(within(tabla).getByText("AAA010101AAA")).toBeInTheDocument()
    expect(within(tabla).getByText("Consultoría")).toBeInTheDocument()
    expect(within(tabla).getByText("72.4")).toBeInTheDocument()
    expect(within(tabla).getByText("Historial corto")).toBeInTheDocument()
    expect(within(tabla).getByText("$1,500,000.00")).toBeInTheDocument()
    expect(
      within(tabla).getByRole("link", { name: "3 alertas de Nube Andina" })
    ).toHaveAttribute("href", "/alertas?proveedor=p1")
    expect(
      within(tabla).getByRole("link", { name: "1 alerta de Consultores Bajío" })
    ).toBeInTheDocument()
    expect(within(tabla).getByText("En riesgo")).toBeInTheDocument()
    expect(within(tabla).getByText("Inactivo")).toBeInTheDocument()
    expect(
      screen.getByText("Mostrando 1–2 de 2 proveedores")
    ).toBeInTheDocument()
  })

  it("filtra por categoría, estado y riesgo, y cada filtro vuelve a la primera página", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=3")
    await screen.findByRole("table")
    expect(consultaDeLista(simulado).searchParams.get("pagina")).toBe("3")

    await userEvent.click(screen.getByRole("button", { name: "Nube" }))
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("categoria")).toBe(
        "nube"
      )
    )
    expect(consultaDeLista(simulado).searchParams.get("pagina")).toBe("1")
    expect(ubicacionActual()).toBe("/proveedores?categoria=nube")

    await userEvent.click(screen.getByRole("button", { name: "Inactivos" }))
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("estado")).toBe(
        "inactivos"
      )
    )

    const riesgo = screen.getByRole("button", { name: "En riesgo" })
    await userEvent.click(riesgo)
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("en_riesgo")).toBe(
        "true"
      )
    )
    expect(riesgo).toHaveAttribute("aria-pressed", "true")
    expect(ubicacionActual()).toBe(
      "/proveedores?categoria=nube&estado=inactivos&en_riesgo=true"
    )
  })

  it("ordena por columna: las cifras primero de mayor a menor y luego al revés", async () => {
    const simulado = apiDeProveedores()
    renderizar()
    await screen.findByRole("table")
    expect(consultaDeLista(simulado).searchParams.get("orden")).toBe("nombre")
    expect(consultaDeLista(simulado).searchParams.get("direccion")).toBe("asc")

    await userEvent.click(
      screen.getByRole("button", { name: "Ordenar por Puntuación" })
    )
    expect(ubicacionActual()).toBe("/proveedores?orden=puntuacion")
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("direccion")).toBe(
        "desc"
      )
    )
    expect(
      screen.getByRole("columnheader", { name: /Puntuación/ })
    ).toHaveAttribute("aria-sort", "descending")

    await userEvent.click(
      screen.getByRole("button", { name: "Ordenar por Puntuación" })
    )
    expect(ubicacionActual()).toBe(
      "/proveedores?orden=puntuacion&direccion=asc"
    )
    expect(
      screen.getByRole("columnheader", { name: /Puntuación/ })
    ).toHaveAttribute("aria-sort", "ascending")

    await userEvent.click(
      screen.getByRole("button", { name: "Ordenar por Proveedor" })
    )
    expect(ubicacionActual()).toBe("/proveedores")
  })

  it("el gasto anual dice que está en MXN", async () => {
    apiDeProveedores()
    renderizar()
    await screen.findByRole("table")

    expect(
      screen.getByRole("button", { name: "Ordenar por Gasto anual (MXN)" })
    ).toBeInTheDocument()
  })

  it("busca por nombre o RFC", async () => {
    const simulado = apiDeProveedores()
    renderizar()
    await screen.findByRole("table")

    await userEvent.type(
      screen.getByLabelText("Buscar por nombre o RFC"),
      "  andina "
    )
    await userEvent.click(screen.getByRole("button", { name: "Buscar" }))

    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("busqueda")).toBe(
        "andina"
      )
    )
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

    await userEvent.click(
      screen.getByRole("button", { name: "Limpiar filtros" })
    )

    await waitFor(() => expect(ubicacionActual()).toBe("/proveedores"))
    expect(campo).toHaveValue("")
    expect(campo).toHaveFocus()
  })

  it("pagina con Siguiente", async () => {
    const simulado = apiDeProveedores({ ...PAGINA, total: 60 })
    renderizar()
    expect(
      await screen.findByText("Mostrando 1–25 de 60 proveedores")
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Anterior" })).toHaveAttribute(
      "aria-disabled",
      "true"
    )

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))

    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("pagina")).toBe("2")
    )
    expect(ubicacionActual()).toBe("/proveedores?pagina=2")
  })

  it("ignora parámetros inválidos de la URL", async () => {
    const simulado = apiDeProveedores()
    renderizar(
      "/proveedores?pagina=abc&categoria=hackeo&estado=quiza&en_riesgo=tal&orden=hackeo&direccion=x"
    )
    await screen.findByRole("table")

    const url = consultaDeLista(simulado)
    expect(url.searchParams.get("pagina")).toBe("1")
    expect(url.searchParams.get("orden")).toBe("nombre")
    expect(url.searchParams.get("direccion")).toBe("asc")
    expect(url.searchParams.has("categoria")).toBe(false)
    expect(url.searchParams.has("estado")).toBe(false)
    expect(url.searchParams.has("en_riesgo")).toBe(false)
  })

  it("limita la página al máximo que acepta la API", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=999999999")
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("pagina")).toBe("1000")
    )
  })

  it("sin proveedores invita al administrador a importar", async () => {
    sesionDePrueba.roles = ["admin"]
    apiDeProveedores(VACIA)
    renderizar()

    expect(
      await screen.findByText("Aún no hay proveedores")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Ir a Importación" })
    ).toHaveAttribute("href", "/importacion")
  })

  it("sin proveedores, un comprador recibe la indicación sin enlace de importación", async () => {
    apiDeProveedores(VACIA)
    renderizar()

    expect(
      await screen.findByText(
        "Pida a un administrador que importe el catálogo del ERP."
      )
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("link", { name: "Ir a Importación" })
    ).not.toBeInTheDocument()
  })

  it("sin resultados con filtros hay un solo Limpiar filtros, que deja el foco en el buscador", async () => {
    apiDeProveedores(VACIA)
    renderizar("/proveedores?q=zzz&categoria=nube")

    expect(await screen.findByText("Sin resultados")).toBeInTheDocument()
    const botones = screen.getAllByRole("button", { name: "Limpiar filtros" })
    expect(botones).toHaveLength(1)
    await userEvent.click(botones[0])
    expect(ubicacionActual()).toBe("/proveedores")
    expect(screen.getByLabelText("Buscar por nombre o RFC")).toHaveFocus()
  })

  it.each([
    [
      "con filtros",
      "/proveedores?categoria=nube&pagina=5",
      "Hay 30 proveedores que coinciden",
      "/proveedores?categoria=nube",
    ],
    [
      "sin filtros",
      "/proveedores?pagina=5",
      "Hay 30 proveedores en total",
      "/proveedores",
    ],
  ])(
    "una página fuera de rango %s ofrece volver a la primera y deja el foco en el buscador",
    async (_caso, ruta, descripcion, destino) => {
      apiDeProveedores({ total: 30, elementos: [] })
      renderizar(ruta)

      expect(
        await screen.findByText("Esta página no tiene resultados")
      ).toBeInTheDocument()
      expect(screen.getByText(new RegExp(descripcion))).toBeInTheDocument()
      expect(screen.queryByText("Sin resultados")).not.toBeInTheDocument()

      await userEvent.click(
        screen.getByRole("button", { name: "Ir a la primera página" })
      )
      expect(ubicacionActual()).toBe(destino)
      expect(screen.getByLabelText("Buscar por nombre o RFC")).toHaveFocus()
    }
  )

  it("si la inteligencia no responde, lo dice y permite reintentar", async () => {
    let fallar = true
    simularApi((url) =>
      url.startsWith("/api/inteligencia/proveedores?")
        ? fallar
          ? new Response("Bad Gateway", { status: 502 })
          : respuestaJson(PAGINA)
        : new Response("", { status: 404 })
    )
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible; intente más tarde."
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(
      await screen.findByRole("link", { name: "Nube Andina" })
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    apiDeProveedores()
    const { container } = renderizar()
    await screen.findByRole("table")
    await esperarSinViolaciones(container)
  })
})
