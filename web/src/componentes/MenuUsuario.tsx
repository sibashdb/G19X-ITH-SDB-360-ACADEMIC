import { ChevronsUpDown, CircleHelp, LogOut } from "lucide-react"
import { useAuth } from "react-oidc-context"
import { useNavigate } from "react-router"
import { NOMBRES_ROL, useRoles, useUsuarioId } from "@/auth"
import { iniciales } from "@/componentes/Iniciales"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { mostrarGuia, useGuia } from "@/guia"

/** Cuenta de la persona, abajo en el menú lateral; al contraerlo solo quedan sus iniciales. */
export function MenuUsuario() {
  const auth = useAuth()
  const roles = useRoles()
  const usuario = useUsuarioId()
  const guia = useGuia(usuario)
  const navegar = useNavigate()
  const { isMobile } = useSidebar()
  const perfil = auth.user?.profile
  const nombre =
    [perfil?.given_name, perfil?.family_name].filter(Boolean).join(" ") ||
    perfil?.preferred_username ||
    "Usuario"
  const textoRoles =
    roles.map((rol) => NOMBRES_ROL[rol]).join(" · ") || "Sin rol asignado"
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              tooltip={nombre}
              aria-label={`Cuenta de ${nombre}`}
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <span
                aria-hidden
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-sidebar-primary text-xs font-semibold text-sidebar-primary-foreground"
              >
                {iniciales(nombre)}
              </span>
              <span className="grid flex-1 leading-tight">
                <span className="truncate font-medium">{nombre}</span>
                <span className="truncate text-xs text-sidebar-foreground/70">
                  {textoRoles}
                </span>
              </span>
              <ChevronsUpDown aria-hidden className="ml-auto" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side={isMobile ? "top" : "right"}
            align="end"
            className="w-56"
          >
            <DropdownMenuLabel className="space-y-0.5">
              <span className="block font-medium">{nombre}</span>
              <span className="block text-xs font-normal text-muted-foreground">
                {textoRoles}
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {guia.oculta && (
              <DropdownMenuItem
                onSelect={() => {
                  mostrarGuia(usuario)
                  void navegar("/")
                }}
              >
                <CircleHelp aria-hidden />
                Mostrar guía de uso
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={() => void auth.signoutRedirect()}>
              <LogOut aria-hidden />
              Cerrar sesión
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
