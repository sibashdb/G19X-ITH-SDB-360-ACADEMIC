import { ChartLine } from "lucide-react"
import { useId, useState } from "react"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"
import { EstadoVacio } from "@/componentes/Estados"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { KPIS_DESEMPENO, formatoKpi, formatoPeriodo, type ClaveKpi, type Desempeno } from "@/tipos"

/** Valor del tooltip con su unidad; usa el decimal original ("99.10") para coincidir con la tabla. */
export function formatearValorTooltip(valor: unknown, texto: unknown, unidad: string): string {
  return formatoKpi(typeof texto === "string" ? texto : String(valor), unidad)
}

/** Gráfica de un indicador por mes y tabla con todos (alternativa accesible a la gráfica). */
export function DesempenoProveedor({ registros }: { registros: Desempeno[] }) {
  const [clave, setClave] = useState<ClaveKpi>("sla_cumplimiento_pct")
  const idEtiqueta = useId()

  if (registros.length === 0) {
    return (
      <EstadoVacio
        icono={ChartLine}
        titulo="Sin datos de desempeño"
        descripcion="Aún no se ha importado el desempeño mensual de este proveedor."
      />
    )
  }

  const kpi = KPIS_DESEMPENO.find((k) => k.clave === clave) ?? KPIS_DESEMPENO[0]
  // La API entrega del mes más reciente al más antiguo; la gráfica va en orden cronológico.
  // `texto` conserva el decimal tal como llega (p. ej. "99.10") para que el tooltip coincida con la tabla.
  const serie = [...registros]
    .reverse()
    .map((r) => ({ periodo: r.periodo, valor: Number(r[clave]), texto: r[clave] }))
  const configuracion = { valor: { label: kpi.nombre, color: "var(--chart-1)" } } satisfies ChartConfig

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span id={idEtiqueta} className="text-sm font-medium">
          Indicador
        </span>
        <Select value={clave} onValueChange={(valor) => setClave(valor as ClaveKpi)}>
          <SelectTrigger aria-labelledby={idEtiqueta} className="w-60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {KPIS_DESEMPENO.map((k) => (
              <SelectItem key={k.clave} value={k.clave}>
                {k.nombre}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <figure aria-label={`${kpi.nombre} de los últimos ${serie.length} meses`}>
        <ChartContainer config={configuracion} className="aspect-auto h-64 w-full">
          <LineChart accessibilityLayer data={serie} margin={{ left: 8, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="periodo"
              tickFormatter={formatoPeriodo}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis tickLine={false} axisLine={false} width={44} domain={["auto", "auto"]} />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(valor) => formatoPeriodo(String(valor))}
                  formatter={(valor, _nombre, item) => (
                    <>
                      <div
                        className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
                        style={{ backgroundColor: item.color }}
                      />
                      <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                        <span className="text-muted-foreground">{kpi.nombre}</span>
                        <span className="font-mono font-medium text-foreground tabular-nums">
                          {formatearValorTooltip(valor, item.payload?.texto, kpi.unidad)}
                        </span>
                      </div>
                    </>
                  )}
                />
              }
            />
            <ChartLegend content={<ChartLegendContent />} />
            <Line dataKey="valor" type="monotone" stroke="var(--color-valor)" strokeWidth={2} dot={false} />
          </LineChart>
        </ChartContainer>
      </figure>
      <Table>
        <TableCaption>Valores mensuales de los indicadores</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Periodo</TableHead>
            {KPIS_DESEMPENO.map((k) => (
              <TableHead key={k.clave} className="text-right">
                {k.nombre}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {registros.map((r) => (
            <TableRow key={r.periodo}>
              <TableCell>{formatoPeriodo(r.periodo)}</TableCell>
              {KPIS_DESEMPENO.map((k) => (
                <TableCell key={k.clave} className="text-right">
                  {formatoKpi(r[k.clave], k.unidad)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
