import { ArrowLeft, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"

/** "Mostrando 1–25 de 60 …" con Anterior/Siguiente. */
export function Paginacion({
  pagina,
  total,
  porPagina,
  nombre,
  alCambiar,
}: {
  pagina: number
  total: number
  porPagina: number
  nombre: string
  alCambiar: (pagina: number) => void
}) {
  const paginas = Math.max(1, Math.ceil(total / porPagina))
  const desde = (pagina - 1) * porPagina + 1
  const hasta = Math.min(pagina * porPagina, total)
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
      <span aria-live="polite">
        Mostrando {desde.toLocaleString("es-MX")}–
        {hasta.toLocaleString("es-MX")} de {total.toLocaleString("es-MX")}{" "}
        {nombre}
      </span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={pagina <= 1}
          onClick={() => alCambiar(pagina - 1)}
        >
          <ArrowLeft aria-hidden />
          Anterior
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={pagina >= paginas}
          onClick={() => alCambiar(pagina + 1)}
        >
          Siguiente
          <ArrowRight aria-hidden />
        </Button>
      </div>
    </div>
  )
}
