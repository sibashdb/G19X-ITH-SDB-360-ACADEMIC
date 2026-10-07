import { cleanup, screen } from "@testing-library/react"
import { Tags } from "lucide-react"
import { afterEach, describe, expect, it } from "vitest"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

afterEach(cleanup)

describe("SiguientePaso", () => {
  it("muestra cada enlace con su descripción y destino", async () => {
    const { container } = renderizarPagina(
      <SiguientePaso
        enlaces={[
          {
            titulo: "Revisar precios",
            descripcion: "Compare lo que paga con el mercado.",
            ruta: "/precios",
            icono: Tags,
          },
        ]}
      />
    )
    expect(
      screen.getByRole("heading", { level: 2, name: "Siguiente paso" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /Revisar precios/ })
    ).toHaveAttribute("href", "/precios")
    expect(
      screen.getByText("Compare lo que paga con el mercado.")
    ).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })
})
