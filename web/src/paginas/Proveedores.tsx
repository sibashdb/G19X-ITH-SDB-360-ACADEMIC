import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ArrowLeft, ArrowRight, Search, X } from "lucide-react"
import { useEffect, useRef, type FormEvent, type ReactNode } from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Iniciales } from "@/componentes/Iniciales"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import {
  CATEGORIAS,
  NOMBRES_CATEGORIA,
  NOMBRES_TAMANO,
  type PaginaProveedores,
} from "@/tipos"

const POR_PAGINA = 25
const PAGINA_MAXIMA = 40_000 // la API acepta desplazamientos de hasta 1,000,000
const ESTADOS = ["activos", "inactivos"] as const

function Filtro({
  activo,
  onClick,
  children,
}: {
  activo: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant={activo ? "default" : "outline"}
      aria-pressed={activo}
      className="rounded-full"
      onClick={onClick}
    >
      {children}
    </Button>
  )
}

export function Proveedores() {
  const token = useToken()
  const roles = useRoles()
  const [parametros, actualizar] = useParametros()
  const q = (parametros.get("q") ?? "").trim().slice(0, 100)
  const categoria = unoDe(parametros.get("categoria"), CATEGORIAS)
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const pagina = enteroPositivo(parametros.get("pagina"), 1, PAGINA_MAXIMA)
  const hayFiltros = Boolean(q || categoria || estado)

  // El campo no es controlado ni se remonta (así conserva el foco tras Enter): cuando `q` cambia
  // por Atrás/Adelante o por "Limpiar filtros", se copia al campo si el texto escrito difiere.
  const campoBusqueda = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const campo = campoBusqueda.current
    if (campo && campo.value.trim() !== q) campo.value = q
  }, [q])

  const consulta = useQuery({
    queryKey: ["proveedores", { q, categoria, estado, pagina }],
    queryFn: () => {
      const busqueda = new URLSearchParams({
        limite: String(POR_PAGINA),
        desplazamiento: String((pagina - 1) * POR_PAGINA),
      })
      if (q) busqueda.set("q", q)
      if (categoria) busqueda.set("categoria", categoria)
      if (estado) busqueda.set("activo", String(estado === "activos"))
      return pedir<PaginaProveedores>(
        `/proveedores/proveedores?${busqueda}`,
        token
      )
    },
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = String(
      new FormData(evento.currentTarget).get("q") ?? ""
    ).trim()
    actualizar({ q: texto || null, pagina: null })
  }
  const limpiar = () =>
    actualizar({ q: null, categoria: null, estado: null, pagina: null })
  const botonLimpiar = (
    <Button type="button" variant="ghost" onClick={limpiar}>
      <X aria-hidden />
      Limpiar filtros
    </Button>
  )

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError) {
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    }
    const { total, elementos } = consulta.data
    if (elementos.length === 0) {
      // Primero la página fuera de rango: con filtros también puede haber coincidencias en otras páginas.
      if (pagina > 1 && total > 0) {
        return (
          <EstadoVacio
            titulo="Esta página no tiene resultados"
            descripcion={`Hay ${total.toLocaleString("es-MX")} proveedores ${
              hayFiltros
                ? "que coinciden con la búsqueda o los filtros"
                : "en total"
            }.`}
            accion={
              <Button
                variant="outline"
                onClick={() => actualizar({ pagina: null })}
              >
                Ir a la primera página
              </Button>
            }
          />
        )
      }
      if (hayFiltros) {
        return (
          <EstadoVacio
            titulo="Sin resultados"
            descripcion="Ningún proveedor coincide con la búsqueda o los filtros."
            accion={botonLimpiar}
          />
        )
      }
      const esAdmin = roles.includes("admin")
      return (
        <EstadoVacio
          titulo="Aún no hay proveedores"
          descripcion={
            esAdmin
              ? "Importe el catálogo de proveedores del ERP para comenzar."
              : "Pida a un administrador que importe el catálogo del ERP."
          }
          accion={
            esAdmin && (
              <Button asChild>
                <Link to="/importacion">Ir a Importación</Link>
              </Button>
            )
          }
        />
      )
    }

    const paginas = Math.max(1, Math.ceil(total / POR_PAGINA))
    const desde = (pagina - 1) * POR_PAGINA + 1
    const hasta = Math.min(pagina * POR_PAGINA, total)
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Proveedor</TableHead>
              <TableHead>Categorías</TableHead>
              <TableHead>Tamaño</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Iniciales nombre={p.nombre} />
                    <div>
                      <Link
                        to={`/proveedores/${encodeURIComponent(p.id)}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {p.nombre}
                      </Link>
                      <div className="font-mono text-xs text-muted-foreground">
                        {p.rfc}
                      </div>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {p.categorias.map((c) => (
                      <Badge key={c} variant="secondary">
                        {NOMBRES_CATEGORIA[c] ?? c}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>{NOMBRES_TAMANO[p.tamano] ?? p.tamano}</TableCell>
                <TableCell>
                  <EtiquetaEstado activo={p.activo} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
          <span aria-live="polite">
            Mostrando {desde.toLocaleString("es-MX")}–
            {hasta.toLocaleString("es-MX")} de {total.toLocaleString("es-MX")}{" "}
            proveedores
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagina <= 1}
              onClick={() => actualizar({ pagina: String(pagina - 1) })}
            >
              <ArrowLeft aria-hidden />
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pagina >= paginas}
              onClick={() => actualizar({ pagina: String(pagina + 1) })}
            >
              Siguiente
              <ArrowRight aria-hidden />
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Proveedores"
        descripcion="Quién le vende servicios de TI, en qué categorías y si sigue activo."
      />
      <Card>
        <CardContent className="space-y-4">
          <form
            role="search"
            onSubmit={buscar}
            className="flex flex-wrap items-center gap-2"
          >
            <label htmlFor="busqueda" className="sr-only">
              Buscar por nombre o RFC
            </label>
            <div className="relative w-full max-w-sm">
              <Search
                aria-hidden
                className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                id="busqueda"
                name="q"
                ref={campoBusqueda}
                defaultValue={q}
                placeholder="Nombre o RFC"
                maxLength={100}
                className="pl-8"
              />
            </div>
            <Button type="submit">Buscar</Button>
            {hayFiltros && botonLimpiar}
          </form>
          <div className="flex flex-wrap items-center gap-2">
            <div
              role="group"
              aria-label="Filtrar por categoría"
              className="flex flex-wrap gap-2"
            >
              <Filtro
                activo={!categoria}
                onClick={() => actualizar({ categoria: null, pagina: null })}
              >
                Todas
              </Filtro>
              {CATEGORIAS.map((c) => (
                <Filtro
                  key={c}
                  activo={categoria === c}
                  onClick={() => actualizar({ categoria: c, pagina: null })}
                >
                  {NOMBRES_CATEGORIA[c]}
                </Filtro>
              ))}
            </div>
            <div
              role="group"
              aria-label="Filtrar por estado"
              className="flex flex-wrap gap-2 md:ml-auto"
            >
              <Filtro
                activo={!estado}
                onClick={() => actualizar({ estado: null, pagina: null })}
              >
                Todos
              </Filtro>
              <Filtro
                activo={estado === "activos"}
                onClick={() => actualizar({ estado: "activos", pagina: null })}
              >
                Activos
              </Filtro>
              <Filtro
                activo={estado === "inactivos"}
                onClick={() =>
                  actualizar({ estado: "inactivos", pagina: null })
                }
              >
                Inactivos
              </Filtro>
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
    </section>
  )
}
