import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { CircleCheck, CircleX, Download, History, X } from "lucide-react"
import { useId, useRef, useState } from "react"
import { descargar, pedir } from "@/api"
import { describirActividad } from "@/actividad"
import { useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Filtro } from "@/componentes/Filtro"
import { Paginacion } from "@/componentes/Paginacion"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora } from "@/fechas"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import type { PaginaActividad, PaginaUsuarios } from "@/tipos"
import { nombreCompleto } from "@/usuarios"

const POR_PAGINA = 25
const MAX_EXPORTACION = 10_000
// Radix Select no admite el valor vacío: "todas" representa "sin filtro".
const TODAS = "todas"
const GRUPOS = [
  ["sesiones", "Sesiones"],
  ["usuarios", "Usuarios"],
  ["importaciones", "Importaciones"],
  ["catalogo", "Catálogo"],
  ["inteligencia", "Inteligencia"],
  ["negociacion", "Negociación"],
] as const
const CLAVES_GRUPO = GRUPOS.map(([clave]) => clave)
const FECHA_MINIMA = "2000-01-01"
const FECHA_MAXIMA = "2100-12-31"

/** AAAA-MM-DD dentro del rango que acepta la API; otro valor cuenta como "sin filtro". */
function fecha(valor: string | null): string | null {
  return valor &&
    /^\d{4}-\d{2}-\d{2}$/.test(valor) &&
    valor >= FECHA_MINIMA &&
    valor <= FECHA_MAXIMA
    ? valor
    : null
}

/**
 * Texto que muestra un campo de fecha: lo que la persona escribió (aunque aún sea una fecha a
 * medias, como el "0002" de empezar a teclear el año) y, si la fecha de la URL cambia por fuera,
 * el valor nuevo.
 */
function useTextoFecha(deLaUrl: string | null) {
  const valor = deLaUrl ?? ""
  const [texto, setTexto] = useState(valor)
  const [previo, setPrevio] = useState(valor)
  if (valor !== previo) {
    setPrevio(valor)
    setTexto(valor)
  }
  return [texto, setTexto] as const
}

export function Actividad() {
  return (
    <RequiereRol rol="admin">
      <ContenidoActividad />
    </RequiereRol>
  )
}

