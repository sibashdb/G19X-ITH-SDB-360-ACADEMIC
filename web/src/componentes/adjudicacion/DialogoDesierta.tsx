import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useRef, useState, type FormEvent } from "react"
import type { Evaluacion } from "@/adjudicacion"
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
import type { Evento } from "@/negociacion"

/** «Declarar desierta» la negociación en evaluación, con el motivo que queda en la bitácora. */
export function DialogoDesierta({
  evento,
  alDeclarar,
}: {
  evento: Evento
  alDeclarar: () => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [abierto, setAbierto] = useState(false)
  const [motivo, setMotivo] = useState("")
  const declarada = useRef(false)
  const campo = useRef<HTMLTextAreaElement>(null)
  const declarar = useMutation({
    mutationFn: () =>
      pedir<Evaluacion>(
        `/negociacion/eventos/${encodeURIComponent(evento.id)}/desierta`,
        token,
        enviarJson("POST", { motivo })
      ),
    onSuccess: async () => {
      declarada.current = true
      setAbierto(false)
      alDeclarar()
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
    onError: (error) => {
      // El error del campo no es una región viva: con el foco en el campo, se lee junto a él.
      if (erroresPorCampo(error).motivo) campo.current?.focus()
      // Un 409 es que la negociación ya cambió: se actualiza lo que hay detrás del diálogo, sin
      // esperar a la consulta para mostrar el mensaje.
      if (error instanceof ErrorApi && error.estado === 409)
        void cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
  })
  const error = erroresPorCampo(declarar.error).motivo

  function enviar(envio: FormEvent<HTMLFormElement>) {
    envio.preventDefault()
    if (!declarar.isPending) declarar.mutate()
  }

  return (
    <Dialog
      open={abierto}
      onOpenChange={(valor) => {
        // Cerrar con la solicitud en camino borraría su estado y permitiría enviar otra.
        if (!valor && declarar.isPending) return
        setAbierto(valor)
        if (!valor) {
          setMotivo("")
          declarar.reset()
        }
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" variant="outline">
          Declarar desierta
        </Button>
      </DialogTrigger>
      <DialogContent
        onCloseAutoFocus={(cierre) => {
          // La negociación sale de «En evaluación» y el botón que abrió el diálogo se desmonta: el
          // foco pasa al contenido y no a <body> (ver DialogoCancelar).
          if (!declarada.current) return
          cierre.preventDefault()
          document.getElementById("contenido")?.focus()
        }}
      >
        <form onSubmit={enviar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Declarar desierta la negociación</DialogTitle>
            <DialogDescription>
              La negociación termina sin adjudicar a ningún proveedor y se les
              avisa por correo. No se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <Campo
            id={`${id}-motivo`}
            etiqueta="Motivo"
            ayuda="Queda en la bitácora y en la Actividad."
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
            className={
              declarar.isError && !error
                ? "text-sm text-destructive"
                : "sr-only"
            }
          >
            {declarar.isError && !error ? declarar.error.message : ""}
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
              aria-disabled={declarar.isPending}
            >
              Declarar desierta
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
