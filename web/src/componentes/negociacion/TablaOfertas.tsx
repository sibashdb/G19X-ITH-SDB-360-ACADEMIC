import { CircleCheck, CircleX } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  NOMBRES_AUTOR,
  formatoTermino,
  formatoUtilidad,
  type SesionDetalle,
} from "@/negociacion"
import { formatoMoneda } from "@/tipos"

/** Todas las ofertas de la sesión, con sus valores, lo que valen para el comprador y su validez. */
export function TablaOfertas({ datos }: { datos: SesionDetalle }) {
  if (datos.ofertas.length === 0) {
    return <p className="text-sm text-muted-foreground">Aún no hay ofertas.</p>
  }
  const palancas = datos.palancas.filter((p) => p.clave !== "precio")
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ronda</TableHead>
          <TableHead>De</TableHead>
          {datos.lineas.map((l) => (
            <TableHead key={l.id} className="text-right">
              {l.nombre}
            </TableHead>
          ))}
          {palancas.map((p) => (
            <TableHead key={p.clave} className="text-right">
              {p.nombre}
            </TableHead>
          ))}
          <TableHead className="text-right">Para usted</TableHead>
          <TableHead>¿Dentro de sus límites?</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {datos.ofertas.map((o) => (
          <TableRow key={o.id}>
            <TableCell className="tabular-nums">{o.ronda}</TableCell>
            <TableCell>{NOMBRES_AUTOR[o.autor]}</TableCell>
            {datos.lineas.map((l) => (
              <TableCell key={l.id} className="text-right tabular-nums">
                {o.valores.precios[l.id]
                  ? formatoMoneda(o.valores.precios[l.id], datos.moneda)
                  : "—"}
              </TableCell>
            ))}
            {palancas.map((p) => (
              <TableCell key={p.clave} className="text-right tabular-nums">
                {o.valores.palancas[p.clave]
                  ? formatoTermino(
                      o.valores.palancas[p.clave],
                      p.unidad,
                      datos.moneda
                    )
                  : "—"}
              </TableCell>
            ))}
            <TableCell className="text-right tabular-nums">
              {formatoUtilidad(o.utilidad)}
            </TableCell>
            <TableCell>
              {o.valida ? (
                <span className="inline-flex items-center gap-1 text-success">
                  <CircleCheck aria-hidden className="size-4" />
                  Sí
                </span>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <CircleX aria-hidden className="size-4 text-destructive" />
                  No
                  {o.fuera_de_limites_confirmada && " (lo confirmó Compras)"}
                </span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
