import { cleanup, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Layout } from "@/componentes/Layout"
import { tokenConRoles } from "@/pruebas/sesion"
import { esperarSinViolaciones } from "@/pruebas/utilidades"
import { CLAVE_TEMA, ProveedorTema } from "@/tema"

const removeUser = vi.fn().mockResolvedValue(undefined)
const signinRedirect = vi.fn().mockResolvedValue(undefined)
const signoutRedirect = vi.fn().mockResolvedValue(undefined)
const estado = vi.hoisted(() => ({
  autenticacion: {} as object,
  parametrosDeLogin: false,
}))

vi.mock("react-oidc-context", () => ({
  hasAuthParams: () => estado.parametrosDeLogin,
  useAuth: () => estado.autenticacion,
}))

function sesionCon(roles: string[]) {
  return {
    isAuthenticated: true,
    isLoading: false,
    activeNavigator: undefined,
    error: undefined,
    user: {
      access_token: tokenConRoles(roles),
      profile: {
        given_name: "Ana",
        family_name: "López",
        preferred_username: "ana.lopez",
      },
    },
    removeUser,
    signinRedirect,
    signoutRedirect,
  }
}

function renderizar(ruta = "/") {
  return render(
    <ProveedorTema>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="*" element={<h1>Contenido de prueba</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ProveedorTema>
  )
}

beforeEach(() => {
  estado.autenticacion = sesionCon(["comprador"])
  estado.parametrosDeLogin = false
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.classList.remove("dark")
})

describe("Layout con la sesión en error", () => {
  it("muestra un mensaje en español y permite volver a iniciar sesión", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    estado.autenticacion = {
      error: new Error("invalid_grant: Token is not active"),
      isAuthenticated: false,
      isLoading: false,
      activeNavigator: undefined,
      user: null,
      removeUser,
      signinRedirect,
    }
    renderizar("/proveedores/p1?pestana=contratos")

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Su sesión expiró o no se pudo iniciar sesión."
    )
    expect(screen.queryByText(/invalid_grant/)).not.toBeInTheDocument()
    expect(signinRedirect).not.toHaveBeenCalled()

    await userEvent.click(
      screen.getByRole("button", { name: "Volver a iniciar sesión" })
    )

    expect(removeUser).toHaveBeenCalledOnce()
    expect(signinRedirect).toHaveBeenCalledOnce()
    expect(signinRedirect).toHaveBeenCalledWith({
      state: "/proveedores/p1?pestana=contratos",
    })
    expect(removeUser.mock.invocationCallOrder[0]).toBeLessThan(
      signinRedirect.mock.invocationCallOrder[0]
    )
  })
})

describe("Layout con la devolución del login fallida", () => {
  // Si Keycloak devolvió ?error=…&state=…, la URL aún trae los parámetros de autenticación:
  // guardarlos como estado los restauraría después de un login correcto y cada recarga
  // volvería a mostrar "Su sesión expiró".
  it("no guarda los parámetros de autenticación al volver a iniciar sesión", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    estado.parametrosDeLogin = true
    estado.autenticacion = {
      error: new Error("No matching state found in storage"),
      isAuthenticated: false,
      isLoading: false,
      activeNavigator: undefined,
      user: null,
      removeUser,
      signinRedirect,
    }
    renderizar("/proveedores/p1?error=access_denied&state=xyz")

    await userEvent.click(
      screen.getByRole("button", { name: "Volver a iniciar sesión" })
    )

    expect(signinRedirect).toHaveBeenCalledWith({ state: "/proveedores/p1" })
  })
})

describe("Layout sin sesión", () => {
  it("redirige al inicio de sesión recordando la ruta y sus parámetros", () => {
    estado.autenticacion = {
      isAuthenticated: false,
      isLoading: false,
      activeNavigator: undefined,
      error: undefined,
      user: null,
      removeUser,
      signinRedirect,
    }
    renderizar("/proveedores/p1?pestana=desempeno")

    expect(signinRedirect).toHaveBeenCalledOnce()
    expect(signinRedirect).toHaveBeenCalledWith({
      state: "/proveedores/p1?pestana=desempeno",
    })
  })
})

