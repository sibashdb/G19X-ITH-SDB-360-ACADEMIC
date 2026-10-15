import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useState, type FormEvent } from "react"
import { ErrorApi, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { Seccion } from "@/componentes/Seccion"
import { Campo } from "@/componentes/negociacion/Campo"
import {
  CamposValores,
  valoresCapturados,
  valoresVacios,
} from "@/componentes/negociacion/CamposValores"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { crearClaves, type SesionDetalle, type Valores } from "@/negociacion"

type Respuesta = {
  tipo: "mensaje" | "aceptar" | "cerrar"
  texto: string
  contraoferta?: Valores
  confirmar_fuera_de_limites: boolean
}

const AVISOS: Record<Respuesta["tipo"], string> = {
  mensaje: "Se envió su respuesta.",
  aceptar: "Aceptó la última oferta: queda como acuerdo tentativo.",
  cerrar: "Cerró la sesión sin acuerdo.",
}

/**
 * El comprador responde a mano mientras atiende la sesión (spec §7). Si lo que envía sale de sus
 * límites, la API pide confirmarlo; la confirmación queda marcada para el aprobador.
 */
export function RespuestaManual({ datos }: { datos: SesionDetalle }) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [claves] = useState(crearClaves)
  const palancas = datos.palancas.filter((p) => p.clave !== "precio")
  const propuesta = datos.ofertas.findLast((o) => o.autor !== "proveedor")
  const hayOfertaDelProveedor = datos.ofertas.some(
    (o) => o.autor === "proveedor"
  )
  const [texto, setTexto] = useState("")
  const [conContraoferta, setConContraoferta] = useState(false)
  const [valores, setValores] = useState<Valores>(
    () => propuesta?.valores ?? valoresVacios(datos.lineas, palancas)
  )
  // La respuesta que espera confirmar que sale de los límites.
  const [pendiente, setPendiente] = useState<Respuesta | null>(null)
  const [aviso, setAviso] = useState("")

  const responder = useMutation({
    mutationFn: (cuerpo: Respuesta) => {
      const json = JSON.stringify(cuerpo)
      return pedir<SesionDetalle>(
        `/negociacion/sesiones/${encodeURIComponent(datos.id)}/respuestas`,
        token,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": claves.para(json),
          },
          body: json,
        }
      )
    },
    onSuccess: async (_respuesta, cuerpo) => {
      claves.olvidar()
      setPendiente(null)
      setTexto("")
      setConContraoferta(false)
      setAviso(AVISOS[cuerpo.tipo])
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
      // Aceptar o cerrar termina la sesión: la página quita el formulario y el botón de control, y
      // el foco caería en <body>. El diálogo ya devolvió el foco a su botón antes de la petición.
      if (cuerpo.tipo === "aceptar" || cuerpo.tipo === "cerrar")
        document.getElementById("contenido")?.focus()
    },
    onError: (error, cuerpo) => {
      setAviso("")
      if (
        error instanceof ErrorApi &&
        error.codigo === "fuera_de_limites" &&
        !cuerpo.confirmar_fuera_de_limites
      )
        setPendiente(cuerpo)
    },
  })
  const errores = erroresPorCampo(responder.error)
  const fueraDeLimites =
    responder.error instanceof ErrorApi &&
    responder.error.codigo === "fuera_de_limites"

  function enviar(cuerpo: Respuesta) {
    if (!responder.isPending) responder.mutate(cuerpo)
  }

  function enviarMensaje(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    enviar({
      tipo: "mensaje",
      texto,
      contraoferta: conContraoferta ? valoresCapturados(valores) : undefined,
      confirmar_fuera_de_limites: false,
    })
  }

  return (
    <Seccion
      titulo="Responder al proveedor"
      descripcion="Usted atiende esta sesión: el agente no responderá hasta que la devuelva."
    >
      <form onSubmit={enviarMensaje} className="space-y-4">
        <Campo
          id={`${id}-texto`}
          etiqueta="Mensaje para el proveedor"
          ayuda={`${texto.length.toLocaleString("es-MX")} de 2,000 caracteres`}
          error={errores.texto}
        >
          {(control) => (
            <Textarea
              {...control}
              required
              maxLength={2000}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
            />
          )}
        </Campo>
        <div className="flex items-center gap-2">
          <Checkbox
            id={`${id}-con`}
            checked={conContraoferta}
            onCheckedChange={(valor) => setConContraoferta(valor === true)}
          />
          <Label htmlFor={`${id}-con`}>Incluir una contraoferta</Label>
        </div>
        {conContraoferta && (
          <CamposValores
            id={`${id}-valores`}
            lineas={datos.lineas}
            palancas={palancas}
            moneda={datos.moneda}
            valores={valores}
            alCambiar={setValores}
            errores={errores}
            prefijo="contraoferta"
          />
        )}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" aria-disabled={responder.isPending}>
            Enviar respuesta
          </Button>
          {hayOfertaDelProveedor && (
            <ConfirmarAccion
              titulo="¿Aceptar la última oferta?"
              descripcion="La última oferta del proveedor queda como acuerdo tentativo; no es vinculante hasta la adjudicación."
              textoConfirmar="Aceptar oferta"
              alConfirmar={() =>
                enviar({
                  tipo: "aceptar",
                  texto: "",
                  confirmar_fuera_de_limites: false,
                })
              }
            >
              <Button type="button" variant="outline">
                Aceptar la última oferta
              </Button>
            </ConfirmarAccion>
          )}
          <ConfirmarAccion
            titulo="¿Cerrar sin acuerdo?"
            descripcion="La sesión termina sin acuerdo y el proveedor ya no podrá ofertar."
            textoConfirmar="Cerrar sin acuerdo"
            alConfirmar={() =>
              enviar({
                tipo: "cerrar",
                texto,
                confirmar_fuera_de_limites: false,
              })
            }
          >
            <Button type="button" variant="outline">
              Cerrar sin acuerdo
            </Button>
          </ConfirmarAccion>
        </div>
        <p role="status" className={aviso ? "text-sm text-success" : "sr-only"}>
          {aviso}
        </p>
        {responder.isError &&
          !fueraDeLimites &&
          Object.keys(errores).length === 0 && (
            <p role="alert" className="text-sm text-destructive">
              {responder.error.message}
            </p>
          )}
      </form>
      <AlertDialog
        open={pendiente !== null}
        onOpenChange={(abierto) => {
          if (!abierto) setPendiente(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Esto sale de sus límites</AlertDialogTitle>
            <AlertDialogDescription>
              {`${responder.error?.message ?? ""} Si continúa, la sesión queda marcada y el aprobador lo verá.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Revisar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pendiente)
                  enviar({ ...pendiente, confirmar_fuera_de_limites: true })
              }}
            >
              Enviar de todos modos
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Seccion>
  )
}
