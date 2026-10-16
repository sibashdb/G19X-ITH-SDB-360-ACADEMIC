import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  CircleAlert,
  CircleCheck,
  RefreshCw,
  Send,
  TriangleAlert,
} from "lucide-react"
import { useId, useState, type FormEvent, type ReactNode } from "react"
import { enviarJson, ErrorApi, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { BandaReferencia } from "@/componentes/negociacion/BandaReferencia"
import { Campo } from "@/componentes/negociacion/Campo"
import { DialogoCancelar } from "@/componentes/negociacion/DialogoCancelar"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
  aEntradaFechaHora,
  desdeEntradaFechaHora,
  formatoFechaHora,
} from "@/fechas"
import { formatoDecimal, porUnidad } from "@/inteligencia"
import { cn } from "@/lib/utils"
import {
  ESTILOS,
  PASOS,
  formatoTermino,
  type ClavePalanca,
  type EnlaceInvitacion,
  type Estilo,
  type Evento,
  type PalancaEvento,
  type Publicacion,
} from "@/negociacion"
import { formatoMoneda } from "@/tipos"

type ValorPalanca = {
  activa: boolean
  peso: string
  ideal: string
  limite: string
}
type Formulario = {
  titulo: string
  fechaLimite: string
  rondas: string
  estilo: Estilo
  plazo: string
  lineas: { ideal: string; limite: string }[]
  palancas: Record<ClavePalanca, ValorPalanca>
}

function desdeEvento(evento: Evento): Formulario {
  return {
    titulo: evento.titulo,
    fechaLimite: aEntradaFechaHora(new Date(evento.fecha_limite)),
    rondas: String(evento.rondas_max),
    estilo: evento.estilo,
    plazo: String(evento.plazo_meses),
    lineas: evento.lineas.map((l) => ({
      ideal: l.ideal ?? "",
      limite: l.limite ?? "",
    })),
    palancas: Object.fromEntries(
      evento.palancas.map((p) => [
        p.clave,
        {
          activa: p.activa,
          peso: p.activa ? String(p.peso) : "",
          ideal: p.ideal ?? "",
          limite: p.limite ?? "",
        },
      ])
    ) as Record<ClavePalanca, ValorPalanca>,
  }
}

/** El cuerpo del PATCH: todo lo editable. Un campo vacío va como null y lo señala la validación. */
function aCambios(evento: Evento, f: Formulario) {
  const nulo = (valor: string) => (valor.trim() === "" ? null : valor.trim())
  return {
    version: evento.version,
    titulo: f.titulo,
    fecha_limite: desdeEntradaFechaHora(f.fechaLimite),
    rondas_max: Number(f.rondas),
    estilo: f.estilo,
    ...(evento.tipo === "compra" ? { plazo_meses: Number(f.plazo) } : {}),
    lineas: evento.lineas.map((l, i) => ({
      codigo_servicio: l.codigo_servicio,
      cantidad: l.cantidad,
      ideal: nulo(f.lineas[i].ideal),
      limite: nulo(f.lineas[i].limite),
    })),
    palancas: evento.palancas
      .filter((p) => f.palancas[p.clave].activa)
      .map((p) => {
        const v = f.palancas[p.clave]
        const peso = Number(v.peso) || 0
        return p.clave === "precio"
          ? { clave: p.clave, peso }
          : {
              clave: p.clave,
              peso,
              ideal: nulo(v.ideal),
              limite: nulo(v.limite),
            }
      }),
  }
}

/**
 * Editor del borrador (spec §10.1). Se monta con `key={evento.version}`: al guardar, la versión
 * nueva lo vuelve a montar con lo que quedó en el servidor (y sus errores y avisos).
 */
