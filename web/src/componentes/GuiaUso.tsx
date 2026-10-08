import { useQuery } from "@tanstack/react-query"
import { Check } from "lucide-react"
import { useId, type ReactNode } from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ocultarGuia, useGuia } from "@/guia"
import { cn } from "@/lib/utils"
import type { PaginaProveedores } from "@/tipos"

type Paso = {
  titulo: string
  descripcion: string
  estado: "hecho" | "pendiente" | "proximamente"
  accion?: ReactNode
}

const NOMBRE_ESTADO = {
  hecho: "Hecho",
  pendiente: "Pendiente",
  proximamente: "Próximamente",
} as const

function enlace(texto: string, ruta: string) {
  return (
    <Link to={ruta} className="text-sm font-medium text-accent hover:underline">
      {texto}
    </Link>
  )
}

/** Los 4 pasos del flujo de trabajo, con su avance; se puede ocultar. */
export function GuiaUso() {
  const token = useToken()
  const roles = useRoles()
  const guia = useGuia()
  const idTitulo = useId()
  const datos = useQuery({
    queryKey: ["proveedores", "existencia"],
    queryFn: () =>
      pedir<PaginaProveedores>(
        "/proveedores/proveedores?limite=1&desplazamiento=0",
        token
      ),
    enabled: Boolean(token) && !guia.oculta,
  })

  // Sin la respuesta, el paso 1 y el avance serían inventados (y luego cambiarían de golpe).
  if (guia.oculta || !datos.isSuccess) return null

  const hayDatos = (datos.data?.total ?? 0) > 0
  const pasos: Paso[] = [
    {
      titulo: "Importar contratos y proveedores",
      descripcion:
        "Cargue los datos del ERP: catálogo, proveedores, contratos y desempeño.",
      estado: hayDatos ? "hecho" : "pendiente",
      accion: hayDatos ? undefined : roles.includes("admin") ? (
        enlace("Ir a Importación", "/importacion")
      ) : (
        <span className="text-sm text-muted-foreground">
          Administración importa los datos del ERP.
        </span>
      ),
    },
    {
      titulo: "Conocer a sus proveedores",
      descripcion: "Revise quién le vende, sus contratos y cómo rinde.",
      estado: guia.visitas.proveedores ? "hecho" : "pendiente",
      accion: guia.visitas.proveedores
        ? undefined
        : enlace("Ver proveedores", "/proveedores"),
    },
    {
      titulo: "Ver el precio justo",
      descripcion:
        "Compare lo que paga con el precio de referencia del mercado.",
      estado: guia.visitas.precios ? "hecho" : "pendiente",
      accion: guia.visitas.precios
        ? undefined
        : enlace("Ver precios", "/precios"),
    },
    {
      titulo: "Negociar y aprobar",
      descripcion:
        "La IA negocia dentro de sus límites y usted aprueba el cierre.",
      estado: "proximamente",
    },
  ]
  const listos = pasos.filter((p) => p.estado === "hecho").length

  return (
    <section
      aria-labelledby={idTitulo}
      className="space-y-4 rounded-xl border bg-card p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <h2 id={idTitulo} className="text-base font-semibold">
            Cómo usar PluriOne
          </h2>
          <p className="text-sm text-muted-foreground">{listos} de 3 listos</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            ocultarGuia()
            // El botón desaparece con la guía: el foco pasa al contenido en vez de perderse.
            document.getElementById("contenido")?.focus()
          }}
        >
          Ocultar guía
        </Button>
      </div>
      <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {pasos.map((paso, i) => (
          <li key={paso.titulo} className="space-y-2 rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <span
                aria-hidden
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  paso.estado === "hecho"
                    ? "bg-exito-suave text-success"
                    : "bg-info-suave text-accent"
                )}
              >
                {paso.estado === "hecho" ? (
                  <Check className="size-3.5" />
                ) : (
                  i + 1
                )}
              </span>
              <span className="font-medium">{paso.titulo}</span>
            </div>
            <p className="text-sm text-muted-foreground">{paso.descripcion}</p>
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant={
                  paso.estado === "hecho"
                    ? "success"
                    : paso.estado === "proximamente"
                      ? "outline"
                      : "secondary"
                }
              >
                {NOMBRE_ESTADO[paso.estado]}
              </Badge>
              {paso.accion}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
