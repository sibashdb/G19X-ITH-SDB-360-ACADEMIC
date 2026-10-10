import { Hexagon } from "lucide-react"
import { useId } from "react"
import { Link, useLocation } from "react-router"
import { useRoles } from "@/auth"
import {
  estaActiva,
  navegacionPara,
  type ElementoNavegacion,
} from "@/componentes/navegacion"
import { MenuUsuario } from "@/componentes/MenuUsuario"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

function ElementoMenu({
  elemento: { titulo, descripcion, ruta, icono: Icono },
  activa,
  alNavegar,
}: {
  elemento: ElementoNavegacion
  activa: boolean
  alNavegar: () => void
}) {
  const idDescripcion = useId()
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={activa}
        tooltip={{
          children: (
            <span className="flex flex-col">
              <span className="font-medium">{titulo}</span>
              <span className="text-xs">{descripcion}</span>
            </span>
          ),
        }}
        className="data-[active=true]:bg-sidebar-primary data-[active=true]:text-sidebar-primary-foreground"
      >
        <Link
          to={ruta}
          aria-current={activa ? "page" : undefined}
          aria-describedby={idDescripcion}
          onClick={alNavegar}
        >
          <Icono aria-hidden />
          <span>{titulo}</span>
          {/* Oculta a la vista: el lector de pantalla la lee como descripción del enlace. */}
          <span id={idDescripcion} hidden>
            {descripcion}
          </span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

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
      {/* La marca también va dentro de la navegación: axe exige que todo contenido esté en una región. */}
      <nav aria-label="Principal" className="flex min-h-0 flex-1 flex-col">
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
          {navegacionPara(roles).map((seccion) => (
            <SidebarGroup key={seccion.titulo}>
              <SidebarGroupLabel>{seccion.titulo}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {seccion.elementos.map((elemento) => (
                    <ElementoMenu
                      key={elemento.ruta}
                      elemento={elemento}
                      activa={estaActiva(
                        elemento.ruta,
                        pathname,
                        elemento.exacta
                      )}
                      alNavegar={alNavegar}
                    />
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </SidebarContent>
        <SidebarFooter>
          <MenuUsuario />
        </SidebarFooter>
      </nav>
    </Sidebar>
  )
}
