import { FileText } from "lucide-react"
import { EstadoVacio } from "@/componentes/Estados"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFecha, formatoMoneda, type Contrato } from "@/tipos"

export function TablaContratos({ contratos }: { contratos: Contrato[] }) {
  if (contratos.length === 0) {
    return (
      <EstadoVacio
        icono={FileText}
        titulo="Sin contratos registrados"
        descripcion="Este proveedor aún no tiene contratos importados."
      />
    )
  }
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
        </TableRow>
      </TableHeader>
      <TableBody>
        {contratos.flatMap((c) =>
          c.lineas.map((linea, i) => (
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
                {Number(linea.cantidad).toLocaleString("es-MX")} {linea.unidad}
              </TableCell>
              <TableCell className="text-right">
                {formatoMoneda(linea.precio_unitario, c.moneda)}
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
