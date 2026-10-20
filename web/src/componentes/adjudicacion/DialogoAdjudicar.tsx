import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Fragment, useId, useRef, useState, type FormEvent } from "react"
import {
  razonesAprobacion,
  textoPesos,
  type Candidato,
  type Evaluacion,
  type Recomendacion,
} from "@/adjudicacion"
import { ErrorApi, enviarJson, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { Campo } from "@/componentes/negociacion/Campo"
import { Termino } from "@/componentes/Termino"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import type { Evento } from "@/negociacion"
import { formatoMoneda } from "@/tipos"

// Copia de services/negociacion/src/negociacion/adjudicacion.py (justificacion_de): si cambia allá, cambia aquí.
const JUSTIFICACION_MIN = 10
const JUSTIFICACION_MAX = 1000
const JUSTIFICACION_OBLIGATORIA =
  "Para elegir un proveedor distinto del recomendado, escriba la justificación (de 10 a 1,000 caracteres)."
const JUSTIFICACION_LONGITUD =
  "La justificación debe tener de 10 a 1,000 caracteres."

/** Por qué no sirve la justificación, con el texto del servicio; undefined si sirve. */
function errorDeJustificacion(texto: string): string | undefined {
  const limpia = texto.trim()
  if (!limpia) return JUSTIFICACION_OBLIGATORIA
  if (limpia.length < JUSTIFICACION_MIN || limpia.length > JUSTIFICACION_MAX)
    return JUSTIFICACION_LONGITUD
  return undefined
}

/**
 * Confirmación de «Adjudicar» a un candidato: anticipa si la propuesta se adjudica directamente o va
 * a un aprobador (quien decide es el servicio) y pide la justificación si no es el recomendado.
 */
export function DialogoAdjudicar({
  evento,
  candidato,
  recomendacion,
  alAdjudicar,
  alConflicto,
  alEmpezar,
}: {
  evento: Evento
  candidato: Candidato
  /** La recomendación que se ve: sus pesos son los que se mandan, para que el servicio calcule lo mismo. */
  recomendacion: Recomendacion
  alAdjudicar: (resultado: Evaluacion) => void
  /** El texto del servicio ante un 409: la página lo conserva si la negociación ya no está en evaluación. */
  alConflicto: (mensaje: string) => void
  /** Se llama al abrir la confirmación: el aviso de un conflicto anterior ya no viene al caso. */
  alEmpezar: () => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [abierto, setAbierto] = useState(false)
  const [justificacion, setJustificacion] = useState("")
  const [intentado, setIntentado] = useState(false)
  const adjudicada = useRef(false)
  const campo = useRef<HTMLTextAreaElement>(null)
  const abridor = useRef<HTMLButtonElement>(null)
  const pideJustificacion = candidato.id !== recomendacion.recomendado
  const adjudicar = useMutation({
    // Sin red, que falle de inmediato y se pueda cerrar el diálogo: por omisión la solicitud
    // se quedaría en espera y el diálogo, sin poder cerrarse.
    networkMode: "always",
    mutationFn: () =>
      pedir<Evaluacion>(
        `/negociacion/eventos/${encodeURIComponent(evento.id)}/adjudicacion`,
        token,
        enviarJson("POST", {
          sesion_id: candidato.id,
          pesos: textoPesos(recomendacion.pesos),
          justificacion: pideJustificacion ? justificacion.trim() : undefined,
        })
      ),
    onSuccess: async (resultado) => {
      adjudicada.current = true
      setAbierto(false)
      alAdjudicar(resultado)
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
    onError: (error) => {
      // El error del campo no es una región viva: con el foco en el campo, se lee junto a él.
      if (erroresPorCampo(error).justificacion) campo.current?.focus()
      // Un 409 es que la negociación ya cambió: se actualiza lo que hay detrás del diálogo, sin
      // esperar a la consulta para mostrar el mensaje. Si la sección desaparece, el texto queda
      // en la página.
      if (error instanceof ErrorApi && error.estado === 409) {
        alConflicto(error.message)
        void cliente.invalidateQueries({ queryKey: ["negociacion"] })
      }
    },
  })

  const razones = razonesAprobacion(
    candidato.costo_total_mxn,
    recomendacion.umbral_aprobacion,
    evento.sesiones.find((s) => s.id === candidato.id)?.fuera_de_limites ??
      false
  )
  const costo = formatoMoneda(candidato.costo_total_mxn, "MXN")
  const umbral = formatoMoneda(recomendacion.umbral_aprobacion, "MXN")
  const termino = (
    <Termino clave="umbral_aprobacion">umbral de aprobación</Termino>
  )
  const textoRazon = {
    umbral: (
      <>
        el costo total ({costo}) supera el {termino} ({umbral})
      </>
    ),
    fuera_de_limites: <>el acuerdo está fuera de sus límites</>,
  }
  const regla = razones.length ? (
    <>
      Irá a un aprobador porque{" "}
      {razones.map((r, i) => (
        <Fragment key={r}>
          {i > 0 && " y "}
          {textoRazon[r]}
        </Fragment>
      ))}
      .
    </>
  ) : (
    <>
      Se adjudicará directamente: el costo total ({costo}) no supera el{" "}
      {termino} ({umbral}) y el acuerdo está dentro de sus límites.
    </>
  )

  // El 422 de la justificación va junto al campo (si se pide); cualquier otro error, en el aviso del diálogo.
  const delServicio = erroresPorCampo(adjudicar.error)
  const localmente = intentado ? errorDeJustificacion(justificacion) : undefined
  const errorCampo = pideJustificacion
    ? (localmente ?? delServicio.justificacion)
    : undefined
  const aviso =
    adjudicar.isError && !(pideJustificacion && delServicio.justificacion)
      ? (Object.values(delServicio)[0] ?? adjudicar.error.message)
      : ""

  function enviar(envio: FormEvent<HTMLFormElement>) {
    envio.preventDefault()
    if (adjudicar.isPending) return
    setIntentado(true)
    if (pideJustificacion && errorDeJustificacion(justificacion)) {
      campo.current?.focus()
      return
    }
    adjudicar.mutate()
  }

  return (
    <Dialog
      open={abierto}
      onOpenChange={(valor) => {
        // Cerrar con la propuesta en camino borraría su estado y permitiría enviar otra.
        if (!valor && adjudicar.isPending) return
        setAbierto(valor)
        if (valor) alEmpezar()
        else {
          setJustificacion("")
          setIntentado(false)
          adjudicar.reset()
        }
      }}
    >
      <DialogTrigger asChild>
        <Button ref={abridor} type="button" variant="outline" size="sm">
          {/* El espacio va fuera del sr-only: dentro, el nombre sale «Adjudicara…». */}
          Adjudicar <span className="sr-only">a {candidato.nombre}</span>
        </Button>
      </DialogTrigger>
      <DialogContent
        onCloseAutoFocus={(cierre) => {
          // El botón que abrió el diálogo se desmonta al salir la negociación de «En evaluación»: el
          // foco pasa al contenido y no a <body>. Va aquí y no tras la invalidación porque Radix
          // devuelve el foco al botón después de cerrar y pisaría el del contenido. Radix también
          // llama a esto si el diálogo se desmonta abierto (un 409): entonces el botón ya no existe.
          if (!adjudicada.current && abridor.current?.isConnected) return
          cierre.preventDefault()
          document.getElementById("contenido")?.focus()
        }}
      >
        {/* noValidate: el aviso lo da la página, en español y junto al campo, no el navegador. */}
        <form noValidate onSubmit={enviar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Adjudicar a {candidato.nombre}</DialogTitle>
            <DialogDescription>{regla}</DialogDescription>
          </DialogHeader>
          {pideJustificacion && (
            <Campo
              id={`${id}-justificacion`}
              etiqueta="Justificación"
              ayuda="Explique por qué se aparta de la recomendación (de 10 a 1,000 caracteres)."
              error={errorCampo}
            >
              {(control) => (
                <Textarea
                  {...control}
                  ref={campo}
                  required
                  maxLength={JUSTIFICACION_MAX}
                  value={justificacion}
                  onChange={(e) => setJustificacion(e.target.value)}
                />
              )}
            </Campo>
          )}
          <p
            role="alert"
            className={aviso ? "text-sm text-destructive" : "sr-only"}
          >
            {aviso}
          </p>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Volver
              </Button>
            </DialogClose>
            <Button type="submit" aria-disabled={adjudicar.isPending}>
              Confirmar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
