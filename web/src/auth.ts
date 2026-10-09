import { useAuth, type AuthProviderProps } from "react-oidc-context"

export type Rol = "admin" | "comprador" | "aprobador"

export const ROLES: readonly Rol[] = ["admin", "comprador", "aprobador"]

export const NOMBRES_ROL: Record<Rol, string> = {
  admin: "Administración",
  comprador: "Compras",
  aprobador: "Aprobación",
}

export const DESCRIPCIONES_ROL: Record<Rol, string> = {
  admin: "Gestiona usuarios, catálogos e importaciones.",
  comprador: "Crea y supervisa las negociaciones.",
  aprobador: "Aprueba adjudicaciones y cierres.",
}

/** Empieza con una sola barra (ni "//" ni barra y barra invertida): nunca apunta a otro origen. */
const RUTA_RELATIVA = /^\/(?![/\\])/

/** Además de la forma, exige que resuelva al mismo origen (el navegador ignora tabulaciones y saltos). */
function rutaSegura(estado: unknown): estado is string {
  return (
    typeof estado === "string" &&
    RUTA_RELATIVA.test(estado) &&
    new URL(estado, window.location.origin).origin === window.location.origin
  )
}

export const configuracionOidc: AuthProviderProps = {
  authority:
    import.meta.env.VITE_OIDC_AUTHORITY ??
    "http://localhost:8080/auth/realms/plataforma",
  client_id: "web",
  redirect_uri: `${window.location.origin}/`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  automaticSilentRenew: true,
  // Layout guarda la ruta pedida como `state` al iniciar sesión; aquí se restaura (si es relativa
  // y segura) para que un enlace profundo llegue a su destino y no caiga siempre en el Tablero.
  onSigninCallback: (usuario) => {
    const estado = usuario?.state
    const destino = rutaSegura(estado) ? estado : null
    window.history.replaceState(
      {},
      document.title,
      destino ?? window.location.pathname
    )
    // createBrowserRouter solo se entera de un cambio de URL hecho a mano por el evento popstate.
    if (destino) window.dispatchEvent(new PopStateEvent("popstate"))
  },
}

/** Lee los roles del token solo para decidir qué mostrar; la API vuelve a validarlos. */
export function rolesDeToken(token: string | undefined): Rol[] {
  const partes = token?.split(".") ?? []
  if (partes.length !== 3) return []
  try {
    const base64 = partes[1].replace(/-/g, "+").replace(/_/g, "/")
    const carga = JSON.parse(
      atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "="))
    )
    const roles: unknown = carga?.realm_access?.roles
    // Conserva el orden del token y descarta roles ajenos a la plataforma (p. ej. offline_access).
    return Array.isArray(roles)
      ? roles.filter((r): r is Rol => ROLES.includes(r as Rol))
      : []
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
