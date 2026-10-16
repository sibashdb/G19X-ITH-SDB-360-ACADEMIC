import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CircleOff, Handshake, Link2Off, Send, UserRound } from "lucide-react"
import { useEffect, useId, useRef, useState, type FormEvent } from "react"
import { ErrorApi, erroresPorCampo } from "@/api"
import { SelectorTema } from "@/componentes/BarraSuperior"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Campo } from "@/componentes/negociacion/Campo"
import {
  CamposValores,
  valoresCapturados,
  valoresVacios,
} from "@/componentes/negociacion/CamposValores"
import { ValoresOferta } from "@/componentes/negociacion/ValoresOferta"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { formatoFechaHora } from "@/fechas"
import { formatoDecimal, porUnidad } from "@/inteligencia"
import { cn } from "@/lib/utils"
import {
  crearClaves,
  esFinal,
  type Autor,
  type Valores,
  type VistaPortal,
} from "@/negociacion"
import { pedirPortal, tomarToken } from "@/portal"

const CLAVE = ["portal"]

/** Cómo se llama a cada autor en la conversación que ve el proveedor. */
const AUTORES: Record<Autor, string> = {
  proveedor: "Usted",
  agente: "Agente de compras",
  comprador: "Equipo de compras",
  sistema: "Aviso",
}

/** El portal del proveedor (spec §10.2): fuera del Layout, sin inicio de sesión. */
export function Portal() {
  const cliente = useQueryClient()
  // `version` cambia con cada enlace nuevo: la sesión se monta de cero y no arrastra la del anterior.
  const [enlace, setEnlace] = useState(() => ({
    token: tomarToken(),
    version: 0,
  }))
  useEffect(() => {
    document.title = "Portal de proveedores · PluriOne"
  }, [])
  // Pegar en la misma pestaña el enlace reenviado cambia solo el fragmento: no recarga la página.
  useEffect(() => {
    function alCambiarFragmento() {
      const nuevo = tomarToken()
      if (!nuevo || nuevo === enlace.token) return
      cliente.removeQueries({ queryKey: CLAVE })
      setEnlace((anterior) => ({ token: nuevo, version: anterior.version + 1 }))
    }
    window.addEventListener("hashchange", alCambiarFragmento)
    return () => window.removeEventListener("hashchange", alCambiarFragmento)
  }, [cliente, enlace.token])
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-2 px-4 py-2">
          <p className="font-semibold">PluriOne · Portal de proveedores</p>
          <SelectorTema />
        </div>
      </header>
      <main
        id="contenido"
        tabIndex={-1}
        className="mx-auto max-w-3xl space-y-6 px-4 py-6 outline-hidden"
      >
        {enlace.token ? (
          <SesionPortal key={enlace.version} token={enlace.token} />
        ) : (
          <EnlaceInvalido />
        )}
      </main>
    </div>
  )
}

function EnlaceInvalido() {
  return (
    <>
      {/* Sin sesión no hay título de la negociación: la página conserva su encabezado principal. */}
      <h1 className="sr-only">Portal de proveedores</h1>
      <EstadoVacio
        icono={Link2Off}
        titulo="El enlace no es válido o ya venció"
        descripcion="Pida al equipo de compras que le reenvíe la invitación. Cada enlace es personal y deja de servir al llegar la fecha límite, al reenviarse o si se cancela la negociación."
      />
    </>
  )
}

/** El mismo 401 para un enlace falso, revocado o vencido; también si vence con la página abierta. */
function enlaceRechazado(error: unknown): boolean {
  return error instanceof ErrorApi && error.estado === 401
}

