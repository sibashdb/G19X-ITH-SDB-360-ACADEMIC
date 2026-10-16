import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { GuiaUso } from "@/componentes/GuiaUso"
import { claveGuia } from "@/guia"
import { USUARIO_DE_PRUEBA, sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

function conProveedores(total: number) {
  simularApi((url) =>
    url.startsWith("/api/proveedores/proveedores?")
      ? respuestaJson({ total, elementos: [] })
      : new Response("", { status: 404 })
  )
}

const paso = (numero: number) => screen.getAllByRole("listitem")[numero - 1]

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("GuiaUso", () => {
  it("con datos importados marca el paso 1 y cuenta el avance", async () => {
    conProveedores(60)
    renderizarPagina(<GuiaUso />)

    expect(
      await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    ).toBeInTheDocument()
    expect(await screen.findByText("1 de 4 listos")).toBeInTheDocument()
    expect(paso(1)).toHaveTextContent("Hecho")
    expect(paso(2)).toHaveTextContent("Pendiente")
    expect(
      within(paso(2)).getByRole("link", { name: "Ver proveedores" })
    ).toHaveAttribute("href", "/proveedores")
    expect(paso(4)).toHaveTextContent("Pendiente")
    expect(
      within(paso(4)).getByRole("link", { name: "Ver negociaciones" })
    ).toHaveAttribute("href", "/negociaciones")
    expect(
      screen.getByRole("link", { name: "Centro de ayuda" })
    ).toHaveAttribute("href", "/ayuda")
  })

  it("el enlace dentro de la frase va subrayado: no se distingue solo por color", async () => {
    conProveedores(60)
    renderizarPagina(<GuiaUso />)
    // jsdom no calcula estilos: la clase es la evidencia de que el subrayado está siempre puesto.
    expect(
      await screen.findByRole("link", { name: "Centro de ayuda" })
    ).toHaveClass("underline")
  })

  it("las visitas registradas marcan los pasos 2 y 3", async () => {
    conProveedores(60)
    localStorage.setItem(
      claveGuia(USUARIO_DE_PRUEBA),
      JSON.stringify({
        oculta: false,
        visitas: { proveedores: true, precios: true },
      })
    )
    renderizarPagina(<GuiaUso />)
    expect(await screen.findByText("3 de 4 listos")).toBeInTheDocument()
  })

  it("la visita a Negociaciones marca el paso 4", async () => {
    conProveedores(60)
    localStorage.setItem(
      claveGuia(USUARIO_DE_PRUEBA),
      JSON.stringify({
        oculta: false,
        visitas: { proveedores: true, precios: true, negociaciones: true },
      })
    )
    renderizarPagina(<GuiaUso />)
    expect(await screen.findByText("4 de 4 listos")).toBeInTheDocument()
  })

  it("sin datos, el admin ve el enlace a Importación", async () => {
    conProveedores(0)
    renderizarPagina(<GuiaUso />)
    await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    expect(
      within(paso(1)).getByRole("link", { name: "Ir a Importación" })
    ).toHaveAttribute("href", "/importacion")
  })

  it("sin datos, otros roles leen que Administración importa los datos", async () => {
    sesionDePrueba.roles = ["comprador"]
    conProveedores(0)
    renderizarPagina(<GuiaUso />)
    await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    expect(
      within(paso(1)).getByText("Administración importa los datos del ERP.")
    ).toBeInTheDocument()
    expect(
      within(paso(1)).queryByRole("link", { name: "Ir a Importación" })
    ).not.toBeInTheDocument()
  })

  it("se oculta con 'Ocultar guía'", async () => {
    conProveedores(60)
    renderizarPagina(<GuiaUso />)
    await userEvent.click(
      await screen.findByRole("button", { name: "Ocultar guía" })
    )
    expect(
      screen.queryByRole("heading", { name: "Cómo usar PluriOne" })
    ).not.toBeInTheDocument()
    expect(
      JSON.parse(localStorage.getItem(claveGuia(USUARIO_DE_PRUEBA)) ?? "{}")
        .oculta
    ).toBe(true)
  })

  it("al ocultarse, el foco pasa al contenido en vez de perderse", async () => {
    conProveedores(60)
    renderizarPagina(
      <>
        <div id="contenido" tabIndex={-1} />
        <GuiaUso />
      </>
    )
    await userEvent.click(
      await screen.findByRole("button", { name: "Ocultar guía" })
    )
    expect(document.getElementById("contenido")).toHaveFocus()
  })

  it("mientras no llega la respuesta no muestra la guía ni un avance inventado", () => {
    simularApi(() => new Promise<Response>(() => {}))
    renderizarPagina(<GuiaUso />)
    expect(
      screen.queryByRole("heading", { name: "Cómo usar PluriOne" })
    ).not.toBeInTheDocument()
    expect(screen.queryByText("0 de 4 listos")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("link", { name: "Ir a Importación" })
    ).not.toBeInTheDocument()
  })

  it("si la consulta falla, no muestra la guía ni un avance inventado", async () => {
    simularApi(() => new Response("", { status: 500 }))
    const { cliente } = renderizarPagina(<GuiaUso />)
    await waitFor(() =>
      expect(cliente.getQueryState(["proveedores", "existencia"])?.status).toBe(
        "error"
      )
    )
    expect(
      screen.queryByRole("heading", { name: "Cómo usar PluriOne" })
    ).not.toBeInTheDocument()
    expect(screen.queryByText("0 de 4 listos")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("link", { name: "Ir a Importación" })
    ).not.toBeInTheDocument()
  })

  it("con la guía oculta no consulta al servidor", async () => {
    localStorage.setItem(
      claveGuia(USUARIO_DE_PRUEBA),
      JSON.stringify({
        oculta: true,
        visitas: { proveedores: false, precios: false },
      })
    )
    const simulado = simularApi(() =>
      respuestaJson({ total: 60, elementos: [] })
    )
    renderizarPagina(<GuiaUso />)
    await new Promise((resolver) => setTimeout(resolver, 50))
    expect(simulado).not.toHaveBeenCalled()
  })

  it("con el almacenamiento bloqueado se muestra con los pasos 2 y 3 pendientes", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    conProveedores(60)
    renderizarPagina(<GuiaUso />)
    expect(await screen.findByText("1 de 4 listos")).toBeInTheDocument()
    expect(paso(2)).toHaveTextContent("Pendiente")
    expect(paso(3)).toHaveTextContent("Pendiente")
  })

  it("los términos de los pasos abren su definición", async () => {
    conProveedores(60)
    renderizarPagina(<GuiaUso />)
    expect(
      await screen.findByRole("button", { name: "desempeño" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "precio de referencia" })
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    conProveedores(60)
    const { container } = renderizarPagina(<GuiaUso />)
    await screen.findByText("1 de 4 listos")
    await esperarSinViolaciones(container)
  })
})
