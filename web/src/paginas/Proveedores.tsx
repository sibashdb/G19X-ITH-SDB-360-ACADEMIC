import { keepPreviousData } from "@tanstack/react-query"
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Search,
  TriangleAlert,
  X,
} from "lucide-react"
import { useEffect, useRef, type FormEvent, type ReactNode } from "react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import { BarraPuntuacion } from "@/componentes/BarraPuntuacion"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Filtro } from "@/componentes/Filtro"
import { Iniciales } from "@/componentes/Iniciales"
import { Paginacion } from "@/componentes/Paginacion"
import { Termino } from "@/componentes/Termino"
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
import {
  useInteligencia,
  useUmbralRiesgo,
  type PaginaProveedoresConPuntuacion,
} from "@/inteligencia"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA, formatoMoneda } from "@/tipos"

const POR_PAGINA = 25
const PAGINA_MAXIMA = 1000 // la que acepta la API
const ESTADOS = ["activos", "inactivos"] as const
const ORDENES = [
  "nombre",
  "puntuacion",
  "gasto_anual",
  "contratos_vigentes",
  "alertas",
] as const
const DIRECCIONES = ["asc", "desc"] as const
type Orden = (typeof ORDENES)[number]
type Direccion = (typeof DIRECCIONES)[number]

/** El nombre va de la A a la Z; las cifras, primero de mayor a menor. */
const DIRECCION_INICIAL: Record<Orden, Direccion> = {
  nombre: "asc",
  puntuacion: "desc",
  gasto_anual: "desc",
  contratos_vigentes: "desc",
  alertas: "desc",
}

function EncabezadoOrdenable({
  columna,
  orden,
  direccion,
  alOrdenar,
  children,
  className,
}: {
  columna: Orden
  orden: Orden
  direccion: Direccion
  alOrdenar: (columna: Orden) => void
  children: ReactNode
  className?: string
}) {
  const activa = orden === columna
  const Icono = !activa
    ? ArrowUpDown
    : direccion === "asc"
      ? ArrowUp
      : ArrowDown
  return (
    <TableHead
      aria-sort={
        activa ? (direccion === "asc" ? "ascending" : "descending") : undefined
      }
      className={className}
    >
      <Button
        variant="ghost"
        size="sm"
        className="-mx-2"
        onClick={() => alOrdenar(columna)}
      >
        <span className="sr-only">Ordenar por</span> {children}
        <Icono aria-hidden />
      </Button>
    </TableHead>
  )
}

