import { useQuery, type UseQueryResult } from "@tanstack/react-query"
import { ArrowLeft, ChartLine, FileQuestion, Tags, Trophy } from "lucide-react"
import { useId } from "react"
import { Link, useParams } from "react-router"
import { Line, LineChart } from "recharts"
import { ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { DesempenoProveedor } from "@/componentes/DesempenoProveedor"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import {
  ContenidoConsulta,
  EstadoCarga,
  EstadoError,
  EstadoVacio,
} from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Iniciales } from "@/componentes/Iniciales"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { TablaContratos } from "@/componentes/TablaContratos"
import { Tendencia } from "@/componentes/Tendencia"
import { Termino } from "@/componentes/Termino"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  COMPONENTES,
  formatoDecimal,
  formatoPuntuacion,
  useInteligencia,
  type MercadoLinea,
  type PaginaAlertas,
  type Puntuacion,
} from "@/inteligencia"
import { unoDe, useParametros } from "@/parametros"
import {
  KPIS_DESEMPENO,
  NOMBRES_CATEGORIA,
  NOMBRES_TAMANO,
  formatoKpi,
  formatoPeriodo,
  type Contrato,
  type Desempeno,
  type ProveedorDetalle as Detalle,
} from "@/tipos"

const PESTANAS = ["resumen", "contratos", "desempeno"] as const
const CONFIG_HISTORIAL = {
  puntuacion: { label: "Puntuación", color: "var(--chart-1)" },
} satisfies ChartConfig

/** Para lo que viene de la inteligencia: la ficha sigue útil aunque eso falle. */
function NoDisponible({
  texto,
  alReintentar,
}: {
  texto: string
  alReintentar: () => void
}) {
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      {texto}
      <Button
        variant="link"
        size="sm"
        className="h-auto p-0"
        onClick={alReintentar}
      >
        Reintentar
      </Button>
    </p>
  )
}

function ResumenPuntuacion({
  consulta,
}: {
  consulta: UseQueryResult<Puntuacion>
}) {
  if (consulta.isPending) return <Skeleton className="h-10 w-32" />
  if (consulta.isError) {
    if (consulta.error instanceof ErrorApi && consulta.error.estado === 404) {
      return (
        <span className="text-muted-foreground">Sin puntuación todavía</span>
      )
    }
    return (
      <NoDisponible
        texto="No se pudo consultar."
        alReintentar={() => void consulta.refetch()}
      />
    )
  }
  const p = consulta.data
  if (p.puntuacion === null) {
    return <span className="text-muted-foreground">Sin datos de desempeño</span>
  }
  const historial = p.historial
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums">
          {formatoPuntuacion(p.puntuacion)}
        </span>
        <span className="text-muted-foreground">de 100</span>
        <Tendencia valor={p.tendencia} />
      </div>
      {p.historial_corto && (
        <p className="text-xs text-warning">
          <Termino clave="historialCorto">Historial corto</Termino>
        </p>
      )}
      {historial.length > 1 && (
        <>
          <div aria-hidden className="h-10 w-36">
            {/* Decorativa y dentro de aria-hidden: sin accessibilityLayer, que la haría enfocable. */}
            <ChartContainer
              config={CONFIG_HISTORIAL}
              className="aspect-auto h-10 w-36"
            >
              <LineChart
                accessibilityLayer={false}
                data={historial}
                margin={{ top: 4, right: 0, bottom: 4, left: 0 }}
              >
                <Line
                  dataKey="puntuacion"
                  type="monotone"
                  stroke="var(--color-puntuacion)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ChartContainer>
          </div>
          <p className="text-xs text-muted-foreground">
            Últimos {historial.length} meses: de{" "}
            {formatoPuntuacion(historial[0].puntuacion)} a{" "}
            {formatoPuntuacion(historial[historial.length - 1].puntuacion)}
          </p>
        </>
      )}
    </div>
  )
}

function AlertasDelProveedor({
  consulta,
  proveedorId,
}: {
  consulta: UseQueryResult<PaginaAlertas>
  proveedorId: string
}) {
  const idTitulo = useId()
  if (consulta.isPending) return null
  if (consulta.isError) {
    return (
      <NoDisponible
        texto="No se pudieron consultar sus alertas."
        alReintentar={() => void consulta.refetch()}
      />
    )
  }
  const { total, elementos } = consulta.data
  if (total === 0) {
    return <p className="text-sm text-muted-foreground">Sin alertas activas.</p>
  }
  return (
    <section aria-labelledby={idTitulo} className="space-y-1 border-t pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={idTitulo} className="text-base font-semibold">
          Alertas activas ({total.toLocaleString("es-MX")})
        </h2>
        <Link
          to={`/alertas?proveedor=${encodeURIComponent(proveedorId)}`}
          className="text-sm font-medium text-accent hover:underline"
        >
          Ver sus {total.toLocaleString("es-MX")}{" "}
          {total === 1 ? "alerta" : "alertas"}
        </Link>
      </div>
      <div className="divide-y">
        {elementos.map((alerta) => (
          <ElementoAlerta key={alerta.id} alerta={alerta} />
        ))}
      </div>
    </section>
  )
}

