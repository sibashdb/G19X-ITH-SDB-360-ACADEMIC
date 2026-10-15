import { cleanup, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Correos } from "@/paginas/Correos"
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

const CORREOS = {
  total: 2,
  buzon_url: "http://localhost:8025",
  elementos: [
    {
      id: "c2",
      fecha: "2026-10-08T18:00:00Z",
      tipo: "restablecimiento",
      destinatario: "ana@plataforma.example",
      solicitado_por: "admin1",
      estado: "fallido",
      error: "No se pudo entregar el correo al servidor de correo.",
    },
    {
      id: "c1",
      fecha: "2026-10-07T18:00:00Z",
      tipo: "invitacion",
      destinatario: "ana@plataforma.example",
      solicitado_por: "admin1",
      estado: "enviado",
      error: null,
    },
  ],
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Correos", () => {
  it("lista los correos con su estado y enlaza al buzón", async () => {
    simularApi(() => respuestaJson(CORREOS))
    const { container } = renderizarPagina(<Correos />, {
      ruta: "/sistema/correos",
    })
    expect(await screen.findByText("Invitación")).toBeInTheDocument()
    expect(screen.getByText("Restablecimiento")).toBeInTheDocument()
    expect(screen.getByText("No se envió")).toBeInTheDocument()
    expect(screen.getByText("Enviado")).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /Abrir buzón de desarrollo/ })
    ).toHaveAttribute("href", "http://localhost:8025")
    await esperarSinViolaciones(container)
  })

  it("muestra las invitaciones a negociar", async () => {
    simularApi(() =>
      respuestaJson({
        total: 1,
        buzon_url: null,
        elementos: [
          {
            id: "c3",
            fecha: "2026-10-13T18:00:00Z",
            tipo: "negociacion",
            destinatario: "lucia@nubenorte.example",
            solicitado_por: "comprador1",
            estado: "enviado",
            error: null,
          },
        ],
      })
    )
    renderizarPagina(<Correos />, { ruta: "/sistema/correos" })
    expect(await screen.findByText("Invitación a negociar")).toBeInTheDocument()
  })

  it("estado vacío sin buzón", async () => {
    simularApi(() =>
      respuestaJson({ total: 0, elementos: [], buzon_url: null })
    )
    renderizarPagina(<Correos />, { ruta: "/sistema/correos" })
    expect(
      await screen.findByText("Aún no se han enviado correos")
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("link", { name: /Abrir buzón de desarrollo/ })
    ).not.toBeInTheDocument()
  })
})
