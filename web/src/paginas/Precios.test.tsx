import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Precios } from "@/paginas/Precios"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"
import { normalizarTexto } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const SERVICIOS = [
  {
    id: "s1",
    codigo: "CONS-01",
    nombre: "Consultoría SAP",
    categoria: "consultoria",
    unidad: "hora",
    moneda: "MXN",
  },
  {
    id: "s2",
    codigo: "NUBE-01",
    nombre: "Cómputo en la nube",
    categoria: "nube",
    unidad: "mes",
    moneda: "USD",
  },
  {
    id: "s3",
    codigo: "NUBE-02",
    nombre: "Almacenamiento de objetos",
    categoria: "nube",
    unidad: "TB",
    moneda: "USD",
  },
]

const conCatalogo = (servicios: object[] = SERVICIOS) =>
  simularApi({ "/api/proveedores/servicios": () => respuestaJson(servicios) })

const renderizar = (ruta = "/precios") =>
  renderizarPagina(<Precios />, { ruta })
const lista = () => screen.getByRole("list", { name: "Servicios del catálogo" })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  sesionDePrueba.roles = ["admin"]
})

describe("normalizarTexto", () => {
  it("quita acentos y mayúsculas", () => {
    expect(normalizarTexto("Consultoría ÓPTIMA")).toBe("consultoria optima")
  })
})

describe("Precios", () => {
  it("muestra un esqueleto mientras carga el catálogo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("agrupa los servicios por categoría", async () => {
    conCatalogo()
    renderizar()

    expect(
      await screen.findByRole("button", { name: /Consultoría SAP/ })
    ).toBeInTheDocument()
    expect(within(lista()).getByText("Consultoría")).toBeInTheDocument()
    expect(within(lista()).getByText("Nube")).toBeInTheDocument()
    expect(screen.getByText("Elija un servicio")).toBeInTheDocument()
  })

  // jsdom no pinta el foco: se revisan las clases. La lista tiene overflow-y-auto, que recorta el
  // contorno por defecto, así que el anillo va hacia adentro; outline-hidden (y no outline-none)
  // conserva un contorno transparente que el modo de alto contraste sí muestra.
  it("los botones de la lista muestran un anillo de foco que el scroll no recorta", async () => {
    conCatalogo()
    renderizar()

    const boton = await screen.findByRole("button", { name: /Consultoría SAP/ })

    expect(boton).toHaveClass(
      "outline-hidden",
      "focus-visible:ring-2",
      "focus-visible:ring-inset"
    )
    expect(boton).not.toHaveClass("outline-none")
  })

  it("busca por nombre o código sin importar acentos ni mayúsculas", async () => {
    conCatalogo()
    renderizar()
    await screen.findByRole("button", { name: /Consultoría SAP/ })
    const buscador = screen.getByRole("searchbox", {
      name: "Buscar servicio por nombre o código",
    })

    await userEvent.type(buscador, "CONSULTORIA")
    expect(within(lista()).getAllByRole("button")).toHaveLength(1)

    await userEvent.clear(buscador)
    await userEvent.type(buscador, "nube-02")
    expect(
      within(lista()).getByRole("button", { name: /Almacenamiento de objetos/ })
    ).toBeInTheDocument()
    expect(within(lista()).getAllByRole("button")).toHaveLength(1)

    await userEvent.clear(buscador)
    await userEvent.type(buscador, "zzz")
    expect(
      screen.getByText("Ningún servicio coincide con «zzz».")
    ).toBeInTheDocument()
  })

  it("elegir un servicio lo refleja en la URL y muestra su detalle", async () => {
    conCatalogo()
    renderizar()

    await userEvent.click(
      await screen.findByRole("button", { name: /Cómputo en la nube/ })
    )

    expect(ubicacionActual()).toBe("/precios?servicio=NUBE-01")
    expect(
      screen.getByRole("button", { name: /Cómputo en la nube/ })
    ).toHaveAttribute("aria-pressed", "true")
    expect(
      screen.getByRole("heading", { level: 2, name: "Cómputo en la nube" })
    ).toBeInTheDocument()
    expect(
      screen.getByText("NUBE-01 · Nube · por mes · USD")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /Ver proveedores de esta categoría/ })
    ).toHaveAttribute("href", "/proveedores?categoria=nube")
  })

  it("un servicio desconocido en la URL pide elegir uno", async () => {
    conCatalogo()
    renderizar("/precios?servicio=NO-EXISTE")
    expect(await screen.findByText("Elija un servicio")).toBeInTheDocument()
  })

  it("cambia a la vista de todos los sobreprecios", async () => {
    conCatalogo()
    renderizar()
    await screen.findByRole("button", { name: /Consultoría SAP/ })

    await userEvent.click(
      screen.getByRole("button", { name: "Todos los sobreprecios" })
    )

    expect(ubicacionActual()).toBe("/precios?vista=sobreprecios")
    expect(
      screen.getByRole("heading", { level: 2, name: "Todos los sobreprecios" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Todos los sobreprecios" })
    ).toHaveAttribute("aria-pressed", "true")
  })

  it("con el catálogo vacío invita al administrador a importar", async () => {
    conCatalogo([])
    renderizar()
    expect(
      await screen.findByText("El catálogo está vacío")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Ir a Importación" })
    ).toHaveAttribute("href", "/importacion")
  })

  it("muestra el error en español y permite reintentar", async () => {
    let fallar = true
    simularApi(() =>
      fallar ? new Response("", { status: 502 }) : respuestaJson(SERVICIOS)
    )
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(
      await screen.findByRole("button", { name: /Consultoría SAP/ })
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    conCatalogo()
    const { container } = renderizar("/precios?servicio=NUBE-01")
    await screen.findByRole("heading", { level: 2, name: "Cómputo en la nube" })
    await esperarSinViolaciones(container)
  })
})