export function EditorBorrador({
  evento,
  alAvisar,
  alPublicar,
}: {
  evento: Evento
  alAvisar: (texto: string) => void
  alPublicar: (enlaces: EnlaceInvitacion[]) => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [inicial] = useState(() => desdeEvento(evento))
  const [f, setF] = useState(inicial)
  const sucio = JSON.stringify(f) !== JSON.stringify(inicial)
  const ruta = `/negociacion/eventos/${encodeURIComponent(evento.id)}`
  const renovacion = evento.tipo === "renovacion"

  const guardar = useMutation({
    mutationFn: () =>
      pedir<Evento>(ruta, token, enviarJson("PATCH", aCambios(evento, f))),
    // Se vacía el aviso al empezar: así el siguiente, aunque sea igual, se vuelve a anunciar.
    onMutate: () => alAvisar(""),
    onSuccess: async () => {
      alAvisar("Se guardaron los cambios.")
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
      // La versión nueva vuelve a montar el editor y el botón enfocado desaparece: el foco pasa
      // al contenido y no a <body>. Solo tras guardar, para no mover el foco mientras se edita.
      document.getElementById("contenido")?.focus()
    },
  })
  const publicar = useMutation({
    mutationFn: () =>
      pedir<Publicacion>(`${ruta}/publicar`, token, { method: "POST" }),
    // Los enlaces solo viven en el diálogo: la mutación no los conserva en caché.
    gcTime: 0,
    onMutate: () => alAvisar(""),
    onSuccess: async ({ enlaces }) => {
      alPublicar(enlaces)
      alAvisar(
        enlaces.every((e) => e.correo_estado === "enviado")
          ? "Se publicó la negociación y se enviaron las invitaciones."
          : "Se publicó la negociación; algunas invitaciones no se enviaron: revise los enlaces."
      )
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
  })

  const errores: Record<string, string> = {
    ...Object.fromEntries(evento.errores.map((e) => [e.campo, e.mensaje])),
    ...erroresPorCampo(publicar.error),
    ...erroresPorCampo(guardar.error),
  }
  const avisos = Object.fromEntries(
    evento.avisos.map((a) => [a.campo, a.mensaje])
  )
  const conflicto =
    guardar.error instanceof ErrorApi && guardar.error.estado === 409
  const total = Object.values(f.palancas)
    .filter((p) => p.activa)
    .reduce((suma, p) => suma + (Number(p.peso) || 0), 0)
  const publicable = !sucio && evento.errores.length === 0
  const invitados =
    evento.invitados.length === 1
      ? "1 proveedor"
      : `${evento.invitados.length} proveedores`
  const estadoPublicar = sucio
    ? "Guarde los cambios antes de publicar."
    : evento.errores.length > 0
      ? "Corrija lo marcado para poder publicar."
      : `Se enviará la invitación a ${invitados}.`

  function cambiarLinea(i: number, campo: "ideal" | "limite", valor: string) {
    setF((p) => ({
      ...p,
      lineas: p.lineas.map((l, j) => (j === i ? { ...l, [campo]: valor } : l)),
    }))
  }

  function cambiarPalanca(clave: ClavePalanca, cambio: Partial<ValorPalanca>) {
    setF((p) => ({
      ...p,
      palancas: { ...p.palancas, [clave]: { ...p.palancas[clave], ...cambio } },
    }))
  }

  function activar(p: PalancaEvento, activa: boolean) {
    const actual = f.palancas[p.clave]
    // En renovación, el límite sugerido de una palanca es su valor vigente (spec §5.2).
    const limite =
      activa && !actual.limite && renovacion && p.vigente
        ? p.vigente
        : actual.limite
    cambiarPalanca(p.clave, { activa, limite })
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (sucio && !guardar.isPending) guardar.mutate()
  }

  function numero(
    idCampo: string,
    etiqueta: string,
    valor: string,
    alCambiar: (valor: string) => void,
    paso: string,
    campo: string,
    ayuda?: string
  ) {
    const aviso: ReactNode = avisos[campo] && (
      <span className="inline-flex gap-1 text-warning">
        <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
        {avisos[campo]}
      </span>
    )
    return (
      <Campo
        id={idCampo}
        etiqueta={etiqueta}
        ayuda={aviso || ayuda}
        error={errores[campo]}
      >
        {(control) => (
          <Input
            {...control}
            type="number"
            inputMode="decimal"
            min="0"
            // El tope de Monto en la API: pasado, el 422 nombra el campo por índice y no cae en él.
            max="10000000"
            step={paso}
            value={valor}
            onChange={(e) => alCambiar(e.target.value)}
          />
        )}
      </Campo>
    )
  }

  return (
    <form onSubmit={enviar} className="space-y-6">
      <Seccion titulo="Datos generales">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo id={`${id}-titulo`} etiqueta="Título" error={errores.titulo}>
            {(control) => (
              <Input
                {...control}
                required
                maxLength={120}
                value={f.titulo}
                onChange={(e) => setF({ ...f, titulo: e.target.value })}
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
                value={f.fechaLimite}
                onChange={(e) => setF({ ...f, fechaLimite: e.target.value })}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-rondas`}
            etiqueta="Rondas"
            ayuda="De 2 a 12."
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
                value={f.rondas}
                onChange={(e) => setF({ ...f, rondas: e.target.value })}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-estilo`}
            etiqueta="Estilo del agente"
            ayuda={ESTILOS.find((e) => e.clave === f.estilo)?.descripcion}
            error={errores.estilo}
          >
            {(control) => (
              <Select
                value={f.estilo}
                onValueChange={(v) => setF({ ...f, estilo: v as Estilo })}
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
              ayuda="Al cambiarlo, al guardar se vuelve a consultar el precio de referencia."
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
                  value={f.plazo}
                  onChange={(e) => setF({ ...f, plazo: e.target.value })}
                />
              )}
            </Campo>
          )}
        </div>
      </Seccion>

      <Seccion
        titulo="Precio por línea"
        descripcion={
          <>
            Fije el <Termino clave="ideal">ideal</Termino> y el{" "}
            <Termino clave="limite">límite</Termino> del precio unitario. La
            banda <Termino clave="percentiles" /> es la referencia del mercado
            {evento.referencia_fecha
              ? ` (consultada el ${formatoFechaHora(evento.referencia_fecha)})`
              : ""}
            .
          </>
        }
      >
        <ol className="space-y-4">
          {evento.lineas.map((linea, i) => (
            <li key={linea.id} className="space-y-3 rounded-lg border p-3">
              <div>
                <h3 className="font-medium">{linea.nombre}</h3>
                <p className="text-sm text-muted-foreground">
                  {`Cantidad: ${formatoDecimal(Number(linea.cantidad), 4)} · precio ${porUnidad(linea.unidad)}`}
                  {linea.precio_vigente &&
                    ` · Precio vigente: ${formatoMoneda(linea.precio_vigente, evento.moneda)}`}
                </p>
              </div>
              <BandaReferencia
                banda={linea.referencia}
                moneda={evento.moneda}
              />
              <div className="grid gap-3 sm:grid-cols-2">
                {numero(
                  `${id}-ideal-${i}`,
                  `Ideal (${linea.nombre})`,
                  f.lineas[i].ideal,
                  (v) => cambiarLinea(i, "ideal", v),
                  PASOS.precio,
                  `lineas.${i}.ideal`
                )}
                {numero(
                  `${id}-limite-${i}`,
                  `Límite (${linea.nombre})`,
                  f.lineas[i].limite,
                  (v) => cambiarLinea(i, "limite", v),
                  PASOS.precio,
                  `lineas.${i}.limite`
                )}
              </div>
            </li>
          ))}
        </ol>
      </Seccion>

      <Seccion
        titulo="Qué más se negocia"
        descripcion={
          <>
            Active las <Termino clave="palanca">palancas</Termino> que le
            importen y reparta 100 puntos de peso entre ellas y el precio.
          </>
        }
      >
        <div className="space-y-4">
          <p
            aria-live="polite"
            className={cn(
              "flex items-center gap-2 text-sm font-medium",
              total === 100 ? "text-success" : "text-warning"
            )}
          >
            {total === 100 ? (
              <CircleCheck aria-hidden className="size-4" />
            ) : (
              <TriangleAlert aria-hidden className="size-4" />
            )}
            {`Total: ${total} de 100`}
            {total !== 100 && " · Los pesos deben sumar 100."}
          </p>
          {errores.palancas && (
            <p className="text-sm text-destructive">{errores.palancas}</p>
          )}
          <ul className="space-y-4">
            {evento.palancas.map((p) => {
              const v = f.palancas[p.clave]
              const idCasilla = `${id}-activa-${p.clave}`
              return (
                <li key={p.clave} className="space-y-3 rounded-lg border p-3">
                  {p.clave === "precio" ? (
                    <p className="font-medium">
                      {p.nombre}: siempre se negocia
                    </p>
                  ) : (
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id={idCasilla}
                        checked={v.activa}
                        onCheckedChange={(c) => activar(p, c === true)}
                      />
                      <Label
                        htmlFor={idCasilla}
                      >{`Negociar: ${p.nombre}`}</Label>
                    </div>
                  )}
                  {v.activa && (
                    <div className="grid gap-3 sm:grid-cols-3">
                      <Campo
                        id={`${id}-peso-${p.clave}`}
                        etiqueta={`Peso (${p.nombre})`}
                        error={errores[`palancas.${p.clave}.peso`]}
                      >
                        {(control) => (
                          <Input
                            {...control}
                            type="number"
                            inputMode="numeric"
                            min={1}
                            max={100}
                            step={1}
                            value={v.peso}
                            onChange={(e) =>
                              cambiarPalanca(p.clave, { peso: e.target.value })
                            }
                          />
                        )}
                      </Campo>
                      {p.clave !== "precio" && (
                        <>
                          {numero(
                            `${id}-ideal-${p.clave}`,
                            `Ideal (${p.nombre})`,
                            v.ideal,
                            (x) => cambiarPalanca(p.clave, { ideal: x }),
                            PASOS[p.clave],
                            `palancas.${p.clave}.ideal`,
                            `En ${p.unidad}.`
                          )}
                          {numero(
                            `${id}-limite-${p.clave}`,
                            `Límite (${p.nombre})`,
                            v.limite,
                            (x) => cambiarPalanca(p.clave, { limite: x }),
                            PASOS[p.clave],
                            `palancas.${p.clave}.limite`,
                            p.vigente
                              ? `Hoy: ${formatoTermino(p.vigente, p.unidad, evento.moneda)}.`
                              : `En ${p.unidad}.`
                          )}
                        </>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      </Seccion>

      <Seccion
        titulo={renovacion ? "Proveedor" : "Proveedores invitados"}
        descripcion="Para cambiar los servicios o los proveedores, cancele este borrador y cree otro."
      >
        {errores.proveedores && (
          <p className="text-sm text-destructive">{errores.proveedores}</p>
        )}
        <ul className="list-disc pl-5 text-sm">
          {evento.invitados.map((i) => (
            <li key={i.id}>{i.nombre}</li>
          ))}
        </ul>
      </Seccion>

      {conflicto ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>No se guardaron sus cambios</AlertTitle>
          <AlertDescription>
            <p>{guardar.error?.message}</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() =>
                void cliente.invalidateQueries({ queryKey: ["negociacion"] })
              }
            >
              <RefreshCw aria-hidden />
              Recargar
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        (guardar.isError || publicar.isError) && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertTitle>No se pudo completar</AlertTitle>
            <AlertDescription>
              {(guardar.error ?? publicar.error)?.message}
            </AlertDescription>
          </Alert>
        )
      )}

      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <Button type="submit" aria-disabled={!sucio || guardar.isPending}>
            Guardar cambios
          </Button>
          {publicable ? (
            <ConfirmarAccion
              titulo="¿Publicar la negociación?"
              descripcion="Se crea una sesión por proveedor y se le envía su invitación por correo. Después ya no podrá cambiar los límites."
              textoConfirmar="Publicar"
              alConfirmar={() => {
                if (!publicar.isPending) publicar.mutate()
              }}
            >
              <Button type="button" aria-describedby={`${id}-publicar`}>
                <Send aria-hidden />
                Publicar
              </Button>
            </ConfirmarAccion>
          ) : (
            <Button
              type="button"
              aria-disabled
              aria-describedby={`${id}-publicar`}
            >
              <Send aria-hidden />
              Publicar
            </Button>
          )}
          <DialogoCancelar
            ruta={ruta}
            borrador
            alCancelar={() => alAvisar("Se canceló el borrador.")}
          />
        </div>
        <p id={`${id}-publicar`} className="text-sm text-muted-foreground">
          {estadoPublicar}
        </p>
      </div>
    </form>
  )
}
