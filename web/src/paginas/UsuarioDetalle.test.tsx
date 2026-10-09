import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { UsuarioDetalle } from "@/paginas/UsuarioDetalle"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"
import type { UsuarioAdmin } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ANA: UsuarioAdmin = {
  id: "u-ana",
  usuario: "ana.lopez",
  nombre: "Ana",
  apellidos: "López",
  correo: "ana@plataforma.example",
  roles: ["comprador"],
  activo: true,
  creado_en: "2026-10-01T00:00:00Z",
  ultimo_acceso: "2026-10-07T18:00:00Z",
}
const RUTA = "/api/administracion/usuarios/u-ana"
const ACTIVIDAD = {
  total: 1,
  elementos: [
    {
      id: "a1",
      fecha: "2026-10-07T18:00:00Z",
      actor_id: "u-ana",
      actor_nombre: "ana.lopez",
      tipo: "sesion.iniciada",
      objeto_tipo: null,
      objeto_id: null,
      objeto_nombre: null,
      detalle: {},
      resultado: "exito",
      ip: "10.0.0.7",
    },
  ],
}

function api(cambios: Record<string, () => Response | Promise<Response>> = {}) {
  return simularApi((url) => {
    const respuesta = Object.entries(cambios).find(([clave]) => url === clave)
    if (respuesta) return respuesta[1]()
    if (url === RUTA) return respuestaJson(ANA)
    if (url.startsWith("/api/administracion/actividad?"))
      return respuestaJson(ACTIVIDAD)
    return new Response("", { status: 404 })
  })
}

function renderizar() {
  return renderizarPagina(<UsuarioDetalle />, {
    ruta: "/sistema/usuarios/u-ana",
    patron: "/sistema/usuarios/:id",
  })
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("UsuarioDetalle", () => {
  it("muestra datos, roles, estado y actividad reciente", async () => {
    api()
    renderizar()
    expect(
      await screen.findByRole("heading", { level: 1, name: "Ana López" })
    ).toBeInTheDocument()
    expect(screen.getByLabelText("Compras")).toBeChecked()
    expect(screen.getByText("Activo")).toBeInTheDocument()
    expect(screen.getByText("Inició sesión")).toBeInTheDocument()
  })

  it("guarda solo lo que cambió", async () => {
    // La API simulada responde por URL (sin método): GET y PATCH devuelven el mismo usuario.
    const fetch = api()
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await userEvent.click(screen.getByLabelText("Aprobación"))
    await userEvent.click(
      screen.getByRole("button", { name: "Guardar cambios" })
    )
    expect(await screen.findByText("Cambios guardados.")).toBeInTheDocument()
    // simularApi tipa las llamadas solo con la URL; el segundo argumento sí llega (como en Usuarios.test.tsx).
    const llamadas = fetch.mock.calls as unknown as [string, RequestInit?][]
    const patch = llamadas.find(([, init]) => init?.method === "PATCH")!
    expect(JSON.parse(String(patch[1]?.body))).toEqual({
      roles: ["comprador", "aprobador"],
    })
  })

  it("explica una regla de protección", async () => {
    api({
      [`${RUTA}/desactivar`]: () =>
        respuestaJson(
          {
            title: "Conflicto",
            detail: "No puede desactivar su propia cuenta.",
            codigo: "regla_proteccion",
          },
          409
        ),
    })
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await userEvent.click(screen.getByRole("button", { name: "Desactivar" }))
    const confirmacion = await screen.findByRole("alertdialog")
    expect(
      within(confirmacion).getByText(/No podrá iniciar sesión/)
    ).toBeInTheDocument()
    await userEvent.click(
      within(confirmacion).getByRole("button", { name: "Desactivar la cuenta" })
    )
    expect(
      await screen.findByText("No puede desactivar su propia cuenta.")
    ).toBeInTheDocument()
  })

  it("asigna una contraseña temporal tras confirmar y la muestra una vez", async () => {
    api({
      [`${RUTA}/contrasena`]: () =>
        respuestaJson({ contrasena_temporal: "Ab1#cdefghijklmn" }),
    })
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await userEvent.click(
      screen.getByRole("button", { name: "Asignar contraseña temporal" })
    )
    await userEvent.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Asignar",
      })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Contraseña temporal de Ana López",
    })
    expect(within(dialogo).getByText("Ab1#cdefghijklmn")).toBeInTheDocument()
  })

  it("al cerrar la contraseña temporal, el foco vuelve a «Asignar contraseña temporal»", async () => {
    api({
      [`${RUTA}/contrasena`]: () =>
        respuestaJson({ contrasena_temporal: "Ab1#cdefghijklmn" }),
    })
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await userEvent.click(
      screen.getByRole("button", { name: "Asignar contraseña temporal" })
    )
    await userEvent.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Asignar",
      })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Contraseña temporal de Ana López",
    })
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Listo" })
    )
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Asignar contraseña temporal" })
      ).toHaveFocus()
    )
  })

  it("si el correo no sale, ofrece la contraseña temporal", async () => {
    api({
      [`${RUTA}/contrasena`]: () =>
        respuestaJson(
          {
            title: "Servicio no disponible",
            detail:
              "No se pudo enviar el correo. Intente de nuevo en unos minutos o asigne una contraseña temporal.",
            codigo: "correo_no_enviado",
          },
          503
        ),
    })
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await userEvent.click(
      screen.getByRole("button", {
        name: "Enviar correo para definir contraseña",
      })
    )
    expect(
      await screen.findByText(/No se pudo enviar el correo/)
    ).toBeInTheDocument()
  })

  it("usuario inexistente", async () => {
    api({
      [RUTA]: () =>
        respuestaJson(
          {
            title: "No encontrado",
            detail: "El usuario no existe.",
            codigo: "usuario_no_encontrado",
          },
          404
        ),
    })
    renderizar()
    expect(
      await screen.findByText("Este usuario no existe")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Volver a Usuarios" })
    ).toHaveAttribute("href", "/sistema/usuarios")
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizar()
    await screen.findByRole("heading", { level: 1, name: "Ana López" })
    await screen.findByText("Inició sesión")
    await esperarSinViolaciones(container)
  })
})