function ContenidoActividad() {
  const token = useToken()
  const id = useId()
  const [parametros, actualizar] = useParametros()
  const persona = parametros.get("persona")?.slice(0, 64) || null
  const tipo = unoDe(parametros.get("tipo"), CLAVES_GRUPO)
  const desde = fecha(parametros.get("desde"))
  const hasta = fecha(parametros.get("hasta"))
  const pagina = enteroPositivo(parametros.get("pagina"), 1, 10_000)
  const [textoDesde, setTextoDesde] = useTextoFecha(desde)
  const [textoHasta, setTextoHasta] = useTextoFecha(hasta)
  const rangoInvalido = Boolean(desde && hasta && hasta < desde)
  const hayFiltros = Boolean(persona || tipo || desde || hasta)
  const [exportando, setExportando] = useState(false)
  const [errorExportacion, setErrorExportacion] = useState<string | null>(null)
  // "Limpiar filtros" se desmonta al usarse: el foco pasa al primer filtro, que sigue en pantalla.
  const selectorPersona = useRef<HTMLButtonElement>(null)

  const filtros = new URLSearchParams()
  if (persona) filtros.set("persona", persona)
  if (tipo) filtros.set("tipo", tipo)
  if (desde) filtros.set("desde", desde)
  if (hasta) filtros.set("hasta", hasta)

  // ponytail: la lista del filtro trae hasta 100 personas; con más, cambiar a búsqueda por texto.
  const personas = useQuery({
    queryKey: ["usuarios", "filtro-actividad"],
    queryFn: () =>
      pedir<PaginaUsuarios>("/administracion/usuarios?tamano=100", token),
    enabled: Boolean(token),
  })
  const consulta = useQuery({
    queryKey: ["actividad", "lista", { persona, tipo, desde, hasta, pagina }],
    queryFn: () => {
      const busqueda = new URLSearchParams(filtros)
      busqueda.set("pagina", String(pagina))
      busqueda.set("tamano", String(POR_PAGINA))
      return pedir<PaginaActividad>(
        `/administracion/actividad?${busqueda}`,
        token
      )
    },
    enabled: Boolean(token) && !rangoInvalido,
    placeholderData: keepPreviousData,
  })

  async function exportar() {
    if (exportando || rangoInvalido) return
    setExportando(true)
    setErrorExportacion(null)
    try {
      await descargar(
        `/administracion/actividad/exportar?${filtros}`,
        token,
        "actividad.csv"
      )
    } catch (error) {
      setErrorExportacion(
        error instanceof Error ? error.message : "No se pudo exportar."
      )
    } finally {
      setExportando(false)
    }
  }

  // La URL solo cambia con una fecha completa y dentro del rango (o al vaciar el campo).
  function cambiarFecha(
    clave: "desde" | "hasta",
    texto: string,
    guardarTexto: (texto: string) => void
  ) {
    guardarTexto(texto)
    if (texto === "" || fecha(texto))
      actualizar({ [clave]: texto || null, pagina: null })
  }

  function limpiar() {
    setTextoDesde("")
    setTextoHasta("")
    actualizar({
      persona: null,
      tipo: null,
      desde: null,
      hasta: null,
      pagina: null,
    })
    selectorPersona.current?.focus()
  }
  const opcionesPersona = personas.data?.elementos ?? []
  const personaConocida = opcionesPersona.some((u) => u.id === persona)

  function contenido() {
    if (rangoInvalido) return null
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
      return hayFiltros ? (
        <EstadoVacio
          titulo="Sin resultados"
          descripcion="Ningún registro coincide con los filtros."
        />
      ) : (
        <EstadoVacio
          icono={History}
          titulo="Aún no hay actividad registrada"
          descripcion="Aquí aparecerán los inicios de sesión, las acciones sobre usuarios, las importaciones, los cambios del catálogo y los de la puntuación y el modelo de precios."
        />
      )
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Persona</TableHead>
              <TableHead>Acción</TableHead>
              <TableHead>Resultado</TableHead>
              <TableHead>IP</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((a) => (
              <TableRow key={a.id}>
                <TableCell>
                  <time dateTime={a.fecha}>{formatoFechaHora(a.fecha)}</time>
                </TableCell>
                <TableCell>{a.actor_nombre}</TableCell>
                <TableCell className="whitespace-normal">
                  {describirActividad(a)}
                </TableCell>
                <TableCell>
                  {a.resultado === "exito" ? (
                    <Badge variant="success">
                      <CircleCheck aria-hidden />
                      Éxito
                    </Badge>
                  ) : (
                    <Badge variant="destructive">
                      <CircleX aria-hidden />
                      Falló
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {a.ip ?? (
                    <>
                      <span aria-hidden>—</span>
                      <span className="sr-only">Sin IP</span>
                    </>
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
          nombre="registros"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Actividad"
        descripcion="Quién hizo qué y cuándo: inicios de sesión, cambios de usuarios, importaciones, catálogo y puntuación. Nada de esto se puede borrar."
        acciones={
          <Button
            variant="outline"
            aria-disabled={exportando || rangoInvalido}
            onClick={() => void exportar()}
          >
            <Download aria-hidden />
            {exportando ? "Exportando…" : "Exportar CSV"}
          </Button>
        }
      />
      {consulta.data && consulta.data.total > MAX_EXPORTACION && (
        <p className="text-sm text-muted-foreground">
          Se exportarán los 10,000 registros más recientes; acote las fechas
          para obtener el resto.
        </p>
      )}
      {errorExportacion && (
        <p role="alert" className="text-sm text-destructive">
          {errorExportacion}
        </p>
      )}
      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="grid gap-1.5">
              <span id={`${id}-persona`} className="text-sm font-medium">
                Persona
              </span>
              <Select
                value={persona ?? TODAS}
                onValueChange={(v) =>
                  actualizar({ persona: v === TODAS ? null : v, pagina: null })
                }
              >
                <SelectTrigger
                  ref={selectorPersona}
                  aria-labelledby={`${id}-persona`}
                  className="w-64"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={TODAS}>Todas las personas</SelectItem>
                  {persona && !personaConocida && (
                    <SelectItem value={persona}>{persona}</SelectItem>
                  )}
                  {opcionesPersona.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {nombreCompleto(u)} ({u.usuario})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}-desde`}>Desde</Label>
              <Input
                id={`${id}-desde`}
                type="date"
                min={FECHA_MINIMA}
                max={FECHA_MAXIMA}
                value={textoDesde}
                onChange={(e) =>
                  cambiarFecha("desde", e.target.value, setTextoDesde)
                }
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}-hasta`}>Hasta</Label>
              <Input
                id={`${id}-hasta`}
                type="date"
                min={FECHA_MINIMA}
                max={FECHA_MAXIMA}
                value={textoHasta}
                aria-invalid={rangoInvalido || undefined}
                aria-describedby={rangoInvalido ? `${id}-rango` : undefined}
                onChange={(e) =>
                  cambiarFecha("hasta", e.target.value, setTextoHasta)
                }
              />
            </div>
            {hayFiltros && (
              <Button type="button" variant="ghost" onClick={limpiar}>
                <X aria-hidden />
                Limpiar filtros
              </Button>
            )}
          </div>
          {rangoInvalido && (
            <p
              id={`${id}-rango`}
              role="alert"
              className="text-sm text-destructive"
            >
              La fecha final debe ser igual o posterior a la inicial.
            </p>
          )}
          <div
            role="group"
            aria-label="Filtrar por tipo"
            className="flex flex-wrap gap-2"
          >
            <Filtro
              activo={!tipo}
              onClick={() => actualizar({ tipo: null, pagina: null })}
            >
              Todos
            </Filtro>
            {GRUPOS.map(([clave, nombre]) => (
              <Filtro
                key={clave}
                activo={tipo === clave}
                onClick={() => actualizar({ tipo: clave, pagina: null })}
              >
                {nombre}
              </Filtro>
            ))}
          </div>
          {contenido()}
        </CardContent>
      </Card>
    </section>
  )
}
