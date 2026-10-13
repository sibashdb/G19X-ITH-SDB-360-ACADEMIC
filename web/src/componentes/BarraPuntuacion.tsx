import { Badge } from "@/components/ui/badge"
import {
  formatoPuntuacion,
  rangoPuntuacion,
  type Confianza,
  type RangoPuntuacion,
} from "@/inteligencia"
import { cn } from "@/lib/utils"

const COLOR: Record<RangoPuntuacion, string> = {
  bajo: "bg-destructive",
  medio: "bg-warning",
  alto: "bg-success",
}

/** Puntuación con una barra de color por rango; la cifra es la señal, la barra la acompaña. */
export function BarraPuntuacion({
  puntuacion,
  confianza,
  umbral,
}: {
  puntuacion: number | null
  confianza: Confianza | null
  umbral: number
}) {
  if (puntuacion === null) {
    return <span className="text-sm text-muted-foreground">Sin datos</span>
  }
  const rango = rangoPuntuacion(puntuacion, umbral)
  return (
    <div className="flex min-w-28 flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium tabular-nums">
          {formatoPuntuacion(puntuacion)}
        </span>
        {confianza === "baja" && (
          <Badge variant="warning">Historial corto</Badge>
        )}
      </div>
      <div aria-hidden className="h-1.5 w-full rounded-full bg-muted">
        <div
          data-rango={rango}
          className={cn("h-full rounded-full", COLOR[rango])}
          style={{ width: `${puntuacion}%` }}
        />
      </div>
    </div>
  )
}
