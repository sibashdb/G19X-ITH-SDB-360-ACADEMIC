import type { UseQueryResult } from "@tanstack/react-query"
import { CircleAlert, Inbox, RefreshCw, type LucideIcon } from "lucide-react"
import type { ReactNode } from "react"
import { ErrorApi } from "@/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export function EstadoCarga({ filas = 5, etiqueta = "Cargando…" }: { filas?: number; etiqueta?: string }) {
  return (
    <div role="status" className="space-y-2">
      <span className="sr-only">{etiqueta}</span>
      {Array.from({ length: filas }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  )
}

export function EstadoVacio({
  icono: Icono = Inbox,
  titulo,
  descripcion,
  accion,
}: {
  icono?: LucideIcon
  titulo: string
  descripcion: string
  accion?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center">
      <Icono aria-hidden className="size-8 text-muted-foreground" />
      <p className="font-medium">{titulo}</p>
      <p className="max-w-prose text-sm text-muted-foreground">{descripcion}</p>
      {accion && <div className="mt-2">{accion}</div>}
    </div>
  )
}

export function EstadoError({ error, alReintentar }: { error: Error; alReintentar?: () => void }) {
  const titulo = error instanceof ErrorApi ? error.titulo : "No se pudo cargar la información"
  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden />
      <AlertTitle>{titulo}</AlertTitle>
      <AlertDescription>
        <p>{error.message}</p>
        {alReintentar && (
          <Button variant="outline" size="sm" className="mt-2" onClick={alReintentar}>
            <RefreshCw aria-hidden />
            Reintentar
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

/** Muestra carga, error con "Reintentar" o el contenido de una consulta. */
export function ContenidoConsulta<T>({
  consulta,
  children,
}: {
  consulta: UseQueryResult<T>
  children: (datos: T) => ReactNode
}) {
  if (consulta.isPending) return <EstadoCarga />
  if (consulta.isError) {
    return <EstadoError error={consulta.error} alReintentar={() => void consulta.refetch()} />
  }
  return children(consulta.data)
}