export function Proveedores() {
  const roles = useRoles()
  const umbral = useUmbralRiesgo()
  const [parametros, actualizar] = useParametros()
  const q = (parametros.get("q") ?? "").trim().slice(0, 100)
  const categoria = unoDe(parametros.get("categoria"), CATEGORIAS)
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const enRiesgo = parametros.get("en_riesgo") === "true"
  const orden: Orden = unoDe(parametros.get("orden"), ORDENES) ?? "nombre"
  const direccion: Direccion =
    unoDe(parametros.get("direccion"), DIRECCIONES) ?? DIRECCION_INICIAL[orden]
  const pagina = enteroPositivo(parametros.get("pagina"), 1, PAGINA_MAXIMA)
  const hayFiltros = Boolean(q || categoria || estado || enRiesgo)

  // El campo no es controlado ni se remonta (así conserva el foco tras Enter): cuando `q` cambia
  // por Atrás/Adelante o por "Limpiar filtros", se copia al campo si el texto escrito difiere.
  const campoBusqueda = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const campo = campoBusqueda.current
    if (campo && campo.value.trim() !== q) campo.value = q
  }, [q])

  const busqueda = new URLSearchParams({
    orden,
    direccion,
    pagina: String(pagina),
    tamano: String(POR_PAGINA),
  })
  if (q) busqueda.set("busqueda", q)
  if (categoria) busqueda.set("categoria", categoria)
  if (estado) busqueda.set("estado", estado)
  if (enRiesgo) busqueda.set("en_riesgo", "true")
  const consulta = useInteligencia<PaginaProveedoresConPuntuacion>(
    `/proveedores?${busqueda}`,
    { placeholderData: keepPreviousData }
  )

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = String(
      new FormData(evento.currentTarget).get("q") ?? ""
    ).trim()
    actualizar({ q: texto || null, pagina: null })
  }
  // Los botones que se usan desaparecen: el foco pasa al buscador, que sigue en pantalla.
  function limpiar() {
    actualizar({
      q: null,
      categoria: null,
      estado: null,
      en_riesgo: null,
      pagina: null,
    })
    campoBusqueda.current?.focus()
  }
  function irALaPrimera() {
    actualizar({ pagina: null })
    campoBusqueda.current?.focus()
  }
  // Los valores por omisión no se escriben en la URL.
  function ordenar(columna: Orden) {
    const nueva =
      columna === orden
        ? direccion === "asc"
          ? "desc"
          : "asc"
        : DIRECCION_INICIAL[columna]
    actualizar({
      orden: columna === "nombre" ? null : columna,
      direccion: nueva === DIRECCION_INICIAL[columna] ? null : nueva,
      pagina: null,
    })
  }
  const encabezado = (columna: Orden, texto: string, className?: string) => (
    <EncabezadoOrdenable
      columna={columna}
      orden={orden}
      direccion={direccion}
      alOrdenar={ordenar}
      className={className}
    >
      {texto}
    </EncabezadoOrdenable>
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
              <Button variant="outline" onClick={irALaPrimera}>
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
            descripcion="Ningún proveedor coincide con la búsqueda o los filtros. Pruebe con otros o use «Limpiar filtros»."
          />
        )
      }
      const esAdmin = roles.includes("admin")
      return (
        <EstadoVacio
          titulo="Aún no hay proveedores"
          descripcion={
            esAdmin
              ? "Importe el catálogo de proveedores del ERP para comenzar. Si ya lo importó, espere a que la inteligencia termine de recibir los datos."
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

    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              {encabezado("nombre", "Proveedor")}
              <TableHead>Categorías</TableHead>
              {encabezado("puntuacion", "Puntuación")}
              {encabezado("gasto_anual", "Gasto anual", "text-right")}
              {encabezado(
                "contratos_vigentes",
                "Contratos vigentes",
                "text-right"
              )}
              {encabezado("alertas", "Alertas", "text-right")}
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Iniciales nombre={p.nombre} />
                    <div className="space-y-0.5">
                      <Link
                        to={`/proveedores/${encodeURIComponent(p.id)}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {p.nombre}
                      </Link>
                      <div className="font-mono text-xs text-muted-foreground">
                        {p.rfc}
                      </div>
                      {p.en_riesgo && (
                        <Badge variant="destructive">
                          <TriangleAlert aria-hidden />
                          En riesgo
                        </Badge>
                      )}
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
                <TableCell>
                  <BarraPuntuacion
                    puntuacion={p.puntuacion}
                    confianza={p.confianza}
                    umbral={umbral}
                  />
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatoMoneda(p.gasto_anual, "MXN")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {p.contratos_vigentes.toLocaleString("es-MX")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {p.alertas > 0 ? (
                    <Link
                      to={`/alertas?proveedor=${encodeURIComponent(p.id)}`}
                      aria-label={`${p.alertas} ${p.alertas === 1 ? "alerta" : "alertas"} de ${p.nombre}`}
                      className="font-medium text-accent hover:underline"
                    >
                      {p.alertas.toLocaleString("es-MX")}
                    </Link>
                  ) : (
                    <span className="text-muted-foreground">0</span>
                  )}
                </TableCell>
                <TableCell>
                  <EtiquetaEstado activo={p.activo} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="proveedores"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Proveedores"
        descripcion={
          <>
            Quién le vende servicios de TI, cuánto le paga al año y cómo rinde
            según su <Termino clave="puntuacion">puntuación</Termino>.
          </>
        }
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
            {hayFiltros && (
              <Button type="button" variant="ghost" onClick={limpiar}>
                <X aria-hidden />
                Limpiar filtros
              </Button>
            )}
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
              aria-label="Filtrar por estado y riesgo"
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
              <Filtro
                activo={enRiesgo}
                onClick={() =>
                  actualizar({
                    en_riesgo: enRiesgo ? null : "true",
                    pagina: null,
                  })
                }
              >
                <TriangleAlert aria-hidden />
                En riesgo
              </Filtro>
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
    </section>
  )
}