function Encabezado({
  proveedor: p,
  puntuacion,
  alertas,
}: {
  proveedor: Detalle
  puntuacion: UseQueryResult<Puntuacion>
  alertas: UseQueryResult<PaginaAlertas>
}) {
  return (
    <Card>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Iniciales nombre={p.nombre} tamano="lg" />
              <h1 className="text-2xl font-semibold tracking-tight">
                {p.nombre}
              </h1>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span className="font-mono">{p.rfc}</span>
              <span aria-hidden>·</span>
              <span>{NOMBRES_TAMANO[p.tamano] ?? p.tamano}</span>
              <EtiquetaEstado activo={p.activo} />
            </div>
            <div className="flex flex-wrap gap-1">
              {p.categorias.map((c) => (
                <Badge key={c} variant="secondary">
                  {NOMBRES_CATEGORIA[c] ?? c}
                </Badge>
              ))}
            </div>
          </div>
          <dl className="grid gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Contacto</dt>
              <dd>{p.contacto_nombre}</dd>
              <dd>
                <a
                  href={`mailto:${p.contacto_email}`}
                  className="break-all text-accent hover:underline"
                >
                  {p.contacto_email}
                </a>
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Contratos vigentes</dt>
              <dd className="text-2xl font-semibold">{p.contratos_vigentes}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">
                <Termino clave="puntuacion">Puntuación</Termino>
              </dt>
              <dd>
                <ResumenPuntuacion consulta={puntuacion} />
              </dd>
            </div>
          </dl>
        </div>
        <AlertasDelProveedor consulta={alertas} proveedorId={p.id} />
      </CardContent>
    </Card>
  )
}

function FrenteASuCategoria({
  consulta,
}: {
  consulta: UseQueryResult<Puntuacion>
}) {
  // Sin datos o con error, el encabezado ya lo dice: aquí no se repite.
  if (!consulta.isSuccess || consulta.data.componentes.length === 0) return null
  const p = consulta.data
  const grupo = p.categoria ? NOMBRES_CATEGORIA[p.categoria] : "su categoría"
  return (
    <Seccion
      titulo="Frente a su categoría"
      descripcion={
        <>
          Promedio de los últimos 12 meses frente a la mediana de {grupo}. La
          barra es su <Termino clave="percentil">percentil</Termino>: más larga
          es mejor.
        </>
      }
    >
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {COMPONENTES.map((c) => {
          const componente = p.componentes.find((x) => x.kpi === c.clave)
          if (!componente) return null
          return (
            <li key={c.clave} className="space-y-1 rounded-lg border p-3">
              <div className="flex justify-between gap-2 text-sm">
                <span className="font-medium">{c.nombre}</span>
                <span className="text-muted-foreground tabular-nums">
                  Percentil {formatoPuntuacion(componente.percentil)}
                </span>
              </div>
              <div aria-hidden className="h-2 rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-chart-1"
                  style={{ width: `${componente.percentil}%` }}
                />
              </div>
              <p className="text-sm tabular-nums">
                {formatoKpi(formatoDecimal(componente.valor), c.unidad)}{" "}
                <span className="text-muted-foreground">
                  · mediana{" "}
                  {formatoKpi(
                    formatoDecimal(componente.mediana_categoria),
                    c.unidad
                  )}
                </span>
              </p>
            </li>
          )
        })}
      </ul>
    </Seccion>
  )
}

function UltimoMes({ consulta }: { consulta: UseQueryResult<Desempeno[]> }) {
  return (
    <ContenidoConsulta consulta={consulta}>
      {(registros) => {
        const ultimo = registros[0]
        if (!ultimo) {
          return (
            <EstadoVacio
              icono={ChartLine}
              titulo="Sin datos de desempeño"
              descripcion="Aún no se ha importado el desempeño mensual de este proveedor."
            />
          )
        }
        return (
          <Seccion
            titulo={`Desempeño de ${formatoPeriodo(ultimo.periodo)}`}
            descripcion={
              <>
                Último mes registrado del{" "}
                <Termino clave="desempeno">desempeño</Termino> del proveedor,
                incluido el cumplimiento del <Termino clave="sla">SLA</Termino>.
              </>
            }
          >
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {KPIS_DESEMPENO.map((kpi) => (
                <div key={kpi.clave} className="rounded-lg border p-3">
                  <dt className="text-sm text-muted-foreground">
                    {kpi.nombre}
                  </dt>
                  <dd className="text-xl font-semibold">
                    {formatoKpi(ultimo[kpi.clave], kpi.unidad)}
                  </dd>
                </div>
              ))}
            </dl>
          </Seccion>
        )
      }}
    </ContenidoConsulta>
  )
}