function SesionPortal({ token }: { token: string }) {
  const consulta = useQuery({
    queryKey: CLAVE,
    queryFn: () => pedirPortal<VistaPortal>("/sesion", token),
    // Un enlace rechazado (401) no se reenvía: no se reintenta ni se sigue consultando con él.
    retry: (fallos, error) => fallos < 1 && !enlaceRechazado(error),
    // Mientras atiende una persona, su respuesta llega sin que el proveedor envíe nada.
    refetchInterval: (q) => {
      const vista = q.state.data
      if (enlaceRechazado(q.state.error)) return false
      return vista && vista.atendido_por === "persona" && !esFinal(vista.estado)
        ? 3000
        : false
    },
  })
  if (consulta.isPending) return <EstadoCarga />
  if (enlaceRechazado(consulta.error)) return <EnlaceInvalido />
  if (consulta.isLoadingError) {
    return (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  }
  const vista = consulta.data
  // Esta región siempre está montada, así que anuncia el desenlace aunque el formulario (con su
  // «Se envió su oferta.») desaparezca. El desenlace va oculto: la alerta visible dice lo mismo.
  const aviso = consulta.isRefetchError
    ? "No se pudo actualizar; se volverá a intentar en unos segundos."
    : vista.estado === "acuerdo_tentativo"
      ? "La negociación terminó con un acuerdo tentativo."
      : vista.estado === "sin_acuerdo" || vista.estado === "expirada"
        ? "La negociación terminó sin acuerdo."
        : ""
  return (
    <>
      <p
        role="status"
        className={consulta.isRefetchError ? "text-sm text-warning" : "sr-only"}
      >
        {aviso}
      </p>
      <Resumen vista={vista} />
      <Seccion titulo="Conversación">
        <ConversacionPortal vista={vista} />
      </Seccion>
      {!esFinal(vista.estado) && <Ofertar token={token} vista={vista} />}
    </>
  )
}

function Resumen({ vista }: { vista: VistaPortal }) {
  const restantes =
    vista.rondas_restantes === 1
      ? "Le queda 1 ronda"
      : `Le quedan ${vista.rondas_restantes} rondas`
  return (
    <div className="space-y-4">
      <EncabezadoPagina
        titulo={vista.titulo}
        descripcion={`${vista.folio} · Fecha límite: ${formatoFechaHora(vista.fecha_limite)}${esFinal(vista.estado) ? "" : ` · ${restantes}`}`}
      />
      {vista.estado === "acuerdo_tentativo" && (
        <Alert role="status">
          <Handshake aria-hidden />
          <AlertTitle>Acuerdo tentativo</AlertTitle>
          <AlertDescription>
            Su oferta quedó como acuerdo tentativo. No es vinculante hasta que
            se adjudique y se apruebe; el equipo de compras se pondrá en
            contacto con usted.
          </AlertDescription>
        </Alert>
      )}
      {(vista.estado === "sin_acuerdo" || vista.estado === "expirada") && (
        <Alert role="status">
          <CircleOff aria-hidden />
          <AlertTitle>La negociación terminó sin acuerdo</AlertTitle>
          <AlertDescription>
            Gracias por participar. Si tiene dudas, comuníquese con el equipo de
            compras.
          </AlertDescription>
        </Alert>
      )}
      {vista.atendido_por === "persona" && !esFinal(vista.estado) && (
        <Alert role="status">
          <UserRound aria-hidden />
          <AlertTitle>Le atiende una persona</AlertTitle>
          <AlertDescription>
            Una persona del equipo de compras revisará su oferta y le responderá
            aquí. Esta página se actualiza sola.
          </AlertDescription>
        </Alert>
      )}
      <Seccion titulo="Qué se negocia">
        <ul className="space-y-1 text-sm">
          {vista.lineas.map((l) => (
            <li key={l.id}>
              <span className="font-medium">{l.nombre}</span>
              {`: cantidad ${formatoDecimal(Number(l.cantidad), 4)}, precio ${porUnidad(l.unidad)} en ${vista.moneda}`}
            </li>
          ))}
          {vista.palancas.map((p) => (
            <li key={p.clave}>
              <span className="font-medium">{p.nombre}</span>
              {` (en ${p.unidad})`}
            </li>
          ))}
        </ul>
      </Seccion>
    </div>
  )
}

function ConversacionPortal({ vista }: { vista: VistaPortal }) {
  if (vista.mensajes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aún no hay mensajes: envíe su primera oferta con el formulario de abajo.
      </p>
    )
  }
  return (
    <ol className="space-y-3">
      {vista.mensajes.map((m, i) => (
        // La conversación solo crece: el índice es una clave estable.
        <li
          key={i}
          className={cn(
            "space-y-2 rounded-lg border p-3",
            m.autor === "proveedor" && "bg-muted/40"
          )}
        >
          <p className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">
              {AUTORES[m.autor]}
            </span>
            <span>{formatoFechaHora(m.fecha)}</span>
          </p>
          {m.texto && (
            <p className="text-sm break-words whitespace-pre-wrap">{m.texto}</p>
          )}
          {m.oferta && (
            <ValoresOferta
              valores={m.oferta}
              lineas={vista.lineas}
              palancas={vista.palancas}
              moneda={vista.moneda}
            />
          )}
        </li>
      ))}
    </ol>
  )
}

