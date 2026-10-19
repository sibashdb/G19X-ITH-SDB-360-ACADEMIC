import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { CircleAlert, CircleCheck, ExternalLink, Mail } from "lucide-react"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Paginacion } from "@/componentes/Paginacion"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora } from "@/fechas"
import { enteroPositivo, useParametros } from "@/parametros"
import type { PaginaCorreos } from "@/tipos"

const POR_PAGINA = 25
const TIPOS = {
  invitacion: "Invitación",
  restablecimiento: "Restablecimiento",
  negociacion: "Invitación a negociar",
  resultado_negociacion: "Resultado de negociación",
}

export function Correos() {
  return (
    <RequiereRol rol="admin">
      <ContenidoCorreos />
    </RequiereRol>
  )
}

function ContenidoCorreos() {
  const token = useToken()
  const [parametros, actualizar] = useParametros()
  const pagina = enteroPositivo(parametros.get("pagina"), 1, 10_000)
  const consulta = useQuery({
    queryKey: ["correos", pagina],
    queryFn: () =>
      pedir<PaginaCorreos>(
        `/administracion/correos?${new URLSearchParams({ pagina: String(pagina), tamano: String(POR_PAGINA) })}`,
        token
      ),
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError)
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    const { total, elementos } = consulta.data
    if (elementos.length === 0)
      return (
        <EstadoVacio
          icono={Mail}
          titulo="Aún no se han enviado correos"
          descripcion="Las invitaciones, los restablecimientos de contraseña, las invitaciones a negociar y sus resultados aparecerán aquí."
        />
      )
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Destinatario</TableHead>
              <TableHead>Lo pidió</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((c) => (
              <TableRow key={c.id}>
                <TableCell>
                  <time dateTime={c.fecha}>{formatoFechaHora(c.fecha)}</time>
                </TableCell>
                <TableCell>{TIPOS[c.tipo]}</TableCell>
                <TableCell>{c.destinatario}</TableCell>
                <TableCell>{c.solicitado_por}</TableCell>
                <TableCell>
                  {c.estado === "enviado" ? (
                    <Badge variant="success">
                      <CircleCheck aria-hidden />
                      Enviado
                    </Badge>
                  ) : (
                    <Badge variant="destructive" title={c.error ?? undefined}>
                      <CircleAlert aria-hidden />
                      No se envió
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="correos"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  const buzon = consulta.data?.buzon_url
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Correos del sistema"
        descripcion="Invitaciones y correos para restablecer la contraseña que envió la plataforma, y si salieron bien."
        acciones={
          buzon && (
            <Button asChild variant="outline">
              <a href={buzon} target="_blank" rel="noreferrer">
                Abrir buzón de desarrollo
                <ExternalLink aria-hidden />
              </a>
            </Button>
          )
        }
      />
      <Card>
        <CardContent>{contenido()}</CardContent>
      </Card>
    </section>
  )
}
