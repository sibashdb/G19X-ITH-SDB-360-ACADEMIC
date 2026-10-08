import {
  ArrowRight,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export type Tono = "info" | "exito" | "advertencia" | "riesgo"

const ESTILO_TONO: Record<Tono, { icono: string; acento: string }> = {
  info: { icono: "bg-info-suave text-accent", acento: "" },
  exito: { icono: "bg-exito-suave text-success", acento: "" },
  advertencia: {
    icono: "bg-advertencia-suave text-warning",
    acento: "border-l-3 border-l-warning",
  },
  riesgo: {
    icono: "bg-riesgo-suave text-destructive",
    acento: "border-l-3 border-l-destructive",
  },
}

export function TarjetaKpi({
  titulo,
  valor,
  detalle,
  icono: Icono,
  enlace,
  textoEnlace,
  tono = "info",
  variacion,
}: {
  titulo: ReactNode
  valor: string | null
  detalle?: string
  icono: LucideIcon
  enlace: string
  textoEnlace: string
  tono?: Tono
  variacion?: { texto: string; direccion: "sube" | "baja" }
}) {
  const estilo = ESTILO_TONO[tono]
  const Tendencia = variacion?.direccion === "baja" ? TrendingDown : TrendingUp
  return (
    <Card size="sm" className={cn(estilo.acento)}>
      <CardContent className="space-y-2">
        <div className="flex items-start justify-between gap-2 text-sm text-muted-foreground">
          <span>{titulo}</span>
          <span
            data-tono={tono}
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-lg",
              estilo.icono
            )}
          >
            <Icono aria-hidden className="size-4" />
          </span>
        </div>
        <p className="text-2xl font-semibold">
          {valor ?? (
            <>
              <span aria-hidden>—</span>
              <span className="sr-only">Sin datos</span>
            </>
          )}
        </p>
        {variacion && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <Tendencia aria-hidden className="size-3.5" />
            {variacion.texto}
          </p>
        )}
        {detalle && <p className="text-xs text-muted-foreground">{detalle}</p>}
        <Link
          to={enlace}
          className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
        >
          {textoEnlace}
          <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      </CardContent>
    </Card>
  )
}
