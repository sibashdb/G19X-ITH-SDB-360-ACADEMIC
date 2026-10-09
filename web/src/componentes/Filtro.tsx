import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"

export function Filtro({
  activo,
  onClick,
  children,
}: {
  activo: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant={activo ? "default" : "outline"}
      aria-pressed={activo}
      className="rounded-full"
      onClick={onClick}
    >
      {children}
    </Button>
  )
}
