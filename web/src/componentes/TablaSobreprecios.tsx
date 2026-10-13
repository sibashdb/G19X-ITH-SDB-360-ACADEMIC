import { Link } from "react-router"
import { Termino } from "@/componentes/Termino"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { Sobreprecio } from "@/inteligencia"
import { formatoFecha, formatoMoneda } from "@/tipos"

/** Líneas de contratos vigentes que pagan más que el P75, con su ahorro potencial. */
export function TablaSobreprecios({
  filas,
  conServicio = false,
}: {
  filas: Sobreprecio[]
  conServicio?: boolean
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Contrato</TableHead>
          <TableHead>Proveedor</TableHead>
          {conServicio && <TableHead>Servicio</TableHead>}
          <TableHead className="text-right">Precio pagado</TableHead>
          <TableHead className="text-right">P75 del mercado</TableHead>
          <TableHead className="text-right">
            <Termino clave="ahorroPotencial">Ahorro potencial</Termino>
          </TableHead>
          <TableHead>Vence</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {filas.map((f, i) => (
          // El índice evita claves repetidas: un contrato puede tener el mismo servicio dos veces.
          <TableRow key={`${f.contrato_id}:${f.codigo_servicio}:${i}`}>
            <TableCell className="font-mono">{f.folio}</TableCell>
            <TableCell>
              <Link
                to={`/proveedores/${encodeURIComponent(f.proveedor_id)}?pestana=contratos`}
                className="text-accent hover:underline"
              >
                {f.proveedor}
              </Link>
            </TableCell>
            {conServicio && (
              <TableCell>
                <Link
                  to={`/precios?servicio=${encodeURIComponent(f.codigo_servicio)}`}
                  className="text-accent hover:underline"
                >
                  {f.servicio}
                </Link>
              </TableCell>
            )}
            <TableCell className="text-right tabular-nums">
              {formatoMoneda(f.precio, f.moneda)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatoMoneda(f.p75, f.moneda)}
            </TableCell>
            <TableCell className="text-right font-medium tabular-nums">
              {formatoMoneda(f.ahorro_potencial, f.moneda)}
              {f.moneda !== "MXN" && (
                <div className="text-xs font-normal text-muted-foreground">
                  {formatoMoneda(f.ahorro_potencial_mxn, "MXN")} MXN
                </div>
              )}
            </TableCell>
            <TableCell>{formatoFecha(f.fecha_fin)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
