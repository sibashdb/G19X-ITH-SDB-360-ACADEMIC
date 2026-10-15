import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { X } from "lucide-react"
import { useDeferredValue, useId, useRef, useState } from "react"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { EstadoCarga, EstadoError } from "@/componentes/Estados"
import { Campo } from "@/componentes/negociacion/Campo"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  NOMBRES_CATEGORIA,
  type PaginaProveedores,
  type ProveedorResumen,
} from "@/tipos"

export type Invitado = { id: string; nombre: string }

const MAXIMO = 10 // los que acepta la API (spec §5.1)

/** Busca proveedores activos y elige de 1 a 10; los elegidos se ven aunque cambie la búsqueda. */
export function SelectorProveedores({
  elegidos,
  alCambiar,
  error,
}: {
  elegidos: Invitado[]
  alCambiar: (elegidos: Invitado[]) => void
  error?: string
}) {
  const token = useToken()
  const id = useId()
  const buscador = useRef<HTMLInputElement>(null)
  const [busqueda, setBusqueda] = useState("")
  const texto = useDeferredValue(busqueda.trim())
  const parametros = new URLSearchParams({
    activo: "true",
    limite: "50",
    desplazamiento: "0",
  })
  if (texto) parametros.set("q", texto)
  const consulta = useQuery({
    queryKey: ["proveedores", "invitables", texto],
    queryFn: () =>
      pedir<PaginaProveedores>(`/proveedores/proveedores?${parametros}`, token),
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })
  const lleno = elegidos.length >= MAXIMO

  function alternar(proveedor: ProveedorResumen, marcado: boolean) {
    alCambiar(
      marcado
        ? [...elegidos, { id: proveedor.id, nombre: proveedor.nombre }]
        : elegidos.filter((e) => e.id !== proveedor.id)
    )
  }

  function quitar(invitado: Invitado) {
    alCambiar(elegidos.filter((e) => e.id !== invitado.id))
    // El botón «Quitar» desaparece con su etiqueta: el foco pasa al buscador, que sigue en pantalla.
    buscador.current?.focus()
  }

  function lista() {
    if (consulta.isPending) return <EstadoCarga filas={3} />
    if (consulta.isError) {
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    }
    const { total, elementos } = consulta.data
    if (elementos.length === 0) {
      return (
        <p className="text-sm text-muted-foreground">
          Ningún proveedor activo coincide con la búsqueda.
        </p>
      )
    }
    return (
      <fieldset className="space-y-2">
        <legend className="sr-only">Proveedores para invitar</legend>
        <ul className="max-h-72 space-y-2 overflow-y-auto rounded-lg border p-3">
          {elementos.map((p) => {
            const marcado = elegidos.some((e) => e.id === p.id)
            const idCasilla = `${id}-${p.id}`
            return (
              <li key={p.id} className="flex items-center gap-2">
                <Checkbox
                  id={idCasilla}
                  checked={marcado}
                  disabled={!marcado && lleno}
                  onCheckedChange={(valor) => alternar(p, valor === true)}
                />
                <Label htmlFor={idCasilla} className="font-normal">
                  {p.nombre}
                  <span className="text-muted-foreground">
                    {" · "}
                    {p.categorias.map((c) => NOMBRES_CATEGORIA[c]).join(", ")}
                  </span>
                </Label>
              </li>
            )
          })}
        </ul>
        {total > elementos.length && (
          <p className="text-sm text-muted-foreground">
            Hay más proveedores: escriba parte del nombre para encontrarlos.
          </p>
        )}
      </fieldset>
    )
  }

  return (
    <div className="space-y-3">
      <Campo
        id={`${id}-buscar`}
        etiqueta="Buscar proveedor"
        ayuda="Por nombre o RFC; solo aparecen los proveedores activos."
      >
        {(control) => (
          <Input
            {...control}
            ref={buscador}
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            // Enter en el buscador no envía el formulario de la negociación que lo contiene.
            onKeyDown={(e) => {
              if (e.key === "Enter") e.preventDefault()
            }}
          />
        )}
      </Campo>
      <p aria-live="polite" className="text-sm text-muted-foreground">
        {`${elegidos.length} de ${MAXIMO} proveedores elegidos`}
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {elegidos.length > 0 && (
        <ul aria-label="Proveedores elegidos" className="flex flex-wrap gap-2">
          {elegidos.map((e) => (
            <li key={e.id}>
              <Badge variant="secondary" className="gap-1">
                {e.nombre}
                <button
                  type="button"
                  aria-label={`Quitar a ${e.nombre}`}
                  className="rounded-sm outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => quitar(e)}
                >
                  <X aria-hidden className="size-3" />
                </button>
              </Badge>
            </li>
          ))}
        </ul>
      )}
      {lista()}
    </div>
  )
}
