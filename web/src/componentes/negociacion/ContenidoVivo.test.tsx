import { useQuery } from "@tanstack/react-query"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"
import { ContenidoVivo } from "@/componentes/negociacion/ContenidoVivo"
import { renderizarPagina } from "@/pruebas/utilidades"

afterEach(() => {
  cleanup()
})

describe("ContenidoVivo", () => {
  it("conserva los datos si una actualización falla y lo avisa", async () => {
    let llamadas = 0
    function Vista() {
      const consulta = useQuery({
        queryKey: ["vivo"],
        queryFn: async () => {
          llamadas += 1
          if (llamadas > 1) throw new Error("caída")
          return "Hola"
        },
      })
      return (
        <>
          <button onClick={() => void consulta.refetch()}>Actualizar</button>
          <ContenidoVivo consulta={consulta}>{(d) => <p>{d}</p>}</ContenidoVivo>
        </>
      )
    }
    renderizarPagina(<Vista />)
    expect(await screen.findByText("Hola")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Actualizar" }))
    expect(
      await screen.findByText(
        "No se pudo actualizar; se muestran los últimos datos recibidos."
      )
    ).toHaveAttribute("role", "status")
    expect(screen.getByText("Hola")).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Reintentar" })
    ).not.toBeInTheDocument()
  })

  it("si nunca cargó, muestra el error con Reintentar", async () => {
    function Vista() {
      const consulta = useQuery({
        queryKey: ["vivo-error"],
        queryFn: async (): Promise<string> => {
          throw new Error("caída")
        },
      })
      return (
        <ContenidoVivo consulta={consulta}>{(d) => <p>{d}</p>}</ContenidoVivo>
      )
    }
    renderizarPagina(<Vista />)
    expect(
      await screen.findByRole("button", { name: "Reintentar" })
    ).toBeInTheDocument()
    expect(screen.getByText("caída")).toBeInTheDocument()
  })
})
