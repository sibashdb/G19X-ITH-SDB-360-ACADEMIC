import { Termino } from "@/componentes/Termino"
import { cn } from "@/lib/utils"
import type { Banda } from "@/negociacion"
import { formatoMoneda } from "@/tipos"

/**
 * P25, P50 y P75 de la foto guardada en el evento (spec D5), no la referencia de hoy: así el
 * comprador ve lo mismo que se usó al sugerir sus límites. ReferenciaPrecio consulta la de hoy.
 */
export function BandaReferencia({
  banda,
  moneda,
}: {
  banda: Banda | null
  moneda: string
}) {
  if (!banda) {
    return (
      <p className="text-sm text-muted-foreground">
        Sin referencia de precio: no hay contratos comparables recientes. Fije
        el ideal y el límite con su criterio.
      </p>
    )
  }
  const valores: [string, string, string][] = [
    ["P25", "Bajo", banda.p25],
    ["P50", "Típico", banda.p50],
    ["P75", "Alto", banda.p75],
  ]
  return (
    <div className="space-y-1">
      <dl className="grid grid-cols-3 gap-2">
        {valores.map(([clave, nombre, valor]) => (
          <div
            key={clave}
            className={cn(
              "rounded-md border p-2",
              clave === "P50" && "border-accent"
            )}
          >
            <dt className="text-xs text-muted-foreground">
              {nombre} ({clave})
            </dt>
            <dd className="text-sm font-medium tabular-nums">
              {formatoMoneda(valor, moneda)}
            </dd>
          </div>
        ))}
      </dl>
      {banda.confianza === "baja" && (
        <p className="text-xs text-warning">
          <Termino clave="bajaConfianza">Baja confianza</Termino>: hay pocos
          contratos comparables.
        </p>
      )}
    </div>
  )
}
