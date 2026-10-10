import { cleanup, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Panel } from "@/paginas/Panel"
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

const ESTADO = {
  version: "abc1234",
  comprobado_en: new Date().toISOString(),
  servicios: [
    {
      clave: "base_de_datos",
      nombre: "Base de datos de administración",
      estado: "sano",
      tiempo_ms: 4,
      detalle: "Funciona con normalidad.",
    },
    {
      clave: "correo",
      nombre: "Buzón de correo (Mailpit)",
      estado: "con_problemas",
      tiempo_ms: 1500,
      detalle: "Responde con lentitud.",
    },
  ],
}
const ACTIVIDAD = {
  total: 1,
  elementos: [
    {
      id: "a1",
      fecha: "2026-10-09T18:00:00Z",
      actor_id: "admin-1",
      actor_nombre: "admin1",
      tipo: "servicio.creado",
      objeto_tipo: "servicio",
      objeto_id: "NUBE-VM-2",
      objeto_nombre: "NUBE-VM-2",
      detalle: {},
      resultado: "exito",
      ip: null,
    },
  ],
}

function api(resumen: object) {
  return simularApi((url) => {
    if (url.startsWith("/api/administracion/resumen"))
      return respuestaJson(resumen)
    if (url.startsWith("/api/administracion/estado"))
      return respuestaJson(ESTADO)
    return respuestaJson(ACTIVIDAD)
  })
}

const tarjeta = (titulo: string) =>
  screen.getByText(titulo).closest<HTMLElement>("[data-slot=card]")!

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Panel", () => {
  it("resume usuarios, intentos fallidos, servicios y correos", async () => {
    api({ usuarios_activos: 12, intentos_fallidos_24h: 6, correos_7d: 3 })
    const { container } = renderizarPagina(<Panel />, { ruta: "/sistema" })
    await screen.findByText("Usuarios activos")
    expect(
      await within(tarjeta("Usuarios activos")).findByText("12")
    ).toBeInTheDocument()
    const fallidos = tarjeta("Intentos fallidos (24 h)")
    expect(within(fallidos).getByText("6")).toBeInTheDocument()
    expect(fallidos.querySelector("[data-tono]")).toHaveAttribute(
      "data-tono",
      "riesgo"
    )
    const servicios = tarjeta("Servicios con problemas")
    expect(await within(servicios).findByText("1")).toBeInTheDocument()
    expect(
      within(servicios).getByText("Buzón de correo (Mailpit)")
    ).toBeInTheDocument()
    expect(servicios.querySelector("[data-tono]")).toHaveAttribute(
      "data-tono",
      "advertencia"
    )
    expect(
      within(tarjeta("Correos (7 días)")).getByText("3")
    ).toBeInTheDocument()
    expect(
      await screen.findAllByText("Dio de alta el servicio NUBE-VM-2")
    ).not.toHaveLength(0)
    expect(
      screen.getByRole("link", { name: "Ver toda la actividad" })
    ).toHaveAttribute("href", "/sistema/actividad")
    await esperarSinViolaciones(container)
  })

  it("con un intento fallido el tono es de advertencia; sin ninguno, de éxito", async () => {
    api({ usuarios_activos: 1, intentos_fallidos_24h: 1, correos_7d: 0 })
    renderizarPagina(<Panel />, { ruta: "/sistema" })
    await screen.findByText("Intentos fallidos (24 h)")
    const fallidos = tarjeta("Intentos fallidos (24 h)")
    expect(await within(fallidos).findByText("1")).toBeInTheDocument()
    expect(fallidos.querySelector("[data-tono]")).toHaveAttribute(
      "data-tono",
      "advertencia"
    )
  })

  it("sin el servicio de identidad, los usuarios activos quedan sin dato", async () => {
    api({ usuarios_activos: null, intentos_fallidos_24h: 0, correos_7d: 0 })
    renderizarPagina(<Panel />, { ruta: "/sistema" })
    expect(
      await screen.findByText("No se pudo consultar el servicio de identidad.")
    ).toBeInTheDocument()
    expect(
      within(tarjeta("Usuarios activos")).getByText("Sin datos")
    ).toBeInTheDocument()
  })

  it("solo administración lo ve", () => {
    sesionDePrueba.roles = ["comprador"]
    api({ usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 })
    renderizarPagina(<Panel />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })
})
