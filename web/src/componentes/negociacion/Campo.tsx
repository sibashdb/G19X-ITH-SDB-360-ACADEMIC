import type { ReactNode } from "react"
import { Label } from "@/components/ui/label"

export type PropsControl = {
  id: string
  "aria-invalid"?: true
  "aria-describedby"?: string
}

/** Etiqueta, control, ayuda y error de un campo; el control recibe el id y los aria-* que los enlazan. */
export function Campo({
  id,
  etiqueta,
  ayuda,
  error,
  children,
}: {
  id: string
  etiqueta: ReactNode
  ayuda?: ReactNode
  error?: string
  children: (control: PropsControl) => ReactNode
}) {
  const idAyuda = ayuda ? `${id}-ayuda` : undefined
  const idError = error ? `${id}-error` : undefined
  const descritoPor = [idAyuda, idError].filter(Boolean).join(" ") || undefined
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id}>{etiqueta}</Label>
      {children({
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": descritoPor,
      })}
      {ayuda && (
        <p id={idAyuda} className="text-sm text-muted-foreground">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={idError} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
