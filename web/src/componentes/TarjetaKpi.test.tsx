import { cleanup, screen } from "@testing-library/react"
import { Wallet } from "lucide-react"
import { afterEach, describe, expect, it } from "vitest"
import { TarjetaKpi } from "@/componentes/TarjetaKpi"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

afterEach(cleanup)

const base = {
  titulo: "Gasto anual contratado",
  icono: Wallet,
  enlace: "/proveedores",
  textoEnlace: "Ver proveedores",
}

describe("TarjetaKpi", () => {
  it("sin valor muestra un guion y 'Sin datos' para lectores de pantalla", () => {
    renderizarPagina(<TarjetaKpi {...base} valor={null} />)
    expect(screen.getByText("Sin datos")).toHaveClass("sr-only")
    expect(
      screen.getByRole("link", { name: "Ver proveedores" })
    ).toHaveAttribute("href", "/proveedores")
  })

  it("pinta el icono con el tinte de su tono y marca con un acento los estados de atención", () => {
    const { container } = renderizarPagina(
      <TarjetaKpi {...base} valor="12" tono="advertencia" />
    )
    expect(container.querySelector('[data-tono="advertencia"]')).toHaveClass(
      "bg-advertencia-suave",
      "text-warning"
    )
    expect(container.querySelector('[data-slot="card"]')).toHaveClass(
      "border-l-warning"
    )
  })

  it("el tono informativo no lleva acento lateral", () => {
    const { container } = renderizarPagina(<TarjetaKpi {...base} valor="12" />)
    expect(container.querySelector('[data-tono="info"]')).toHaveClass(
      "bg-info-suave",
      "text-accent"
    )
    expect(container.querySelector('[data-slot="card"]')).not.toHaveClass(
      "border-l-3"
    )
  })

  it("muestra la variación con texto, no solo con color", () => {
    renderizarPagina(
      <TarjetaKpi
        {...base}
        valor="$48.2 M"
        variacion={{
          texto: "3.1 % más que el año anterior",
          direccion: "sube",
        }}
      />
    )
    expect(
      screen.getByText("3.1 % más que el año anterior")
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(
      <TarjetaKpi
        {...base}
        valor="12"
        tono="riesgo"
        variacion={{ texto: "2 menos que el mes anterior", direccion: "baja" }}
      />
    )
    await esperarSinViolaciones(container)
  })
})
