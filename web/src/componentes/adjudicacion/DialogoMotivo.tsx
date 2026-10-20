import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useRef, useState, type FormEvent, type ReactNode } from "react"
import { DECISION, type Evaluacion } from "@/adjudicacion"
import { ErrorApi, enviarJson, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { Campo } from "@/componentes/negociacion/Campo"
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

const MOTIVO_VACIO = "Escriba el motivo."

/**
 * Un diálogo que pide un motivo (de 1 a 500 caracteres) y lo manda con un POST a `ruta`; lo usan
 * «Declarar desierta» y «Rechazar». `datos` va en el mismo cuerpo. `ocupado` es que hay otra
 * decisión en camino: el botón que abre el diálogo no abre mientras tanto.
 */
export function DialogoMotivo({
  ruta,
  datos,
  ocupado = false,
  textoAbrir,
  textoEnviar,
  titulo,
  descripcion,
  etiqueta,
  ayuda,
  alTerminar,
  alConflicto,
  alEmpezar,
}: {
  /** Ruta completa del POST, p. ej. `/negociacion/eventos/{id}/desierta`. */
  ruta: string
  datos?: Record<string, unknown>
  ocupado?: boolean
  /** El botón que abre el diálogo. */
  textoAbrir: string
  /** El botón que envía el motivo. */
  textoEnviar: string
  titulo: string
  descripcion: ReactNode
  etiqueta: string
  ayuda: string
  alTerminar: () => void
  /** El texto del servicio ante un 409: la página lo conserva si la sección y este diálogo desaparecen. */
  alConflicto: (mensaje: string) => void
  /** Se llama al abrir el diálogo: el aviso de un conflicto anterior ya no viene al caso. */
  alEmpezar: () => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [abierto, setAbierto] = useState(false)
  const [motivo, setMotivo] = useState("")
  const [intentado, setIntentado] = useState(false)
  const terminada = useRef(false)
  const campo = useRef<HTMLTextAreaElement>(null)
  const abridor = useRef<HTMLButtonElement>(null)
  const enviarMotivo = useMutation({
    // Sin red, que falle de inmediato y se pueda cerrar el diálogo: por omisión la solicitud
    // se quedaría en espera y el diálogo, sin poder cerrarse.
    networkMode: "always",
    mutationKey: DECISION,
    mutationFn: () =>
      pedir<Evaluacion>(
        ruta,
        token,
        enviarJson("POST", { ...datos, motivo: motivo.trim() })
      ),
    onSuccess: async () => {
      terminada.current = true
      setAbierto(false)
      alTerminar()
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
    onError: (error) => {
      // El error del campo no es una región viva: con el foco en el campo, se lee junto a él.
      if (erroresPorCampo(error).motivo) campo.current?.focus()
      // Un 409 es que la negociación ya cambió: se actualiza lo que hay detrás del diálogo, sin
      // esperar a la consulta para mostrar el mensaje. Si la sección desaparece, el texto queda
      // en la página.
      if (error instanceof ErrorApi && error.estado === 409) {
        alConflicto(error.message)
        void cliente.invalidateQueries({ queryKey: ["negociacion"] })
        // La propuesta que se iba a decidir ya no es la vigente: se vuelve a abrir desde la
        // pantalla actualizada.
        if (error.codigo === "propuesta_distinta") setAbierto(false)
      }
    },
  })
  const error =
    (intentado && !motivo.trim() ? MOTIVO_VACIO : undefined) ??
    erroresPorCampo(enviarMotivo.error).motivo
  // Cualquier otro error del servicio, en el aviso del diálogo; cerrado, el aviso es el de la página.
  const aviso =
    abierto && enviarMotivo.isError && !error ? enviarMotivo.error.message : ""

  function enviar(envio: FormEvent<HTMLFormElement>) {
    envio.preventDefault()
    if (enviarMotivo.isPending) return
    setIntentado(true)
    if (!motivo.trim()) {
      campo.current?.focus()
      return
    }
    enviarMotivo.mutate()
  }

  return (
    <Dialog
      open={abierto}
      onOpenChange={(valor) => {
        // Cerrar con la solicitud en camino borraría su estado y permitiría enviar otra.
        if (!valor && enviarMotivo.isPending) return
        // Con otra decisión en camino no se abre: se decidirían dos cosas a la vez.
        if (valor && ocupado) return
        setAbierto(valor)
        // Se limpia al abrir y no al cerrar: así nada cambia mientras el diálogo se desvanece.
        if (valor) {
          terminada.current = false
          setMotivo("")
          setIntentado(false)
          enviarMotivo.reset()
          alEmpezar()
        }
      }}
    >
      <DialogTrigger asChild>
        <Button
          ref={abridor}
          type="button"
          variant="outline"
          aria-disabled={ocupado}
        >
          {textoAbrir}
        </Button>
      </DialogTrigger>
      <DialogContent
        onCloseAutoFocus={(cierre) => {
          // Si la acción se hizo, la negociación sale de su estado y el botón que abrió el diálogo
          // se desmonta: el foco pasa al contenido y no a <body> (ver DialogoCancelar). Radix
          // también llama a esto si el diálogo se desmonta abierto (un 409): entonces el botón ya
          // no existe. En un cierre normal, el foco vuelve al botón.
          if (!terminada.current && abridor.current?.isConnected) return
          cierre.preventDefault()
          // Si la sección ya puso el foco en otra parte (p. ej. en su aviso de que la propuesta
          // cambió), se queda ahí: solo se rescata el foco que quedó en <body>.
          if (document.activeElement === document.body)
            document.getElementById("contenido")?.focus()
        }}
      >
        {/* noValidate: el aviso lo da la página, en español y junto al campo, no el navegador. */}
        <form noValidate onSubmit={enviar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>{titulo}</DialogTitle>
            <DialogDescription>{descripcion}</DialogDescription>
          </DialogHeader>
          <Campo
            id={`${id}-motivo`}
            etiqueta={etiqueta}
            ayuda={ayuda}
            error={error}
          >
            {(control) => (
              <Textarea
                {...control}
                ref={campo}
                required
                maxLength={500}
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
              />
            )}
          </Campo>
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
            <Button
              type="submit"
              variant="destructive"
              aria-disabled={enviarMotivo.isPending}
            >
              {textoEnviar}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
