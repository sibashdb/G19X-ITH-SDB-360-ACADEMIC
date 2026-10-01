import { Hexagon } from "lucide-react"
import { Link, useLocation } from "react-router"
import { useRoles } from "@/auth"
import { estaActiva, navegacionPara } from "@/componentes/navegacion"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export function BarraLateral() {
  const { pathname } = useLocation()
  const roles = useRoles()
  const { isMobile, setOpenMobile } = useSidebar()
  // En móvil el menú es un panel deslizable: se cierra al elegir una opción.
  const alNavegar = () => {
    if (isMobile) setOpenMobile(false)
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/" onClick={alNavegar}>
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <Hexagon aria-hidden className="size-4" />
                </span>
                <span className="grid leading-tight">
                  <span className="font-semibold">PluriOne</span>
                  <span className="text-xs text-sidebar-foreground/70">
                    Negociación con proveedores
                  </span>
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <nav aria-label="Principal">
          {navegacionPara(roles).map((seccion) => (
            <SidebarGroup key={seccion.titulo}>
              <SidebarGroupLabel>{seccion.titulo}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {seccion.elementos.map(({ titulo, ruta, icono: Icono }) => {
                    const activa = estaActiva(ruta, pathname)
                    return (
                      <SidebarMenuItem key={ruta}>
                        <SidebarMenuButton
                          asChild
                          isActive={activa}
                          tooltip={titulo}
                          className="data-[active=true]:bg-sidebar-primary data-[active=true]:text-sidebar-primary-foreground"
                        >
                          <Link
                            to={ruta}
                            aria-current={activa ? "page" : undefined}
                            onClick={alNavegar}
                          >
                            <Icono aria-hidden />
                            <span>{titulo}</span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    )
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </nav>
      </SidebarContent>
    </Sidebar>
  )
}
