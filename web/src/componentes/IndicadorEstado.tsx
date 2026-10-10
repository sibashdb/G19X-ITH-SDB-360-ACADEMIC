import {
  CircleCheck,
  CircleX,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import type { EstadoServicio } from "@/tipos"

const ESTILOS: Record<
  EstadoServicio,
  {
    texto: string
    icono: LucideIcon
    variante: "success" | "warning" | "destructive"
  }
> = {
  sano: { texto: "Sano", icono: CircleCheck, variante: "success" },
  con_problemas: {
    texto: "Con problemas",
    icono: TriangleAlert,
    variante: "warning",
  },
  caido: { texto: "Caído", icono: CircleX, variante: "destructive" },
}

/** Estado de un servicio con icono y texto: el color nunca va solo. */
export function IndicadorEstado({ estado }: { estado: EstadoServicio }) {
  const { texto, icono: Icono, variante } = ESTILOS[estado]
  return (
    <Badge variant={variante}>
      <Icono aria-hidden />
      {texto}
    </Badge>
  )
}
