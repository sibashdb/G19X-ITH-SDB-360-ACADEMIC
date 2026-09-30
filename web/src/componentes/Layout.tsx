import { useEffect } from "react"
import { NavLink, Outlet } from "react-router"
import { hasAuthParams, useAuth } from "react-oidc-context"
import { useRoles } from "@/auth"
import { Button } from "@/components/ui/button"

function claseEnlace({ isActive }: { isActive: boolean }): string {
  return isActive ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
}

export function Layout() {
  const auth = useAuth()
  const roles = useRoles()

  useEffect(() => {
    const puedeRedirigir =
      !hasAuthParams() && !auth.isAuthenticated && !auth.activeNavigator && !auth.isLoading
    if (puedeRedirigir && !auth.error) void auth.signinRedirect()
  }, [auth])

  // El mensaje original de la librería suele venir en inglés: solo se registra, no se muestra.
  useEffect(() => {
    if (auth.error) console.error("Error de sesión:", auth.error)
  }, [auth.error])

  async function volverAIniciarSesion() {
    await auth.removeUser().catch((error: unknown) => console.error("No se pudo limpiar la sesión:", error))
    await auth.signinRedirect()
  }

  if (auth.error) {
    return (
      <div role="alert" className="space-y-3 p-6">
        <p>Tu sesión expiró o no se pudo iniciar sesión.</p>
        <Button onClick={() => void volverAIniciarSesion()}>Volver a iniciar sesión</Button>
      </div>
    )
  }
  if (!auth.isAuthenticated) return <p className="p-6">Redirigiendo al inicio de sesión…</p>

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <nav aria-label="Principal" className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <span className="font-semibold">Plataforma de Negociación</span>
          <NavLink to="/" end className={claseEnlace}>
            Inicio
          </NavLink>
          <NavLink to="/proveedores" className={claseEnlace}>
            Proveedores
          </NavLink>
          {roles.includes("admin") && (
            <NavLink to="/importacion" className={claseEnlace}>
              Importación
            </NavLink>
          )}
          <span className="ml-auto text-sm text-muted-foreground">
            {auth.user?.profile.preferred_username}
          </span>
          <Button variant="outline" size="sm" onClick={() => void auth.signoutRedirect()}>
            Cerrar sesión
          </Button>
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
