import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { GuiaUso } from "@/componentes/GuiaUso"
import { CLAVE_GUIA } from "@/guia"
import { sesionDePrueba } from "@/pruebas/sesion"
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

const paso = (numero: number) =>
  screen.getAllByRole("listitem")[numero - 1]

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
      screen.getByRole("heading", { name: "Cómo usar PluriOne" })
    ).toBeInTheDocument()
    expect(await screen.findByText("1 de 3 listos")).toBeInTheDocument()
    expect(paso(1)).toHaveTextContent("Hecho")
    expect(paso(2)).toHaveTextContent("Pendiente")
    expect(within(paso(2)).getByRole("link", { name: "Ver proveedores" })).toHaveAttribute(
      "href",
      "/proveedores"
    )
    expect(paso(4)).toHaveTextContent("Próximamente")
  })

  it("las visitas registradas marcan los pasos 2 y 3", async () => {
    conProveedores(60)
    localStorage.setItem(
      CLAVE_GUIA,
      JSON.stringify({ oculta: false, visitas: { proveedores: true, precios: true } })
    )
    renderizarPagina(<GuiaUso />)
    expect(await screen.findByText("3 de 3 listos")).toBeInTheDocument()
  })

  it("sin datos, el admin ve el enlace a Importación", async () => {
    conProveedores(0)
    renderizarPagina(<GuiaUso />)
    expect(
      await within(paso(1)).findByRole("link", { name: "Ir a Importación" })
    ).toHaveAttribute("href", "/importacion")
  })

  it("sin datos, otros roles leen que Administración importa los datos", async () => {
    sesionDePrueba.roles = ["comprador"]
    conProveedores(0)
    renderizarPagina(<GuiaUso />)
    expect(
      await within(paso(1)).findByText("Administración importa los datos del ERP.")
    ).toBeInTheDocument()
    expect(
      within(paso(1)).queryByRole("link", { name: "Ir a Importación" })
    ).not.toBeInTheDocument()
  })

  it("se oculta con 'Ocultar guía'", async () => {
    conProveedores(60)
    renderizarPagina(<GuiaUso />)
    await userEvent.click(screen.getByRole("button", { name: "Ocultar guía" }))
    expect(
      screen.queryByRole("heading", { name: "Cómo usar PluriOne" })
    ).not.toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem(CLAVE_GUIA) ?? "{}").oculta).toBe(true)
  })

  it("con el almacenamiento bloqueado se muestra con los pasos 2 y 3 pendientes", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    conProveedores(60)
    renderizarPagina(<GuiaUso />)
    expect(await screen.findByText("1 de 3 listos")).toBeInTheDocument()
    expect(paso(2)).toHaveTextContent("Pendiente")
    expect(paso(3)).toHaveTextContent("Pendiente")
  })

  it("no tiene violaciones de accesibilidad", async () => {
    conProveedores(60)
    const { container } = renderizarPagina(<GuiaUso />)
    await screen.findByText("1 de 3 listos")
    await esperarSinViolaciones(container)
  })
})
