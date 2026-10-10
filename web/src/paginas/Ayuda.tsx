import { Search, X } from "lucide-react"
import { useEffect, useRef, type FormEvent } from "react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import {
  ARTICULOS,
  buscarArticulos,
  PREGUNTAS,
  TEMAS,
  type Articulo,
} from "@/ayuda"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { GLOSARIO } from "@/glosario"
import { useParametros } from "@/parametros"

function ListaArticulos({ articulos }: { articulos: Articulo[] }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {articulos.map((a) => (
        <li key={a.slug}>
          <Link
            to={`/ayuda/${a.slug}`}
            className="block h-full rounded-xl border bg-card p-4 outline-hidden transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="block font-medium">{a.titulo}</span>
            <span className="block text-sm text-muted-foreground">
              {a.resumen}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function Ayuda() {
  const esAdmin = useRoles().includes("admin")
  const [parametros, actualizar] = useParametros()
  const q = (parametros.get("q") ?? "").trim().slice(0, 100)
  const campo = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (campo.current && campo.current.value.trim() !== q)
      campo.current.value = q
  }, [q])

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = String(
      new FormData(evento.currentTarget).get("q") ?? ""
    ).trim()
    actualizar({ q: texto || null })
  }

  const temas = TEMAS.filter((t) => esAdmin || !t.soloAdmin)
  const preguntas = PREGUNTAS.filter((p) => esAdmin || !p.soloAdmin)
  const resultados = q ? buscarArticulos(q, esAdmin) : null

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Centro de ayuda"
        descripcion="Guías paso a paso, preguntas frecuentes y el significado de cada término."
      />
      <form
        role="search"
        onSubmit={buscar}
        className="flex flex-wrap items-center gap-2"
      >
        <label htmlFor="busqueda-ayuda" className="sr-only">
          Buscar en la ayuda
        </label>
        <div className="relative w-full max-w-md">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            id="busqueda-ayuda"
            type="search"
            name="q"
            ref={campo}
            defaultValue={q}
            placeholder="¿Qué necesita hacer?"
            maxLength={100}
            className="pl-8"
          />
        </div>
        <Button type="submit">Buscar</Button>
        {q && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              actualizar({ q: null })
              // El botón se desmonta al usarse: el foco pasa al campo, que sigue en pantalla.
              campo.current?.focus()
            }}
          >
            <X aria-hidden />
            Limpiar búsqueda
          </Button>
        )}
      </form>
      {resultados ? (
        <Seccion titulo={`Resultados para «${q}»`}>
          {resultados.length > 0 ? (
            <ListaArticulos articulos={resultados} />
          ) : (
            <EstadoVacio
              titulo="Sin resultados"
              descripcion="Pruebe con otras palabras o revise las preguntas frecuentes."
            />
          )}
        </Seccion>
      ) : (
        temas.map((t) => (
          <Seccion key={t.clave} titulo={t.titulo} descripcion={t.descripcion}>
            <ListaArticulos
              articulos={ARTICULOS.filter((a) => a.tema === t.clave)}
            />
          </Seccion>
        ))
      )}
      <Seccion titulo="Preguntas frecuentes">
        <div className="divide-y">
          {preguntas.map((p) => (
            <details key={p.pregunta} className="py-3">
              <summary className="cursor-pointer font-medium">
                {p.pregunta}
              </summary>
              <p className="mt-2 text-sm text-muted-foreground">
                {p.respuesta}
              </p>
            </details>
          ))}
        </div>
      </Seccion>
      <Seccion
        titulo="Glosario"
        descripcion="Los términos técnicos de la plataforma, en lenguaje llano."
      >
        <dl className="grid gap-4 sm:grid-cols-2">
          {Object.values(GLOSARIO).map((g) => (
            <div key={g.termino}>
              <dt className="font-medium">{g.termino}</dt>
              <dd className="text-sm text-muted-foreground">{g.definicion}</dd>
            </div>
          ))}
        </dl>
      </Seccion>
    </section>
  )
}
