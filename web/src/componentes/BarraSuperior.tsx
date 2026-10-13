import {
  Bell,
  BellOff,
  CircleHelp,
  Monitor,
  Moon,
  Sun,
  type LucideIcon,
} from "lucide-react"
import { Fragment, type ReactNode } from "react"
import { Link, useLocation } from "react-router"
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
import {
  rutaDeAlerta,
  useInteligencia,
  type PaginaAlertas,
} from "@/inteligencia"
import { NOMBRES_TEMA, useTema, type Tema } from "@/tema"
import { NOMBRES_SEVERIDAD, NOMBRES_TIPO_ALERTA } from "@/tipos"

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

/** Campana: cuántas alertas hay y las 5 principales; se renueva cada minuto. */
function MenuAlertas() {
  const alertas = useInteligencia<PaginaAlertas>("/alertas?limite=5", {
    refetchInterval: 60_000,
  })
  const total = alertas.data?.total ?? 0
  const estado = (texto: ReactNode) => (
    <DropdownMenuLabel className="flex items-center gap-2 py-3 text-sm font-normal">
      {texto}
    </DropdownMenuLabel>
  )
  let contenido: ReactNode
  if (alertas.isPending) contenido = estado("Cargando…")
  else if (alertas.isError)
    contenido = estado("No se pudieron cargar las alertas.")
  else if (alertas.data.elementos.length === 0)
    contenido = estado(
      <>
        <BellOff aria-hidden className="size-4" />
        No hay alertas activas
      </>
    )
  else
    contenido = alertas.data.elementos.map((alerta) => (
      <DropdownMenuItem key={alerta.id} asChild>
        <Link
          to={rutaDeAlerta(alerta)}
          className="flex flex-col items-start gap-0.5"
        >
          <span className="text-xs text-muted-foreground">
            Severidad {NOMBRES_SEVERIDAD[alerta.severidad].toLowerCase()} ·{" "}
            {NOMBRES_TIPO_ALERTA[alerta.tipo]}
          </span>
          <span className="break-words whitespace-normal">{alerta.titulo}</span>
        </Link>
      </DropdownMenuItem>
    ))
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-lg"
          className="relative"
          aria-label={
            total > 0
              ? `Alertas: ${total.toLocaleString("es-MX")} activas`
              : "Alertas"
          }
        >
          <Bell aria-hidden />
          {total > 0 && (
            <span
              aria-hidden
              className="absolute top-0.5 right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-xs leading-none font-semibold text-destructive-foreground tabular-nums"
            >
              {total > 99 ? "99+" : total}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>
          Alertas{total > 0 && ` (${total.toLocaleString("es-MX")})`}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {contenido}
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
        <Button asChild variant="ghost" size="icon-lg">
          <Link to="/ayuda" aria-label="Centro de ayuda">
            <CircleHelp aria-hidden />
          </Link>
        </Button>
        <MenuAlertas />
        <SelectorTema />
      </div>
    </header>
  )
}
