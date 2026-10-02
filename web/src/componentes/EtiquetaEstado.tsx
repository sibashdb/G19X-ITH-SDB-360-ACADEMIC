import { CircleCheck, CircleOff } from "lucide-react"
import { Badge } from "@/components/ui/badge"

export function EtiquetaEstado({ activo }: { activo: boolean }) {
  return activo ? (
    <Badge variant="success">
      <CircleCheck aria-hidden />
      Activo
    </Badge>
  ) : (
    <Badge variant="outline">
      <CircleOff aria-hidden />
      Inactivo
    </Badge>
  )
}
