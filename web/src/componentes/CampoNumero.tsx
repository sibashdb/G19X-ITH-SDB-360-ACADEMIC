import { useId, type ComponentProps } from "react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

/** Un campo numérico con su etiqueta, su ayuda y el error del servicio junto a él. */
export function CampoNumero({
  nombre,
  etiqueta,
  ayuda,
  error,
  "aria-describedby": otraDescripcion,
  ...entrada
}: {
  nombre: string
  etiqueta: string
  ayuda?: string
  error?: string
} & Omit<ComponentProps<typeof Input>, "id" | "name">) {
  const id = useId()
  // La descripción que llega (p. ej. el total de los pesos) se suma a la ayuda y al error.
  const descripciones = [
    otraDescripcion,
    ayuda && `${id}-ayuda`,
    error && `${id}-error`,
  ]
    .filter(Boolean)
    .join(" ")
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{etiqueta}</Label>
      <Input
        id={id}
        name={nombre}
        type="number"
        required
        aria-invalid={error ? true : undefined}
        aria-describedby={descripciones || undefined}
        className="w-32"
        {...entrada}
      />
      {ayuda && (
        <p id={`${id}-ayuda`} className="text-xs text-muted-foreground">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
