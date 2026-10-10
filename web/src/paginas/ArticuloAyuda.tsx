import { ArrowLeft, FileQuestion } from "lucide-react"
import { Link, useParams } from "react-router"
import { articuloPorSlug, esSoloAdmin } from "@/ayuda"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Button } from "@/components/ui/button"

export function ArticuloAyuda() {
  const articulo = articuloPorSlug(useParams().articulo)
  if (!articulo)
    return (
      <EstadoVacio
        icono={FileQuestion}
        titulo="No encontramos ese artículo"
        descripcion="Puede que el enlace esté incompleto o que el artículo haya cambiado de nombre."
        accion={
          <Button asChild variant="outline">
            <Link to="/ayuda">Volver al Centro de ayuda</Link>
          </Button>
        }
      />
    )
  const contenido = (
    <article className="max-w-3xl space-y-6">
      <Link
        to="/ayuda"
        className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
      >
        <ArrowLeft aria-hidden className="size-4" />
        Centro de ayuda
      </Link>
      <EncabezadoPagina
        titulo={articulo.titulo}
        descripcion={articulo.resumen}
      />
      {articulo.secciones.map((s, i) => (
        <section key={s.titulo ?? i} className="space-y-2">
          {s.titulo && <h2 className="text-base font-semibold">{s.titulo}</h2>}
          {s.parrafos?.map((p) => (
            <p key={p} className="text-sm leading-relaxed">
              {p}
            </p>
          ))}
          {s.pasos && (
            <ol className="list-decimal space-y-1 pl-5 text-sm leading-relaxed">
              {s.pasos.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ol>
          )}
        </section>
      ))}
      {articulo.enlaces && (
        <div className="flex flex-wrap gap-2">
          {articulo.enlaces.map((e) => (
            <Button key={e.ruta} asChild variant="outline">
              <Link to={e.ruta}>{e.texto}</Link>
            </Button>
          ))}
        </div>
      )}
    </article>
  )
  return esSoloAdmin(articulo) ? (
    <RequiereRol rol="admin">{contenido}</RequiereRol>
  ) : (
    contenido
  )
}
