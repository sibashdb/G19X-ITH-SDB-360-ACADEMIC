import { Building2, Tags, Trophy } from "lucide-react"
import { Link } from "react-router"
import { BarraPuntuacion } from "@/componentes/BarraPuntuacion"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoConsulta, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { Tendencia } from "@/componentes/Tendencia"
import { Termino } from "@/componentes/Termino"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  COMPONENTES,
  formatoPuntuacion,
  useInteligencia,
  useUmbralRiesgo,
  type FilaRanking,
} from "@/inteligencia"
import { unoDe, useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA, type Categoria } from "@/tipos"

const TODAS = "todas"
const OPCIONES: [string, string][] = [
  [TODAS, "Todas"],
  ...CATEGORIAS.map((c): [string, string] => [c, NOMBRES_CATEGORIA[c]]),
]

function TablaRanking({ categoria }: { categoria: Categoria | null }) {
  const umbral = useUmbralRiesgo()
  const ranking = useInteligencia<FilaRanking[]>(
    categoria ? `/ranking?categoria=${categoria}` : "/ranking"
  )
  return (
    <ContenidoConsulta consulta={ranking}>
      {(filas) =>
        filas.length === 0 ? (
          <EstadoVacio
            icono={Trophy}
            titulo="Sin puntuaciones todavía"
            descripcion={
              <>
                El ranking ordena a los proveedores activos por su{" "}
                <Termino clave="desempeno">desempeño</Termino>; aparecerá cuando
                se importe el desempeño mensual.
              </>
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-right">
                  <span aria-hidden>#</span>
                  <span className="sr-only">Posición</span>
                </TableHead>
                <TableHead>Proveedor</TableHead>
                <TableHead>Puntuación</TableHead>
                {COMPONENTES.map((c) => (
                  <TableHead key={c.clave} className="text-right">
                    {c.corto}
                  </TableHead>
                ))}
                <TableHead className="text-right">Meses</TableHead>
                <TableHead>Tendencia</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filas.map((f) => (
                <TableRow key={f.proveedor_id}>
                  <TableCell className="text-right tabular-nums">
                    {f.posicion}
                  </TableCell>
                  <TableCell>
                    <Link
                      to={`/proveedores/${encodeURIComponent(f.proveedor_id)}`}
                      className="font-medium text-accent hover:underline"
                    >
                      {f.nombre}
                    </Link>
                    <div className="text-xs text-muted-foreground">
                      {NOMBRES_CATEGORIA[f.categoria] ?? f.categoria}
                    </div>
                  </TableCell>
                  <TableCell>
                    <BarraPuntuacion
                      puntuacion={f.puntuacion}
                      confianza={f.historial_corto ? "baja" : "normal"}
                      umbral={umbral}
                    />
                  </TableCell>
                  {COMPONENTES.map((c) => (
                    <TableCell
                      key={c.clave}
                      className="text-right tabular-nums"
                    >
                      {formatoPuntuacion(f.componentes[c.clave])}
                    </TableCell>
                  ))}
                  <TableCell className="text-right tabular-nums">
                    {f.meses}
                  </TableCell>
                  <TableCell>
                    <Tendencia valor={f.tendencia} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )
      }
    </ContenidoConsulta>
  )
}

export function Ranking() {
  const [parametros, actualizar] = useParametros()
  const activa = unoDe(parametros.get("categoria"), CATEGORIAS) ?? TODAS
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Ranking de proveedores"
        descripcion={
          <>
            Los proveedores mejor calificados de cada categoría según su{" "}
            <Termino clave="puntuacion">puntuación</Termino>.
          </>
        }
      />
      <Tabs
        value={activa}
        onValueChange={(valor) =>
          actualizar({ categoria: valor === TODAS ? null : valor })
        }
      >
        <TabsList className="h-auto flex-wrap">
          {OPCIONES.map(([valor, nombre]) => (
            <TabsTrigger key={valor} value={valor}>
              {nombre}
            </TabsTrigger>
          ))}
        </TabsList>
        {OPCIONES.map(([valor, nombre]) => (
          <TabsContent key={valor} value={valor} className="mt-4">
            <Seccion
              titulo={`Ranking · ${valor === TODAS ? "Todas las categorías" : nombre}`}
              descripcion={
                <>
                  Cada indicador muestra su{" "}
                  <Termino clave="percentil">percentil</Termino> (100 es el
                  mejor). Cada proveedor se compara con los de su categoría
                  principal, o con todos si esa categoría tiene menos de 20. Con{" "}
                  <Termino clave="historialCorto">historial corto</Termino>, la
                  puntuación se acerca al promedio hasta tener 6 meses de datos.
                </>
              }
            >
              <TablaRanking
                categoria={valor === TODAS ? null : (valor as Categoria)}
              />
            </Seccion>
          </TabsContent>
        ))}
      </Tabs>
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver proveedores",
            descripcion: "Revise quién le vende y sus contratos.",
            ruta: "/proveedores",
            icono: Building2,
          },
          {
            titulo: "Revisar precios",
            descripcion: "Compare lo que paga con el mercado.",
            ruta: "/precios",
            icono: Tags,
          },
        ]}
      />
    </section>
  )
}
