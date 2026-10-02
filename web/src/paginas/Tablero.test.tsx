import { cleanup, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Tablero } from "@/paginas/Tablero"
import { sesionDePrueba } from "@/pruebas/sesion"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
})

describe("Tablero", () => {
  it("saluda y muestra los cuatro indicadores sin datos con su enlace", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Tablero />)

    expect(screen.getByRole("heading", { level: 1, name: "Tablero" })).toBeInTheDocument()
    expect(screen.getByText(/Hola, Ana\./)).toBeInTheDocument()
    expect(screen.getAllByText("Sin datos")).toHaveLength(4)
    expect(screen.getByRole("link", { name: "Ver vencimientos" })).toHaveAttribute("href", "/alertas?tipo=vencimiento")
    expect(screen.getByRole("link", { name: "Ver riesgos" })).toHaveAttribute("href", "/alertas?tipo=riesgo")
    expect(screen.getByRole("link", { name: "Ver sobreprecios" })).toHaveAttribute("href", "/precios?vista=sobreprecios")
    expect(screen.getByRole("note")).toHaveTextContent("Inteligencia en preparación")
  })

  it("solo el administrador ve el estado de los datos", () => {
    renderizarPagina(<Tablero />)
    expect(screen.getByRole("heading", { name: "Estado de los datos" })).toBeInTheDocument()

    cleanup()
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Tablero />)
    expect(screen.queryByRole("heading", { name: "Estado de los datos" })).not.toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(<Tablero />)
    await esperarSinViolaciones(container)
  })
})
