import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Alertas } from "@/paginas/Alertas"
import {
  esperarSinViolaciones,
  renderizarPagina,
  ubicacionActual,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

afterEach(cleanup)

describe("Alertas", () => {
  it("lee los filtros de la URL y ofrece quitarlos", async () => {
    renderizarPagina(<Alertas />, {
      ruta: "/alertas?tipo=vencimiento&severidad=alta",
    })

    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveTextContent(
      "Contrato por vencer"
    )
    expect(
      screen.getByRole("combobox", { name: "Severidad" })
    ).toHaveTextContent("Alta")
    expect(screen.getByText("No hay alertas activas")).toBeInTheDocument()

    await userEvent.click(
      screen.getByRole("button", { name: "Quitar filtros" })
    )
    expect(ubicacionActual()).toBe("/alertas")
  })

  it("cambiar el tipo actualiza la URL", async () => {
    renderizarPagina(<Alertas />, { ruta: "/alertas" })
    await userEvent.click(screen.getByRole("combobox", { name: "Tipo" }))
    await userEvent.click(
      await screen.findByRole("option", { name: "Sobreprecio" })
    )
    expect(ubicacionActual()).toBe("/alertas?tipo=sobreprecio")
  })

  it("ignora valores inválidos de la URL", () => {
    renderizarPagina(<Alertas />, {
      ruta: "/alertas?tipo=inventado&severidad=x",
    })
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveTextContent(
      "Todos los tipos"
    )
    expect(
      screen.queryByRole("button", { name: "Quitar filtros" })
    ).not.toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(<Alertas />, { ruta: "/alertas" })
    await esperarSinViolaciones(container)
  })

  it("sugiere ver proveedores y revisar precios", () => {
    renderizarPagina(<Alertas />, { ruta: "/alertas" })
    expect(
      screen.getByRole("link", { name: /Ver proveedores/ })
    ).toHaveAttribute("href", "/proveedores")
    expect(
      screen.getByRole("link", { name: /Revisar precios/ })
    ).toHaveAttribute("href", "/precios")
  })
})
