import { Copy } from "lucide-react"
import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { EnlaceInvitacion } from "@/negociacion"

/**
 * Los enlaces de invitación, que la API entrega una sola vez (spec D3). Se abre por estado; al
 * cerrar, el padre los descarta. El foco vuelve a quien abrió el diálogo si sigue en pantalla
 * (p. ej. «Reenviar» en la tabla de sesiones); si ya no (el botón «Publicar» desaparece al publicar), pasa al
 * contenido de la página. Quien lo abre por una petición puede indicar `abridor`: cuando la
 * respuesta llega, el foco puede estar aún en una confirmación que se está cerrando.
 */
export function DialogoEnlaces({
  enlaces,
  abridor = null,
  alCerrar,
}: {
  enlaces: EnlaceInvitacion[] | null
  abridor?: HTMLElement | null
  alCerrar: () => void
}) {
  const [copia, setCopia] = useState<{ id: string; ok: boolean } | null>(null)
  const abrio = useRef<Element | null>(null)

  async function copiar(enlace: EnlaceInvitacion) {
    try {
      await navigator.clipboard.writeText(enlace.enlace)
      setCopia({ id: enlace.sesion_id, ok: true })
    } catch {
      setCopia({ id: enlace.sesion_id, ok: false })
    }
  }

  const copiado = enlaces?.find((e) => e.sesion_id === copia?.id)
  const textoCopia =
    copiado &&
    (copia?.ok
      ? `Se copió el enlace de ${copiado.proveedor_nombre}.`
      : "No se pudo copiar; selecciónelo y cópielo a mano.")
  return (
    <Dialog
      open={enlaces !== null}
      onOpenChange={(abierto) => {
        if (!abierto) {
          setCopia(null)
          alCerrar()
        }
      }}
    >
      <DialogContent
        className="sm:max-w-2xl"
        // Un clic fuera no los cierra: se pierden y no se pueden volver a ver. Escape y «Listo» sí.
        onInteractOutside={(evento) => evento.preventDefault()}
        onOpenAutoFocus={() => {
          abrio.current = abridor ?? document.activeElement
        }}
        onCloseAutoFocus={(evento) => {
          // Radix solo devuelve el foco a un DialogTrigger y este diálogo se abre por estado, así
          // que se hace aquí: al elemento que lo abrió si sigue en pantalla; si no (o si no había
          // nada enfocado: <body>), al contenido, para que no caiga en <body>.
          const previo = abrio.current
          evento.preventDefault()
          if (
            previo instanceof HTMLElement &&
            previo.isConnected &&
            previo !== document.body
          )
            previo.focus()
          else document.getElementById("contenido")?.focus()
        }}
      >
        <DialogHeader>
          <DialogTitle>
            {enlaces?.length === 1
              ? "Enlace de invitación"
              : "Enlaces de invitación"}
          </DialogTitle>
          <DialogDescription>
            Solo se muestran ahora. Si pierde uno, use «Reenviar» en la tabla de
            sesiones: el enlace anterior deja de servir.
          </DialogDescription>
        </DialogHeader>
        <ul className="max-h-[60svh] space-y-3 overflow-y-auto">
          {enlaces?.map((e) => (
            <li key={e.sesion_id} className="space-y-2 rounded-lg border p-3">
              <p className="font-medium">{e.proveedor_nombre}</p>
              <p className="text-sm text-muted-foreground">
                {e.correo_estado === "enviado"
                  ? `Se envió por correo a ${e.destinatario}.`
                  : `No se pudo enviar el correo a ${e.destinatario}: comparta el enlace o reenvíe la invitación.`}
              </p>
              <p className="rounded-md bg-muted px-2 py-1 font-mono text-xs break-all select-all">
                {e.enlace}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void copiar(e)}
              >
                <Copy aria-hidden />
                Copiar{" "}
                <span className="sr-only">
                  el enlace de {e.proveedor_nombre}
                </span>
              </Button>
            </li>
          ))}
        </ul>
        <p
          aria-live="polite"
          className={textoCopia ? "text-sm text-muted-foreground" : "sr-only"}
        >
          {textoCopia}
        </p>
        <DialogFooter>
          <DialogClose asChild>
            <Button>Listo</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
