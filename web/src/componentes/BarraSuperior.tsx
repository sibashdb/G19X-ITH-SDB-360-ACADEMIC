import {
  Bell,
  BellOff,
  LogOut,
  Monitor,
  Moon,
  Sun,
  type LucideIcon,
} from "lucide-react"
import { Fragment } from "react"
import { useAuth } from "react-oidc-context"
import { Link, useLocation } from "react-router"
import { NOMBRES_ROL, useRoles } from "@/auth"
import { migasDe } from "@/componentes/navegacion"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { NOMBRES_TEMA, useTema, type Tema } from "@/tema"

const ICONOS_TEMA: Record<Tema, LucideIcon> = {
  claro: Sun,
  oscuro: Moon,
  sistema: Monitor,
}

function Migas() {
  const migas = migasDe(useLocation().pathname)
  return (
    <Breadcrumb>
      <BreadcrumbList>
        {migas.map((miga, i) => {
          const ultima = i === migas.length - 1
          return (
            <Fragment key={`${i}-${miga.titulo}`}>
              {i > 0 && <BreadcrumbSeparator className="hidden md:block" />}
              <BreadcrumbItem
                className={ultima ? undefined : "hidden md:inline-flex"}
              >
                {ultima ? (
                  <BreadcrumbPage>{miga.titulo}</BreadcrumbPage>
                ) : miga.ruta ? (
                  <BreadcrumbLink asChild>
                    <Link to={miga.ruta}>{miga.titulo}</Link>
                  </BreadcrumbLink>
                ) : (
                  <span>{miga.titulo}</span>
                )}
              </BreadcrumbItem>
            </Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}

/** Campana: el conteo y las 5 alertas más severas llegan en el Plan B. */
function MenuAlertas() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-lg" aria-label="Alertas">
          <Bell aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel>Alertas</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <p className="flex items-center gap-2 px-2 py-3 text-sm text-muted-foreground">
          <BellOff aria-hidden className="size-4" />
          No hay alertas activas
        </p>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/alertas">Ver todas las alertas</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function SelectorTema() {
  const { tema, cambiarTema } = useTema()
  const Icono = ICONOS_TEMA[tema]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-lg"
          aria-label={`Tema: ${NOMBRES_TEMA[tema]}`}
        >
          <Icono aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Tema</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={tema}
          onValueChange={(valor) => cambiarTema(valor as Tema)}
        >
          {(Object.keys(NOMBRES_TEMA) as Tema[]).map((opcion) => {
            const IconoOpcion = ICONOS_TEMA[opcion]
            return (
              <DropdownMenuRadioItem key={opcion} value={opcion}>
                <IconoOpcion aria-hidden />
                {NOMBRES_TEMA[opcion]}
              </DropdownMenuRadioItem>
            )
          })}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function MenuUsuario() {
  const auth = useAuth()
  const roles = useRoles()
  const perfil = auth.user?.profile
  const nombre =
    [perfil?.given_name, perfil?.family_name].filter(Boolean).join(" ") ||
    perfil?.preferred_username ||
    "Usuario"
  const iniciales = nombre
    .split(" ")
    .map((parte) => parte[0])
    .slice(0, 2)
    .join("")
    .toUpperCase()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="h-9 gap-2 px-2"
          aria-label={`Cuenta de ${nombre}`}
        >
          <span
            aria-hidden
            className="flex size-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground"
          >
            {iniciales}
          </span>
          <span className="hidden text-sm font-medium md:inline">{nombre}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="space-y-0.5">
          <span className="block font-medium">{nombre}</span>
          <span className="block text-xs font-normal text-muted-foreground">
            {roles.map((rol) => NOMBRES_ROL[rol]).join(" · ") ||
              "Sin rol asignado"}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void auth.signoutRedirect()}>
          <LogOut aria-hidden />
          Cerrar sesión
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function BarraSuperior() {
  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator
        orientation="vertical"
        className="mr-2 data-[orientation=vertical]:h-4"
      />
      <Migas />
      <div className="ml-auto flex items-center gap-1">
        <MenuAlertas />
        <SelectorTema />
        <MenuUsuario />
      </div>
    </header>
  )
}
