import { CircleCheck, TriangleAlert } from "lucide-react"
import { useId, useState, type FormEvent } from "react"
import {
  CRITERIOS,
  mensajePesos,
  NOMBRES_CRITERIO,
  pesosValidos,
  sonEnteros,
  totalPesos,
  type Criterio,
  type Pesos,
} from "@/adjudicacion"
import { CampoNumero } from "@/componentes/CampoNumero"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * Cuatro pesos que suman 100 para recalcular la recomendación. `pesos` solo da los valores
 * iniciales: después, los campos son de quien escribe. `error` es el rechazo del servicio y se
 * oculta con la primera edición que sigue.
 */
export function AjustarPesos({
  pesos,
  error,
  alRecalcular,
}: {
  pesos: Pesos
  error?: string
  alRecalcular: (pesos: Pesos) => void
}) {
  const idTotal = useId()
  const [campos, setCampos] = useState(
    () =>
      Object.fromEntries(
        CRITERIOS.map((criterio) => [criterio, String(pesos[criterio])])
      ) as Record<Criterio, string>
  )
  const [intentado, setIntentado] = useState(false)
  // El rechazo del servicio que la persona ya empezó a corregir.
  const [corregido, setCorregido] = useState<string | undefined>()
  const total = totalPesos(campos)
  const validos = pesosValidos(campos)
  // Un campo que no es entero cuenta 0 en el total: se avisa aparte para que el total no engañe.
  const enteros = sonEnteros(campos)
  const problema = mensajePesos(campos)
  const mensaje =
    intentado && problema ? problema : error === corregido ? undefined : error

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setIntentado(true)
    setCorregido(undefined)
    if (validos) alRecalcular(validos)
  }

  return (
    // noValidate: el aviso lo da la página, en español y junto a los campos, no el navegador.
    <form noValidate onSubmit={enviar} className="space-y-3">
      <fieldset className="space-y-3">
        <legend className="text-sm font-semibold">
          Ajustar pesos (deben sumar 100)
        </legend>
        <p className="text-sm text-muted-foreground">
          Pruebe otros pesos para ver cómo cambia la recomendación.
        </p>
        <div className="flex flex-wrap gap-3">
          {CRITERIOS.map((criterio) => (
            <CampoNumero
              key={criterio}
              nombre={criterio}
              etiqueta={`Peso (${NOMBRES_CRITERIO[criterio]})`}
              min={0}
              max={100}
              step={1}
              inputMode="numeric"
              value={campos[criterio]}
              aria-describedby={idTotal}
              onChange={(e) => {
                setCampos({ ...campos, [criterio]: e.target.value })
                setIntentado(false)
                setCorregido(error)
              }}
            />
          ))}
        </div>
        <p
          id={idTotal}
          aria-live="polite"
          aria-atomic="true"
          className={cn(
            "flex items-center gap-1 text-sm font-medium",
            validos ? "text-success" : "text-warning"
          )}
        >
          {validos ? (
            <CircleCheck aria-hidden className="size-4" />
          ) : (
            <TriangleAlert aria-hidden className="size-4" />
          )}
          {`Total: ${total} de 100`}
          {!validos &&
            (enteros
              ? " · Los pesos deben sumar 100."
              : " · Revise los campos.")}
        </p>
        <p
          role="alert"
          className={mensaje ? "text-sm text-destructive" : "sr-only"}
        >
          {mensaje}
        </p>
      </fieldset>
      <Button type="submit">Recalcular</Button>
    </form>
  )
}
