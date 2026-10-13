import { FileText } from "lucide-react"
import { EstadoVacio } from "@/componentes/Estados"
import { PosicionMercado } from "@/componentes/PosicionMercado"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { MercadoLinea } from "@/inteligencia"
import { formatoFecha, formatoMoneda, type Contrato } from "@/tipos"

/** Contratos con sus líneas; con `mercado`, cada línea vigente se compara con el mercado. */
export function TablaContratos({
  contratos,
  mercado,
}: {
  contratos: Contrato[]
  mercado?: MercadoLinea[]
}) {
  if (contratos.length === 0) {
    return (
      <EstadoVacio
        icono={FileText}
        titulo="Sin contratos registrados"
        descripcion="Este proveedor aún no tiene contratos importados."
      />
    )
  }
  const porLinea = new Map(
    mercado?.map((m) => [`${m.contrato_id}:${m.codigo_servicio}`, m])
  )
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Folio</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead>Vigencia</TableHead>
          <TableHead>Servicio</TableHead>
          <TableHead className="text-right">Cantidad</TableHead>
          <TableHead className="text-right">Precio unitario</TableHead>
          {mercado && <TableHead>Precio vs. mercado</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {contratos.flatMap((c) =>
          c.lineas.map((linea, i) => {
            const comparada = porLinea.get(`${c.id}:${linea.codigo_servicio}`)
            return (
              // El índice evita claves repetidas: la API permite el mismo servicio en varias líneas.
              <TableRow key={`${c.id}-${i}`}>
                <TableCell className="font-mono">
                  {i === 0 ? c.folio : ""}
                </TableCell>
                <TableCell>
                  {i === 0 ? (c.tipo === "nuevo" ? "Nuevo" : "Renovación") : ""}
                </TableCell>
                <TableCell>
                  {i === 0
                    ? `${formatoFecha(c.fecha_inicio)} – ${formatoFecha(c.fecha_fin)}`
                    : ""}
                </TableCell>
                <TableCell>{linea.nombre_servicio}</TableCell>
                <TableCell className="text-right">
                  {Number(linea.cantidad).toLocaleString("es-MX")}{" "}
                  {linea.unidad}
                </TableCell>
                <TableCell className="text-right">
                  {formatoMoneda(linea.precio_unitario, c.moneda)}
                </TableCell>
                {mercado && (
                  <TableCell>
                    {comparada ? (
                      <PosicionMercado linea={comparada} />
                    ) : (
                      <span className="text-muted-foreground">
                        <span aria-hidden>—</span>
                        <span className="sr-only">
                          Sin comparación: el contrato no está vigente
                        </span>
                      </span>
                    )}
                  </TableCell>
                )}
              </TableRow>
            )
          })
        )}
      </TableBody>
    </Table>
  )
}
