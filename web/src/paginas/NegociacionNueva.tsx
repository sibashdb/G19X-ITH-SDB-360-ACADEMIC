import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CircleAlert, Plus, X } from "lucide-react"
import { useId, useRef, useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"
import { enviarJson, ErrorApi, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { Campo } from "@/componentes/negociacion/Campo"
import {
  SelectorProveedores,
  type Invitado,
} from "@/componentes/negociacion/SelectorProveedores"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
import { aEntradaFechaHora, desdeEntradaFechaHora } from "@/fechas"
import { formatoDecimal, porUnidad } from "@/inteligencia"
import {
  ESTILOS,
  esUuid,
  sugerirFechaLimite,
  type Estilo,
  type Evento,
} from "@/negociacion"
import {
  formatoFecha,
  formatoMoneda,
  type Contrato,
  type ProveedorDetalle,
  type Servicio,
} from "@/tipos"

const MAXIMO_LINEAS = 20 // las que acepta la API (spec §5.1)
// Errores que se muestran junto a su campo; cualquier otro va en el aviso de arriba del botón.
const CAMPO_PROPIO =
  /^(titulo|fecha_limite|rondas_max|estilo|plazo_meses|proveedores|lineas\.\d+\.(codigo_servicio|cantidad))$/

type Renovacion = { proveedor: ProveedorDetalle; contrato: Contrato }
type LineaCaptura = { clave: number; codigo: string; cantidad: string }

export function NegociacionNueva() {
  return (
    <RequiereRol rol="comprador">
      <Contenido />
    </RequiereRol>
  )
}

function Contenido() {
  const [parametros] = useSearchParams()
  const proveedor = parametros.get("proveedor")
  const contrato = parametros.get("contrato")
  // Ids inválidos en la URL abren una compra normal: nunca llegan a la API.
  const renovar = esUuid(proveedor) && esUuid(contrato)
  return (
    <div className="space-y-6">
      <EncabezadoPagina
        titulo={renovar ? "Renovar un contrato" : "Nueva negociación"}
        descripcion={
          renovar
            ? "El agente negociará la renovación con el proveedor actual."
            : "Elija qué se compra y a quién invitar; los límites se fijan en el siguiente paso."
        }
      />
      {esUuid(proveedor) && esUuid(contrato) ? (
        <CargarRenovacion proveedorId={proveedor} contratoId={contrato} />
      ) : (
        <Formulario renovacion={null} />
      )}
    </div>
  )
}

function CargarRenovacion({
  proveedorId,
  contratoId,
}: {
  proveedorId: string
  contratoId: string
}) {
  const token = useToken()
  const ruta = `/proveedores/proveedores/${encodeURIComponent(proveedorId)}`
  const detalle = useQuery({
    queryKey: ["proveedor", proveedorId],
    queryFn: () => pedir<ProveedorDetalle>(ruta, token),
    enabled: Boolean(token),
  })
  const contratos = useQuery({
    queryKey: ["proveedor", proveedorId, "contratos"],
    queryFn: () => pedir<Contrato[]>(`${ruta}/contratos`, token),
    enabled: Boolean(token),
  })
  if (detalle.isPending || contratos.isPending) return <EstadoCarga />
  if (detalle.isError) {
    return (
      <EstadoError
        error={detalle.error}
        alReintentar={() => void detalle.refetch()}
      />
    )
  }
  if (contratos.isError) {
    return (
      <EstadoError
        error={contratos.error}
        alReintentar={() => void contratos.refetch()}
      />
    )
  }
  const contrato = contratos.data.find(
    (c) => c.id.toLowerCase() === contratoId.toLowerCase()
  )
  if (!contrato) {
    return (
      <EstadoVacio
        titulo="No se puede renovar este contrato"
        descripcion={`${detalle.data.nombre} no tiene un contrato con ese identificador. Use «Renovar» desde el Tablero, las Alertas o la ficha del proveedor.`}
        accion={
          <Button asChild variant="outline">
            <Link to="/negociaciones/nueva">Crear una compra nueva</Link>
          </Button>
        }
      />
    )
  }
  return <Formulario renovacion={{ proveedor: detalle.data, contrato }} />
}

function ContratoRenovado({ renovacion }: { renovacion: Renovacion }) {
  const { proveedor, contrato } = renovacion
  return (
    <Seccion
      titulo="Contrato que se renueva"
      descripcion="Las líneas, la moneda y el plazo salen del contrato, y el único invitado es el proveedor actual."
    >
      <dl className="mb-4 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Proveedor</dt>
          <dd className="font-medium">{proveedor.nombre}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Contrato</dt>
          <dd className="font-mono">{contrato.folio}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Vigencia</dt>
          <dd>{`${formatoFecha(contrato.fecha_inicio)} – ${formatoFecha(contrato.fecha_fin)}`}</dd>
        </div>
      </dl>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Servicio</TableHead>
            <TableHead className="text-right">Cantidad</TableHead>
            <TableHead className="text-right">Precio vigente</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {contrato.lineas.map((l, i) => (
            // El índice evita claves repetidas: un contrato puede repetir un servicio.
            <TableRow key={`${l.codigo_servicio}-${i}`}>
              <TableCell className="whitespace-normal">
                {l.nombre_servicio}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatoDecimal(Number(l.cantidad), 4)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {`${formatoMoneda(l.precio_unitario, contrato.moneda)} ${porUnidad(l.unidad)}`}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Seccion>
  )
}

function Formulario({ renovacion }: { renovacion: Renovacion | null }) {
  const token = useToken()
  const cliente = useQueryClient()
  const navegar = useNavigate()
  const id = useId()
  const agregar = useRef<HTMLButtonElement>(null)
  const [titulo, setTitulo] = useState(
    renovacion ? `Renovación ${renovacion.contrato.folio}` : ""
  )
  const [fechaLimite, setFechaLimite] = useState(() =>
    aEntradaFechaHora(sugerirFechaLimite())
  )
  const [rondas, setRondas] = useState("6")
  const [estilo, setEstilo] = useState<Estilo>("balanceado")
  const [plazo, setPlazo] = useState("12")
  const [lineas, setLineas] = useState<LineaCaptura[]>([
    { clave: 1, codigo: "", cantidad: "" },
  ])
  const [invitados, setInvitados] = useState<Invitado[]>([])
  // Claves de las filas sin servicio al intentar enviar; se validan aquí, antes de llamar a la API.
  const [sinServicio, setSinServicio] = useState<number[]>([])
  const catalogo = useQuery({
    queryKey: ["servicios", "activos"],
    queryFn: () => pedir<Servicio[]>("/proveedores/servicios", token),
    enabled: Boolean(token) && renovacion === null,
  })
  const crear = useMutation({
    mutationFn: (cuerpo: Record<string, unknown>) =>
      pedir<Evento>("/negociacion/eventos", token, enviarJson("POST", cuerpo)),
    onSuccess: async (evento) => {
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
      navegar(`/negociaciones/${encodeURIComponent(evento.id)}`)
    },
  })
  const errores = erroresPorCampo(crear.error)
  const generales = Object.entries(errores).filter(
    ([campo]) => !CAMPO_PROPIO.test(campo)
  )
  const estiloElegido = ESTILOS.find((e) => e.clave === estilo)

  // Un error de la API apunta a `lineas.N`: al mover las filas ya no apunta a la misma.
  function olvidarErrorDeApi() {
    if (crear.isError) crear.reset()
  }

  function cambiarLinea(clave: number, cambio: Partial<LineaCaptura>) {
    setLineas((previas) =>
      previas.map((l) => (l.clave === clave ? { ...l, ...cambio } : l))
    )
  }

  function agregarLinea() {
    if (lineas.length >= MAXIMO_LINEAS) return
    olvidarErrorDeApi()
    setLineas((previas) => [
      ...previas,
      {
        clave: Math.max(...previas.map((l) => l.clave)) + 1,
        codigo: "",
        cantidad: "",
      },
    ])
  }

  function quitarLinea(clave: number) {
    if (lineas.length === 1) return
    olvidarErrorDeApi()
    setLineas((previas) => previas.filter((l) => l.clave !== clave))
    // El botón «Quitar» desaparece con su fila: el foco pasa a «Agregar servicio».
    agregar.current?.focus()
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    // Una compra espera al catálogo: sin él no hay filas y los errores de línea no tendrían dónde verse.
    if (crear.isPending || (!renovacion && !catalogo.isSuccess)) return
    if (!renovacion) {
      const vacias = lineas.filter((l) => !l.codigo).map((l) => l.clave)
      setSinServicio(vacias)
      if (vacias.length > 0) {
        olvidarErrorDeApi()
        document.getElementById(`${id}-servicio-${vacias[0]}`)?.focus()
        return
      }
    }
    const comun = {
      titulo,
      fecha_limite: desdeEntradaFechaHora(fechaLimite),
      rondas_max: Number(rondas),
      estilo,
    }
    crear.mutate(
      renovacion
        ? {
            ...comun,
            tipo: "renovacion",
            proveedor_id: renovacion.proveedor.id,
            contrato_id: renovacion.contrato.id,
          }
        : {
            ...comun,
            tipo: "compra",
            plazo_meses: Number(plazo),
            // Se envían todas las filas: así el índice `lineas.N` del error es la fila N de la pantalla.
            lineas: lineas.map((l) => ({
              codigo_servicio: l.codigo,
              cantidad: l.cantidad,
            })),
            proveedores: invitados.map((i) => i.id),
          }
    )
  }

  function lineasDeCompra() {
    if (catalogo.isPending) return <EstadoCarga filas={2} />
    if (catalogo.isError) {
      return (
        <EstadoError
          error={catalogo.error}
          alReintentar={() => void catalogo.refetch()}
        />
      )
    }
    return (
      <div className="space-y-4">
        <ol className="space-y-4">
          {lineas.map((linea, i) => {
            const servicio = catalogo.data.find(
              (s) => s.codigo === linea.codigo
            )
            return (
              <li
                key={linea.clave}
                className="grid gap-3 rounded-lg border p-3 sm:grid-cols-[1fr_12rem_auto] sm:items-start"
              >
                <Campo
                  id={`${id}-servicio-${linea.clave}`}
                  etiqueta={`Servicio ${i + 1}`}
                  error={
                    sinServicio.includes(linea.clave)
                      ? "Elija un servicio."
                      : errores[`lineas.${i}.codigo_servicio`]
                  }
                >
                  {(control) => (
                    <Select
                      value={linea.codigo}
                      onValueChange={(codigo) => {
                        cambiarLinea(linea.clave, { codigo })
                        setSinServicio((claves) =>
                          claves.filter((c) => c !== linea.clave)
                        )
                      }}
                    >
                      <SelectTrigger {...control} className="w-full">
                        <SelectValue placeholder="Elija un servicio" />
                      </SelectTrigger>
                      <SelectContent>
                        {catalogo.data.map((s) => (
                          <SelectItem key={s.codigo} value={s.codigo}>
                            {`${s.nombre} (${s.moneda})`}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </Campo>
                <Campo
                  id={`${id}-cantidad-${linea.clave}`}
                  etiqueta={`Cantidad ${i + 1}`}
                  ayuda={
                    servicio
                      ? `Se cotiza ${porUnidad(servicio.unidad)}.`
                      : undefined
                  }
                  error={errores[`lineas.${i}.cantidad`]}
                >
                  {(control) => (
                    <Input
                      {...control}
                      type="number"
                      inputMode="decimal"
                      min="0.0001"
                      step="any"
                      required
                      value={linea.cantidad}
                      onChange={(e) =>
                        cambiarLinea(linea.clave, { cantidad: e.target.value })
                      }
                    />
                  )}
                </Campo>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="sm:mt-6"
                  aria-label={`Quitar el servicio ${i + 1}`}
                  aria-disabled={lineas.length === 1}
                  onClick={() => quitarLinea(linea.clave)}
                >
                  <X aria-hidden />
                </Button>
              </li>
            )
          })}
        </ol>
        <Button
          ref={agregar}
          type="button"
          variant="outline"
          aria-disabled={lineas.length >= MAXIMO_LINEAS}
          onClick={agregarLinea}
        >
          <Plus aria-hidden />
          Agregar servicio
        </Button>
      </div>
    )
  }

  return (
    <form onSubmit={enviar} className="space-y-6">
      <Seccion titulo="Datos generales">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo
            id={`${id}-titulo`}
            etiqueta="Título"
            ayuda="Lo verán los proveedores en su invitación."
            error={errores.titulo}
          >
            {(control) => (
              <Input
                {...control}
                required
                maxLength={120}
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-fecha`}
            etiqueta="Fecha límite"
            ayuda="Al publicar debe quedar entre 1 hora y 60 días en el futuro."
            error={errores.fecha_limite}
          >
            {(control) => (
              <Input
                {...control}
                type="datetime-local"
                required
                value={fechaLimite}
                onChange={(e) => setFechaLimite(e.target.value)}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-rondas`}
            etiqueta="Rondas"
            ayuda={
              <>
                Cuántas ofertas puede hacer cada proveedor (
                <Termino clave="ronda">rondas</Termino>): de 2 a 12.
              </>
            }
            error={errores.rondas_max}
          >
            {(control) => (
              <Input
                {...control}
                type="number"
                inputMode="numeric"
                min={2}
                max={12}
                step={1}
                required
                value={rondas}
                onChange={(e) => setRondas(e.target.value)}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-estilo`}
            etiqueta="Estilo del agente"
            ayuda={estiloElegido?.descripcion}
            error={errores.estilo}
          >
            {(control) => (
              <Select
                value={estilo}
                onValueChange={(v) => setEstilo(v as Estilo)}
              >
                <SelectTrigger {...control} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ESTILOS.map((e) => (
                    <SelectItem key={e.clave} value={e.clave}>
                      {e.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </Campo>
          {!renovacion && (
            <Campo
              id={`${id}-plazo`}
              etiqueta="Plazo del contrato (meses)"
              ayuda="De 1 a 60. Con este plazo se consulta el precio de referencia."
              error={errores.plazo_meses}
            >
              {(control) => (
                <Input
                  {...control}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={60}
                  step={1}
                  required
                  value={plazo}
                  onChange={(e) => setPlazo(e.target.value)}
                />
              )}
            </Campo>
          )}
        </div>
      </Seccion>
      {renovacion ? (
        <ContratoRenovado renovacion={renovacion} />
      ) : (
        <>
          <Seccion
            titulo="Qué se compra"
            descripcion="De 1 a 20 servicios del catálogo, todos en la misma moneda."
          >
            {lineasDeCompra()}
          </Seccion>
          <Seccion
            titulo="Proveedores invitados"
            descripcion="De 1 a 10 proveedores activos; cada uno recibe su propio enlace."
          >
            <SelectorProveedores
              elegidos={invitados}
              alCambiar={setInvitados}
              error={errores.proveedores}
            />
          </Seccion>
        </>
      )}
      {crear.isError && (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>
            {crear.error instanceof ErrorApi
              ? crear.error.titulo
              : "No se pudo crear la negociación"}
          </AlertTitle>
          <AlertDescription>
            <p>{crear.error.message}</p>
            {generales.length > 0 && (
              <ul className="list-disc pl-5">
                {generales.map(([campo, mensaje]) => (
                  <li key={campo}>{mensaje}</li>
                ))}
              </ul>
            )}
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          aria-disabled={
            crear.isPending || (!renovacion && !catalogo.isSuccess)
          }
        >
          Crear borrador
        </Button>
        <Button asChild variant="outline">
          <Link to="/negociaciones">Volver a la lista</Link>
        </Button>
      </div>
    </form>
  )
}
