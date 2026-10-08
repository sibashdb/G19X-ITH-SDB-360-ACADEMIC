import { cleanup, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Tablero } from "@/paginas/Tablero"
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

beforeEach(() => {
  simularApi((url) =>
    url.startsWith("/api/proveedores/proveedores?")
      ? respuestaJson({ total: 60, elementos: [] })
      : new Response("", { status: 404 })
  )
})

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe("Tablero", () => {
  it("muestra la guía de uso arriba del tablero", async () => {
    renderizarPagina(<Tablero />)
    expect(
      await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    ).toBeInTheDocument()
  })

  it("saluda y muestra los cuatro indicadores sin datos con su enlace", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Tablero />)

    expect(
      screen.getByRole("heading", { level: 1, name: "Tablero" })
    ).toBeInTheDocument()
    expect(screen.getByText(/Hola, Ana\./)).toBeInTheDocument()
    expect(screen.getAllByText("Sin datos")).toHaveLength(4)
    expect(
      screen.getByRole("link", { name: "Ver vencimientos" })
    ).toHaveAttribute("href", "/alertas?tipo=vencimiento")
    expect(screen.getByRole("link", { name: "Ver riesgos" })).toHaveAttribute(
      "href",
      "/alertas?tipo=riesgo"
    )
    expect(
      screen.getByRole("link", { name: "Ver sobreprecios" })
    ).toHaveAttribute("href", "/precios?vista=sobreprecios")
    expect(screen.getByRole("note")).toHaveTextContent(
      "Inteligencia en preparación"
    )
    expect(
      screen.getByRole("button", { name: "sobreprecios" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "puntuación" })
    ).toBeInTheDocument()
  })

  it("solo el administrador ve el estado de los datos", () => {
    renderizarPagina(<Tablero />)
    expect(
      screen.getByRole("heading", { name: "Estado de los datos" })
    ).toBeInTheDocument()

    cleanup()
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Tablero />)
    expect(
      screen.queryByRole("heading", { name: "Estado de los datos" })
    ).not.toBeInTheDocument()
  })

  it("las secciones con destino ofrecen ver el detalle", () => {
    renderizarPagina(<Tablero />)
    expect(
      screen.getByRole("link", { name: "Ver alertas de vencimiento" })
    ).toHaveAttribute("href", "/alertas?tipo=vencimiento")
    expect(screen.getByRole("link", { name: "Ver todas las alertas" })).toHaveAttribute(
      "href",
      "/alertas"
    )
    expect(screen.getByRole("link", { name: "Ver ranking completo" })).toHaveAttribute(
      "href",
      "/ranking"
    )
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(<Tablero />)
    await esperarSinViolaciones(container)
  })
})
