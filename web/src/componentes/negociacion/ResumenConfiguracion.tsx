import { Seccion } from "@/componentes/Seccion"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora } from "@/fechas"
import {
  ESTILOS,
  NOMBRES_TIPO,
  formatoTermino,
  type Evento,
} from "@/negociacion"
import { formatoMoneda } from "@/tipos"

/** La configuración de una negociación, de solo lectura: publicada, cerrada o vista sin el rol de compras. */
export function ResumenConfiguracion({ evento }: { evento: Evento }) {
  const estilo =
    ESTILOS.find((e) => e.clave === evento.estilo)?.nombre ?? evento.estilo
  const datos: [string, string][] = [
    ["Tipo", NOMBRES_TIPO[evento.tipo]],
    ["Fecha límite", formatoFechaHora(evento.fecha_limite)],
    ["Rondas", String(evento.rondas_max)],
    ["Estilo del agente", estilo],
    [
      "Plazo del contrato",
      `${evento.plazo_meses} ${evento.plazo_meses === 1 ? "mes" : "meses"}`,
    ],
    ["Moneda", evento.moneda],
    ["Creada por", evento.creado_por_nombre],
  ]
  if (evento.publicado_en)
    datos.push(["Publicada", formatoFechaHora(evento.publicado_en)])
  if (evento.motivo_cancelacion)
    datos.push(["Motivo de cancelación", evento.motivo_cancelacion])
  const activas = evento.palancas.filter((p) => p.activa)
  const monto = (valor: string | null) =>
    valor ? formatoMoneda(valor, evento.moneda) : "—"
  const termino = (valor: string | null, unidad: string) =>
    valor ? formatoTermino(valor, unidad, evento.moneda) : "—"

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Seccion titulo="Configuración">
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          {datos.map(([titulo, valor]) => (
            <div key={titulo}>
              <dt className="text-muted-foreground">{titulo}</dt>
              <dd className="font-medium break-words">{valor}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-sm">
          <span className="text-muted-foreground">Invitados: </span>
          {evento.invitados.map((i) => i.nombre).join(", ")}
        </p>
      </Seccion>
      <Seccion
        titulo="Sus límites"
        descripcion="Solo usted los ve; el proveedor nunca los conoce."
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Término</TableHead>
              <TableHead className="text-right">Peso</TableHead>
              <TableHead className="text-right">Ideal</TableHead>
              <TableHead className="text-right">Límite</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {evento.lineas.map((l) => (
              <TableRow key={l.id}>
                <TableCell className="whitespace-normal">{`Precio: ${l.nombre}`}</TableCell>
                <TableCell className="text-right">—</TableCell>
                <TableCell className="text-right tabular-nums">
                  {monto(l.ideal)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {monto(l.limite)}
                </TableCell>
              </TableRow>
            ))}
            {activas.map((p) => (
              <TableRow key={p.clave}>
                <TableCell className="whitespace-normal">{p.nombre}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {p.peso}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {termino(p.ideal, p.unidad)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {termino(p.limite, p.unidad)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Seccion>
    </div>
  )
}