type Oferta = { valores: Valores; nota: string; confirmar_valores: boolean }

function Ofertar({ token, vista }: { token: string; vista: VistaPortal }) {
  const cliente = useQueryClient()
  const id = useId()
  const enviarBoton = useRef<HTMLButtonElement>(null)
  const [claves] = useState(crearClaves)
  const [clavesEscalar] = useState(crearClaves)
  const [valores, setValores] = useState<Valores>(() =>
    valoresVacios(vista.lineas, vista.palancas)
  )
  const [nota, setNota] = useState("")
  const [confirmo, setConfirmo] = useState(false)
  const [aviso, setAviso] = useState("")

  // Al pasar a «le atiende una persona» desaparece «Hablar con una persona»: si el foco se perdió
  // con él, va a «Enviar oferta». Si la persona está escribiendo en otro campo, no se le quita.
  const atendidoPor = vista.atendido_por
  const anterior = useRef(atendidoPor)
  useEffect(() => {
    if (anterior.current !== atendidoPor && atendidoPor === "persona") {
      const activo = document.activeElement
      if (!activo || activo === document.body) enviarBoton.current?.focus()
    }
    anterior.current = atendidoPor
  }, [atendidoPor])

  // Si el enlace venció o la negociación terminó, la vista nueva lo explica.
  function alFallar(error: Error) {
    setAviso("")
    if (
      error instanceof ErrorApi &&
      (error.estado === 401 || error.estado === 409)
    )
      void cliente.invalidateQueries({ queryKey: CLAVE })
  }

  const ofertar = useMutation({
    mutationFn: (cuerpo: Oferta) => {
      const json = JSON.stringify(cuerpo)
      return pedirPortal<VistaPortal>("/ofertas", token, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": claves.para(json),
        },
        body: json,
      })
    },
    onSuccess: (nueva) => {
      claves.olvidar()
      cliente.setQueryData(CLAVE, nueva)
      setConfirmo(false)
      // Si el agente pidió aclarar un precio, los mismos valores se confirman y se reenvían.
      if (nueva.pide_confirmacion) {
        setAviso(
          "Revise su oferta: si es correcta, marque «Confirmo estos valores» y envíela de nuevo."
        )
        return
      }
      setValores(valoresVacios(vista.lineas, vista.palancas))
      setNota("")
      setAviso("Se envió su oferta.")
    },
    onError: alFallar,
  })
  const escalar = useMutation({
    mutationFn: () =>
      pedirPortal<VistaPortal>("/escalar", token, {
        method: "POST",
        headers: { "Idempotency-Key": clavesEscalar.para("escalar") },
      }),
    onSuccess: (nueva) => {
      clavesEscalar.olvidar()
      cliente.setQueryData(CLAVE, nueva)
      setAviso("Avisamos al equipo de compras; una persona le responderá aquí.")
    },
    onError: alFallar,
  })
  const errores = erroresPorCampo(ofertar.error)

  function aceptarPropuesta() {
    if (!vista.ultima_propuesta) return
    setValores(vista.ultima_propuesta)
    setAviso(
      "Llenamos el formulario con la propuesta del agente. Revísela y pulse «Enviar oferta» para aceptarla."
    )
    enviarBoton.current?.focus()
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (ofertar.isPending) return
    ofertar.mutate({
      valores: valoresCapturados(valores),
      nota: nota.trim(),
      confirmar_valores: vista.pide_confirmacion && confirmo,
    })
  }

  return (
    <>
      {vista.ultima_propuesta && (
        <Seccion titulo="Última propuesta del agente">
          <div className="space-y-3">
            <ValoresOferta
              valores={vista.ultima_propuesta}
              lineas={vista.lineas}
              palancas={vista.palancas}
              moneda={vista.moneda}
            />
            <Button type="button" variant="outline" onClick={aceptarPropuesta}>
              <Handshake aria-hidden />
              Aceptar esta propuesta
            </Button>
          </div>
        </Seccion>
      )}
      <Seccion
        titulo="Su oferta"
        descripcion={
          vista.atendido_por === "agente"
            ? "Indique un precio unitario por línea y un valor por cada término. El agente le responde al momento."
            : "Indique un precio unitario por línea y un valor por cada término. Una persona le responderá aquí."
        }
      >
        <form onSubmit={enviar} className="space-y-4">
          <CamposValores
            id={`${id}-valores`}
            lineas={vista.lineas}
            palancas={vista.palancas}
            moneda={vista.moneda}
            valores={valores}
            alCambiar={setValores}
            errores={errores}
            prefijo="valores"
          />
          <Campo
            id={`${id}-nota`}
            etiqueta="Nota para el equipo de compras (opcional)"
            ayuda={`${nota.length.toLocaleString("es-MX")} de 2,000 caracteres. La lee una persona; no cambia su oferta.`}
            error={errores.nota}
          >
            {(control) => (
              <Textarea
                {...control}
                maxLength={2000}
                value={nota}
                onChange={(e) => setNota(e.target.value)}
              />
            )}
          </Campo>
          {vista.pide_confirmacion && (
            <div className="flex items-start gap-2">
              <Checkbox
                id={`${id}-confirmo`}
                checked={confirmo}
                onCheckedChange={(valor) => setConfirmo(valor === true)}
              />
              <Label htmlFor={`${id}-confirmo`}>
                Confirmo estos valores: los revisé y son correctos.
              </Label>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              ref={enviarBoton}
              type="submit"
              aria-disabled={ofertar.isPending}
            >
              <Send aria-hidden />
              Enviar oferta
            </Button>
            {vista.atendido_por === "agente" && (
              <ConfirmarAccion
                titulo="¿Hablar con una persona?"
                descripcion="Una persona del equipo de compras le responderá aquí. Puede seguir enviando ofertas mientras tanto."
                textoConfirmar="Hablar con una persona"
                alConfirmar={() => {
                  if (!escalar.isPending) escalar.mutate()
                }}
              >
                <Button type="button" variant="outline">
                  <UserRound aria-hidden />
                  Hablar con una persona
                </Button>
              </ConfirmarAccion>
            )}
          </div>
          <p role="status" className={aviso ? "text-sm" : "sr-only"}>
            {aviso}
          </p>
          {ofertar.isError && (
            <p role="alert" className="text-sm text-destructive">
              {ofertar.error.message}
            </p>
          )}
          {escalar.isError && (
            <p role="alert" className="text-sm text-destructive">
              {escalar.error.message}
            </p>
          )}
        </form>
      </Seccion>
    </>
  )
}
