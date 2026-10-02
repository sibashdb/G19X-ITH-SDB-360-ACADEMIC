import { cleanup, fireEvent, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Importacion } from "@/paginas/Importacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const zonaDeArchivo = () => screen.getByLabelText(/Arrastre el archivo CSV/)

function soltar(...archivos: File[]) {
  fireEvent.drop(zonaDeArchivo().closest("label")!, {
    dataTransfer: { files: archivos },
  })
}

async function irAlPasoDeArchivo(tipo = /Catálogo de servicios/) {
  await userEvent.click(screen.getByRole("radio", { name: tipo }))
  await userEvent.click(screen.getByRole("button", { name: "Continuar" }))
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Importacion", () => {
  it("guía la importación en tres pasos y muestra el resumen", async () => {
    simularApi({
      "/api/proveedores/importaciones/servicios": () =>
        respuestaJson({
          entidad: "servicios",
          filas: 40,
          registros: 40,
          omitidos: 0,
          eventos: 0,
        }),
    })
    renderizarPagina(<Importacion />)

    expect(
      screen.getByRole("radio", { name: /Catálogo de servicios/ })
    ).toBeChecked()
    expect(screen.getByText("Tipo de archivo").closest("li")).toHaveAttribute(
      "aria-current",
      "step"
    )
    await irAlPasoDeArchivo()
    await userEvent.upload(
      zonaDeArchivo(),
      new File(["x"], "servicios.csv", { type: "text/csv" })
    )
    expect(screen.getByText(/servicios\.csv/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    expect(
      await screen.findByText("Importación completada")
    ).toBeInTheDocument()
    expect(screen.getByText("Resultado").closest("li")).toHaveAttribute(
      "aria-current",
      "step"
    )
    expect(screen.getByText("Registros").nextElementSibling).toHaveTextContent(
      "40"
    )
    expect(
      screen.getByRole("button", { name: /Importar Proveedores/ })
    ).toBeInTheDocument()
  })

  it("muestra los errores por fila que devuelve la API y permite elegir otro archivo", async () => {
    const simulado = simularApi({
      "/api/proveedores/importaciones/proveedores": () =>
        respuestaJson(
          {
            title: "Archivo con errores",
            detail: "Se encontraron 1 error(es); no se importó ninguna fila.",
            errores: [
              { fila: 2, campo: "contacto_email", mensaje: "Formato inválido" },
            ],
          },
          422
        ),
    })
    renderizarPagina(<Importacion />)

    await irAlPasoDeArchivo(/Proveedores/)
    await userEvent.upload(
      zonaDeArchivo(),
      new File(["rfc\n"], "proveedores.csv", { type: "text/csv" })
    )
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    expect(await screen.findByText("Formato inválido")).toBeInTheDocument()
    expect(screen.getByText("contacto_email")).toBeInTheDocument()
    const [url, init] = simulado.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ]
    expect(url).toBe("/api/proveedores/importaciones/proveedores")
    expect(init.method).toBe("POST")

    await userEvent.click(
      screen.getByRole("button", { name: "Elegir otro archivo" })
    )
    expect(zonaDeArchivo()).toBeInTheDocument()
  })

  it("no permite volver atrás mientras la importación está en curso", async () => {
    simularApi({
      "/api/proveedores/importaciones/servicios": () =>
        new Promise<Response>(() => {}),
    })
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()
    await userEvent.upload(
      zonaDeArchivo(),
      new File(["x"], "servicios.csv", { type: "text/csv" })
    )

    expect(screen.getByRole("button", { name: "Atrás" })).toBeEnabled()
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    expect(
      await screen.findByRole("button", { name: "Importando…" })
    ).toBeDisabled()
    expect(screen.getByRole("button", { name: "Atrás" })).toBeDisabled()
  })

  it("invalida todas las consultas tras importar, incluido el catálogo de servicios", async () => {
    simularApi({
      "/api/proveedores/importaciones/servicios": () =>
        respuestaJson({
          entidad: "servicios",
          filas: 1,
          registros: 1,
          omitidos: 0,
          eventos: 1,
        }),
    })
    const { cliente } = renderizarPagina(<Importacion />)
    // Consultas de otras páginas que una importación puede dejar obsoletas (Precios usa "servicios").
    const claves = [
      ["servicios"],
      ["proveedores", {}],
      ["proveedor", "p1"],
      ["proveedor", "p1", "contratos"],
    ]
    for (const clave of claves) cliente.setQueryData(clave, [])

    await irAlPasoDeArchivo()
    await userEvent.upload(
      zonaDeArchivo(),
      new File(["x"], "servicios.csv", { type: "text/csv" })
    )
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))
    await screen.findByText("Importación completada")

    for (const clave of claves) {
      expect(
        cliente.getQueryState(clave)?.isInvalidated,
        JSON.stringify(clave)
      ).toBe(true)
    }
  })

  it("rechaza en el navegador un archivo que no es CSV", async () => {
    const simulado = simularApi({})
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()

    soltar(new File(["x"], "datos.xlsx"))

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El archivo debe tener extensión .csv."
    )
    expect(screen.getByRole("button", { name: "Importar" })).toBeDisabled()
    expect(simulado).not.toHaveBeenCalled()
  })

  it("acepta la extensión .CSV en mayúsculas", async () => {
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()

    soltar(new File(["x"], "DATOS.CSV"))

    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Importar" })).toBeEnabled()
  })

  it("rechaza archivos de más de 10 MB y vacíos", async () => {
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()

    const grande = new File(["x"], "grande.csv")
    Object.defineProperty(grande, "size", { value: 10 * 1024 * 1024 + 1 })
    soltar(grande)
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El archivo excede el límite de 10 MB."
    )

    soltar(new File([], "vacio.csv"))
    expect(screen.getByRole("alert")).toHaveTextContent(
      "El archivo está vacío."
    )
  })

  it("pide soltar un solo archivo", async () => {
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()

    soltar(new File(["x"], "a.csv"), new File(["y"], "b.csv"))

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Suelte un solo archivo a la vez."
    )
    expect(screen.getByRole("button", { name: "Importar" })).toBeDisabled()
  })

  it("solo los administradores pueden importar", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Importacion />)

    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    expect(screen.queryByRole("radio")).not.toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad en los pasos", async () => {
    const { container } = renderizarPagina(<Importacion />)
    await esperarSinViolaciones(container)
    await irAlPasoDeArchivo()
    await esperarSinViolaciones(container)
  })
})
