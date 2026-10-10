import { describirActividad } from "@/actividad"
import { Badge } from "@/components/ui/badge"
import { formatoFechaHora } from "@/fechas"
import type { RegistroActividad } from "@/tipos"

/** Registros de la bitácora; si `personaId` es quien actuó, no se repite su nombre. */
export function ListaActividad({
  elementos,
  personaId,
}: {
  elementos: RegistroActividad[]
  personaId?: string
}) {
  return (
    <ul className="divide-y">
      {elementos.map((a) => (
        <li
          key={a.id}
          className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-sm"
        >
          <time
            dateTime={a.fecha}
            className="w-44 shrink-0 text-muted-foreground"
          >
            {formatoFechaHora(a.fecha)}
          </time>
          <span className="min-w-0 flex-1">
            {a.actor_id !== personaId && (
              <span className="font-medium">{a.actor_nombre}: </span>
            )}
            {describirActividad(a)}
          </span>
          {a.resultado === "fallo" && (
            <Badge variant="destructive">Falló</Badge>
          )}
        </li>
      ))}
    </ul>
  )
}
