import { Lock } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"
import { NOMBRES_ROL, useRoles, type Rol } from "@/auth"
import { EstadoVacio } from "@/componentes/Estados"
import { Button } from "@/components/ui/button"

/** Oculta una sección a quien no tiene el rol. Solo es interfaz: la API vuelve a validar. */
export function RequiereRol({
  rol,
  children,
}: {
  rol: Rol
  children: ReactNode
}) {
  const roles = useRoles()
  if (roles.includes(rol)) return children
  return (
    <EstadoVacio
      icono={Lock}
      titulo="Acceso restringido"
      descripcion={`Esta sección es solo para el rol de ${NOMBRES_ROL[rol]}.`}
      accion={
        <Button asChild variant="outline">
          <Link to="/">Ir al tablero</Link>
        </Button>
      }
    />
  )
}
