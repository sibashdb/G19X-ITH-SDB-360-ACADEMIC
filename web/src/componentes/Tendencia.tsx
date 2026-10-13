import { Minus, TrendingDown, TrendingUp } from "lucide-react"
import { formatoPuntuacion } from "@/inteligencia"
import { cn } from "@/lib/utils"

/** Cambio de la puntuación contra hace 3 meses, con icono, signo y texto para lectores. */
export function Tendencia({ valor }: { valor: number | null }) {
  if (valor === null) {
    return (
      <span className="text-muted-foreground">
        <span aria-hidden>—</span>
        <span className="sr-only">Sin tendencia</span>
      </span>
    )
  }
  const [Icono, color, signo] =
    valor > 0
      ? ([TrendingUp, "text-success", "+"] as const)
      : valor < 0
        ? ([TrendingDown, "text-destructive", ""] as const)
        : ([Minus, "text-muted-foreground", ""] as const)
  return (
    <span className={cn("inline-flex items-center gap-1 tabular-nums", color)}>
      <Icono aria-hidden className="size-4" />
      {signo}
      {formatoPuntuacion(valor)}
      <span className="sr-only"> puntos en 3 meses</span>
    </span>
  )
}
