import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Usuarios } from "@/paginas/Usuarios"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaDiferida,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
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
  ultimo_acceso: null,
}
const LISTA = { total: 1, elementos: [ANA] }

function api(
  alta: () => Response | Promise<Response> = () =>
    respuestaJson(
      { usuario: ANA, correo_enviado: true, contrasena_temporal: null },
      201
    )
) {
  return simularApi((url) => {
    if (url.startsWith("/api/administracion/usuarios?"))
      return respuestaJson(LISTA)
    if (url === "/api/administracion/usuarios") return alta()
    return new Response("", { status: 404 })
  })
}

async function llenarAlta(metodo: "invitacion" | "temporal" = "invitacion") {
  await userEvent.click(screen.getByRole("button", { name: "Nuevo usuario" }))
  const panel = await screen.findByRole("dialog", { name: "Nuevo usuario" })
  await userEvent.type(within(panel).getByLabelText("Nombre"), "Ana")
  await userEvent.type(within(panel).getByLabelText("Apellidos"), "López")
  await userEvent.type(
    within(panel).getByLabelText("Correo"),
    "Ana.López@plataforma.example"
  )
  await userEvent.click(within(panel).getByLabelText("Compras"))
  if (metodo === "temporal")
    await userEvent.click(within(panel).getByLabelText("Contraseña temporal"))
  return panel
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Usuarios", () => {
  it("lista con roles, estado y último acceso", async () => {
    api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    const fila = (
      await screen.findByRole("link", { name: "Ana López" })
    ).closest("tr")!
    expect(within(fila).getByText("Compras")).toBeInTheDocument()
    expect(within(fila).getByText("Activo")).toBeInTheDocument()
    expect(within(fila).getByText("Nunca")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Ana López" })).toHaveAttribute(
      "href",
      "/sistema/usuarios/u-ana"
    )
  })

  it("los filtros viajan en la URL y en la consulta", async () => {
    const fetch = api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    await userEvent.click(
      within(screen.getByRole("group", { name: "Filtrar por rol" })).getByRole(
        "button",
        { name: "Aprobación" }
      )
    )
    expect(ubicacionActual()).toBe("/sistema/usuarios?rol=aprobador")
    await waitFor(() =>
      expect(urlDeLlamada(fetch).searchParams.get("rol")).toBe("aprobador")
    )
  })

  it("alta por invitación: envía los datos y avisa", async () => {
    const fetch = api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta()
    expect(within(panel).getByLabelText("Usuario")).toHaveValue("ana.lopez")
    await userEvent.click(
      within(panel).getByRole("button", { name: "Dar de alta" })
    )
    expect(
      await screen.findByText(/Se envió la invitación a ana@plataforma.example/)
    ).toBeInTheDocument()
    const llamada = fetch.mock.calls.find(
      ([url]) => url === "/api/administracion/usuarios"
    ) as unknown as [string, RequestInit]
    expect(JSON.parse(String(llamada[1].body))).toEqual({
      usuario: "ana.lopez",
      nombre: "Ana",
      apellidos: "López",
      correo: "Ana.López@plataforma.example",
      roles: ["comprador"],
      metodo: "invitacion",
    })
  })

  it("la contraseña temporal se muestra una sola vez", async () => {
    api(() =>
      respuestaJson(
        {
          usuario: ANA,
          correo_enviado: null,
          contrasena_temporal: "Xy7#abcdefghijkl",
        },
        201
      )
    )
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta("temporal")
    await userEvent.click(
      within(panel).getByRole("button", { name: "Dar de alta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Contraseña temporal de Ana López",
    })
    expect(within(dialogo).getByText("Xy7#abcdefghijkl")).toBeInTheDocument()
    expect(
      within(dialogo).getByText(/No se volverá a mostrar/)
    ).toBeInTheDocument()
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Listo" })
    )
    expect(screen.queryByText("Xy7#abcdefghijkl")).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Nuevo usuario" }))
    expect(screen.queryByText("Xy7#abcdefghijkl")).not.toBeInTheDocument()
  })

  it("al cerrar el panel de alta con Esc, el foco vuelve a «Nuevo usuario»", async () => {
    api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    await userEvent.click(screen.getByRole("button", { name: "Nuevo usuario" }))
    await screen.findByRole("dialog", { name: "Nuevo usuario" })
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Nuevo usuario" })
      ).toHaveFocus()
    )
  })

  it("tras un alta por invitación, el foco vuelve a «Nuevo usuario»", async () => {
    api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta()
    await userEvent.click(
      within(panel).getByRole("button", { name: "Dar de alta" })
    )
    await screen.findByText(/Se envió la invitación a ana@plataforma.example/)
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Nuevo usuario" })
      ).toHaveFocus()
    )
  })

  it("al cerrar la contraseña temporal, el foco vuelve a «Nuevo usuario»", async () => {
    api(() =>
      respuestaJson(
        {
          usuario: ANA,
          correo_enviado: null,
          contrasena_temporal: "Xy7#abcdefghijkl",
        },
        201
      )
    )
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta("temporal")
    await userEvent.click(
      within(panel).getByRole("button", { name: "Dar de alta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Contraseña temporal de Ana López",
    })
    // El panel que se cierra no debe quitarle el foco al diálogo que se abre.
    await new Promise((resolver) => setTimeout(resolver, 50))
    expect(dialogo).toContainElement(document.activeElement as HTMLElement)
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Listo" })
    )
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Nuevo usuario" })
      ).toHaveFocus()
    )
  })

  it("el panel de alta ocupa todo el ancho en pantallas chicas y 28rem desde sm", async () => {
    api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    await userEvent.click(screen.getByRole("button", { name: "Nuevo usuario" }))
    const panel = await screen.findByRole("dialog", { name: "Nuevo usuario" })
    // jsdom no mide el diseño: el SheetContent trae w-3/4 y sm:max-w-sm con la variante data-[side=right]:,
    // y solo esa misma variante los reemplaza (tailwind-merge).
    expect(panel).toHaveClass(
      "data-[side=right]:w-full",
      "data-[side=right]:sm:max-w-md"
    )
    expect(panel).not.toHaveClass(
      "data-[side=right]:w-3/4",
      "data-[side=right]:sm:max-w-sm"
    )
  })

  it("muestra el duplicado junto al campo", async () => {
    api(() =>
      respuestaJson(
        {
          title: "Conflicto",
          detail: "Ya existe un usuario con ese nombre de usuario.",
          codigo: "usuario_duplicado",
          errores: [
            {
              campo: "usuario",
              mensaje: "Ya existe un usuario con ese nombre de usuario.",
            },
          ],
        },
        409
      )
    )
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta()
    await userEvent.click(
      within(panel).getByRole("button", { name: "Dar de alta" })
    )
    const campo = within(panel).getByLabelText("Usuario")
    expect(campo).toHaveAttribute("aria-invalid", "true")
    expect(campo).toHaveAccessibleDescription(
      /Ya existe un usuario con ese nombre de usuario./
    )
  })

  it("«Dar de alta»: con error del servidor, el foco sigue en el botón y no envía dos veces", async () => {
    const lenta = respuestaDiferida()
    const fetch = api(() => lenta.promesa)
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta()
    const boton = within(panel).getByRole("button", { name: "Dar de alta" })
    await userEvent.click(boton)
    await userEvent.click(boton)
    expect(boton).toHaveFocus()
    // jsdom no desenfoca un botón con `disabled`, pero el navegador sí: debe quedar solo `aria-disabled`.
    expect(boton).not.toBeDisabled()
    expect(boton).toHaveAttribute("aria-disabled", "true")
    await act(async () =>
      lenta.resolver(
        respuestaJson(
          {
            title: "Conflicto",
            detail: "Ya existe un usuario con ese nombre de usuario.",
            codigo: "usuario_duplicado",
            errores: [
              {
                campo: "usuario",
                mensaje: "Ya existe un usuario con ese nombre de usuario.",
              },
            ],
          },
          409
        )
      )
    )
    await waitFor(() =>
      expect(within(panel).getByLabelText("Usuario")).toHaveAttribute(
        "aria-invalid",
        "true"
      )
    )
    expect(boton).toHaveFocus()
    expect(
      fetch.mock.calls.filter(([url]) => url === "/api/administracion/usuarios")
    ).toHaveLength(1)
  })

  it("si la invitación no sale, lo dice y lleva a la ficha", async () => {
    api(() =>
      respuestaJson(
        { usuario: ANA, correo_enviado: false, contrasena_temporal: null },
        201
      )
    )
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    const panel = await llenarAlta()
    await userEvent.click(
      within(panel).getByRole("button", { name: "Dar de alta" })
    )
    expect(
      await screen.findByText(
        "Se creó la cuenta, pero no se pudo enviar la invitación."
      )
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Abrir la ficha de Ana López" })
    ).toHaveAttribute("href", "/sistema/usuarios/u-ana")
  })

  it("si el alta queda incompleta, lo dice y actualiza la lista", async () => {
    const fetch = api(() =>
      respuestaJson(
        {
          title: "Servicio no disponible",
          detail:
            "Se creó la cuenta, pero no se pudo terminar de configurar. Abra su ficha en Usuarios para asignar los roles o la contraseña.",
          codigo: "alta_incompleta",
          usuario_id: "u-ana",
        },
        503
      )
    )
    const consultasDeLista = () =>
      fetch.mock.calls.filter(([url]) =>
        url.startsWith("/api/administracion/usuarios?")
      ).length
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    await screen.findByRole("link", { name: "Ana López" })
    expect(consultasDeLista()).toBe(1)
    const panel = await llenarAlta()
    await userEvent.click(
      within(panel).getByRole("button", { name: "Dar de alta" })
    )
    expect(
      await within(panel).findByText(
        /Se creó la cuenta, pero no se pudo terminar de configurar/
      )
    ).toBeInTheDocument()
    await waitFor(() => expect(consultasDeLista()).toBe(2))
  })

  it("con el servicio de identidad caído, ofrece reintentar", async () => {
    simularApi(() =>
      respuestaJson(
        {
          title: "Servicio no disponible",
          detail:
            "No se pudo conectar con el servicio de identidad. Intente de nuevo en unos minutos.",
          codigo: "identidad_no_disponible",
        },
        503
      )
    )
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    expect(
      await screen.findByText(
        /No se pudo conectar con el servicio de identidad/
      )
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /Reintentar/ })
    ).toBeInTheDocument()
  })

  it("solo para administración", async () => {
    sesionDePrueba.roles = ["comprador"]
    api()
    renderizarPagina(<Usuarios />, { ruta: "/sistema/usuarios" })
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad (lista y alta abierta)", async () => {
    api()
    const { container } = renderizarPagina(<Usuarios />, {
      ruta: "/sistema/usuarios",
    })
    await screen.findByRole("link", { name: "Ana López" })
    await esperarSinViolaciones(container)
    await userEvent.click(screen.getByRole("button", { name: "Nuevo usuario" }))
    await screen.findByRole("dialog", { name: "Nuevo usuario" })
    await esperarSinViolaciones(document.body)
  })
})
