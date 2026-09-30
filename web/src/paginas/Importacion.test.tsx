import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Importacion } from "@/paginas/Importacion"

vi.mock("react-oidc-context", () => {
  const carga = btoa(JSON.stringify({ realm_access: { roles: ["admin"] } }))
  return { useAuth: () => ({ user: { access_token: `cabecera.${carga}.firma` } }) }
})

function respuestaJson(cuerpo: object, estado: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { "Content-Type": "application/json" },
  })
}

function renderizar(
  cliente = new QueryClient({ defaultOptions: { mutations: { retry: false } } }),
) {
  return render(
    <QueryClientProvider client={cliente}>
      <Importacion />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Importacion", () => {
  it("muestra los errores por fila que devuelve la API", async () => {
    const simulado = vi.fn().mockResolvedValue(
      respuestaJson(
        {
          title: "Archivo con errores",
          detail: "Se encontraron 1 error(es); no se importó ninguna fila.",
          errores: [{ fila: 2, campo: "contacto_email", mensaje: "Formato inválido" }],
        },
        422,
      ),
    )
    vi.stubGlobal("fetch", simulado)
    renderizar()

    await userEvent.selectOptions(screen.getByLabelText("Tipo de archivo"), "proveedores")
    await userEvent.upload(
      screen.getByLabelText("Archivo CSV"),
      new File(["rfc\n"], "proveedores.csv", { type: "text/csv" }),
    )
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    expect(await screen.findByText("Formato inválido")).toBeInTheDocument()
    expect(screen.getByText("contacto_email")).toBeInTheDocument()
    const [url, init] = simulado.mock.calls[0]
    expect(url).toBe("/api/proveedores/importaciones/proveedores")
    expect(init.method).toBe("POST")
  })

  it("muestra el resumen cuando la importación es correcta", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        respuestaJson({ entidad: "servicios", filas: 40, registros: 40, omitidos: 0, eventos: 0 }, 200),
      ),
    )
    renderizar()

    await userEvent.upload(
      screen.getByLabelText("Archivo CSV"),
      new File(["x"], "servicios.csv", { type: "text/csv" }),
    )
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    expect(await screen.findByText(/40 registros/)).toBeInTheDocument()
  })

  it("invalida la lista y los detalles de proveedores tras importar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        respuestaJson({ entidad: "contratos", filas: 1, registros: 1, omitidos: 0, eventos: 1 }, 200),
      ),
    )
    const cliente = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const invalidar = vi.spyOn(cliente, "invalidateQueries")
    renderizar(cliente)

    await userEvent.upload(
      screen.getByLabelText("Archivo CSV"),
      new File(["x"], "contratos.csv", { type: "text/csv" }),
    )
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))
    await screen.findByText(/1 registros/)

    expect(invalidar).toHaveBeenCalledWith({ queryKey: ["proveedores"] })
    expect(invalidar).toHaveBeenCalledWith({ queryKey: ["proveedor"] })
  })
})