export function ProveedorDetalle() {
  const { id = "" } = useParams()
  const token = useToken()
  const [parametros, actualizar] = useParametros()
  const pestana = unoDe(parametros.get("pestana"), PESTANAS) ?? "resumen"
  const idCodificado = encodeURIComponent(id)
  const ruta = `/proveedores/proveedores/${idCodificado}`

  const detalle = useQuery({
    queryKey: ["proveedor", id],
    queryFn: () => pedir<Detalle>(ruta, token),
    enabled: Boolean(token),
  })
  const contratos = useQuery({
    queryKey: ["proveedor", id, "contratos"],
    queryFn: () => pedir<Contrato[]>(`${ruta}/contratos`, token),
    enabled: detalle.isSuccess,
  })
  const desempeno = useQuery({
    queryKey: ["proveedor", id, "desempeno"],
    queryFn: () => pedir<Desempeno[]>(`${ruta}/desempeno?meses=24`, token),
    enabled: detalle.isSuccess,
  })
  const puntuacion = useInteligencia<Puntuacion>(
    `/proveedores/${idCodificado}/puntuacion`,
    { enabled: detalle.isSuccess }
  )
  const mercado = useInteligencia<MercadoLinea[]>(
    `/proveedores/${idCodificado}/mercado`,
    { enabled: detalle.isSuccess }
  )
  const alertas = useInteligencia<PaginaAlertas>(
    `/alertas?proveedor=${idCodificado}&limite=3`,
    { enabled: detalle.isSuccess }
  )

  if (detalle.isPending) return <EstadoCarga filas={3} />
  if (detalle.isError) {
    if (detalle.error instanceof ErrorApi && detalle.error.estado === 404) {
      return (
        <EstadoVacio
          icono={FileQuestion}
          titulo="El proveedor no existe"
          descripcion="Puede que el enlace sea incorrecto o que el proveedor ya no esté en el catálogo."
          accion={
            <Button asChild variant="outline">
              <Link to="/proveedores">Volver a proveedores</Link>
            </Button>
          }
        />
      )
    }
    return (
      <EstadoError
        error={detalle.error}
        alReintentar={() => void detalle.refetch()}
      />
    )
  }

  return (
    <section className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/proveedores">
          <ArrowLeft aria-hidden />
          Proveedores
        </Link>
      </Button>
      <Encabezado
        proveedor={detalle.data}
        puntuacion={puntuacion}
        alertas={alertas}
      />
      <Tabs
        value={pestana}
        onValueChange={(valor) =>
          actualizar({ pestana: valor === "resumen" ? null : valor })
        }
      >
        <TabsList>
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
          <TabsTrigger value="contratos">Contratos</TabsTrigger>
          <TabsTrigger value="desempeno">Desempeño</TabsTrigger>
        </TabsList>
        <TabsContent value="resumen" className="mt-4 space-y-4">
          <FrenteASuCategoria consulta={puntuacion} />
          <UltimoMes consulta={desempeno} />
        </TabsContent>
        <TabsContent value="contratos" className="mt-4">
          <Seccion
            titulo="Contratos"
            descripcion={
              <>
                Cada línea vigente frente al precio del mercado (
                <Termino clave="percentiles">P25 · P50 · P75</Termino>).
              </>
            }
          >
            <div className="space-y-3">
              {mercado.isError && (
                <NoDisponible
                  texto="No se pudo comparar con el mercado."
                  alReintentar={() => void mercado.refetch()}
                />
              )}
              <ContenidoConsulta consulta={contratos}>
                {(datos) => (
                  <TablaContratos contratos={datos} mercado={mercado.data} />
                )}
              </ContenidoConsulta>
            </div>
          </Seccion>
        </TabsContent>
        <TabsContent value="desempeno" className="mt-4">
          <Seccion
            titulo="Desempeño de los últimos 24 meses"
            descripcion={
              <>
                Cómo ha cumplido mes a mes, incluido el{" "}
                <Termino clave="sla">SLA</Termino>.
              </>
            }
          >
            <ContenidoConsulta consulta={desempeno}>
              {(registros) => <DesempenoProveedor registros={registros} />}
            </ContenidoConsulta>
          </Seccion>
        </TabsContent>
      </Tabs>
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver precios de sus servicios",
            descripcion:
              "Compare lo que paga con el precio de referencia del mercado.",
            ruta: "/precios",
            icono: Tags,
          },
          {
            titulo: "Compararlo en el ranking",
            descripcion:
              "Vea cómo se ubica frente a otros proveedores de su categoría.",
            ruta: detalle.data.categorias[0]
              ? `/ranking?categoria=${detalle.data.categorias[0]}`
              : "/ranking",
            icono: Trophy,
          },
        ]}
      />
    </section>
  )
}
