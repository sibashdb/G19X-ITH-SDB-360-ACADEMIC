import { keepPreviousData } from "@tanstack/react-query"
import { Hand, Handshake, Plus, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Filtro } from "@/componentes/Filtro"
import { Paginacion } from "@/componentes/Paginacion"
import { Termino } from "@/componentes/Termino"
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
  NOMBRES_FILTRO_ESTADO,
  NOMBRES_TIPO,
  useNegociacion,
  type EstadoEvento,
  type PaginaEventos,
  type TipoEvento,
} from "@/negociacion"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"

const POR_PAGINA = 25
// Basta una fila: solo importa el total de propuestas por aprobar.
const PENDIENTES = "/eventos?estado=pendiente_aprobacion&pagina=1&tamano=1"
const ESTADOS = Object.keys(NOMBRES_ESTADO_EVENTO) as EstadoEvento[]
const TIPOS = Object.keys(NOMBRES_TIPO) as TipoEvento[]

export function Negociaciones() {
  const roles = useRoles()
  const esComprador = roles.includes("comprador")
  const [parametros, actualizar] = useParametros()
  const filtros = useRef<HTMLDivElement>(null)
  // Los valores de la URL se validan: uno inválido cuenta como "sin filtro" y no llega a la API.
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const tipo = unoDe(parametros.get("tipo"), TIPOS)
  const pagina = enteroPositivo(parametros.get("pagina"), 1, 1000)
  // Al entrar, el aprobador va a «Por aprobar» si hay alguna (spec §7.2). Se revisa una sola vez por
  // visita: después se respeta lo que elija, y mientras tanto la lista espera en vez de saltar.
  const [revisando, setRevisando] = useState(
    () => roles.includes("aprobador") && !estado
  )
  const pendientes = useNegociacion<PaginaEventos>(PENDIENTES, {
    enabled: revisando,
  })
  // Si la revisión falló no hay total, y se muestran todas.
  const porAprobar = (pendientes.data?.total ?? 0) > 0
  const respondio = !pendientes.isFetching
  // La revisión termina con un estado en la URL (el de la redirección o uno elegido a mano) o sin
  // nada por aprobar. Se espera a ver el estado en la URL: el enrutador la cambia en una transición
  // y, si la revisión terminara antes, la lista pediría un instante todas las negociaciones.
  if (revisando && (estado || (respondio && !porAprobar))) setRevisando(false)
  useEffect(() => {
    if (revisando && !estado && respondio && porAprobar)
      actualizar(
        { estado: "pendiente_aprobacion", pagina: null },
        { replace: true }
      )
  }, [revisando, estado, respondio, porAprobar, actualizar])
  const busqueda = new URLSearchParams({
    pagina: String(pagina),
    tamano: String(POR_PAGINA),
  })
  if (estado) busqueda.set("estado", estado)
  if (tipo) busqueda.set("tipo", tipo)
  const consulta = useNegociacion<PaginaEventos>(`/eventos?${busqueda}`, {
    placeholderData: keepPreviousData,
    // Sin datos y sin consulta, la lista muestra «Cargando…» hasta que termine la revisión.
    enabled: !revisando,
  })
  const nueva = esComprador ? (
    <Button asChild>
      <Link to="/negociaciones/nueva">
        <Plus aria-hidden />
        Nueva negociación
      </Link>
    </Button>
  ) : undefined

  // El botón usado desaparece con los datos nuevos: el foco pasa a «Todas», que siempre está en pantalla.
  function quitarFiltros() {
    actualizar({ estado: null, tipo: null, pagina: null })
    filtros.current?.querySelector("button")?.focus()
  }
  function irALaPrimera() {
    actualizar({ pagina: null })
    filtros.current?.querySelector("button")?.focus()
  }

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
            <Button variant="outline" onClick={irALaPrimera}>
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
            <Button variant="outline" onClick={quitarFiltros}>
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
                        <Hand aria-hidden />
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
        descripcion={
          <>
            Un agente negocia por usted con cada proveedor, dentro de los{" "}
            <Termino clave="limite">límites</Termino> que usted fije.
          </>
        }
        acciones={nueva}
      />
      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-4">
            <div
              ref={filtros}
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
                  {NOMBRES_FILTRO_ESTADO[e]}
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
