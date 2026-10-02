import { useQuery, type UseQueryResult } from "@tanstack/react-query"
import { ArrowLeft, ChartLine, FileQuestion } from "lucide-react"
import { Link, useParams } from "react-router"
import { ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { DesempenoProveedor } from "@/componentes/DesempenoProveedor"
import { ContenidoConsulta, EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Seccion } from "@/componentes/Seccion"
import { TablaContratos } from "@/componentes/TablaContratos"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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

function Encabezado({ proveedor: p }: { proveedor: Detalle }) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-start justify-between gap-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">{p.nombre}</h1>
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
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Contacto</dt>
            <dd>{p.contacto_nombre}</dd>
            <dd>
              <a href={`mailto:${p.contacto_email}`} className="text-accent hover:underline">
                {p.contacto_email}
              </a>
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Contratos vigentes</dt>
            <dd className="text-2xl font-semibold">{p.contratos_vigentes}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}

function Resumen({ consulta }: { consulta: UseQueryResult<Desempeno[]> }) {
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
          <Seccion titulo={`Desempeño de ${formatoPeriodo(ultimo.periodo)}`} descripcion="Último mes registrado.">
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {KPIS_DESEMPENO.map((kpi) => (
                <div key={kpi.clave} className="rounded-lg border p-3">
                  <dt className="text-sm text-muted-foreground">{kpi.nombre}</dt>
                  <dd className="text-xl font-semibold">{formatoKpi(ultimo[kpi.clave], kpi.unidad)}</dd>
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
  const ruta = `/proveedores/proveedores/${encodeURIComponent(id)}`

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
    return <EstadoError error={detalle.error} alReintentar={() => void detalle.refetch()} />
  }

  return (
    <section className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/proveedores">
          <ArrowLeft aria-hidden />
          Proveedores
        </Link>
      </Button>
      <Encabezado proveedor={detalle.data} />
      <Tabs
        value={pestana}
        onValueChange={(valor) => actualizar({ pestana: valor === "resumen" ? null : valor })}
      >
        <TabsList>
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
          <TabsTrigger value="contratos">Contratos</TabsTrigger>
          <TabsTrigger value="desempeno">Desempeño</TabsTrigger>
        </TabsList>
        <TabsContent value="resumen" className="mt-4">
          <Resumen consulta={desempeno} />
        </TabsContent>
        <TabsContent value="contratos" className="mt-4">
          <Seccion titulo="Contratos">
            <ContenidoConsulta consulta={contratos}>
              {(datos) => <TablaContratos contratos={datos} />}
            </ContenidoConsulta>
          </Seccion>
        </TabsContent>
        <TabsContent value="desempeno" className="mt-4">
          <Seccion titulo="Desempeño de los últimos 24 meses">
            <ContenidoConsulta consulta={desempeno}>
              {(registros) => <DesempenoProveedor registros={registros} />}
            </ContenidoConsulta>
          </Seccion>
        </TabsContent>
      </Tabs>
    </section>
  )
}