describe("Layout con sesión iniciada", () => {
  it("muestra a un comprador solo las secciones que le corresponden", () => {
    renderizar()
    const menu = screen.getByRole("navigation", { name: "Principal" })
    for (const nombre of [
      "Tablero",
      "Proveedores",
      "Ranking",
      "Precios",
      "Alertas",
    ]) {
      expect(
        within(menu).getByRole("link", { name: nombre })
      ).toBeInTheDocument()
    }
    expect(
      within(menu).queryByRole("link", { name: "Importación" })
    ).not.toBeInTheDocument()
    expect(
      within(menu).queryByRole("link", { name: "Configuración" })
    ).not.toBeInTheDocument()
  })

  it("cada opción del menú lleva su descripción sin cambiar su nombre accesible", () => {
    renderizar()
    const menu = screen.getByRole("navigation", { name: "Principal" })
    const enlace = within(menu).getByRole("link", { name: "Precios" })
    expect(enlace).toHaveAccessibleDescription("Cuánto debería pagar")
    expect(within(menu).getByText("Cuánto debería pagar")).toBeInTheDocument()
  })

  it("muestra al admin Importación y Configuración", () => {
    estado.autenticacion = sesionCon(["admin"])
    renderizar()
    const menu = screen.getByRole("navigation", { name: "Principal" })
    expect(
      within(menu).getByRole("link", { name: "Importación" })
    ).toHaveAttribute("href", "/importacion")
    expect(
      within(menu).getByRole("link", { name: "Configuración" })
    ).toHaveAttribute("href", "/configuracion")
  })

  it("marca la página actual, muestra las migas y titula el documento", () => {
    renderizar("/proveedores/abc")
    const menu = screen.getByRole("navigation", { name: "Principal" })
    expect(
      within(menu).getByRole("link", { name: "Proveedores" })
    ).toHaveAttribute("aria-current", "page")
    expect(
      within(menu).getByRole("link", { name: "Tablero" })
    ).not.toHaveAttribute("aria-current")

    const migas = screen.getByRole("navigation", { name: "Ruta de navegación" })
    expect(
      within(migas).getByRole("link", { name: "Proveedores" })
    ).toHaveAttribute("href", "/proveedores")
    expect(within(migas).getByText("Detalle")).toHaveAttribute(
      "aria-current",
      "page"
    )
    expect(document.title).toBe("Detalle · PluriOne")
  })

  it("tiene un solo main, enlace para saltar al contenido y controles en español", () => {
    renderizar()
    expect(screen.getAllByRole("main")).toHaveLength(1)
    expect(
      screen.getByRole("link", { name: "Saltar al contenido" })
    ).toHaveAttribute("href", "#contenido")
    expect(document.getElementById("contenido")).toContainElement(
      screen.getByRole("heading", { name: "Contenido de prueba" })
    )
    expect(
      screen.getByRole("button", { name: "Mostrar u ocultar el menú" })
    ).toBeInTheDocument()
  })

  // jsdom no mide el diseño: esta clase evita el scroll horizontal de página a 768 y 1024 px,
  // porque el main es un elemento flex y sin ella no se encoge por debajo de su contenido.
  it("deja que el main se encoja para que las tablas desplacen dentro de su contenedor", () => {
    renderizar()
    expect(screen.getByRole("main")).toHaveClass("min-w-0")
  })

  it("cambia el tema desde la barra superior", async () => {
    renderizar()
    await userEvent.click(screen.getByRole("button", { name: "Tema: Sistema" }))
    await userEvent.click(
      await screen.findByRole("menuitemradio", { name: "Oscuro" })
    )

    expect(document.documentElement).toHaveClass("dark")
    expect(localStorage.getItem(CLAVE_TEMA)).toBe("oscuro")
    expect(
      screen.getByRole("button", { name: "Tema: Oscuro" })
    ).toBeInTheDocument()
  })

  it("muestra el usuario con sus roles y cierra sesión", async () => {
    estado.autenticacion = sesionCon(["comprador", "aprobador"])
    renderizar()
    await userEvent.click(
      screen.getByRole("button", { name: "Cuenta de Ana López" })
    )

    expect(await screen.findByText("Compras · Aprobación")).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole("menuitem", { name: "Cerrar sesión" })
    )
    expect(signoutRedirect).toHaveBeenCalledOnce()
  })

  it("el menú de alertas enlaza a la página de alertas", async () => {
    renderizar()
    await userEvent.click(screen.getByRole("button", { name: "Alertas" }))

    expect(
      await screen.findByText("No hay alertas activas")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("menuitem", { name: "Ver todas las alertas" })
    ).toHaveAttribute("href", "/alertas")
  })

  it("no tiene violaciones de accesibilidad", async () => {
    estado.autenticacion = sesionCon(["admin"])
    const { container } = renderizar("/proveedores")
    await esperarSinViolaciones(container)
  })
})
