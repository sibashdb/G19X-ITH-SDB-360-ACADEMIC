import { cleanup, fireEvent, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Actividad } from "@/paginas/Actividad"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const USUARIOS = {
  total: 1,
  elementos: [
    {
      id: "u-ana",
      usuario: "ana",
      nombre: "Ana",
      apellidos: "López",
      correo: "ana@plataforma.example",
      roles: ["comprador"],
      activo: true,
      creado_en: "2026-10-01T00:00:00Z",
      ultimo_acceso: null,
    },
  ],
}

const REGISTROS = {
  total: 2,
  elementos: [
    {
      id: "r2",
      fecha: "2026-10-09T18:00:00Z",
      actor_id: "admin-1",
      actor_nombre: "admin1",
      tipo: "importacion.completada",
      objeto_tipo: "importacion",
      objeto_id: "contratos",
      objeto_nombre: "contratos",
      detalle: { registros: 1250, filas: 1300, omitidos: 50 },
      resultado: "exito",
      ip: "10.0.0.7",
    },
    {
      id: "r1",
      fecha: "2026-10-09T17:00:00Z",
      actor_id: null,
      actor_nombre: "fantasma",
      tipo: "sesion.fallida",
      objeto_tipo: null,
      objeto_id: null,
      objeto_nombre: null,
      detalle: { error: "user_not_found" },
      resultado: "fallo",
      ip: null,
    },
  ],
}

function api(pagina = REGISTROS) {
  return simularApi((url) => {
    if (url.startsWith("/api/administracion/usuarios"))
      return respuestaJson(USUARIOS)
    if (url.startsWith("/api/administracion/actividad/exportar"))
      return new Response("Fecha\n", {
        status: 200,
        headers: { "Content-Type": "text/csv" },
      })
    return respuestaJson(pagina)
  })
}

const llamadasDeLista = (simulado: ReturnType<typeof api>) =>
  simulado.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.startsWith("/api/administracion/actividad?"))

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("Actividad", () => {
  it("muestra quién hizo qué, con el resultado en texto", async () => {
    api()
    const { container } = renderizarPagina(<Actividad />, {
      ruta: "/sistema/actividad",
    })
    expect(
      await screen.findByText("Importó 1,250 contratos")
    ).toBeInTheDocument()
    const fallida = screen
      .getByText("Intento fallido de inicio de sesión: usuario inexistente")
      .closest("tr")!
    expect(within(fallida).getByText("fantasma")).toBeInTheDocument()
    expect(within(fallida).getByText("Falló")).toBeInTheDocument()
    expect(screen.getByText("Mostrando 1–2 de 2 registros")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("los filtros viajan en la URL y en la consulta", async () => {
    const simulado = api()
    renderizarPagina(<Actividad />, {
      ruta: "/sistema/actividad?persona=u-ana",
    })
    await screen.findByText("Importó 1,250 contratos")
    const primera = new URL(llamadasDeLista(simulado)[0], "http://localhost")
    expect(primera.searchParams.get("persona")).toBe("u-ana")
    expect(screen.getByRole("combobox", { name: "Persona" })).toHaveTextContent(
      "Ana López (ana)"
    )

    await userEvent.click(screen.getByRole("button", { name: "Importaciones" }))
    expect(ubicacionActual()).toBe(
      "/sistema/actividad?persona=u-ana&tipo=importaciones"
    )
    // jsdom no escribe tecla por tecla en un campo de fecha: se cambia el valor completo.
    fireEvent.change(screen.getByLabelText("Desde"), {
      target: { value: "2026-10-01" },
    })
    expect(ubicacionActual()).toContain("desde=2026-10-01")
    await screen.findByText("Importó 1,250 contratos")
    const ultima = new URL(
      llamadasDeLista(simulado).at(-1)!,
      "http://localhost"
    )
    expect(ultima.searchParams.get("tipo")).toBe("importaciones")
    expect(ultima.searchParams.get("desde")).toBe("2026-10-01")
  })

  it("un rango invertido avisa junto a las fechas y no consulta", async () => {
    const simulado = api()
    renderizarPagina(<Actividad />, {
      ruta: "/sistema/actividad?desde=2026-10-09&hasta=2026-10-01",
    })
    expect(
      await screen.findByText(
        "La fecha final debe ser igual o posterior a la inicial."
      )
    ).toBeInTheDocument()
    expect(screen.getByLabelText("Hasta")).toHaveAttribute(
      "aria-invalid",
      "true"
    )
    expect(llamadasDeLista(simulado)).toEqual([])
  })

  it("exporta con los mismos filtros y avisa del límite", async () => {
    const simulado = api({ ...REGISTROS, total: 12_000 })
    vi.stubGlobal(
      "URL",
      Object.assign(URL, {
        createObjectURL: vi.fn(() => "blob:x"),
        revokeObjectURL: vi.fn(),
      })
    )
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
    renderizarPagina(<Actividad />, {
      ruta: "/sistema/actividad?tipo=sesiones",
    })
    expect(
      await screen.findByText(
        "Se exportarán los 10,000 registros más recientes; acote las fechas para obtener el resto."
      )
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: /Exportar CSV/ }))
    const exportacion = simulado.mock.calls
      .map(([url]) => String(url))
      .find((url) => url.startsWith("/api/administracion/actividad/exportar"))
    expect(exportacion).toBe(
      "/api/administracion/actividad/exportar?tipo=sesiones"
    )
    expect(screen.getByRole("button", { name: /Exportar CSV/ })).toHaveFocus()
  })

  it("sin resultados con filtros ofrece limpiarlos", async () => {
    api({ total: 0, elementos: [] })
    renderizarPagina(<Actividad />, {
      ruta: "/sistema/actividad?tipo=catalogo",
    })
    expect(await screen.findByText("Sin resultados")).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole("button", { name: "Limpiar filtros" })
    )
    expect(ubicacionActual()).toBe("/sistema/actividad")
  })

  it("al limpiar los filtros, el foco pasa al primer filtro en vez de perderse", async () => {
    api()
    renderizarPagina(<Actividad />, {
      ruta: "/sistema/actividad?persona=u-ana&tipo=sesiones",
    })
    await screen.findByText("Importó 1,250 contratos")
    await userEvent.click(
      screen.getByRole("button", { name: "Limpiar filtros" })
    )
    expect(ubicacionActual()).toBe("/sistema/actividad")
    expect(
      screen.queryByRole("button", { name: "Limpiar filtros" })
    ).not.toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: "Persona" })).toHaveFocus()
  })

  it("solo administración ve la bitácora", () => {
    sesionDePrueba.roles = ["comprador"]
    api()
    renderizarPagina(<Actividad />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })
})
