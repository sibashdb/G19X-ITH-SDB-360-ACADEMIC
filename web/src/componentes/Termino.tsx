import { useId, type ReactNode } from "react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { GLOSARIO, type ClaveGlosario } from "@/glosario"

/** Término técnico con su definición: abre con clic, toque o teclado; Escape la cierra. */
export function Termino({
  clave,
  children,
}: {
  clave: ClaveGlosario
  children?: ReactNode
}) {
  const { termino, definicion } = GLOSARIO[clave]
  const idTitulo = useId()
  const idDefinicion = useId()
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="cursor-help rounded-sm underline decoration-dotted underline-offset-4 outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
        >
          {children ?? termino}
        </button>
      </PopoverTrigger>
      <PopoverContent
        aria-labelledby={idTitulo}
        aria-describedby={idDefinicion}
        className="w-72 space-y-1 text-sm"
      >
        <p id={idTitulo} className="font-medium">
          {termino}
        </p>
        <p id={idDefinicion} className="text-muted-foreground">
          {definicion}
        </p>
      </PopoverContent>
    </Popover>
  )
}
