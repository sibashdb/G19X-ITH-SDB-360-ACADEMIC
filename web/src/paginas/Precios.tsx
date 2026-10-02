import { useQuery } from "@tanstack/react-query"
import { ChartLine, Tags, TrendingUp } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoConsulta, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA, normalizarTexto, type Servicio } from "@/tipos"

function ListaServicios({
  servicios,
  seleccionado,
  alElegir,
}: {
  servicios: Servicio[]
  seleccionado: string | null
  alElegir: (codigo: string) => void
}) {
  const [busqueda, setBusqueda] = useState("")
  const termino = normalizarTexto(busqueda.trim())
  const visibles = servicios.filter(
    (s) => !termino || normalizarTexto(`${s.nombre} ${s.codigo}`).includes(termino)
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
        <p className="px-2 py-4 text-sm text-muted-foreground">Ningún servicio coincide con «{busqueda.trim()}».</p>
      ) : (
        <ul aria-label="Servicios del catálogo" className="max-h-[28rem] space-y-3 overflow-y-auto">
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
                      className="group w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted aria-pressed:bg-accent aria-pressed:text-accent-foreground"
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

function DetalleServicio({ servicio }: { servicio: Servicio }) {
  return (
    <div className="space-y-4">
      <Seccion
        titulo={servicio.nombre}
        descripcion={`${servicio.codigo} · ${NOMBRES_CATEGORIA[servicio.categoria] ?? servicio.categoria} · por ${servicio.unidad} · ${servicio.moneda}`}
      >
        <EstadoVacio
          icono={Tags}
          titulo="Sin precio de referencia todavía"
          descripcion="Aquí verá P25, P50 y P75 para la cantidad y el plazo que indique, con el método usado, su confianza y el número de observaciones."
        />
      </Seccion>
      <Seccion titulo="Historial de precios">
        <EstadoVacio
          icono={ChartLine}
          titulo="Sin historial todavía"
          descripcion="Aquí verá los precios de los contratos en el tiempo sobre la banda P25–P75."
        />
      </Seccion>
      <Seccion titulo="Contratos sobre P75">
        <EstadoVacio
          icono={TrendingUp}
          titulo="Sin sobreprecios detectados todavía"
          descripcion="Aquí verá los contratos vigentes de este servicio por encima de P75 y su ahorro potencial anual."
        />
      </Seccion>
    </div>
  )
}

export function Precios() {
  const token = useToken()
  const roles = useRoles()
  const [parametros, actualizar] = useParametros()
  const vista = parametros.get("vista") === "sobreprecios" ? "sobreprecios" : "servicio"
  const codigo = parametros.get("servicio")

  const servicios = useQuery({
    queryKey: ["servicios"],
    queryFn: () => pedir<Servicio[]>("/proveedores/servicios", token),
    enabled: Boolean(token),
  })

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Precios"
        descripcion="Precio de referencia por servicio (P25, P50 y P75) y contratos por encima del mercado."
        acciones={
          <div role="group" aria-label="Vista" className="flex gap-2">
            <Button
              variant={vista === "servicio" ? "default" : "outline"}
              aria-pressed={vista === "servicio"}
              onClick={() => actualizar({ vista: null })}
            >
              Por servicio
            </Button>
            <Button
              variant={vista === "sobreprecios" ? "default" : "outline"}
              aria-pressed={vista === "sobreprecios"}
              onClick={() => actualizar({ vista: "sobreprecios" })}
            >
              Todos los sobreprecios
            </Button>
          </div>
        }
      />
      <AvisoInteligencia />
      {vista === "sobreprecios" ? (
        <Seccion titulo="Todos los sobreprecios">
          <EstadoVacio
            icono={TrendingUp}
            titulo="Sin sobreprecios detectados todavía"
            descripcion="Aquí verá los contratos vigentes por encima de P75, ordenados por ahorro potencial."
          />
        </Seccion>
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
            const seleccionado = catalogo.find((s) => s.codigo === codigo) ?? null
            return (
              <div className="grid items-start gap-4 lg:grid-cols-[20rem_1fr]">
                <Seccion titulo="Servicios">
                  <ListaServicios
                    servicios={catalogo}
                    seleccionado={seleccionado?.codigo ?? null}
                    alElegir={(nuevo) => actualizar({ servicio: nuevo })}
                  />
                </Seccion>
                {seleccionado ? (
                  <DetalleServicio servicio={seleccionado} />
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
