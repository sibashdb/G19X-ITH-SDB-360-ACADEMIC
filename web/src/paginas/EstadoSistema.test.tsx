import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { EstadoSistema } from "@/paginas/EstadoSistema"
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
      clave: "proveedores",
      nombre: "Servicio de proveedores",
      estado: "caido",
      tiempo_ms: null,
      detalle: "No respondió en 2 s.",
    },
    {
      clave: "mensajeria",
      nombre: "Mensajería (RabbitMQ)",
      estado: "con_problemas",
      tiempo_ms: 30,
      detalle: "Mensajes pendientes en: administracion.actividad (150).",
    },
  ],
}

const IMPORTACIONES = {
  total: 1,
  elementos: [
    {
      id: "i1",
      fecha: "2026-10-09T18:00:00Z",
      actor_id: null,
      actor_nombre: "Sistema (línea de comandos)",
      tipo: "importacion.completada",
      objeto_tipo: "importacion",
      objeto_id: "proveedores",
      objeto_nombre: "proveedores",
      detalle: { registros: 60, filas: 60, omitidos: 0 },
      resultado: "exito",
      ip: null,
    },
  ],
}

function api(estado: () => Response = () => respuestaJson(ESTADO)) {
  return simularApi((url) =>
    url.startsWith("/api/administracion/estado")
      ? estado()
      : respuestaJson(IMPORTACIONES)
  )
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("EstadoSistema", () => {
  it("muestra cada servicio con su estado en texto y su tiempo", async () => {
    api()
    const { container } = renderizarPagina(<EstadoSistema />, {
      ruta: "/sistema/estado",
    })
    const caido = (await screen.findByText("Servicio de proveedores")).closest(
      "li"
    )!
    expect(within(caido).getByText("Caído")).toBeInTheDocument()
    expect(within(caido).getByText("Sin respuesta")).toBeInTheDocument()
    const lento = screen.getByText("Mensajería (RabbitMQ)").closest("li")!
    expect(within(lento).getByText("Con problemas")).toBeInTheDocument()
    expect(within(lento).getByText("Respondió en 30 ms")).toBeInTheDocument()
    expect(screen.getByText(/1 de 3 servicios sanos/)).toBeInTheDocument()
    expect(screen.getByText(/Versión abc1234/)).toBeInTheDocument()
    expect(screen.getByText("Importó 60 proveedores")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("«Volver a comprobar» pide el estado otra vez", async () => {
    const simulado = api()
    renderizarPagina(<EstadoSistema />, { ruta: "/sistema/estado" })
    await screen.findByText("Servicio de proveedores")
    const pedidos = () =>
      simulado.mock.calls.filter(([url]) =>
        String(url).startsWith("/api/administracion/estado")
      ).length
    expect(pedidos()).toBe(1)
    await userEvent.click(
      screen.getByRole("button", { name: /Volver a comprobar/ })
    )
    await waitFor(() => expect(pedidos()).toBe(2))
  })

  it("si la API falla, lo dice y permite reintentar", async () => {
    api(() =>
      respuestaJson(
        { title: "Servicio no disponible", detail: "Intente más tarde." },
        503
      )
    )
    renderizarPagina(<EstadoSistema />, { ruta: "/sistema/estado" })
    expect(
      await screen.findByText("Servicio no disponible")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Reintentar" })
    ).toBeInTheDocument()
  })

  it("solo administración lo ve", () => {
    sesionDePrueba.roles = ["aprobador"]
    api()
    renderizarPagina(<EstadoSistema />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })
})
