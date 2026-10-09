import { Check, Copy } from "lucide-react"
import { useState, type RefObject } from "react"
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

/**
 * Muestra la contraseña temporal una sola vez; al cerrar, el padre la descarta.
 * Se abre por estado, sin disparador: `devolverFoco` es el botón que recibe el foco al cerrar.
 */
export function DialogoContrasenaTemporal({
  datos,
  alCerrar,
  devolverFoco,
}: {
  datos: { nombre: string; contrasena: string } | null
  alCerrar: () => void
  devolverFoco: RefObject<HTMLElement | null>
}) {
  const [copia, setCopia] = useState<"lista" | "copiada" | "fallo">("lista")
  async function copiar() {
    try {
      await navigator.clipboard.writeText(datos?.contrasena ?? "")
      setCopia("copiada")
    } catch {
      setCopia("fallo")
    }
  }
  return (
    <Dialog
      open={datos !== null}
      onOpenChange={(abierto) => {
        if (!abierto) {
          setCopia("lista")
          alCerrar()
        }
      }}
    >
      <DialogContent
        onCloseAutoFocus={(evento) => {
          evento.preventDefault()
          devolverFoco.current?.focus()
        }}
      >
        <DialogHeader>
          <DialogTitle>Contraseña temporal de {datos?.nombre}</DialogTitle>
          <DialogDescription>
            No se volverá a mostrar. Entréguela a la persona por un medio
            seguro; deberá cambiarla al entrar.
          </DialogDescription>
        </DialogHeader>
        <p className="rounded-md border bg-muted px-3 py-2 text-center font-mono text-lg tracking-wider break-all select-all">
          {datos?.contrasena}
        </p>
        <p aria-live="polite" className="text-sm text-muted-foreground">
          {copia === "copiada" && "Contraseña copiada."}
          {copia === "fallo" &&
            "No se pudo copiar; selecciónela y cópiela a mano."}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => void copiar()}>
            {copia === "copiada" ? <Check aria-hidden /> : <Copy aria-hidden />}
            Copiar
          </Button>
          <DialogClose asChild>
            <Button>Listo</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
