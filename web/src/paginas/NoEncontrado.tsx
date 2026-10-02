import { FileQuestion } from "lucide-react"
import { Link } from "react-router"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Button } from "@/components/ui/button"

export function NoEncontrado() {
  return (
    <section className="space-y-6">
      <EncabezadoPagina titulo="Página no encontrada" />
      <EstadoVacio
        icono={FileQuestion}
        titulo="No encontramos esta página"
        descripcion="Revise la dirección o vuelva al tablero."
        accion={
          <Button asChild>
            <Link to="/">Ir al tablero</Link>
          </Button>
        }
      />
    </section>
  )
}
