import { useAuth, type AuthProviderProps } from "react-oidc-context"

export type Rol = "admin" | "comprador" | "aprobador"

const ROLES: readonly Rol[] = ["admin", "comprador", "aprobador"]

export const NOMBRES_ROL: Record<Rol, string> = {
  admin: "Administración",
  comprador: "Compras",
  aprobador: "Aprobación",
}

export const configuracionOidc: AuthProviderProps = {
  authority:
    import.meta.env.VITE_OIDC_AUTHORITY ?? "http://localhost:8080/auth/realms/plataforma",
  client_id: "web",
  redirect_uri: `${window.location.origin}/`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  automaticSilentRenew: true,
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname)
  },
}

/** Lee los roles del token solo para decidir qué mostrar; la API vuelve a validarlos. */
export function rolesDeToken(token: string | undefined): Rol[] {
  const partes = token?.split(".") ?? []
  if (partes.length !== 3) return []
  try {
    const base64 = partes[1].replace(/-/g, "+").replace(/_/g, "/")
    const carga = JSON.parse(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "=")))
    const roles: unknown = carga?.realm_access?.roles
    // Conserva el orden del token y descarta roles ajenos a la plataforma (p. ej. offline_access).
    return Array.isArray(roles) ? roles.filter((r): r is Rol => ROLES.includes(r as Rol)) : []
  } catch {
    return []
  }
}

export function useToken(): string | undefined {
  return useAuth().user?.access_token
}

export function useRoles(): Rol[] {
  return rolesDeToken(useToken())
}
