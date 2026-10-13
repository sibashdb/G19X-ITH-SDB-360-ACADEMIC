import { Building2, Tags, TrendingUp } from "lucide-react"
import { useEffect, useRef, useState, type Ref, type RefObject } from "react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import {
  ContenidoConsulta,
  EstadoCarga,
  EstadoVacio,
} from "@/componentes/Estados"
import { GraficaHistorial } from "@/componentes/GraficaHistorial"
import { Paginacion } from "@/componentes/Paginacion"
import { ReferenciaPrecio } from "@/componentes/ReferenciaPrecio"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { TablaSobreprecios } from "@/componentes/TablaSobreprecios"
import { Termino } from "@/componentes/Termino"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  porUnidad,
  useInteligencia,
  type HistorialPrecios,
  type ServicioPrecios,
  type Sobreprecio,
} from "@/inteligencia"
import { enteroPositivo, useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA, normalizarTexto } from "@/tipos"

const POR_PAGINA = 25
const DOS_COLUMNAS = "(min-width: 1024px)" // el `lg` de Tailwind

function ListaServicios({
  servicios,
  seleccionado,
  alElegir,
}: {
  servicios: ServicioPrecios[]
  seleccionado: string | null
  alElegir: (codigo: string) => void
}) {
  const [busqueda, setBusqueda] = useState("")
  const termino = normalizarTexto(busqueda.trim())
  const visibles = servicios.filter(
    (s) =>
      !termino || normalizarTexto(`${s.nombre} ${s.codigo}`).includes(termino)
  )
  const grupos = CATEGORIAS.map((categoria) => ({
    categoria,
    servicios: visibles.filter((s) => s.categoria === categoria),
  })).filter((grupo) => grupo.servicios.length > 0)

  return (
    <div className="space-y-3">
      <label htmlFor="buscar-servicio" className="sr-only">
        Buscar servicio por nombre o código
      </label>
      <Input
        id="buscar-servicio"
        type="search"
        placeholder="Nombre o código"
        value={busqueda}
        onChange={(evento) => setBusqueda(evento.target.value)}
      />
      {grupos.length === 0 ? (
        <p className="px-2 py-4 text-sm break-words text-muted-foreground">
          Ningún servicio coincide con «{busqueda.trim()}».
        </p>
      ) : (
        <ul
          aria-label="Servicios del catálogo"
          className="max-h-[28rem] space-y-3 overflow-y-auto"
        >
          {grupos.map((grupo) => (
            <li key={grupo.categoria}>
              <p className="px-2 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {NOMBRES_CATEGORIA[grupo.categoria]}
              </p>
              <ul className="space-y-1">
                {grupo.servicios.map((s) => (
                  <li key={s.codigo}>
                    <button
                      type="button"
                      aria-pressed={s.codigo === seleccionado}
                      onClick={() => alElegir(s.codigo)}
                      className="group w-full rounded-md px-2 py-1.5 text-left text-sm outline-hidden transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset aria-pressed:bg-accent aria-pressed:text-accent-foreground aria-pressed:focus-visible:ring-accent-foreground"
                    >
                      <span className="block">{s.nombre}</span>
                      <span className="font-mono text-xs text-muted-foreground group-aria-pressed:text-accent-foreground">
                        {s.codigo}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function DetalleServicio({
  servicio,
  refTitulo,
}: {
  servicio: ServicioPrecios
  refTitulo: Ref<HTMLHeadingElement>
}) {
  const codigo = encodeURIComponent(servicio.codigo)
  const historial = useInteligencia<HistorialPrecios>(
    `/precios/servicios/${codigo}/historial`
  )
  const sobreprecios = useInteligencia<Sobreprecio[]>(
    `/precios/sobreprecios?codigo=${codigo}`
  )
  const categoria = NOMBRES_CATEGORIA[servicio.categoria] ?? servicio.categoria
  return (
    <div className="space-y-4">
      <Seccion
        titulo={servicio.nombre}
        refTitulo={refTitulo}
        descripcion={`${servicio.codigo} · ${categoria} · ${porUnidad(servicio.unidad)} · ${servicio.moneda}`}
      >
        <p className="mb-4 text-sm text-muted-foreground">
          El <Termino clave="precioReferencia">precio de referencia</Termino>{" "}
          para la cantidad y el plazo que indique: precio bajo, típico y alto
          del mercado (<Termino clave="percentiles">P25, P50 y P75</Termino>).
        </p>
        {historial.isPending ? (
          <EstadoCarga filas={2} />
        ) : (
          <ReferenciaPrecio
            servicio={servicio}
            cantidadSugerida={historial.data?.cantidad ?? "1"}
          />
        )}
      </Seccion>
      <Seccion
        titulo="Historial de precios"
        descripcion="Precio de cada contrato de los últimos 24 meses sobre el rango típico del mercado."
      >
        <ContenidoConsulta consulta={historial}>
          {(datos) => <GraficaHistorial historial={datos} />}
        </ContenidoConsulta>
      </Seccion>
      <Seccion
        titulo="Contratos con sobreprecio"
        descripcion={
          <>
            Contratos vigentes de este servicio que pagan más que el P75, con su{" "}
            <Termino clave="ahorroPotencial">ahorro potencial</Termino>.
          </>
        }
      >
        <ContenidoConsulta consulta={sobreprecios}>
          {(filas) =>
            filas.length === 0 ? (
              <EstadoVacio
                icono={TrendingUp}
                titulo="Sin sobreprecios"
                descripcion="Ningún contrato vigente de este servicio paga más que el P75."
              />
            ) : (
              <TablaSobreprecios filas={filas} />
            )
          }
        </ContenidoConsulta>
      </Seccion>
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver proveedores de esta categoría",
            descripcion: `Proveedores de ${categoria} y sus contratos.`,
            ruta: `/proveedores?categoria=${servicio.categoria}`,
            icono: Building2,
          },
        ]}
      />
    </div>
  )
}

function TodosLosSobreprecios({
  refVista,
}: {
  refVista: RefObject<HTMLButtonElement | null>
}) {
  const [parametros, actualizar] = useParametros()
  const pagina = enteroPositivo(parametros.get("pagina"), 1)
  const consulta = useInteligencia<Sobreprecio[]>("/precios/sobreprecios")
  return (
    <Seccion
      titulo="Todos los sobreprecios"
      descripcion={
        <>
          Contratos vigentes que pagan más que el P75 del mercado, de mayor a
          menor <Termino clave="ahorroPotencial">ahorro potencial</Termino> en
          MXN.
        </>
      }
    >
      <ContenidoConsulta consulta={consulta}>
        {(filas) => {
          if (filas.length === 0) {
            return (
              <EstadoVacio
                icono={TrendingUp}
                titulo="Ningún contrato paga sobreprecio"
                descripcion="Todos los contratos vigentes pagan el precio del mercado o menos."
              />
            )
          }
          const visibles = filas.slice(
            (pagina - 1) * POR_PAGINA,
            pagina * POR_PAGINA
          )
          if (visibles.length === 0) {
            return (
              <EstadoVacio
                titulo="Esta página no tiene resultados"
                descripcion={`Hay ${filas.length.toLocaleString("es-MX")} líneas con sobreprecio.`}
                accion={
                  <Button
                    variant="outline"
                    onClick={() => {
                      actualizar({ pagina: null })
                      // El botón usado desaparece: el foco pasa al selector de vista, que sigue en pantalla.
                      refVista.current?.focus()
                    }}
                  >
                    Ir a la primera página
                  </Button>
                }
              />
            )
          }
          return (
            <div className="space-y-4">
              <TablaSobreprecios filas={visibles} conServicio />
              <Paginacion
                pagina={pagina}
                total={filas.length}
                porPagina={POR_PAGINA}
                nombre="líneas con sobreprecio"
                alCambiar={(p) => actualizar({ pagina: String(p) })}
              />
            </div>
          )
        }}
      </ContenidoConsulta>
    </Seccion>
  )
}

export function Precios() {
  const roles = useRoles()
  const [parametros, actualizar] = useParametros()
  const vista =
    parametros.get("vista") === "sobreprecios" ? "sobreprecios" : "servicio"
  const codigo = parametros.get("servicio")
  const servicios = useInteligencia<ServicioPrecios[]>("/precios/servicios")

  // En una sola columna el detalle queda debajo de la lista: al elegir un servicio se lleva el
  // foco a su título para que la persona vea el resultado sin buscarlo.
  const refDetalle = useRef<HTMLHeadingElement>(null)
  const refVistaSobreprecios = useRef<HTMLButtonElement>(null)
  const enfocarDetalle = useRef(false)
  useEffect(() => {
    if (!enfocarDetalle.current) return
    enfocarDetalle.current = false
    refDetalle.current?.focus()
  }, [codigo])

  function elegir(nuevo: string) {
    if (nuevo === codigo) return
    enfocarDetalle.current = !window.matchMedia(DOS_COLUMNAS).matches
    actualizar({ servicio: nuevo, cantidad: null, plazo: null })
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Precios"
        descripcion={
          <>
            Compare lo que paga con lo que se paga en el mercado: el{" "}
            <Termino clave="precioReferencia">precio de referencia</Termino> de
            cada servicio y los contratos con{" "}
            <Termino clave="sobreprecio">sobreprecio</Termino>.
          </>
        }
        acciones={
          <div role="group" aria-label="Vista" className="flex gap-2">
            <Button
              variant={vista === "servicio" ? "default" : "outline"}
              aria-pressed={vista === "servicio"}
              onClick={() => actualizar({ vista: null, pagina: null })}
            >
              Por servicio
            </Button>
            <Button
              ref={refVistaSobreprecios}
              variant={vista === "sobreprecios" ? "default" : "outline"}
              aria-pressed={vista === "sobreprecios"}
              onClick={() =>
                actualizar({ vista: "sobreprecios", pagina: null })
              }
            >
              Todos los sobreprecios
            </Button>
          </div>
        }
      />
      {vista === "sobreprecios" ? (
        <TodosLosSobreprecios refVista={refVistaSobreprecios} />
      ) : (
        <ContenidoConsulta consulta={servicios}>
          {(catalogo) => {
            if (catalogo.length === 0) {
              const esAdmin = roles.includes("admin")
              return (
                <EstadoVacio
                  icono={Tags}
                  titulo="El catálogo está vacío"
                  descripcion={
                    esAdmin
                      ? "Importe el catálogo de servicios del ERP para consultar precios."
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
            const seleccionado =
              catalogo.find((s) => s.codigo === codigo) ?? null
            return (
              <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
                <Seccion titulo="Servicios">
                  <ListaServicios
                    servicios={catalogo}
                    seleccionado={seleccionado?.codigo ?? null}
                    alElegir={elegir}
                  />
                </Seccion>
                {seleccionado ? (
                  <DetalleServicio
                    key={seleccionado.codigo}
                    servicio={seleccionado}
                    refTitulo={refDetalle}
                  />
                ) : (
                  <Seccion titulo="Servicio">
                    <EstadoVacio
                      icono={Tags}
                      titulo="Elija un servicio"
                      descripcion="Seleccione un servicio del catálogo para ver su precio de referencia y su historial."
                    />
                  </Seccion>
                )}
              </div>
            )
          }}
        </ContenidoConsulta>
      )}
    </section>
  )
}
