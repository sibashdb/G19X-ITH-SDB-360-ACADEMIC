import { FileText } from "lucide-react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
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
import { hoyEnMexico } from "@/fechas"
import type { MercadoLinea } from "@/inteligencia"
import { rutaRenovacion } from "@/negociacion"
import { formatoFecha, formatoMoneda, type Contrato } from "@/tipos"

/** Contratos con sus líneas; con `mercado`, cada línea vigente se compara con el mercado. */
export function TablaContratos({
  contratos,
  mercado,
  proveedorId,
}: {
  contratos: Contrato[]
  mercado?: MercadoLinea[]
  /** Con él, el comprador ve «Renovar» en los contratos vigentes. */
  proveedorId?: string
}) {
  const puedeRenovar = useRoles().includes("comprador") && Boolean(proveedorId)
  const hoy = hoyEnMexico()
  // Fechas "AAAA-MM-DD": compararlas como texto respeta el orden del calendario.
  const vigente = (c: Contrato) => c.fecha_inicio <= hoy && hoy <= c.fecha_fin
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
            const delMercado = porLinea.get(`${c.id}:${linea.codigo_servicio}`)
            // La inteligencia guarda una sola línea por (contrato, servicio) y la API permite repetirlo:
            // solo se compara la línea cuyo precio es el del mercado, para no atribuir a una el de otra.
            // Es una comparación para decidir qué mostrar, no una operación con montos.
            const comparada =
              delMercado &&
              Number(delMercado.precio) === Number(linea.precio_unitario)
                ? delMercado
                : undefined
            return (
              // El índice evita claves repetidas: la API permite el mismo servicio en varias líneas.
              <TableRow key={`${c.id}-${i}`}>
                <TableCell className="font-mono">
                  {i === 0 && (
                    <div className="space-y-1">
                      <div>{c.folio}</div>
                      {puedeRenovar && proveedorId && vigente(c) && (
                        <Link
                          to={rutaRenovacion(proveedorId, c.id)}
                          aria-label={`Renovar el contrato ${c.folio}`}
                          className="font-sans text-sm font-medium text-accent hover:underline"
                        >
                          Renovar
                        </Link>
                      )}
                    </div>
                  )}
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
                          Sin comparación con el mercado
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
