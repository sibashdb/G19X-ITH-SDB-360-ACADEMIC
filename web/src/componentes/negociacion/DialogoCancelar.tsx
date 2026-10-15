import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useRef, useState, type FormEvent } from "react"
import { enviarJson, erroresPorCampo, pedir } from "@/api"
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

/** «Cancelar borrador» o «Cancelar negociación», con el motivo que queda en la bitácora. */
export function DialogoCancelar({
  ruta,
  borrador,
  alCancelar,
}: {
  ruta: string
  borrador: boolean
  alCancelar: () => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [abierto, setAbierto] = useState(false)
  const [motivo, setMotivo] = useState("")
  const cancelada = useRef(false)
  const cancelar = useMutation({
    mutationFn: () =>
      pedir<Evento>(`${ruta}/cancelar`, token, enviarJson("POST", { motivo })),
    onSuccess: async () => {
      cancelada.current = true
      setAbierto(false)
      alCancelar()
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
  })
  const error = erroresPorCampo(cancelar.error).motivo
  const accion = borrador ? "Cancelar borrador" : "Cancelar negociación"

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    // El diálogo se dibuja en un portal, pero React propaga el submit al formulario padre.
    evento.stopPropagation()
    if (!cancelar.isPending) cancelar.mutate()
  }

  return (
    <Dialog
      open={abierto}
      onOpenChange={(valor) => {
        setAbierto(valor)
        if (!valor) {
          setMotivo("")
          cancelar.reset()
        }
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" variant="outline">
          {accion}
        </Button>
      </DialogTrigger>
      <DialogContent
        onCloseAutoFocus={(evento) => {
          // El evento queda cancelado y el botón que abrió el diálogo se desmonta: el foco pasa al
          // contenido y no a <body>. Va aquí y no tras la invalidación porque Radix devuelve el foco
          // al botón después de cerrar, y con una respuesta rápida eso pisaría el del contenido.
          if (!cancelada.current) return
          evento.preventDefault()
          document.getElementById("contenido")?.focus()
        }}
      >
        <form onSubmit={enviar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>
              {borrador ? "Cancelar el borrador" : "Cancelar la negociación"}
            </DialogTitle>
            <DialogDescription>
              {borrador
                ? "El borrador queda cancelado y no se envía nada a los proveedores."
                : "Los enlaces dejan de servir y las sesiones que sigan abiertas terminan sin acuerdo. No se puede deshacer."}
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
                required
                maxLength={500}
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
              />
            )}
          </Campo>
          {cancelar.isError && !error && (
            <p role="alert" className="text-sm text-destructive">
              {cancelar.error.message}
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Volver
              </Button>
            </DialogClose>
            <Button
              type="submit"
              variant="destructive"
              aria-disabled={cancelar.isPending}
            >
              {accion}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
