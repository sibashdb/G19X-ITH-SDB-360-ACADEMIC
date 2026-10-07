import { ArrowRight, type LucideIcon } from "lucide-react"
import { useId } from "react"
import { Link } from "react-router"

export type EnlaceSiguiente = {
  titulo: string
  descripcion: string
  ruta: string
  icono: LucideIcon
}

/** Sugiere a dónde ir después de la pantalla actual. */
export function SiguientePaso({ enlaces }: { enlaces: EnlaceSiguiente[] }) {
  const idTitulo = useId()
  return (
    <section aria-labelledby={idTitulo} className="space-y-3">
      <h2 id={idTitulo} className="text-base font-semibold">
        Siguiente paso
      </h2>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {enlaces.map(({ titulo, descripcion, ruta, icono: Icono }) => (
          <li key={ruta}>
            <Link
              to={ruta}
              className="flex h-full items-start gap-3 rounded-xl border bg-card p-4 outline-hidden transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-info-suave">
                <Icono aria-hidden className="size-4 text-accent" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{titulo}</span>
                <span className="block text-sm text-muted-foreground">
                  {descripcion}
                </span>
              </span>
              <ArrowRight
                aria-hidden
                className="size-4 shrink-0 self-center text-muted-foreground"
              />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
