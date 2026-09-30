import { useQuery } from "@tanstack/react-query"
import { Link, useParams } from "react-router"
import { ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  NOMBRES_CATEGORIA,
  NOMBRES_TAMANO,
  formatoFecha,
  formatoMoneda,
  type Contrato,
  type Desempeno,
  type ProveedorDetalle as Detalle,
} from "@/tipos"

export function ProveedorDetalle() {
  const { id = "" } = useParams()
  const token = useToken()
  const ruta = `/proveedores/proveedores/${id}`

  const detalle = useQuery({
    queryKey: ["proveedor", id],
    queryFn: () => pedir<Detalle>(ruta, token),
    enabled: Boolean(token),
  })
  const contratos = useQuery({
    queryKey: ["proveedor", id, "contratos"],
    queryFn: () => pedir<Contrato[]>(`${ruta}/contratos`, token),
    enabled: detalle.isSuccess,
  })
  const desempeno = useQuery({
    queryKey: ["proveedor", id, "desempeno"],
    queryFn: () => pedir<Desempeno[]>(`${ruta}/desempeno?meses=12`, token),
    enabled: detalle.isSuccess,
  })

  if (detalle.isPending) return <p>Cargando…</p>
  if (detalle.isError) {
    const noExiste = detalle.error instanceof ErrorApi && detalle.error.estado === 404
    return (
      <section className="space-y-2">
        <p role="alert">{noExiste ? "El proveedor no existe." : detalle.error.message}</p>
        <Link to="/proveedores" className="underline">
          Volver a proveedores
        </Link>
      </section>
    )
  }

  const p = detalle.data
  return (
    <section className="space-y-6">
      <Link to="/proveedores" className="text-sm underline">
        ← Proveedores
      </Link>
      <Card>
        <CardHeader>
          <CardTitle>{p.nombre}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
          <span>
            RFC: <span className="font-mono">{p.rfc}</span>
          </span>
          <span>Tamaño: {NOMBRES_TAMANO[p.tamano] ?? p.tamano}</span>
          <span>
            Contacto: {p.contacto_nombre} · {p.contacto_email}
          </span>
          <span>Contratos vigentes: {p.contratos_vigentes}</span>
          <span className="space-x-1">
            {p.categorias.map((c) => (
              <Badge key={c} variant="secondary">
                {NOMBRES_CATEGORIA[c]}
              </Badge>
            ))}
          </span>
          <span>{p.activo ? "Activo" : "Inactivo"}</span>
        </CardContent>
      </Card>

      <h2 className="text-xl font-semibold">Contratos</h2>
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
          {contratos.data?.flatMap((c) =>
            c.lineas.map((linea, i) => (
              <TableRow key={`${c.id}-${linea.codigo_servicio}`}>
                <TableCell className="font-mono">{i === 0 ? c.folio : ""}</TableCell>
                <TableCell>{i === 0 ? (c.tipo === "nuevo" ? "Nuevo" : "Renovación") : ""}</TableCell>
                <TableCell>
                  {i === 0 ? `${formatoFecha(c.fecha_inicio)} – ${formatoFecha(c.fecha_fin)}` : ""}
                </TableCell>
                <TableCell>{linea.nombre_servicio}</TableCell>
                <TableCell className="text-right">
                  {Number(linea.cantidad).toLocaleString("es-MX")} {linea.unidad}
                </TableCell>
                <TableCell className="text-right">
                  {formatoMoneda(linea.precio_unitario, c.moneda)}
                </TableCell>
              </TableRow>
            )),
          )}
        </TableBody>
      </Table>

      <h2 className="text-xl font-semibold">Desempeño (últimos 12 meses)</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Periodo</TableHead>
            <TableHead className="text-right">Cumplimiento SLA</TableHead>
            <TableHead className="text-right">Resolución (h)</TableHead>
            <TableHead className="text-right">Incidentes críticos</TableHead>
            <TableHead className="text-right">Entregas a tiempo</TableHead>
            <TableHead className="text-right">Satisfacción (1–5)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {desempeno.data?.map((d) => (
            <TableRow key={d.periodo}>
              <TableCell>{formatoFecha(d.periodo)}</TableCell>
              <TableCell className="text-right">{d.sla_cumplimiento_pct} %</TableCell>
              <TableCell className="text-right">{d.tiempo_resolucion_h}</TableCell>
              <TableCell className="text-right">{d.incidentes_criticos}</TableCell>
              <TableCell className="text-right">{d.entregas_a_tiempo_pct} %</TableCell>
              <TableCell className="text-right">{d.satisfaccion}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  )
}
