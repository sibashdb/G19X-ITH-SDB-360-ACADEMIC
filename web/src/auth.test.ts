import type { User } from "oidc-client-ts"
import { createBrowserRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"
import { configuracionOidc, rolesDeToken } from "@/auth"

function tokenCon(carga: object): string {
  const base64url = btoa(JSON.stringify(carga))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "")
  return `cabecera.${base64url}.firma`
}

describe("rolesDeToken", () => {
  it("devuelve solo los roles de la plataforma", () => {
    const token = tokenCon({ realm_access: { roles: ["comprador", "offline_access", "admin"] } })
    expect(rolesDeToken(token)).toEqual(["comprador", "admin"])
  })

  it("tolera tokens ausentes o mal formados", () => {
    expect(rolesDeToken(undefined)).toEqual([])
    expect(rolesDeToken("no-es-un-jwt")).toEqual([])
    expect(rolesDeToken("a.%%%.c")).toEqual([])
  })

  it("tolera tokens sin realm_access", () => {
    expect(rolesDeToken(tokenCon({ sub: "u-1" }))).toEqual([])
  })
})

describe("onSigninCallback", () => {
  afterEach(() => {
    window.history.replaceState({}, "", "/")
  })

  // Simula la vuelta de Keycloak (con ?code y &state en la URL) y devuelve lo que quedó.
  function volverDeKeycloak(estado: unknown) {
    window.history.replaceState({}, "", "/callback?code=abc&state=xyz")
    const alNavegar = vi.fn()
    window.addEventListener("popstate", alNavegar)
    try {
      configuracionOidc.onSigninCallback?.({ state: estado } as User)
    } finally {
      window.removeEventListener("popstate", alNavegar)
    }
    return { url: window.location.pathname + window.location.search, alNavegar }
  }

  it("restaura la ruta guardada y avisa al enrutador", () => {
    const { url, alNavegar } = volverDeKeycloak("/proveedores/p1?pestana=desempeno")

    expect(url).toBe("/proveedores/p1?pestana=desempeno")
    expect(alNavegar).toHaveBeenCalledOnce()
  })

  it("hace que el enrutador del navegador llegue a la ruta restaurada", () => {
    window.history.replaceState({}, "", "/?code=abc&state=xyz")
    const enrutador = createBrowserRouter([{ path: "*", element: null }])

    configuracionOidc.onSigninCallback?.({ state: "/precios?servicio=nube" } as User)

    const { pathname, search } = enrutador.state.location
    expect(pathname + search).toBe("/precios?servicio=nube")
    enrutador.dispose()
  })

  it.each([
    ["sin estado", undefined],
    ["con un estado que no es texto", { ruta: "/precios" }],
    ["con una URL absoluta", "https://evil.example/precios"],
    ["con una ruta relativa al protocolo", "//evil.example/precios"],
    ["con una barra invertida", "/\\evil.example/precios"],
  ])("conserva solo la ruta actual %s", (_caso, estado) => {
    const { url, alNavegar } = volverDeKeycloak(estado)

    expect(url).toBe("/callback")
    expect(alNavegar).not.toHaveBeenCalled()
  })
})
