import {
  CalendarClock,
  Tags,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react"
import { Link } from "react-router"
import { Badge } from "@/components/ui/badge"
import { rutaDeAlerta, type Alerta } from "@/inteligencia"
import {
  NOMBRES_SEVERIDAD,
  NOMBRES_TIPO_ALERTA,
  formatoFecha,
  type Severidad,
  type TipoAlerta,
} from "@/tipos"

const ICONOS: Record<TipoAlerta, LucideIcon> = {
  vencimiento: CalendarClock,
  sobreprecio: Tags,
  riesgo: TriangleAlert,
}
const VARIANTES: Record<Severidad, "destructive" | "warning" | "secondary"> = {
  alta: "destructive",
  media: "warning",
  informativa: "secondary",
}

/** Una alerta: tipo con icono, severidad con texto, título enlazado, explicación y fecha. */
export function ElementoAlerta({ alerta }: { alerta: Alerta }) {
  const Icono = ICONOS[alerta.tipo]
  const fecha =
    alerta.tipo === "vencimiento"
      ? `Vence el ${formatoFecha(alerta.fecha)}`
      : `Calculada el ${formatoFecha(alerta.fecha)}`
  return (
    <article className="flex gap-3 py-3">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted">
        <Icono aria-hidden className="size-4" />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant={VARIANTES[alerta.severidad]}>
            <span className="sr-only">Severidad </span>
            {NOMBRES_SEVERIDAD[alerta.severidad]}
          </Badge>
          <span>
            {NOMBRES_TIPO_ALERTA[alerta.tipo]} · {alerta.proveedor_nombre} ·{" "}
            {fecha}
          </span>
        </div>
        <Link
          to={rutaDeAlerta(alerta)}
          className="block font-medium break-words text-accent hover:underline"
        >
          {alerta.titulo}
        </Link>
        <p className="text-sm break-words text-muted-foreground">
          {alerta.explicacion}
        </p>
      </div>
    </article>
  )
}
