import { ChartLine } from "lucide-react"
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
} from "recharts"
import { EstadoVacio } from "@/componentes/Estados"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoDecimal, type HistorialPrecios } from "@/inteligencia"
import { formatoFecha, formatoMoneda, formatoPeriodo } from "@/tipos"

const CONFIGURACION = {
  rango: { label: "Rango típico (P25–P75)", color: "var(--chart-1)" },
  p50: { label: "Precio típico (P50)", color: "var(--chart-2)" },
  precio: { label: "Precio de cada contrato", color: "var(--chart-3)" },
} satisfies ChartConfig

/** "2026-09-01" → milisegundos a medianoche local, para un eje de tiempo. */
const tiempo = (iso: string) => new Date(`${iso}T00:00:00`).getTime()

/** Milisegundos → "AAAA-MM-01", lo que espera formatoPeriodo. */
function mesDe(milisegundos: number): string {
  const fecha = new Date(milisegundos)
  return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, "0")}-01`
}

/** Precio de cada contrato sobre la banda P25–P75 de la línea base y su P50, mes a mes. */
export function GraficaHistorial({
  historial,
}: {
  historial: HistorialPrecios
}) {
  if (historial.puntos.length === 0 && historial.bandas.length === 0) {
    return (
      <EstadoVacio
        icono={ChartLine}
        titulo="Sin contratos en los últimos 24 meses"
        descripcion="Cuando haya contratos de este servicio verá aquí sus precios y el rango típico del mercado."
      />
    )
  }
  const bandas = historial.bandas.map((b) => ({
    t: tiempo(b.mes),
    rango: [Number(b.p25), Number(b.p75)],
    p50: Number(b.p50),
  }))
  const puntos = historial.puntos.map((p) => ({
    t: tiempo(p.fecha),
    precio: Number(p.precio),
  }))
  return (
    <div className="space-y-3">
      <figure
        aria-label={`Precios de ${historial.puntos.length} contratos sobre el rango típico del mercado, últimos 24 meses`}
      >
        <ChartContainer
          config={CONFIGURACION}
          className="aspect-auto h-72 w-full"
        >
          <ComposedChart data={bandas} margin={{ left: 8, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(t: number) => formatoPeriodo(mesDe(t))}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={64}
              tickFormatter={(valor: number) => formatoDecimal(valor)}
            />
            <ChartLegend content={<ChartLegendContent />} />
            <Area
              dataKey="rango"
              type="monotone"
              stroke="none"
              fill="var(--color-rango)"
              fillOpacity={0.2}
            />
            <Line
              dataKey="p50"
              type="monotone"
              stroke="var(--color-p50)"
              strokeWidth={2}
              dot={false}
            />
            <Scatter
              data={puntos}
              dataKey="precio"
              fill="var(--color-precio)"
            />
          </ComposedChart>
        </ChartContainer>
      </figure>
      <details className="text-sm">
        <summary className="cursor-pointer font-medium text-accent">
          Ver los precios de cada contrato
        </summary>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Inicio</TableHead>
              <TableHead>Contrato</TableHead>
              <TableHead>Proveedor</TableHead>
              <TableHead className="text-right">Cantidad</TableHead>
              <TableHead className="text-right">Precio</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {historial.puntos.map((p, i) => (
              <TableRow key={`${p.folio}-${i}`}>
                <TableCell>{formatoFecha(p.fecha)}</TableCell>
                <TableCell className="font-mono">{p.folio}</TableCell>
                <TableCell>{p.proveedor}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {Number(p.cantidad).toLocaleString("es-MX")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatoMoneda(p.precio, historial.moneda)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </details>
    </div>
  )
}
