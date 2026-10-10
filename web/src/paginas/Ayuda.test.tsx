import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { GLOSARIO } from "@/glosario"
import { Ayuda } from "@/paginas/Ayuda"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  ubicacionActual,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

afterEach(() => cleanup())

describe("Ayuda", () => {
  it("muestra los temas de su rol, las preguntas y el glosario", async () => {
    sesionDePrueba.roles = ["comprador"]
    const { container } = renderizarPagina(<Ayuda />, { ruta: "/ayuda" })
    for (const tema of [
      "Primeros pasos",
      "Proveedores y precios",
      "Datos e importación",
    ])
      expect(screen.getByRole("heading", { name: tema })).toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Administración" })
    ).not.toBeInTheDocument()
    expect(screen.queryByText("La invitación no llegó")).not.toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /Cómo usar PluriOne/ })
    ).toHaveAttribute("href", "/ayuda/como-usar-pluri-one")
    const glosario = screen
      .getByRole("heading", { name: "Glosario" })
      .closest("[data-slot=card]")!
    for (const { termino } of Object.values(GLOSARIO))
      expect(
        within(glosario as HTMLElement).getByText(termino)
      ).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("administración ve también su tema y sus preguntas", () => {
    sesionDePrueba.roles = ["admin"]
    renderizarPagina(<Ayuda />, { ruta: "/ayuda" })
    expect(
      screen.getByRole("heading", { name: "Administración" })
    ).toBeInTheDocument()
    expect(screen.getByText("La invitación no llegó")).toBeInTheDocument()
  })

  it("una pregunta frecuente se abre con clic", async () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Ayuda />, { ruta: "/ayuda" })
    const pregunta = screen.getByText("Mi sesión se cerró sola")
    expect(pregunta.closest("details")).not.toHaveAttribute("open")
    await userEvent.click(pregunta)
    expect(pregunta.closest("details")).toHaveAttribute("open")
  })

  it("la búsqueda va en la URL y muestra los resultados", async () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Ayuda />, { ruta: "/ayuda" })
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Buscar en la ayuda" }),
      "importar"
    )
    await userEvent.click(screen.getByRole("button", { name: "Buscar" }))
    expect(ubicacionActual()).toBe("/ayuda?q=importar")
    expect(
      screen.getByRole("heading", { name: "Resultados para «importar»" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /Importar los datos del ERP/ })
    ).toBeInTheDocument()
  })

  it("sin resultados lo dice", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Ayuda />, { ruta: "/ayuda?q=zzz" })
    expect(screen.getByText("Sin resultados")).toBeInTheDocument()
  })
})
