import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { createMemoryRouter, Outlet, RouterProvider } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ErrorDePagina } from "@/componentes/ErrorDePagina"
import { esperarSinViolaciones } from "@/pruebas/utilidades"

afterEach(() => vi.restoreAllMocks())

/** Misma forma que `rutas.tsx`: un marco que se queda y, dentro, las páginas con su frontera de error. */
function renderizarConPaginaQueFalla() {
  const error = new Error("Failed to fetch dynamically imported module")
  const router = createMemoryRouter(
    [
      {
        path: "/",
        Component: () => (
          <>
            <nav aria-label="Menú de prueba">Menú</nav>
            <Outlet />
          </>
        ),
        children: [
          {
            ErrorBoundary: ErrorDePagina,
            children: [
              {
                path: "precios",
                lazy: () => Promise.reject(error),
              },
            ],
          },
        ],
      },
    ],
    { initialEntries: ["/precios"] }
  )
  const registro = vi.spyOn(console, "error").mockImplementation(() => {})
  const resultado = render(<RouterProvider router={router} />)
  return { error, registro, ...resultado }
}

describe("ErrorDePagina", () => {
  it("conserva el marco y explica en español que la página no se pudo cargar", async () => {
    const { error, registro, container } = renderizarConPaginaQueFalla()

    expect(
      await screen.findByText("No se pudo cargar esta página")
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Puede que haya una versión nueva de la plataforma o que se haya perdido la conexión."
      )
    ).toBeInTheDocument()
    // El menú sigue en pantalla y no se muestra el error crudo ni la pantalla en inglés de la librería.
    expect(
      screen.getByRole("navigation", { name: "Menú de prueba" })
    ).toBeInTheDocument()
    expect(screen.queryByText(/Unexpected Application Error/)).toBeNull()
    expect(screen.queryByText(/dynamically imported/)).toBeNull()
    // El detalle técnico solo va a la consola.
    expect(registro).toHaveBeenCalledWith(expect.any(String), error)
    await esperarSinViolaciones(container)
  })

  it("«Recargar la página» recarga la ventana", async () => {
    renderizarConPaginaQueFalla()
    const recargar = vi.fn()
    vi.stubGlobal("location", { ...window.location, reload: recargar })

    await userEvent.click(
      await screen.findByRole("button", { name: "Recargar la página" })
    )

    expect(recargar).toHaveBeenCalledTimes(1)
    vi.unstubAllGlobals()
  })
})
