import { useQuery } from "@tanstack/react-query"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Bell } from "lucide-react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ErrorApi } from "@/api"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import {
  ContenidoConsulta,
  EstadoCarga,
  EstadoError,
  EstadoVacio,
} from "@/componentes/Estados"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { sesionDePrueba } from "@/pruebas/sesion"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
})

describe("estados estándar", () => {
  it("EstadoCarga anuncia la carga sin texto visible", () => {
    renderizarPagina(<EstadoCarga filas={3} />)
    expect(screen.getByRole("status")).toHaveTextContent("Cargando…")
  })

  it("EstadoVacio muestra título, explicación y acción", () => {
    renderizarPagina(
      <EstadoVacio
        icono={Bell}
        titulo="Sin alertas"
        descripcion="No hay nada pendiente."
        accion={<Button>Actualizar</Button>}
      />
    )
    expect(screen.getByText("Sin alertas")).toBeInTheDocument()
    expect(screen.getByText("No hay nada pendiente.")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Actualizar" })
    ).toBeInTheDocument()
  })

  it("EstadoError usa el título de Problem Details y permite reintentar", async () => {
    const alReintentar = vi.fn()
    renderizarPagina(
      <EstadoError
        error={
          new ErrorApi(503, "Servicio no disponible", "Intente más tarde.")
        }
        alReintentar={alReintentar}
      />
    )
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Servicio no disponible"
    )
    expect(screen.getByRole("alert")).toHaveTextContent("Intente más tarde.")
    // jsdom no calcula estilos: se comprueba que la clase de color de la descripción sea un
    // token propio (una clase fusionada con otra no generaría CSS y dejaría el texto gris).
    expect(screen.getByRole("alert").className.split(/\s+/)).toContain(
      "*:data-[slot=alert-description]:text-destructive"
    )
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(alReintentar).toHaveBeenCalledOnce()
  })

  it("EstadoError sin ErrorApi usa un título genérico y sin reintento no muestra el botón", () => {
    renderizarPagina(<EstadoError error={new Error("Algo falló")} />)
    expect(screen.getByRole("alert")).toHaveTextContent(
      "No se pudo cargar la información"
    )
    expect(
      screen.queryByRole("button", { name: "Reintentar" })
    ).not.toBeInTheDocument()
  })

  it("ContenidoConsulta pasa de error a datos al reintentar", async () => {
    let intentos = 0
    function Consulta() {
      const consulta = useQuery({
        queryKey: ["prueba"],
        queryFn: async () => {
          intentos += 1
          if (intentos === 1)
            throw new ErrorApi(502, "Servicio no disponible", "Caído.")
          return "datos listos"
        },
      })
      return (
        <ContenidoConsulta consulta={consulta}>
          {(datos) => <p>{datos}</p>}
        </ContenidoConsulta>
      )
    }
    renderizarPagina(<Consulta />)

    expect(await screen.findByRole("alert")).toHaveTextContent("Caído.")
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByText("datos listos")).toBeInTheDocument()
  })
})

describe("estructura de página", () => {
  it("EncabezadoPagina y Seccion dan títulos h1 y h2", () => {
    renderizarPagina(
      <>
        <EncabezadoPagina
          titulo="Precios"
          descripcion="Precio de referencia."
        />
        <Seccion titulo="Historial">contenido</Seccion>
      </>
    )
    expect(
      screen.getByRole("heading", { level: 1, name: "Precios" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { level: 2, name: "Historial" })
    ).toBeInTheDocument()
  })

  it("RequiereRol muestra el contenido al rol indicado", () => {
    renderizarPagina(<RequiereRol rol="admin">Panel de admin</RequiereRol>)
    expect(screen.getByText("Panel de admin")).toBeInTheDocument()
  })

  it("RequiereRol bloquea a quien no tiene el rol", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<RequiereRol rol="admin">Panel de admin</RequiereRol>)
    expect(screen.queryByText("Panel de admin")).not.toBeInTheDocument()
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Ir al tablero" })).toHaveAttribute(
      "href",
      "/"
    )
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(
      <>
        <EncabezadoPagina titulo="Prueba" />
        <Seccion titulo="Sección">
          <EstadoVacio titulo="Vacío" descripcion="Nada aquí." />
        </Seccion>
        <EstadoCarga />
        <EstadoError error={new Error("x")} alReintentar={() => {}} />
      </>
    )
    await esperarSinViolaciones(container)
  })
})
