import { vi } from "vitest"

/** Estado de la sesión simulada; cada prueba puede cambiar los roles. */
export const sesionDePrueba = {
  roles: ["admin"] as string[],
  signoutRedirect: vi.fn(async () => {}),
}

/** JWT sin firma con los roles de realm indicados (la interfaz solo lee la carga). */
export function tokenConRoles(roles: string[]): string {
  const carga = btoa(JSON.stringify({ realm_access: { roles } }))
  return `cabecera.${carga}.firma`
}

/**
 * Sustituto de react-oidc-context con la sesión iniciada como "Ana López".
 * Uso: vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())
 */
export function oidcSimulado() {
  return {
    hasAuthParams: () => false,
    useAuth: () => ({
      isAuthenticated: true,
      isLoading: false,
      activeNavigator: undefined,
      error: undefined,
      user: {
        access_token: tokenConRoles(sesionDePrueba.roles),
        profile: {
          given_name: "Ana",
          family_name: "López",
          preferred_username: "ana.lopez",
        },
      },
      signoutRedirect: sesionDePrueba.signoutRedirect,
      signinRedirect: vi.fn(async () => {}),
      removeUser: vi.fn(async () => {}),
    }),
  }
}
