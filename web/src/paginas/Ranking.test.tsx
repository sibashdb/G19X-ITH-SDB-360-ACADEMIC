import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Ranking } from "@/paginas/Ranking"
import {
  esperarSinViolaciones,
  renderizarPagina,
  ubicacionActual,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

afterEach(cleanup)

describe("Ranking", () => {
  it("abre la categoría indicada en la URL", () => {
    renderizarPagina(<Ranking />, { ruta: "/ranking?categoria=nube" })
    expect(screen.getByRole("tab", { name: "Nube" })).toHaveAttribute(
      "aria-selected",
      "true"
    )
    expect(
      screen.getByRole("heading", { name: "Ranking · Nube" })
    ).toBeInTheDocument()
    expect(screen.getByText("Sin puntuaciones todavía")).toBeInTheDocument()
  })

  it("cambiar de pestaña actualiza la URL", async () => {
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    await userEvent.click(screen.getByRole("tab", { name: "Soporte" }))
    expect(ubicacionActual()).toBe("/ranking?categoria=soporte")
    await userEvent.click(screen.getByRole("tab", { name: "Todas" }))
    expect(ubicacionActual()).toBe("/ranking")
  })

  it("una categoría inválida muestra todas", () => {
    renderizarPagina(<Ranking />, { ruta: "/ranking?categoria=inventada" })
    expect(screen.getByRole("tab", { name: "Todas" })).toHaveAttribute(
      "aria-selected",
      "true"
    )
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(<Ranking />, { ruta: "/ranking" })
    await esperarSinViolaciones(container)
  })

  it("sugiere ver proveedores y revisar precios", () => {
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    expect(
      screen.getByRole("link", { name: /Ver proveedores/ })
    ).toHaveAttribute("href", "/proveedores")
    expect(
      screen.getByRole("link", { name: /Revisar precios/ })
    ).toHaveAttribute("href", "/precios")
  })
})
