import { Copy } from "lucide-react"
import { useState } from "react"
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
 * cerrar, el padre los descarta y el foco vuelve al contenido de la página.
 */
export function DialogoEnlaces({
  enlaces,
  alCerrar,
}: {
  enlaces: EnlaceInvitacion[] | null
  alCerrar: () => void
}) {
  const [copia, setCopia] = useState<{ id: string; ok: boolean } | null>(null)

  async function copiar(enlace: EnlaceInvitacion) {
    try {
      await navigator.clipboard.writeText(enlace.enlace)
      setCopia({ id: enlace.sesion_id, ok: true })
    } catch {
      setCopia({ id: enlace.sesion_id, ok: false })
    }
  }

  const copiado = enlaces?.find((e) => e.sesion_id === copia?.id)
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
        onCloseAutoFocus={(evento) => {
          evento.preventDefault()
          document.getElementById("contenido")?.focus()
        }}
      >
        <DialogHeader>
          <DialogTitle>
            {enlaces?.length === 1
              ? "Enlace de invitación"
              : "Enlaces de invitación"}
          </DialogTitle>
          <DialogDescription>
            Solo se muestran ahora. Si pierde uno, use «Reenviar invitación»: el
            enlace anterior deja de servir.
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
                Copiar
                <span className="sr-only">
                  {" "}
                  el enlace de {e.proveedor_nombre}
                </span>
              </Button>
            </li>
          ))}
        </ul>
        <p aria-live="polite" className="text-sm text-muted-foreground">
          {copiado &&
            (copia?.ok
              ? `Se copió el enlace de ${copiado.proveedor_nombre}.`
              : "No se pudo copiar; selecciónelo y cópielo a mano.")}
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
