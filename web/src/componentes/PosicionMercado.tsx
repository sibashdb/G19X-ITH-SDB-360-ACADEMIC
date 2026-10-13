import { ArrowDown, Check, TriangleAlert, type LucideIcon } from "lucide-react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import type { MercadoLinea } from "@/inteligencia"
import { cn } from "@/lib/utils"
import { formatoMoneda } from "@/tipos"

const POSICIONES: Record<
  NonNullable<MercadoLinea["posicion"]>,
  { texto: string; icono: LucideIcon; color: string }
> = {
  bajo_p25: { texto: "Bajo P25", icono: ArrowDown, color: "text-success" },
  justo: { texto: "Justo", icono: Check, color: "text-accent" },
  sobre_p75: {
    texto: "Sobre P75",
    icono: TriangleAlert,
    color: "text-destructive",
  },
}

/** Precio de una línea frente al mercado: icono y texto; el detalle se abre con clic o teclado. */
export function PosicionMercado({ linea }: { linea: MercadoLinea }) {
  if (
    linea.posicion === null ||
    linea.p25 === null ||
    linea.p50 === null ||
    linea.p75 === null
  ) {
    return <span className="text-muted-foreground">Sin referencia</span>
  }
  const { texto, icono: Icono, color } = POSICIONES[linea.posicion]
  const filas: [string, string][] = [
    ["Precio pagado", linea.precio],
    ["P25 (bajo)", linea.p25],
    ["P50 (típico)", linea.p50],
    ["P75 (alto)", linea.p75],
  ]
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex items-center gap-1 rounded-sm font-medium underline decoration-dotted underline-offset-4 outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
            color
          )}
        >
          <Icono aria-hidden className="size-4" />
          {texto}
        </button>
      </PopoverTrigger>
      <PopoverContent
        aria-label={`${linea.servicio} frente al mercado`}
        className="w-72 space-y-2 text-sm"
      >
        <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
          {filas.map(([nombre, valor]) => (
            <div key={nombre} className="contents">
              <dt className="text-muted-foreground">{nombre}</dt>
              <dd className="text-right tabular-nums">
                {formatoMoneda(valor, linea.moneda)}
              </dd>
            </div>
          ))}
          {Number(linea.ahorro_potencial) > 0 && (
            <div className="contents">
              <dt className="font-medium">Ahorro potencial</dt>
              <dd className="text-right font-medium tabular-nums">
                {formatoMoneda(linea.ahorro_potencial, linea.moneda)}
              </dd>
            </div>
          )}
        </dl>
        <p className="text-xs text-muted-foreground">
          {linea.metodo === "modelo"
            ? "Calculado con el modelo de precios"
            : "Calculado con la línea base"}
          {linea.confianza === "baja"
            ? "; baja confianza: hay pocos contratos comparables."
            : "."}
        </p>
      </PopoverContent>
    </Popover>
  )
}
