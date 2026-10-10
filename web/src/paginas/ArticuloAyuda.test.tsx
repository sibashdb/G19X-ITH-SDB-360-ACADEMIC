import { cleanup, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ArticuloAyuda } from "@/paginas/ArticuloAyuda"
import { sesionDePrueba } from "@/pruebas/sesion"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const abrir = (slug: string) =>
  renderizarPagina(<ArticuloAyuda />, {
    ruta: `/ayuda/${slug}`,
    patron: "/ayuda/:articulo",
  })

afterEach(() => cleanup())

describe("ArticuloAyuda", () => {
  it("muestra el artículo con sus pasos y enlaces", async () => {
    sesionDePrueba.roles = ["comprador"]
    const { container } = abrir("importar-datos")
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Importar los datos del ERP",
      })
    ).toBeInTheDocument()
    expect(screen.getAllByRole("listitem").length).toBeGreaterThan(2)
    expect(
      screen.getByRole("link", { name: "Ir a Importación" })
    ).toHaveAttribute("href", "/importacion")
    expect(
      screen.getByRole("link", { name: /Centro de ayuda/ })
    ).toHaveAttribute("href", "/ayuda")
    await esperarSinViolaciones(container)
  })

  it("un artículo que no existe lo dice", () => {
    sesionDePrueba.roles = ["comprador"]
    abrir("no-existe")
    expect(screen.getByText("No encontramos ese artículo")).toBeInTheDocument()
  })

  it("los artículos de administración son solo para administración", () => {
    sesionDePrueba.roles = ["comprador"]
    abrir("gestionar-usuarios")
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    cleanup()
    sesionDePrueba.roles = ["admin"]
    abrir("gestionar-usuarios")
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Dar de alta y administrar usuarios",
      })
    ).toBeInTheDocument()
  })
})
