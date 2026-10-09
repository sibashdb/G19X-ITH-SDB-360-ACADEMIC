import { useMutation, useQueryClient } from "@tanstack/react-query"
import { CircleAlert } from "lucide-react"
import { useId, useState, type FormEvent, type RefObject } from "react"
import { enviarJson, erroresPorCampo, ErrorApi, pedir } from "@/api"
import { useToken, type Rol } from "@/auth"
import { CamposRoles } from "@/componentes/CamposRoles"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { MetodoAlta, ResultadoAlta } from "@/tipos"
import { sugerirUsuario } from "@/usuarios"

const CAMPOS = ["nombre", "apellidos", "correo", "usuario"] as const
const ETIQUETAS: Record<(typeof CAMPOS)[number], string> = {
  nombre: "Nombre",
  apellidos: "Apellidos",
  correo: "Correo",
  usuario: "Usuario",
}
const AYUDA_USUARIO =
  "Entre 3 y 30 caracteres: minúsculas, números, punto o guion."

export function FormularioAltaUsuario({
  abierto,
  alCambiarAbierto,
  alTerminar,
  devolverFoco,
}: {
  abierto: boolean
  alCambiarAbierto: (abierto: boolean) => void
  alTerminar: (resultado: ResultadoAlta) => void
  /** El panel se abre por estado, sin disparador: este botón recibe el foco al cerrarlo. */
  devolverFoco: RefObject<HTMLElement | null>
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [valores, setValores] = useState({
    nombre: "",
    apellidos: "",
    correo: "",
    usuario: "",
  })
  const [usuarioEditado, setUsuarioEditado] = useState(false)
  const [roles, setRoles] = useState<Rol[]>([])
  const [metodo, setMetodo] = useState<MetodoAlta>("invitacion")
  const mutacion = useMutation({
    mutationFn: (datos: object) =>
      pedir<ResultadoAlta>(
        "/administracion/usuarios",
        token,
        enviarJson("POST", datos)
      ),
    onSuccess: (resultado) => {
      reiniciar()
      alCambiarAbierto(false)
      alTerminar(resultado)
    },
    onError: (error) => {
      // La cuenta sí se creó aunque no se terminó de configurar: que aparezca en la lista.
      if (error instanceof ErrorApi && error.codigo === "alta_incompleta")
        void cliente.invalidateQueries({ queryKey: ["usuarios"] })
    },
  })
  const errores = erroresPorCampo(mutacion.error)
  const errorGeneral =
    mutacion.error && Object.keys(errores).length === 0 ? mutacion.error : null

  function reiniciar() {
    setValores({ nombre: "", apellidos: "", correo: "", usuario: "" })
    setUsuarioEditado(false)
    setRoles([])
    setMetodo("invitacion")
    mutacion.reset()
  }

  function cambiar(campo: (typeof CAMPOS)[number], valor: string) {
    setValores((previos) => ({
      ...previos,
      [campo]: valor,
      // El usuario se sugiere del correo hasta que la persona lo escribe a mano.
      ...(campo === "correo" && !usuarioEditado
        ? { usuario: sugerirUsuario(valor) }
        : {}),
    }))
    if (campo === "usuario") setUsuarioEditado(true)
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (mutacion.isPending) return
    mutacion.mutate({ ...valores, roles, metodo })
  }

  return (
    <Sheet
      open={abierto}
      onOpenChange={(siguiente) => {
        if (!siguiente) reiniciar()
        alCambiarAbierto(siguiente)
      }}
    >
      <SheetContent
        className="overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-md"
        onCloseAutoFocus={(evento) => {
          evento.preventDefault()
          devolverFoco.current?.focus()
        }}
      >
        <SheetHeader>
          <SheetTitle>Nuevo usuario</SheetTitle>
          <SheetDescription>
            La persona entrará con su usuario y la contraseña que defina.
          </SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={enviar} className="space-y-5 px-4 pb-4">
          {errorGeneral && (
            <Alert variant="destructive">
              <CircleAlert aria-hidden />
              <AlertTitle>
                {errorGeneral instanceof ErrorApi
                  ? errorGeneral.titulo
                  : "No se pudo dar de alta"}
              </AlertTitle>
              <AlertDescription>{errorGeneral.message}</AlertDescription>
            </Alert>
          )}
          {CAMPOS.map((campo) => {
            const error = errores[campo]
            const ayuda = campo === "usuario" ? AYUDA_USUARIO : null
            const descritoPor =
              [ayuda && `${id}-${campo}-ayuda`, error && `${id}-${campo}-error`]
                .filter(Boolean)
                .join(" ") || undefined
            return (
              <div key={campo} className="grid gap-1.5">
                <Label htmlFor={`${id}-${campo}`}>{ETIQUETAS[campo]}</Label>
                <Input
                  id={`${id}-${campo}`}
                  value={valores[campo]}
                  onChange={(e) => cambiar(campo, e.target.value)}
                  type={campo === "correo" ? "email" : "text"}
                  autoComplete="off"
                  aria-invalid={error ? true : undefined}
                  aria-describedby={descritoPor}
                />
                {ayuda && (
                  <p
                    id={`${id}-${campo}-ayuda`}
                    className="text-xs text-muted-foreground"
                  >
                    {ayuda}
                  </p>
                )}
                {error && (
                  <p
                    id={`${id}-${campo}-error`}
                    className="text-sm text-destructive"
                  >
                    {error}
                  </p>
                )}
              </div>
            )
          })}
          <CamposRoles
            valor={roles}
            alCambiar={setRoles}
            error={errores.roles}
          />
          <div className="space-y-2">
            <p id={`${id}-metodo`} className="text-sm font-medium">
              ¿Cómo obtendrá su contraseña?
            </p>
            <RadioGroup
              aria-labelledby={`${id}-metodo`}
              value={metodo}
              onValueChange={(v) => setMetodo(v as MetodoAlta)}
              className="gap-3"
            >
              <div className="flex items-start gap-2">
                <RadioGroupItem
                  value="invitacion"
                  id={`${id}-invitacion`}
                  aria-describedby={`${id}-invitacion-descripcion`}
                />
                <div className="grid gap-0.5">
                  <Label htmlFor={`${id}-invitacion`}>
                    Invitación por correo (recomendada)
                  </Label>
                  <p
                    id={`${id}-invitacion-descripcion`}
                    className="text-xs text-muted-foreground"
                  >
                    Recibe un enlace para definir su propia contraseña; vence en
                    72 horas.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <RadioGroupItem
                  value="temporal"
                  id={`${id}-temporal`}
                  aria-describedby={`${id}-temporal-descripcion`}
                />
                <div className="grid gap-0.5">
                  <Label htmlFor={`${id}-temporal`}>Contraseña temporal</Label>
                  <p
                    id={`${id}-temporal-descripcion`}
                    className="text-xs text-muted-foreground"
                  >
                    Usted la verá una sola vez y se la entrega; deberá cambiarla
                    al entrar.
                  </p>
                </div>
              </div>
            </RadioGroup>
          </div>
          <SheetFooter className="px-0">
            <Button type="submit" aria-disabled={mutacion.isPending}>
              {mutacion.isPending ? "Dando de alta…" : "Dar de alta"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
