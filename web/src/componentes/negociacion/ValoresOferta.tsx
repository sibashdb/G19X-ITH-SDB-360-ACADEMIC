import { porUnidad } from "@/inteligencia"
import { formatoTermino, type ClavePalanca, type Valores } from "@/negociacion"
import { formatoMoneda } from "@/tipos"

type Linea = { id: string; nombre: string; unidad: string }
type Palanca = { clave: ClavePalanca; nombre: string; unidad: string }

/** Los valores de una oferta: precio unitario por línea y valor por palanca, con su unidad. */
export function ValoresOferta({
  valores,
  lineas,
  palancas,
  moneda,
}: {
  valores: Valores
  lineas: Linea[]
  palancas: Palanca[]
  moneda: string
}) {
  const filas: [string, string][] = [
    ...lineas
      .filter((l) => valores.precios[l.id] !== undefined)
      .map((l): [string, string] => [
        l.nombre,
        `${formatoMoneda(valores.precios[l.id], moneda)} ${porUnidad(l.unidad)}`,
      ]),
    ...palancas
      .filter(
        (p) => p.clave !== "precio" && valores.palancas[p.clave] !== undefined
      )
      .map((p): [string, string] => [
        p.nombre,
        formatoTermino(valores.palancas[p.clave], p.unidad, moneda),
      ]),
  ]
  return (
    <dl className="grid gap-x-4 gap-y-1 rounded-md bg-muted/50 p-2 text-sm sm:grid-cols-[auto_1fr]">
      {filas.map(([nombre, valor], i) => (
        // El índice evita claves repetidas: dos líneas pueden tener el mismo servicio.
        <div key={i} className="contents">
          <dt className="text-muted-foreground">{nombre}</dt>
          <dd className="font-medium tabular-nums">{valor}</dd>
        </div>
      ))}
    </dl>
  )
}
