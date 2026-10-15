import {
  Ban,
  CircleCheck,
  CircleOff,
  Clock,
  Hand,
  Handshake,
  Hourglass,
  Mail,
  MessagesSquare,
  PencilLine,
  type LucideIcon,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
  NOMBRES_ESTADO_EVENTO,
  NOMBRES_ESTADO_SESION,
  type EstadoEvento,
  type EstadoSesion,
} from "@/negociacion"

type Variante = "secondary" | "success" | "warning" | "outline"

const DE_EVENTO: Record<EstadoEvento, [LucideIcon, Variante]> = {
  borrador: [PencilLine, "outline"],
  abierto: [CircleCheck, "success"],
  en_evaluacion: [Hourglass, "secondary"],
  cancelado: [Ban, "outline"],
}

const DE_SESION: Record<EstadoSesion, [LucideIcon, Variante]> = {
  invitada: [Mail, "outline"],
  activa: [MessagesSquare, "secondary"],
  escalada: [Hand, "warning"],
  acuerdo_tentativo: [Handshake, "success"],
  sin_acuerdo: [CircleOff, "outline"],
  expirada: [Clock, "outline"],
}

/** Estado de una negociación con icono y texto: el color no es la única señal. */
export function EtiquetaEstadoEvento({ estado }: { estado: EstadoEvento }) {
  const [Icono, variante] = DE_EVENTO[estado]
  return (
    <Badge variant={variante}>
      <Icono aria-hidden />
      {NOMBRES_ESTADO_EVENTO[estado]}
    </Badge>
  )
}

/** Estado de la sesión con un proveedor, con icono y texto. */
export function EtiquetaEstadoSesion({ estado }: { estado: EstadoSesion }) {
  const [Icono, variante] = DE_SESION[estado]
  return (
    <Badge variant={variante}>
      <Icono aria-hidden />
      {NOMBRES_ESTADO_SESION[estado]}
    </Badge>
  )
}
