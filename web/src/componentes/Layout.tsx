import { useEffect } from "react"
import { hasAuthParams, useAuth } from "react-oidc-context"
import { Outlet, useLocation } from "react-router"
import { BarraLateral } from "@/componentes/BarraLateral"
import { BarraSuperior } from "@/componentes/BarraSuperior"
import { estaActiva, migasDe } from "@/componentes/navegacion"
import { Button } from "@/components/ui/button"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { marcarVisita } from "@/guia"

export function Layout() {
  const auth = useAuth()
  const { pathname, search } = useLocation()
  // Se guarda como `state` del inicio de sesión para volver a la misma página y sus parámetros.
  // Si la URL aún trae los de la devolución de Keycloak (code, state, error), se omiten: guardarlos
  // los restauraría tras un login correcto y cada recarga volvería a mostrar "Su sesión expiró".
  const rutaActual = hasAuthParams() ? pathname : pathname + search

  useEffect(() => {
    const puedeRedirigir =
      !hasAuthParams() &&
      !auth.isAuthenticated &&
      !auth.activeNavigator &&
      !auth.isLoading
    if (puedeRedirigir && !auth.error)
      void auth.signinRedirect({ state: rutaActual })
  }, [auth, rutaActual])

  // El mensaje original de la librería suele venir en inglés: solo se registra, no se muestra.
  useEffect(() => {
    if (auth.error) console.error("Error de sesión:", auth.error)
  }, [auth.error])

  // Cada página tiene su propio título en la pestaña y en el historial del navegador.
  useEffect(() => {
    const migas = migasDe(pathname)
    document.title = `${migas[migas.length - 1].titulo} · PluriOne`
  }, [pathname])

  // La guía del Tablero marca como vistos Proveedores y Precios cuando se visitan.
  const usuario = auth.user?.profile.sub ?? ""
  useEffect(() => {
    if (!usuario) return
    if (estaActiva("/proveedores", pathname))
      marcarVisita(usuario, "proveedores")
    if (estaActiva("/precios", pathname)) marcarVisita(usuario, "precios")
  }, [pathname, usuario])

  async function volverAIniciarSesion() {
    await auth
      .removeUser()
      .catch((error: unknown) =>
        console.error("No se pudo limpiar la sesión:", error)
      )
    await auth.signinRedirect({ state: rutaActual })
  }

  if (auth.error) {
    return (
      <div role="alert" className="space-y-3 p-6">
        <p>Su sesión expiró o no se pudo iniciar sesión.</p>
        <Button onClick={() => void volverAIniciarSesion()}>
          Volver a iniciar sesión
        </Button>
      </div>
    )
  }
  if (!auth.isAuthenticated) {
    return (
      <p className="p-6 text-muted-foreground">
        Redirigiendo al inicio de sesión…
      </p>
    )
  }

  return (
    <TooltipProvider>
      <SidebarProvider>
        <a
          href="#contenido"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
        >
          Saltar al contenido
        </a>
        <BarraLateral />
        <SidebarInset className="min-w-0">
          <BarraSuperior />
          <div
            id="contenido"
            tabIndex={-1}
            className="mx-auto w-full max-w-7xl flex-1 p-4 outline-hidden md:p-6 lg:p-8"
          >
            <Outlet />
          </div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
