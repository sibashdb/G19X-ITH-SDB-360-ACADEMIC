import { useMutation } from "@tanstack/react-query"
import { CircleAlert } from "lucide-react"
import { useId, useState, type FormEvent, type RefObject } from "react"
import { enviarJson, erroresPorCampo, ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  CATEGORIAS,
  MONEDAS,
  NOMBRES_CATEGORIA,
  NOMBRES_UNIDAD,
  UNIDADES,
  type Servicio,
} from "@/tipos"

type Valores = {
  codigo: string
  nombre: string
  categoria: string
  unidad: string
  moneda: string
}
const EDITABLES = ["nombre", "categoria", "unidad", "moneda"] as const
const AYUDA_CODIGO =
  "Letras, números y guiones (3 a 30). No cambia después de crearlo: las importaciones lo usan para identificar el servicio."
const AVISO_CONTRATOS =
  "La categoría, la unidad y la moneda no se pueden cambiar: el servicio ya tiene contratos y sus precios dependen de ellas."

/** Alta (servicio null) o edición de un servicio del catálogo, en un panel lateral. */
export function FormularioServicio({
  abierto,
  alCambiarAbierto,
  servicio,
  devolverFoco,
  alGuardar,
}: {
  abierto: boolean
  alCambiarAbierto: (abierto: boolean) => void
  servicio: Servicio | null
  /** El panel se abre por estado, sin disparador: este elemento recibe el foco al cerrarlo. */
  devolverFoco: RefObject<HTMLElement | null>
  alGuardar: (guardado: Servicio, esAlta: boolean) => void
}) {
  const token = useToken()
  const id = useId()
  const esAlta = servicio === null
  const bloqueado = servicio?.tiene_contratos ?? false
  const [valores, setValores] = useState<Valores>({
    codigo: servicio?.codigo ?? "",
    nombre: servicio?.nombre ?? "",
    categoria: servicio?.categoria ?? "",
    unidad: servicio?.unidad ?? "",
    moneda: servicio?.moneda ?? "",
  })
  const mutacion = useMutation({
    mutationFn: (datos: object) =>
      esAlta
        ? pedir<Servicio>(
            "/proveedores/servicios",
            token,
            enviarJson("POST", datos)
          )
        : pedir<Servicio>(
            `/proveedores/servicios/${encodeURIComponent(servicio.codigo)}`,
            token,
            enviarJson("PATCH", datos)
          ),
    onSuccess: (guardado) => {
      alCambiarAbierto(false)
      alGuardar(guardado, esAlta)
    },
  })
  const errores = erroresPorCampo(mutacion.error)
  const errorGeneral =
    mutacion.error && Object.keys(errores).length === 0 ? mutacion.error : null

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (mutacion.isPending) return
    if (esAlta) {
      mutacion.mutate(valores)
      return
    }
    const cambios = Object.fromEntries(
      EDITABLES.filter((c) => valores[c] !== servicio[c]).map((c) => [
        c,
        valores[c],
      ])
    )
    if (Object.keys(cambios).length === 0) {
      alCambiarAbierto(false)
      return
    }
    mutacion.mutate(cambios)
  }

  function campoTexto(campo: "codigo" | "nombre", etiqueta: string) {
    const error = errores[campo]
    const ayuda = campo === "codigo" ? AYUDA_CODIGO : null
    const descritoPor =
      [ayuda && `${id}-${campo}-ayuda`, error && `${id}-${campo}-error`]
        .filter(Boolean)
        .join(" ") || undefined
    return (
      <div className="grid gap-1.5">
        <Label htmlFor={`${id}-${campo}`}>{etiqueta}</Label>
        <Input
          id={`${id}-${campo}`}
          value={valores[campo]}
          readOnly={campo === "codigo" && !esAlta}
          onChange={(e) =>
            setValores((v) => ({ ...v, [campo]: e.target.value }))
          }
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
          <p id={`${id}-${campo}-error`} className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
    )
  }

  function campoLista(
    campo: "categoria" | "unidad" | "moneda",
    etiqueta: string,
    opciones: [string, string][],
    soloSinContratos = false
  ) {
    const error = errores[campo]
    const deshabilitado = soloSinContratos && bloqueado
    const descritoPor =
      [deshabilitado && `${id}-contratos`, error && `${id}-${campo}-error`]
        .filter(Boolean)
        .join(" ") || undefined
    return (
      <div className="grid gap-1.5">
        <span id={`${id}-${campo}`} className="text-sm font-medium">
          {etiqueta}
        </span>
        <Select
          value={valores[campo] || undefined}
          disabled={deshabilitado}
          onValueChange={(v) =>
            setValores((previos) => ({ ...previos, [campo]: v }))
          }
        >
          <SelectTrigger
            aria-labelledby={`${id}-${campo}`}
            aria-describedby={descritoPor}
            aria-invalid={error ? true : undefined}
            className="w-full"
          >
            <SelectValue placeholder="Elija una opción" />
          </SelectTrigger>
          <SelectContent>
            {opciones.map(([valor, nombre]) => (
              <SelectItem key={valor} value={valor}>
                {nombre}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {error && (
          <p id={`${id}-${campo}-error`} className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
    )
  }

  return (
    <Sheet
      open={abierto}
      onOpenChange={(siguiente) => {
        if (!siguiente) mutacion.reset()
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
          <SheetTitle>
            {esAlta ? "Nuevo servicio" : `Editar ${servicio.codigo}`}
          </SheetTitle>
          <SheetDescription>
            Los servicios del catálogo son los que aparecen en los contratos y
            en Precios.
          </SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={enviar} className="space-y-5 px-4 pb-4">
          {errorGeneral && (
            <Alert variant="destructive">
              <CircleAlert aria-hidden />
              <AlertTitle>
                {errorGeneral instanceof ErrorApi
                  ? errorGeneral.titulo
                  : "No se pudo guardar"}
              </AlertTitle>
              <AlertDescription>{errorGeneral.message}</AlertDescription>
            </Alert>
          )}
          {campoTexto("codigo", "Código")}
          {campoTexto("nombre", "Nombre")}
          {bloqueado && (
            <p id={`${id}-contratos`} className="text-sm text-muted-foreground">
              {AVISO_CONTRATOS}
            </p>
          )}
          {campoLista(
            "categoria",
            "Categoría",
            CATEGORIAS.map((c) => [c, NOMBRES_CATEGORIA[c]]),
            true
          )}
          {campoLista(
            "unidad",
            "Unidad",
            UNIDADES.map((u) => [u, NOMBRES_UNIDAD[u]]),
            true
          )}
          {campoLista(
            "moneda",
            "Moneda",
            MONEDAS.map((m) => [m, m]),
            true
          )}
          <SheetFooter className="px-0">
            <Button type="submit" aria-disabled={mutacion.isPending}>
              {mutacion.isPending
                ? "Guardando…"
                : esAlta
                  ? "Dar de alta"
                  : "Guardar cambios"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
