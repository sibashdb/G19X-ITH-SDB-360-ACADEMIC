import { keepPreviousData } from "@tanstack/react-query"
import { Handshake, Plus, TriangleAlert, X } from "lucide-react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Filtro } from "@/componentes/Filtro"
import { Paginacion } from "@/componentes/Paginacion"
import { EtiquetaEstadoEvento } from "@/componentes/negociacion/Etiquetas"
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
import {
  NOMBRES_ESTADO_EVENTO,
  NOMBRES_TIPO,
  useNegociacion,
  type EstadoEvento,
  type PaginaEventos,
  type TipoEvento,
} from "@/negociacion"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"

const POR_PAGINA = 25
const ESTADOS = Object.keys(NOMBRES_ESTADO_EVENTO) as EstadoEvento[]
const TIPOS = Object.keys(NOMBRES_TIPO) as TipoEvento[]

export function Negociaciones() {
  const esComprador = useRoles().includes("comprador")
  const [parametros, actualizar] = useParametros()
  // Los valores de la URL se validan: uno inválido cuenta como "sin filtro" y no llega a la API.
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const tipo = unoDe(parametros.get("tipo"), TIPOS)
  const pagina = enteroPositivo(parametros.get("pagina"), 1, 1000)
  const busqueda = new URLSearchParams({
    pagina: String(pagina),
    tamano: String(POR_PAGINA),
  })
  if (estado) busqueda.set("estado", estado)
  if (tipo) busqueda.set("tipo", tipo)
  const consulta = useNegociacion<PaginaEventos>(`/eventos?${busqueda}`, {
    placeholderData: keepPreviousData,
  })
  const nueva = esComprador ? (
    <Button asChild>
      <Link to="/negociaciones/nueva">
        <Plus aria-hidden />
        Nueva negociación
      </Link>
    </Button>
  ) : undefined

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError) {
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    }
    const { total, elementos } = consulta.data
    if (total > 0 && elementos.length === 0) {
      return (
        <EstadoVacio
          titulo="Esta página ya no existe"
          descripcion="La lista cambió y ya no llega hasta aquí."
          accion={
            <Button
              variant="outline"
              onClick={() => actualizar({ pagina: null })}
            >
              Ir a la primera página
            </Button>
          }
        />
      )
    }
    if (total === 0) {
      return estado || tipo ? (
        <EstadoVacio
          icono={Handshake}
          titulo="Ninguna negociación con estos filtros"
          descripcion="Pruebe con otro estado o con otro tipo."
          accion={
            <Button
              variant="outline"
              onClick={() =>
                actualizar({ estado: null, tipo: null, pagina: null })
              }
            >
              <X aria-hidden />
              Quitar filtros
            </Button>
          }
        />
      ) : (
        <EstadoVacio
          icono={Handshake}
          titulo="Aún no hay negociaciones"
          descripcion={
            esComprador
              ? "Cree la primera con «Nueva negociación»: elija los servicios, invite a los proveedores y fije sus límites."
              : "Aquí aparecerán las negociaciones que cree el equipo de compras."
          }
        />
      )
    }
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Folio</TableHead>
              <TableHead>Título</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Acuerdos</TableHead>
              <TableHead>Fecha límite</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((e) => (
              <TableRow key={e.id}>
                <TableCell>
                  <Link
                    to={`/negociaciones/${encodeURIComponent(e.id)}`}
                    className="font-mono text-accent hover:underline"
                  >
                    {e.folio}
                  </Link>
                </TableCell>
                <TableCell className="min-w-48 whitespace-normal">
                  {e.titulo}
                </TableCell>
                <TableCell>{NOMBRES_TIPO[e.tipo]}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    <EtiquetaEstadoEvento estado={e.estado} />
                    {e.escaladas > 0 && (
                      <Badge variant="warning">
                        <TriangleAlert aria-hidden />
                        {e.escaladas === 1
                          ? "1 escalada"
                          : `${e.escaladas} escaladas`}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {`${e.acuerdos} de ${e.invitados}`}
                </TableCell>
                <TableCell>{formatoFechaHora(e.fecha_limite)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="negociaciones"
          alCambiar={(p) => actualizar({ pagina: p === 1 ? null : String(p) })}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <EncabezadoPagina
        titulo="Negociaciones"
        descripcion="Un agente negocia por usted con cada proveedor, dentro de los límites que usted fije."
        acciones={nueva}
      />
      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-4">
            <div
              role="group"
              aria-label="Estado"
              className="flex flex-wrap gap-2"
            >
              <Filtro
                activo={!estado}
                onClick={() => actualizar({ estado: null, pagina: null })}
              >
                Todas
              </Filtro>
              {ESTADOS.map((e) => (
                <Filtro
                  key={e}
                  activo={estado === e}
                  onClick={() => actualizar({ estado: e, pagina: null })}
                >
                  {NOMBRES_ESTADO_EVENTO[e]}
                </Filtro>
              ))}
            </div>
            <div
              role="group"
              aria-label="Tipo"
              className="flex flex-wrap gap-2"
            >
              <Filtro
                activo={!tipo}
                onClick={() => actualizar({ tipo: null, pagina: null })}
              >
                Todos los tipos
              </Filtro>
              {TIPOS.map((t) => (
                <Filtro
                  key={t}
                  activo={tipo === t}
                  onClick={() => actualizar({ tipo: t, pagina: null })}
                >
                  {NOMBRES_TIPO[t]}
                </Filtro>
              ))}
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
    </div>
  )
}
