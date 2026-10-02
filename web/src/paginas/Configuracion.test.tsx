import { cleanup, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Configuracion } from "@/paginas/Configuracion"
import { sesionDePrueba } from "@/pruebas/sesion"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
})

describe("Configuracion", () => {
  it("muestra al administrador las secciones de puntuación y modelo", () => {
    renderizarPagina(<Configuracion />)
    expect(screen.getByRole("heading", { name: "Pesos de la puntuación" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Modelo de precios" })).toBeInTheDocument()
  })

  it("bloquea a quien no es administrador", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Configuracion />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Pesos de la puntuación" })).not.toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(<Configuracion />)
    await esperarSinViolaciones(container)
  })
})
