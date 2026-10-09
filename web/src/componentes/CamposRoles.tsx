import { useId } from "react"
import { DESCRIPCIONES_ROL, NOMBRES_ROL, ROLES, type Rol } from "@/auth"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"

/** Casillas de roles, cada una con una línea de qué puede hacer. */
export function CamposRoles({
  valor,
  alCambiar,
  error,
}: {
  valor: Rol[]
  alCambiar: (roles: Rol[]) => void
  error?: string
}) {
  const id = useId()
  function cambiar(rol: Rol, marcado: boolean) {
    const siguientes = marcado
      ? [...valor, rol]
      : valor.filter((r) => r !== rol)
    alCambiar(ROLES.filter((r) => siguientes.includes(r)))
  }
  return (
    <fieldset
      className="space-y-3"
      aria-describedby={error ? `${id}-error` : undefined}
    >
      <legend className="mb-2 text-sm font-medium">Roles</legend>
      {ROLES.map((rol) => (
        <div key={rol} className="flex items-start gap-2">
          <Checkbox
            id={`${id}-${rol}`}
            checked={valor.includes(rol)}
            onCheckedChange={(marcado) => cambiar(rol, marcado === true)}
            aria-describedby={`${id}-${rol}-descripcion`}
          />
          <div className="grid gap-0.5">
            <Label htmlFor={`${id}-${rol}`}>{NOMBRES_ROL[rol]}</Label>
            <p
              id={`${id}-${rol}-descripcion`}
              className="text-xs text-muted-foreground"
            >
              {DESCRIPCIONES_ROL[rol]}
            </p>
          </div>
        </div>
      ))}
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </fieldset>
  )
}
