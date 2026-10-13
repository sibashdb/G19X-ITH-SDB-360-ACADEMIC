import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Paginacion } from "@/componentes/Paginacion"

afterEach(cleanup)

describe("Paginacion", () => {
  it("en la primera página, Anterior sigue enfocable pero no cambia de página", async () => {
    const alCambiar = vi.fn()
    render(
      <Paginacion
        pagina={1}
        total={60}
        porPagina={25}
        nombre="alertas"
        alCambiar={alCambiar}
      />
    )
    const anterior = screen.getByRole("button", { name: "Anterior" })
    expect(anterior).toHaveAttribute("aria-disabled", "true")
    expect(anterior).toBeEnabled()

    anterior.focus()
    await userEvent.keyboard("{Enter}")
    expect(alCambiar).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))
    expect(alCambiar).toHaveBeenCalledWith(2)
  })

  it("en la última página, Siguiente conserva el foco y no avanza", async () => {
    const alCambiar = vi.fn()
    render(
      <Paginacion
        pagina={3}
        total={60}
        porPagina={25}
        nombre="alertas"
        alCambiar={alCambiar}
      />
    )
    const siguiente = screen.getByRole("button", { name: "Siguiente" })
    expect(siguiente).toHaveAttribute("aria-disabled", "true")

    siguiente.focus()
    await userEvent.keyboard("{Enter}")
    expect(alCambiar).not.toHaveBeenCalled()
    expect(siguiente).toHaveFocus()
    expect(
      screen.getByText("Mostrando 51–60 de 60 alertas")
    ).toBeInTheDocument()
  })
})
